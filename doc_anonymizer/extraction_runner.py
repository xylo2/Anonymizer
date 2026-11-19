# Commandes pip à exécuter : Aucune dépendance externe requise

import hashlib
import os
import threading
from typing import Dict, List, Optional, Set, Tuple
from doc_anonymizer.chat_extractors import MultiPlatformChatExtractor
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.teams_chat_extractor import TeamsChatExtractor
from doc_anonymizer.text_utils import DocumentTextUtils


class DocumentExtractionRunner:
    """
    Orchestre l'extraction des sources brutes vers transcriptions/
    tout en collectant les numéros de téléphone et adresses e-mail découverts.
    """

    def __init__(
        self,
        config: PipelineConfig,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Initialise l'extracteur documentaire et ses sous-extracteurs spécialisés.

        :param config: Instance de PipelineConfig.
        :param stop_event: Événement d'interruption Ctrl+C partagé.
        """
        self.config: PipelineConfig = config
        self.stop_event: threading.Event = stop_event or threading.Event()
        self.office_extractor: OfficeAndDocumentExtractor = OfficeAndDocumentExtractor(
            config=config, enable_ocr=config.enable_ocr
        )
        self.comm_extractor: CommunicationExtractor = CommunicationExtractor(
            config=config, doc_extractor=self.office_extractor, stop_event=self.stop_event
        )
        self.chat_extractor: MultiPlatformChatExtractor = MultiPlatformChatExtractor(
            config=config
        )
        self.teams_extractor: TeamsChatExtractor = TeamsChatExtractor(config=config)
        self._seen_content_hashes: Set[str] = set()

    def get_worker_count(self) -> int:
        """Retourne le nombre de threads parallèles d'extraction (1 à 4)."""
        if self.config.extraction_workers > 0:
            return min(8, self.config.extraction_workers)
        cpu_count: int = os.cpu_count() or 2
        return max(1, min(4, cpu_count))

    @staticmethod
    def load_tracking_set(tracking_file: str) -> Set[str]:
        """Charge un ensemble de chemins suivis depuis un fichier texte."""
        items: Set[str] = set()
        if not tracking_file or not os.path.exists(tracking_file):
            return items
        with open(tracking_file, "r", encoding="utf-8", errors="ignore") as f_in:
            for line in f_in:
                stripped: str = line.strip()
                if stripped and not stripped.startswith("#"):
                    items.add(os.path.normpath(stripped))
        return items

    @staticmethod
    def save_tracking_set(tracking_file: str, items: Set[str]) -> None:
        """Sauvegarde atomiquement un ensemble de chemins suivis."""
        if not tracking_file:
            return
        parent: str = os.path.dirname(os.path.abspath(tracking_file))
        if parent:
            os.makedirs(parent, exist_ok=True)
        content: str = "\n".join(sorted(items)) + ("\n" if items else "")
        DocumentTextUtils.atomic_write_text(tracking_file, content)

    def collect_source_files(
        self, already_extracted: Optional[Set[str]] = None
    ) -> List[str]:
        """Inventorie les fichiers sources éligibles non encore extraits."""
        if not os.path.isdir(self.config.sources_dir):
            return []
        excluded: Set[str] = already_extracted or set()
        candidates: List[str] = []
        for root_p, dirs, files in os.walk(self.config.sources_dir):
            dirs[:] = [
                d for d in sorted(dirs)
                if d not in self.config.ignored_dirs and not d.startswith(".")
            ]
            for fname in sorted(files):
                low_fn: str = fname.lower()
                if fname.startswith(".") or low_fn.startswith(("anonymise_", "anonymized_")):
                    continue
                full_p: str = os.path.normpath(os.path.join(root_p, fname))
                if full_p not in excluded:
                    candidates.append(full_p)
        return candidates
    def load_all_filter_contacts(self) -> Tuple[Dict[str, str], Set[str]]:
        """Charge les téléphones cibles et e-mails autorisés depuis les fichiers de contacts."""
        target_phones: Dict[str, str] = {}
        allowed_emails: Set[str] = set()
        for path in (
            self.config.contacts_file,
            self.config.discovered_contacts_file,
            self.config.discovered_chats_file,
            self.config.manual_contacts_file,
        ):
            if not path or not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as f_in:
                for raw_line in f_in:
                    line: str = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    left_p, right_p = line.split("=", 1)
                    left: str = left_p.strip()
                    right: str = right_p.strip()
                    if not left or not right:
                        continue
                    if "@" in right and "@" not in left:
                        left, right = right, left
                    elif DocumentTextUtils._normalize_fr_phone(right) and not DocumentTextUtils._normalize_fr_phone(left):
                        left, right = right, left

                    if "@" in left:
                        norm_m: str = DocumentTextUtils.normalize_identifier(left)
                        if norm_m:
                            allowed_emails.add(norm_m)
                    else:
                        norm_p: str = DocumentTextUtils._normalize_fr_phone(left)
                        if norm_p:
                            target_phones[norm_p] = right
        return target_phones, allowed_emails

    def _write_period_buckets(
        self,
        buckets: Dict[str, str],
        sub_category: str,
        stem_name: str,
        discovered_phones: Set[str],
        discovered_emails: Set[str],
    ) -> List[str]:
        """Écrit les transcriptions découpées par période AAAA-MM sans doublon de contenu."""
        written: List[str] = []
        safe_stem: str = DocumentTextUtils.sanitize_filename(stem_name)
        for period, content in sorted(buckets.items()):
            if not content or not content.strip():
                continue
            digest: str = hashlib.sha256(content.strip().encode("utf-8", errors="ignore")).hexdigest()
            if digest in self._seen_content_hashes:
                continue
            self._seen_content_hashes.add(digest)
            for m_mail in DocumentTextUtils.REGEX_EMAIL.finditer(content):
                discovered_emails.add(m_mail.group(0).lower())
            for m_tel in DocumentTextUtils.REGEX_PHONE.finditer(content):
                norm_tel: str = DocumentTextUtils._normalize_fr_phone(m_tel.group(0))
                if norm_tel:
                    discovered_phones.add(norm_tel)
            out_dir: str = os.path.join(self.config.transcriptions_dir, period, sub_category)
            os.makedirs(out_dir, exist_ok=True)
            out_p: str = os.path.join(out_dir, f"{safe_stem}.txt")
            DocumentTextUtils.atomic_write_text(out_p, content)
            written.append(out_p)
        return written

    def _log_extraction_warning(self, message: str) -> None:
        """Consigne un avertissement ou une erreur d'extraction dans le rapport dédié."""
        rep_dir: str = os.path.dirname(os.path.abspath(self.config.extraction_report_file))
        if rep_dir:
            os.makedirs(rep_dir, exist_ok=True)
        with open(self.config.extraction_report_file, "a", encoding="utf-8") as f_rep:
            f_rep.write(message + "\n")

    def process_single_file(
        self,
        file_path: str,
        target_phones: Dict[str, str],
        allowed_emails: Set[str],
        already_extracted: Set[str],
        sms_processed: Set[str],
        discovered_phones: Set[str],
        discovered_emails: Set[str],
    ) -> List[str]:
        """Extrait un fichier source unique et retourne la liste des transcriptions créées."""
        if self.stop_event.is_set():
            return []
        norm_src: str = os.path.normpath(file_path)
        if not os.path.isfile(norm_src):
            return []
        fname: str = os.path.basename(norm_src)
        low_name: str = fname.lower()
        if low_name.startswith(("anonymise_", "anonymized_")):
            return []
        stem_raw, ext = os.path.splitext(fname)
        ext = ext.lower()

        if low_name.endswith(".zip"):
            self._log_extraction_warning(
                f"[ARCHIVE ZIP IGNORÉE] '{norm_src}' -> veuillez dézipper manuellement."
            )
            return []

        if ext == ".json":
            if low_name in {"group_info.json", "user_info.json"}:
                return []
            buckets, err = self.chat_extractor.extract_json_chat(
                norm_src, target_phones, allowed_emails, discovered_phones, discovered_emails
            )
            if err:
                self._log_extraction_warning(f"{fname} -> {err}")
                return []
            parent_name: str = os.path.basename(os.path.dirname(norm_src))
            out_stem: str = (
                f"chat_{parent_name}_{stem_raw}"
                if low_name in {"messages.json", "message_1.json"} and parent_name
                else stem_raw
            )
            written = self._write_period_buckets(
                buckets, "Chats", out_stem, discovered_phones, discovered_emails
            )
            if written:
                already_extracted.add(norm_src)
            return written
        if ext in {".mbox", ".eml"}:
            mail_buckets, err = self.comm_extractor.extract_emails(
                norm_src, allowed_emails, discovered_emails
            )
            if err:
                self._log_extraction_warning(f"{fname} -> {err}")
                return []
            joined_mails: Dict[str, str] = {
                per: "".join(blocks) for per, blocks in mail_buckets.items()
            }
            written = self._write_period_buckets(
                joined_mails, "Emails", stem_raw, discovered_phones, discovered_emails
            )
            if written:
                already_extracted.add(norm_src)
            return written

        if ext == ".xml":
            sms_buckets, errs = self.comm_extractor.parse_sms_xml(
                norm_src, target_phones, sms_processed, discovered_phones, discovered_emails
            )
            for e in errs:
                self._log_extraction_warning(e)
            joined_sms: Dict[str, str] = {
                per: "".join(blk for _, blk in sorted(items, key=lambda x: x))
                for per, items in sms_buckets.items()
            }
            written = self._write_period_buckets(
                joined_sms, "SMS", stem_raw, discovered_phones, discovered_emails
            )
            if written:
                already_extracted.add(norm_src)
            return written

        extracted_text: Optional[str] = None
        sub_category: str = "Documents"

        if ext in {".txt", ".md", ".csv", ".log"}:
            with open(norm_src, "r", encoding="utf-8", errors="ignore") as f_txt:
                raw_txt: str = f_txt.read()
            if (
                low_name == "_chat.txt"
                or low_name.startswith("discussion whatsapp")
                or self.chat_extractor.is_whatsapp_text_file(raw_txt)
            ):
                wa_buckets = self.chat_extractor.extract_whatsapp_text(norm_src, raw_txt)
                written = self._write_period_buckets(
                    wa_buckets, "Chats", stem_raw, discovered_phones, discovered_emails
                )
                if written:
                    already_extracted.add(norm_src)
                return written
            extracted_text, _ = self.office_extractor.extract_text_or_markdown(norm_src)
        elif ext in {".html", ".htm"}:
            with open(norm_src, "r", encoding="utf-8", errors="ignore") as f_html:
                raw_html: str = f_html.read()
            if self.chat_extractor.is_messenger_html_file(norm_src, raw_html):
                fb_buckets = self.chat_extractor.extract_messenger_html(norm_src, raw_html)
                parent_fb: str = os.path.basename(os.path.dirname(norm_src))
                fb_stem: str = f"chat_{parent_fb}_{stem_raw}" if parent_fb else stem_raw
                written = self._write_period_buckets(
                    fb_buckets, "Chats", fb_stem, discovered_phones, discovered_emails
                )
                if written:
                    already_extracted.add(norm_src)
                return written
            extracted_text, _ = self.office_extractor.extract_html(norm_src)
        elif ext == ".vtt":
            extracted_text, _ = self.teams_extractor.extract_teams_vtt(norm_src)
            sub_category = "Chats"
        elif ext == ".ics":
            extracted_text, _ = self.office_extractor.extract_ics(norm_src)
            sub_category = "Agendas"
        elif ext == ".pdf":
            extracted_text, _ = self.office_extractor.extract_pdf(norm_src, fname)
            sub_category = "PDF"
        elif ext in {".docx", ".doc"}:
            extracted_text, _ = self.office_extractor.extract_docx(norm_src)
        elif ext == ".odt":
            extracted_text, _ = self.office_extractor.extract_odt(norm_src)
        elif ext == ".rtf":
            extracted_text, _ = self.office_extractor.extract_rtf(norm_src)
        elif ext in {".xlsx", ".xls"}:
            extracted_text, _ = self.office_extractor.extract_xlsx(norm_src)
        elif ext == ".pptx":
            extracted_text, _ = self.office_extractor.extract_pptx(norm_src)
        elif ext in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}:
            if self.config.ignore_google_chat_images and "google chat" in norm_src.lower():
                return []
            extracted_text, _ = self.office_extractor.extract_image(norm_src)
            sub_category = "Images"
        elif ext in {".mp3", ".wav", ".ogg", ".m4a", ".flac"}:
            extracted_text, _ = self.comm_extractor.extract_audio(norm_src)
            sub_category = "Audio"
        elif ext == ".aup3":
            extracted_text, _ = self.comm_extractor.extract_audacity_aup3(norm_src)
            sub_category = "Audio"
        else:
            return []

        if not extracted_text or not extracted_text.strip():
            return []

        period: str = DocumentTextUtils.resolve_file_period(extracted_text, fname, norm_src)
        return self._write_period_buckets(
            {period: extracted_text}, sub_category, stem_raw, discovered_phones, discovered_emails
        )

    def finalize_reports(
        self,
        discovered_phones: Set[str],
        discovered_emails: Set[str],
        total_processed: int = 0,
        total_errors: int = 0,
        elapsed: float = 0.0,
    ) -> None:
        """Consolide les rapports d'audit SMS/e-mails en excluant les identifiants RCS Google."""
        existing_sms: Set[str] = set()
        existing_emails: Set[str] = set()

        if os.path.exists(self.config.all_sms_numbers_file):
            with open(self.config.all_sms_numbers_file, "r", encoding="utf-8", errors="ignore") as f_in:
                for line in f_in:
                    val: str = line.strip()
                    if not val or val.startswith("#"):
                        continue
                    if "@" in val:
                        existing_emails.add(val.lower())
                    else:
                        norm_p: str = DocumentTextUtils._normalize_fr_phone(val)
                        existing_sms.add(norm_p if norm_p else val)

        if os.path.exists(self.config.all_emails_file):
            with open(self.config.all_emails_file, "r", encoding="utf-8", errors="ignore") as f_in:
                for line in f_in:
                    val = line.strip()
                    if val and not val.startswith("#"):
                        existing_emails.add(val.lower())

        for raw_entry in existing_sms | discovered_phones:
            val = raw_entry.strip()
            if not val:
                continue
            if "@" in val:
                existing_emails.add(val.lower())
            else:
                norm_p = DocumentTextUtils._normalize_fr_phone(val)
                existing_sms.add(norm_p if norm_p else val)

        rcs_suffix: str = ".google.com"
        all_emails_clean: Set[str] = {
            raw_mail
            for raw_mail in (existing_emails | {e.strip().lower() for e in discovered_emails if e.strip()})
            if not raw_mail.endswith(rcs_suffix)
        }

        sms_dir: str = os.path.dirname(os.path.abspath(self.config.all_sms_numbers_file))
        if sms_dir:
            os.makedirs(sms_dir, exist_ok=True)
        DocumentTextUtils.atomic_write_text(
            self.config.all_sms_numbers_file,
            "# NUMÉROS DE TÉLÉPHONE DÉTECTÉS DANS LES SMS/MMS\n"
            + "\n".join(sorted(existing_sms))
            + ("\n" if existing_sms else ""),
        )

        mail_dir: str = os.path.dirname(os.path.abspath(self.config.all_emails_file))
        if mail_dir:
            os.makedirs(mail_dir, exist_ok=True)
        DocumentTextUtils.atomic_write_text(
            self.config.all_emails_file,
            "# ADRESSES E-MAIL DÉTECTÉES DANS LES DOCUMENTS\n"
            + "\n".join(sorted(all_emails_clean))
            + ("\n" if all_emails_clean else ""),
        )
