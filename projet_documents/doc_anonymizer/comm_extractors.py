# Commandes pip à exécuter : pip install faster-whisper numpy scipy

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
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple
import xml.etree.ElementTree as ET
from faster_whisper import WhisperModel
import numpy as np
from scipy.io import wavfile
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.text_utils import DocumentTextUtils


class CommunicationExtractor:
    """
    Gère l'extraction des messages SMS/MMS (XML), des e-mails (.mbox/.eml),
    la transcription vocale (Whisper avec chargement paresseux et cache)
    et l'extraction Audacity (.aup3).
    """

    MAIN_CHARACTER_TOKEN: str = "{MAIN_CHARACTER}"

    def __init__(
        self,
        config: PipelineConfig,
        doc_extractor: OfficeAndDocumentExtractor,
    ) -> None:
        """
        Initialise l'extracteur sans charger immédiatement Whisper en RAM.

        :param config: Instance de PipelineConfig.
        :param doc_extractor: Extracteur PDF pour les pièces jointes.
        """
        self.config: PipelineConfig = config
        self.doc_extractor: OfficeAndDocumentExtractor = doc_extractor
        self._whisper_model: Optional[WhisperModel] = None
        self._whisper_cache_dir: str = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            ".whisper_cache",
        )

    @property
    def whisper_model(self) -> Optional[WhisperModel]:
        """
        Charge le modèle Whisper uniquement au premier fichier audio rencontré
        et réutilise le cache local sans requête réseau superflue.

        :return: Instance de WhisperModel ou None si l'audio est désactivé.
        """
        if not self.config.enable_audio:
            return None
        if self._whisper_model is None:
            cache_dir: str = os.path.normpath(self._whisper_cache_dir)
            os.makedirs(cache_dir, exist_ok=True)
            print(
                f"Chargement du modèle audio Whisper "
                f"'{self.config.whisper_model}'...",
                flush=True,
            )
            try:
                self._whisper_model = WhisperModel(
                    self.config.whisper_model,
                    device="cpu",
                    compute_type="int8",
                    download_root=cache_dir,
                    local_files_only=True,
                )
            except Exception:
                self._whisper_model = WhisperModel(
                    self.config.whisper_model,
                    device="cpu",
                    compute_type="int8",
                    download_root=cache_dir,
                    local_files_only=False,
                )
        return self._whisper_model

    @staticmethod
    def decode_mime_header(raw_val: Optional[str]) -> str:
        """
        Décode un en-tête MIME (ex. =?UTF-8?Q?...?=) en chaîne Unicode.

        :param raw_val: Valeur brute de l'en-tête.
        :return: Texte décodé.
        """
        if not raw_val:
            return ""
        parts: List[str] = []
        for chunk, enc in decode_header(raw_val):
            if isinstance(chunk, bytes):
                parts.append(
                    chunk.decode(enc or "utf-8", errors="ignore")
                )
            else:
                parts.append(str(chunk))
        return "".join(parts).strip()

    @staticmethod
    def _extract_email_body(msg: Message) -> str:
        """
        Extrait le corps texte principal (text/plain ou repli text/html)
        d'un message MIME.

        :param msg: Objet email.message.Message.
        :return: Texte nettoyé du corps du message.
        """
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
                    if ctype == "text/plain":
                        plain_parts.append(decoded)
                    else:
                        html_parts.append(decoded)
        else:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                charset = msg.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="ignore")
                if msg.get_content_type() == "text/html":
                    html_parts.append(decoded)
                else:
                    plain_parts.append(decoded)

        if plain_parts:
            return "\n".join(plain_parts).strip()
        if html_parts:
            return DocumentTextUtils.html_to_plain_text(
                "\n".join(html_parts)
            ).strip()
        return ""
    def _extract_email_pdf_attachments(
        self, msg: Message, source_label: str
    ) -> List[str]:
        """
        Extrait le texte des pièces jointes PDF d'un message MIME.

        :param msg: Objet email.message.Message.
        :param source_label: Nom du fichier source pour l'affichage.
        :return: Liste des textes extraits des pièces jointes PDF.
        """
        attachments_txt: List[str] = []
        if not msg.is_multipart():
            return attachments_txt

        for part in msg.walk():
            raw_fname: Optional[str] = part.get_filename()
            fname: str = self.decode_mime_header(raw_fname)
            ctype: str = part.get_content_type()
            if ctype == "application/pdf" or fname.lower().endswith(".pdf"):
                pdf_bytes = part.get_payload(decode=True)
                if isinstance(pdf_bytes, bytes) and pdf_bytes:
                    disp_name: str = fname or f"piece_jointe_{source_label}.pdf"
                    pdf_txt, err = self.doc_extractor.extract_pdf(
                        pdf_source=pdf_bytes,
                        display_name=disp_name,
                        is_stream=True,
                    )
                    if pdf_txt and not err:
                        attachments_txt.append(pdf_txt)
        return attachments_txt

    def extract_emails(
        self,
        file_path: str,
        allowed_emails: Set[str],
        discovered_emails: Set[str],
    ) -> Tuple[Dict[str, List[str]], Optional[str]]:
        """
        Extrait les e-mails d'un fichier .mbox ou .eml correspondant aux
        adresses de contacts.txt. Utilise en priorité la date du nom
        de fichier pour les .eml individuels.

        :param file_path: Chemin vers le fichier .mbox ou .eml.
        :param allowed_emails: Ensemble des e-mails filtrés depuis contacts.txt.
        :param discovered_emails: Collecteur global des e-mails rencontrés.
        :return: Tuple (dictionnaire_par_mois, message_erreur).
        """
        fname: str = os.path.basename(file_path)
        is_eml: bool = fname.lower().endswith(".eml")
        eml_filename_period: Optional[str] = (
            DocumentTextUtils.detect_period_in_text(fname)
            if is_eml
            else None
        )
        by_month: DefaultDict[str, List[str]] = defaultdict(list)

        try:
            messages: List[Message] = []
            if is_eml:
                with open(file_path, "rb") as f_eml:
                    messages.append(email.message_from_binary_file(f_eml))
            else:
                mbox = mailbox.mbox(file_path)
                messages.extend(mbox)
                mbox.close()

            for msg in messages:
                raw_headers: List[str] = [
                    str(msg.get(h) or "")
                    for h in ("From", "To", "Cc", "Bcc", "Reply-To")
                ]
                parsed_addrs = getaddresses(raw_headers)
                msg_emails: Set[str] = {
                    DocumentTextUtils.normalize_identifier(addr)
                    for _, addr in parsed_addrs
                    if addr and "@" in addr
                }
                discovered_emails.update(msg_emails)

                if allowed_emails and not (msg_emails & allowed_emails):
                    continue

                raw_date: str = str(msg.get("Date") or "").strip()
                period: str = eml_filename_period or "0000-00"
                date_str: str = raw_date or "Date inconnue"
                if raw_date:
                    try:
                        dt = parsedate_to_datetime(raw_date)
                        date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        if not eml_filename_period:
                            period = dt.strftime("%Y-%m")
                    except Exception:
                        if not eml_filename_period:
                            detected = DocumentTextUtils.detect_period_in_text(
                                raw_date
                            )
                            if detected:
                                period = detected

                sender: str = self.decode_mime_header(msg.get("From"))
                recipients: str = self.decode_mime_header(msg.get("To"))
                subject: str = self.decode_mime_header(msg.get("Subject"))
                body: str = self._extract_email_body(msg)
                pdf_att: List[str] = self._extract_email_pdf_attachments(
                    msg, fname
                )

                block_lines: List[str] = [
                    "========================================\n",
                    f"EMAIL ({fname}) | DATE : {date_str}\n",
                    f"DE : {sender}\n",
                    f"À : {recipients}\n",
                    f"OBJET : {subject}\n",
                    "----------------------------------------\n",
                    f"{body}\n\n",
                ]
                if pdf_att:
                    block_lines.extend(pdf_att)
                by_month[period].append("".join(block_lines))

            return dict(by_month), None
        except Exception as exc:
            return {}, f"Erreur lecture e-mail ({exc})"
    def parse_sms_xml(
        self,
        xml_path: str,
        target_phones: Dict[str, str],
        already_processed: Set[str],
        discovered_phones: Set[str],
    ) -> Tuple[Dict[str, List[Tuple[int, str]]], List[str]]:
        """
        Parcourt en streaming un export XML SMS/MMS (SMS Backup & Restore).

        :param xml_path: Chemin vers le fichier XML.
        :param target_phones: Dictionnaire numéro normalisé -> alias.
        :param already_processed: Clés 'fichier|numero' déjà extraites.
        :param discovered_phones: Collecteur global des numéros rencontrés.
        :return: Tuple (messages_par_mois, liste_erreurs).
        """
        fname: str = os.path.basename(xml_path)
        by_month: DefaultDict[str, List[Tuple[int, str]]] = defaultdict(list)
        errors: List[str] = []

        try:
            context = ET.iterparse(xml_path, events=("end",))
            for _, elem in context:
                if elem.tag not in ("sms", "mms"):
                    continue

                raw_addr: str = elem.attrib.get("address", "")
                norm_num: str = DocumentTextUtils.normalize_identifier(
                    raw_addr
                )
                if norm_num:
                    discovered_phones.add(norm_num)

                track_key: str = f"{fname}|{norm_num}"
                if (
                    norm_num not in target_phones
                    or track_key in already_processed
                ):
                    elem.clear()
                    continue

                alias: str = target_phones[norm_num]
                raw_ts: str = elem.attrib.get("date", "0")
                ts_ms: int = int(raw_ts) if raw_ts.isdigit() else 0
                dt = datetime.datetime.fromtimestamp(ts_ms / 1000.0)
                period: str = dt.strftime("%Y-%m")
                date_fmt: str = dt.strftime("%Y-%m-%d %H:%M:%S")

                msg_type: str = elem.attrib.get(
                    "type", elem.attrib.get("msg_box", "1")
                )
                direction: str = (
                    f"[ENVOYÉ par {self.MAIN_CHARACTER_TOKEN} à {alias}]"
                    if msg_type == "2"
                    else f"[REÇU par {self.MAIN_CHARACTER_TOKEN} de {alias}]"
                )

                body: str = ""
                if elem.tag == "sms":
                    body = elem.attrib.get("body", "").strip()
                else:
                    parts_txt: List[str] = []
                    for part in elem.iter("part"):
                        if part.attrib.get("ct") == "text/plain":
                            txt_p: str = part.attrib.get("text", "").strip()
                            if txt_p:
                                parts_txt.append(txt_p)
                    body = "\n".join(parts_txt).strip()

                if body:
                    block: str = (
                        f"[{date_fmt}] {direction}\n{body}\n"
                        "----------------------------------------\n"
                    )
                    by_month[period].append((ts_ms, block))
                elem.clear()

            return dict(by_month), errors
        except Exception as exc:
            errors.append(f"{fname} -> Erreur parsing XML ({exc})")
            return {}, errors

    def extract_audio(
        self, file_path: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Transcrit un fichier audio via faster-whisper et identifie les
        participants si un numéro est présent dans le nom du fichier.

        :param file_path: Chemin vers le fichier audio.
        :return: Tuple (transcription_formatee, message_erreur).
        """
        model: Optional[WhisperModel] = self.whisper_model
        if not self.config.enable_audio or not model:
            return None, "Transcription audio désactivée"

        fname: str = os.path.basename(file_path)
        phone_match = DocumentTextUtils.REGEX_PHONE.search(fname)
        participants_line: str = ""
        if phone_match:
            raw_num: str = phone_match.group(0)
            participants_line = (
                f"PARTICIPANTS : {self.MAIN_CHARACTER_TOKEN} et {raw_num}\n"
            )

        try:
            segments, _ = model.transcribe(
                file_path, beam_size=5, vad_filter=True
            )
            lines: List[str] = []
            for seg in segments:
                txt: str = seg.text.strip()
                if txt:
                    start_m, start_s = divmod(int(seg.start), 60)
                    lines.append(f"[{start_m:02d}:{start_s:02d}] {txt}")

            if not lines:
                return None, "Aucune parole détectée dans l'audio"

            header: str = (
                "========================================\n"
                f"AUDIO : {fname}\n"
                f"{participants_line}"
                "----------------------------------------\n"
            )
            return header + "\n".join(lines) + "\n\n", None
        except Exception as exc:
            return None, f"Erreur transcription audio ({exc})"

    def extract_audacity_aup3(
        self, file_path: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrait et transcrit la piste audio principale d'un projet Audacity
        (.aup3, base SQLite3) via un fichier WAV temporaire.

        :param file_path: Chemin vers le fichier .aup3.
        :return: Tuple (transcription_formatee, message_erreur).
        """
        if not self.config.enable_audio or not self.whisper_model:
            return None, "Transcription audio désactivée"

        fname: str = os.path.basename(file_path)
        temp_wav: str = f"{file_path}.tmp_extract.wav"
        try:
            conn = sqlite3.connect(file_path)
            cur = conn.cursor()
            cur.execute("SELECT samples FROM sampleblocks ORDER BY blockid")
            rows: List[Any] = cur.fetchall()
            conn.close()

            if not rows:
                return None, "Projet Audacity sans bloc audio"

            raw_bytes: bytes = b"".join(r[0] for r in rows if r and r[0])
            audio_arr = np.frombuffer(raw_bytes, dtype=np.float32)
            if audio_arr.size == 0:
                return None, "Piste audio Audacity vide"

            wavfile.write(temp_wav, 44100, audio_arr)
            res_txt, err = self.extract_audio(temp_wav)
            if res_txt:
                res_txt = res_txt.replace(
                    os.path.basename(temp_wav), fname
                )
            return res_txt, err
        except Exception as exc:
            return None, f"Erreur lecture projet Audacity ({exc})"
        finally:
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except OSError:
                    pass
