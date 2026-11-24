# Commandes pip à exécuter : pip install faster-whisper numpy scipy

from __future__ import annotations
from collections import defaultdict
import datetime
import email
from email.header import decode_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
import mailbox
import os
import re
import sqlite3
import threading
from typing import TYPE_CHECKING, Any, DefaultDict, Dict, List, Optional, Set, Tuple
import xml.etree.ElementTree as ET
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.text_utils import DocumentTextUtils

if TYPE_CHECKING:
    from faster_whisper import WhisperModel


class CommunicationExtractor:
    """
    Gère l'extraction des messages SMS/MMS (XML), des e-mails (.mbox/.eml),
    la transcription vocale (Whisper) et l'extraction Audacity (.aup3).
    """

    MAIN_CHARACTER_TOKEN: str = "{MAIN_CHARACTER}"

    def __init__(
        self,
        config: PipelineConfig,
        doc_extractor: OfficeAndDocumentExtractor,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        self.config: PipelineConfig = config
        self.doc_extractor: OfficeAndDocumentExtractor = doc_extractor
        self.stop_event: threading.Event = stop_event or threading.Event()
        self._whisper_model: Optional[WhisperModel] = None
        self._whisper_cache_dir: str = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            ".whisper_cache",
        )

    @property
    def whisper_model(self) -> Optional[WhisperModel]:
        if not self.config.enable_audio:
            return None
        if self._whisper_model is None:
            from faster_whisper import WhisperModel

            cache_dir: str = os.path.normpath(self._whisper_cache_dir)
            os.makedirs(cache_dir, exist_ok=True)
            print(f"Chargement du modèle audio Whisper '{self.config.whisper_model}'...", flush=True)
            try:
                self._whisper_model = WhisperModel(
                    self.config.whisper_model, device="cpu", compute_type="int8",
                    download_root=cache_dir, local_files_only=True,
                )
            except Exception:
                self._whisper_model = WhisperModel(
                    self.config.whisper_model, device="cpu", compute_type="int8",
                    download_root=cache_dir, local_files_only=False,
                )
        return self._whisper_model
    @staticmethod
    def decode_mime_header(raw_val: Optional[str]) -> str:
        if not raw_val:
            return ""
        parts: List[str] = []
        for chunk, enc in decode_header(raw_val):
            if isinstance(chunk, bytes):
                parts.append(chunk.decode(enc or "utf-8", errors="ignore"))
            else:
                parts.append(str(chunk))
        return "".join(parts).strip()

    @staticmethod
    def _extract_email_body(msg: Message) -> str:
        plain_parts: List[str] = []
        html_parts: List[str] = []
        if msg.is_multipart():
            for part in msg.walk():
                ctype: str = part.get_content_type()
                disp: str = str(part.get("Content-Disposition") or "")
                if "attachment" in disp.lower():
                    continue
                if ctype in ("text/plain", "text/html"):
                    payload = part.get_payload(decode=True)
                    if not isinstance(payload, bytes):
                        continue
                    charset: str = part.get_content_charset() or "utf-8"
                    decoded: str = payload.decode(charset, errors="ignore")
                    (plain_parts if ctype == "text/plain" else html_parts).append(decoded)
        else:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                charset = msg.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="ignore")
                (html_parts if msg.get_content_type() == "text/html" else plain_parts).append(decoded)

        if plain_parts:
            return "\n".join(plain_parts).strip()
        if html_parts:
            return DocumentTextUtils.html_to_plain_text("\n".join(html_parts)).strip()
        return ""

    def _extract_email_pdf_attachments(
        self, msg: Message, source_label: str
    ) -> List[str]:
        attachments_txt: List[str] = []
        if not msg.is_multipart():
            return attachments_txt

        for part in msg.walk():
            raw_file_name: Optional[str] = part.get_filename()
            file_name: str = self.decode_mime_header(raw_file_name)
            ctype: str = part.get_content_type()
            if ctype == "application/pdf" or file_name.lower().endswith(".pdf"):
                pdf_bytes = part.get_payload(decode=True)
                if isinstance(pdf_bytes, bytes) and pdf_bytes:
                    safe_name: str = re.sub(r"[\r\n<>:\"/\\|?*]", "_", file_name).strip()
                    disp_name: str = safe_name or f"piece_jointe_{source_label}.pdf"
                    pdf_txt, err = self.doc_extractor.extract_pdf(
                        pdf_source=pdf_bytes, display_name=disp_name, is_stream=True
                    )
                    if pdf_txt and not err:
                        attachments_txt.append(pdf_txt)
        return attachments_txt
    def extract_emails(
        self, file_path: str, allowed_emails: Set[str], discovered_emails: Set[str],
    ) -> Tuple[Dict[str, List[str]], Optional[str]]:
        file_name: str = os.path.basename(file_path)
        ext: str = os.path.splitext(file_name)[-1].lower()
        by_month: DefaultDict[str, List[str]] = defaultdict(list)
        msg_iterable: Any = ()
        mbox_handle: Optional[mailbox.mbox] = None
        try:
            if ext == ".eml":
                with open(file_path, "rb") as f_eml:
                    msg_iterable = (email.message_from_binary_file(f_eml),)
            elif ext == ".mbox":
                mbox_handle = mailbox.mbox(file_path)
                msg_iterable = mbox_handle
            else:
                return {}, f"Format courriel non pris en charge : {ext}"

            for msg in msg_iterable:
                if self.stop_event.is_set():
                    break
                msg_emails: Set[str] = set()
                hdr_lines: List[str] = []
                for hdr in ("From", "To", "Cc"):
                    raw_h: str = self.decode_mime_header(msg.get(hdr))
                    if not raw_h:
                        continue
                    hdr_lines.append(f"{hdr.upper()} : {raw_h}")
                    for disp_name, addr in getaddresses([raw_h]):
                        norm_m: str = DocumentTextUtils.normalize_identifier(addr)
                        if "@" in norm_m:
                            msg_emails.add(norm_m)
                            clean_d: str = self.decode_mime_header(disp_name).strip()
                            discovered_emails.add(
                                f"{norm_m}|{clean_d}" if len(clean_d.split()) >= 2 else norm_m
                            )
                if allowed_emails and msg_emails and not (msg_emails & allowed_emails):
                    continue
                subject: str = self.decode_mime_header(msg.get("Subject")) or "(Sans objet)"
                raw_date: str = self.decode_mime_header(msg.get("Date"))
                period, date_disp = "0000-00", (raw_date or "Date inconnue")
                if raw_date:
                    try:
                        dt = parsedate_to_datetime(raw_date)
                        period, date_disp = dt.strftime("%Y-%m"), dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        period = DocumentTextUtils.detect_period_in_text(raw_date) or "0000-00"
                body: str = self._extract_email_body(msg)
                pdf_txts: List[str] = self._extract_email_pdf_attachments(msg, file_name)
                if not body and not pdf_txts:
                    continue
                att_sec: str = ("\n" + "\n".join(pdf_txts)) if pdf_txts else ""
                hdr_txt: str = "\n".join(hdr_lines) + "\n" if hdr_lines else ""
                block: str = (
                    f"{'=' * 40}\nEMAIL : {file_name}\nDATE : {date_disp}\n"
                    f"OBJET : {subject}\n{hdr_txt}{'-' * 40}\n{body}{att_sec}\n\n"
                )
                by_month[period].append(block)
            return dict(by_month), None
        except Exception as exc:
            return {}, f"Erreur extraction courriel ({exc})"
        finally:
            if mbox_handle is not None:
                try:
                    mbox_handle.close()
                except Exception:
                    pass
    @staticmethod
    def _validate_safe_xml_header(xml_path: str) -> None:
        with open(xml_path, "rb") as f_head:
            head_upper: bytes = f_head.read(4096).upper()
        if b"<!DOCTYPE" in head_upper or b"<!ENTITY" in head_upper:
            raise ValueError("Déclaration DOCTYPE/ENTITY interdite par sécurité dans le XML.")

    @staticmethod
    def _sms_epoch_to_period_and_label(raw_ts: str) -> Tuple[int, str, str]:
        cleaned: str = raw_ts.strip()
        if not cleaned or not cleaned.isdigit():
            return 0, "0000-00", "Date inconnue"
        ts_ms: int = int(cleaned)
        if ts_ms <= 0:
            return 0, "0000-00", "Date inconnue"
        try:
            dt = datetime.datetime.fromtimestamp(ts_ms / 1000.0, tz=datetime.timezone.utc)
            return ts_ms, dt.strftime("%Y-%m"), dt.strftime("%Y-%m-%d %H:%M:%S")
        except (OSError, OverflowError, ValueError):
            return 0, "0000-00", "Date inconnue"

    def parse_sms_xml(
        self, xml_path: str, target_phones: Dict[str, str], already_processed: Set[str],
        discovered_phones: Set[str], discovered_emails: Optional[Set[str]] = None,
    ) -> Tuple[Dict[str, List[Tuple[int, str]]], List[str]]:
        file_name: str = os.path.basename(xml_path)
        by_month: DefaultDict[str, List[Tuple[int, str]]] = defaultdict(list)
        errors: List[str] = []
        matched_keys: Set[str] = set()
        try:
            self._validate_safe_xml_header(xml_path)
            for _, elem in ET.iterparse(xml_path, events=("end",)):
                if elem.tag not in ("sms", "mms"):
                    continue
                matched_aliases: List[str] = []
                for norm_addr in DocumentTextUtils.split_sms_addresses(elem.attrib.get("address", "")):
                    if "@" in norm_addr:
                        if discovered_emails is not None and not norm_addr.lower().endswith("chat.google.com"):
                            discovered_emails.add(norm_addr)
                    else:
                        discovered_phones.add(norm_addr)
                    pair_key: str = f"{file_name}|{norm_addr}"
                    if norm_addr in target_phones and pair_key not in already_processed:
                        matched_keys.add(pair_key)
                        if target_phones[norm_addr] not in matched_aliases:
                            matched_aliases.append(target_phones[norm_addr])

                if not matched_aliases:
                    elem.clear()
                    continue

                alias: str = ", ".join(matched_aliases)
                ts_ms, period_str, dt_label = self._sms_epoch_to_period_and_label(elem.attrib.get("date", "0"))
                direction: str = (
                    f"[ENVOYÉ par {self.MAIN_CHARACTER_TOKEN} à {alias}]"
                    if elem.attrib.get("type", elem.attrib.get("msg_box", "1")) == "2"
                    else f"[REÇU par {self.MAIN_CHARACTER_TOKEN} de {alias}]"
                )
                body: str = elem.attrib.get("body", "").strip() if elem.tag == "sms" else "\n".join(
                    p.attrib.get("text", "").strip() for p in elem.iter("part")
                    if p.attrib.get("ct") == "text/plain" and p.attrib.get("text", "").strip()
                ).strip()
                if body:
                    by_month[period_str].append(
                        (ts_ms, f"[{dt_label}] {direction}\n{body}\n----------------------------------------\n")
                    )
                elem.clear()
            already_processed.update(matched_keys)
            return dict(by_month), errors
        except Exception as exc:
            errors.append(f"{file_name} -> Erreur parsing XML ({exc})")
            return {}, errors

    def extract_audio(self, file_path: str, media_label: str = "AUDIO") -> Tuple[Optional[str], Optional[str]]:
        if self.stop_event.is_set():
            return None, "Interrompu par l'utilisateur"
        model: Optional[WhisperModel] = self.whisper_model
        if not self.config.enable_audio or not model:
            return None, "Transcription audio/vidéo désactivée"
        file_name: str = os.path.basename(file_path)
        phone_match = DocumentTextUtils.REGEX_PHONE.search(file_name)
        part_line: str = f"PARTICIPANTS : {self.MAIN_CHARACTER_TOKEN} et {phone_match.group(0)}\n" if phone_match else ""
        try:
            segments, _ = model.transcribe(file_path, beam_size=5, vad_filter=True)
            lines: List[str] = []
            for seg in segments:
                if self.stop_event.is_set():
                    return None, "Interrompu par l'utilisateur"
                txt: str = seg.text.strip()
                if txt:
                    mins, secs = divmod(int(seg.start), 60)
                    lines.append(f"[{mins:02d}:{secs:02d}] {txt}")
            if not lines:
                return None, "Aucune parole détectée dans le média"
            return f"========================================\n{media_label} : {file_name}\n{part_line}----------------------------------------\n" + "\n".join(lines) + "\n\n", None
        except Exception as exc:
            err_low: str = str(exc).lower()
            if "no audio" in err_low or "audio stream" in err_low or "invalid data" in err_low:
                return None, "Vidéo sans piste audio exploitable"
            return None, f"Erreur transcription média ({exc})"

    def extract_video(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        return self.extract_audio(file_path, media_label="VIDÉO")

    def extract_audacity_aup3(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        if self.stop_event.is_set():
            return None, "Interrompu par l'utilisateur"
        if not self.config.enable_audio or not self.whisper_model:
            return None, "Transcription audio désactivée"
        import numpy as np
        from scipy.io import wavfile

        file_name: str = os.path.basename(file_path)
        temp_wav: str = f"{file_path}.tmp_extract.wav"
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(file_path)
            cur = conn.cursor()
            cur.execute("SELECT samples FROM sampleblocks ORDER BY blockid")
            rows: List[Any] = cur.fetchall()
            if not rows:
                return None, "Projet Audacity sans bloc audio"
            audio_arr = np.frombuffer(b"".join(next(iter(r)) for r in rows if r and next(iter(r))), dtype=np.float32)
            if audio_arr.size == 0:
                return None, "Piste audio Audacity vide"
            wavfile.write(temp_wav, 44100, audio_arr)
            res_txt, err = self.extract_audio(temp_wav)
            return (res_txt.replace(os.path.basename(temp_wav), file_name) if res_txt else None), err
        except Exception as exc:
            return None, f"Erreur lecture projet Audacity ({exc})"
        finally:
            if conn is not None:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except OSError:
                    pass
