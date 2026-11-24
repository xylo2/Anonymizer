# Commandes pip à exécuter : Aucune dépendance externe requise

import hashlib
import json
import os
import re
import threading
from typing import Dict, List, Optional, Set, Tuple
from doc_anonymizer.chat_extractors import MultiPlatformChatExtractor
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_csv_importer import normalize_phone_identifier
from doc_anonymizer.duplicate_files_manager import DuplicateFilesManager
from doc_anonymizer.linked_sources_manager import LinkedSourcesManager
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.outlook_extractor import OutlookArchiveExtractor
from doc_anonymizer.teams_chat_extractor import TeamsChatExtractor
from doc_anonymizer.text_utils import DocumentTextUtils


class DocumentExtractionRunner:
    """
    Orchestre l'extraction des sources brutes vers transcriptions/
    tout en collectant les numéros, e-mails et doublons ignorés.
    """

    def __init__(
        self,
        config: PipelineConfig,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        self.config: PipelineConfig = config
        self.stop_event: threading.Event = stop_event or threading.Event()
        self.office_extractor: OfficeAndDocumentExtractor = (
            OfficeAndDocumentExtractor(
                config=config, enable_ocr=config.enable_ocr
            )
        )
        self.comm_extractor: CommunicationExtractor = CommunicationExtractor(
            config=config,
            doc_extractor=self.office_extractor,
            stop_event=self.stop_event,
        )
        self.outlook_extractor: OutlookArchiveExtractor = (
            OutlookArchiveExtractor(doc_extractor=self.office_extractor)
        )
        self.chat_extractor: MultiPlatformChatExtractor = (
            MultiPlatformChatExtractor(config=config)
        )
        self.teams_extractor: TeamsChatExtractor = TeamsChatExtractor(
            config=config
        )
        self._seen_content_hashes: Set[str] = set()
        self._write_lock: threading.Lock = threading.Lock()
        self.skipped_zip_files: List[str] = []
        self.duplicate_source_files: List[str] = []
        self._zip_lock: threading.Lock = threading.Lock()
        self._warnings: List[str] = []
    def get_worker_count(self) -> int:
        if self.config.extraction_workers > 0:
            return min(8, self.config.extraction_workers)
        cpu_count: int = os.cpu_count() or 2
        return max(1, min(4, cpu_count))

    @staticmethod
    def load_tracking_set(tracking_file: str) -> Set[str]:
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
        if not tracking_file:
            return
        parent: str = os.path.dirname(os.path.abspath(tracking_file))
        if parent:
            os.makedirs(parent, exist_ok=True)
        content: str = "\n".join(sorted(items)) + ("\n" if items else "")
        DocumentTextUtils.atomic_write_text(tracking_file, content)

    def _log_extraction_warning(self, msg: str) -> None:
        with self._zip_lock:
            if msg not in self._warnings:
                self._warnings.append(msg)

    def _get_ignored_duplicate_paths(self, ws_root: str) -> Set[str]:
        """Charge les doublons ignorés (JSON ou auto-détection binaire)."""
        mgr = DuplicateFilesManager(
            {
                "workspace_root": ws_root,
                "sources_dir": self.config.sources_dir,
            }
        )
        if os.path.isfile(mgr.selection_file):
            return mgr.load_ignored_paths()
        auto_ignored: Set[str] = set()
        self.duplicate_source_files.clear()
        for item in mgr.find_duplicate_items():
            if not item.get("selected"):
                raw_p: str = os.path.normpath(str(item["path"]))
                auto_ignored.add(os.path.normcase(raw_p))
                self.duplicate_source_files.append(raw_p)
        return auto_ignored
    def collect_source_files(
        self, already_extracted: Optional[Set[str]] = None
    ) -> List[str]:
        excluded: Set[str] = already_extracted or set()
        ws_root: str = os.path.dirname(os.path.abspath(self.config.config_path))
        ignored_dups: Set[str] = self._get_ignored_duplicate_paths(ws_root)
        candidates: List[str] = []
        seen: Set[str] = set()
        if os.path.isdir(self.config.sources_dir):
            for root_p, dirs, files in os.walk(self.config.sources_dir):
                dirs[:] = [
                    d for d in sorted(dirs)
                    if d not in self.config.ignored_dirs
                    and not d.startswith(".")
                ]
                for fname in sorted(files):
                    low_fn: str = fname.lower()
                    if fname.startswith(".") or low_fn.startswith(
                        ("anonymise_", "anonymized_")
                    ):
                        continue
                    full_p: str = os.path.normpath(os.path.join(root_p, fname))
                    if os.path.normcase(full_p) in ignored_dups:
                        continue
                    if full_p not in excluded and full_p not in seen:
                        seen.add(full_p)
                        candidates.append(full_p)

        linked_mgr = LinkedSourcesManager(ws_root)
        linked_files, missing_links = linked_mgr.expand_linked_files(
            self.config.ignored_dirs
        )
        for missing_p in missing_links:
            warn_m: str = (
                f"[EMPLACEMENT EXTERNE INDISPONIBLE] '{missing_p}' "
                "-> support débranché ou inaccessible."
            )
            print(warn_m, flush=True)
            self._log_extraction_warning(warn_m)
        for full_p in linked_files:
            if os.path.normcase(full_p) in ignored_dups:
                continue
            if full_p not in excluded and full_p not in seen:
                seen.add(full_p)
                candidates.append(full_p)
        return candidates

    def _load_filter_paths_list(self) -> List[str]:
        sel_file: str = getattr(
            self.config, "selected_extraction_contacts_file", ""
        )
        if sel_file and os.path.exists(sel_file):
            return [sel_file, self.config.manual_contacts_file]
        return [
            self.config.contacts_file,
            self.config.discovered_contacts_file,
            self.config.discovered_chats_file,
            self.config.manual_contacts_file,
        ]
    @staticmethod
    def _normalize_any_phone(raw_phone: str) -> str:
        fr_norm: str = DocumentTextUtils._normalize_fr_phone(raw_phone)
        if fr_norm:
            return fr_norm
        generic: str = normalize_phone_identifier(raw_phone)
        if not generic or "@" in generic or any(ch.isalpha() for ch in generic):
            return ""
        digits_only: str = re.sub(r"\D", "", generic)
        return generic if len(digits_only) >= 4 else ""

    def load_allowed_chat_names(self) -> Set[str]:
        contacts_dir: str = os.path.dirname(os.path.abspath(self.config.contacts_file))
        wl_file: str = os.path.join(contacts_dir, "whitelist_contacts.json")
        allowed_names: Set[str] = set()
        if not os.path.isfile(wl_file):
            return allowed_names
        try:
            with open(wl_file, "r", encoding="utf-8") as f_wl:
                raw_list = json.load(f_wl)
            if isinstance(raw_list, list):
                for entry in raw_list:
                    val: str = str(entry).strip()
                    if not val or "@" in val or any(ch.isdigit() for ch in val):
                        continue
                    norm_n: str = DocumentTextUtils.normalize_word(val)
                    if len(norm_n) >= 2:
                        allowed_names.add(norm_n)
        except (OSError, json.JSONDecodeError):
            pass
        return allowed_names

    def load_allowed_chat_titles(self) -> Optional[Set[str]]:
        contacts_dir: str = os.path.dirname(os.path.abspath(self.config.contacts_file))
        wl_chat_file: str = os.path.join(contacts_dir, "whitelist_chats.json")
        if not os.path.isfile(wl_chat_file):
            return None
        allowed_titles: Set[str] = set()
        try:
            with open(wl_chat_file, "r", encoding="utf-8") as f_wc:
                raw_list = json.load(f_wc)
            if isinstance(raw_list, list):
                for entry in raw_list:
                    norm_t: str = DocumentTextUtils.normalize_word(str(entry))
                    if norm_t:
                        allowed_titles.add(norm_t)
        except (OSError, json.JSONDecodeError):
            pass
        return allowed_titles
    def _is_chat_file_allowed_by_whitelist(
        self, file_path: str, allowed_titles: Optional[Set[str]]
    ) -> bool:
        if allowed_titles is None:
            return True
        from doc_anonymizer.chat_filter_manager import ChatFilterManager

        meta = ChatFilterManager.inspect_chat_file_metadata(file_path)
        if not meta:
            return True
        norm_title: str = DocumentTextUtils.normalize_word(str(meta.get("title") or ""))
        return norm_title in allowed_titles

    def load_all_filter_contacts(self) -> Tuple[Dict[str, str], Set[str]]:
        target_phones: Dict[str, str] = {}
        allowed_emails: Set[str] = set()
        for path in self._load_filter_paths_list():
            if not path or not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as f_in:
                for raw_line in f_in:
                    line: str = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    left_p, right_p = line.split("=", 1)
                    left, right = left_p.strip(), right_p.strip()
                    if not left or not right:
                        continue
                    if "@" in right and "@" not in left:
                        left, right = right, left
                    elif self._normalize_any_phone(right) and not self._normalize_any_phone(left):
                        left, right = right, left
                    if "@" in left:
                        norm_m: str = DocumentTextUtils.normalize_identifier(left)
                        if norm_m:
                            allowed_emails.add(norm_m)
                    else:
                        norm_p: str = self._normalize_any_phone(left)
                        if norm_p:
                            target_phones[norm_p] = right
        return target_phones, allowed_emails
    def _write_period_output(self, period: str, category: str, out_name: str, text: str) -> Optional[str]:
        cleaned: str = DocumentTextUtils.clean_extracted_text(text)
        if not cleaned:
            return None
        digest: str = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
        with self._write_lock:
            if digest in self._seen_content_hashes:
                return None
            self._seen_content_hashes.add(digest)
        out_dir: str = os.path.join(self.config.transcriptions_dir, period or "Date_Inconnue", category)
        os.makedirs(out_dir, exist_ok=True)
        safe_fn: str = DocumentTextUtils.sanitize_filename_component(out_name)
        out_path: str = os.path.join(out_dir, safe_fn)
        DocumentTextUtils.atomic_write_text(out_path, cleaned + "\n")
        return out_path

    def _collect_text_identifiers(self, text: str, phones_out: Set[str], emails_out: Set[str]) -> None:
        with self._write_lock:
            for m_p in DocumentTextUtils.REGEX_PHONE.finditer(text):
                np: str = self._normalize_any_phone(m_p.group(0))
                if np:
                    phones_out.add(np)
            for m_e in DocumentTextUtils.REGEX_EMAIL.finditer(text):
                ne: str = DocumentTextUtils.normalize_identifier(m_e.group(0))
                if ne and not ne.endswith("://google.com"):
                    emails_out.add(ne)

    def _extract_chat_or_comm(
        self, file_path: str, ext: str, target_phones: Dict[str, str], allowed_emails: Set[str],
        sms_processed: Set[str], disc_phones: Set[str], disc_emails: Set[str],
    ) -> Optional[List[str]]:
        fname: str = os.path.basename(file_path)
        stem, _ = os.path.splitext(fname)
        parent_tag: str = DocumentTextUtils.sanitize_filename_component(os.path.basename(os.path.dirname(file_path)))
        allowed_names: Set[str] = self.load_allowed_chat_names()
        allowed_titles: Optional[Set[str]] = self.load_allowed_chat_titles()
        generated: List[str] = []

        if ext == ".xml":
            by_month, errs = self.comm_extractor.parse_sms_xml(file_path, target_phones, sms_processed, disc_phones, disc_emails)
            for e in errs:
                self._log_extraction_warning(e)
            for period, entries in sorted(by_month.items()):
                entries.sort(key=lambda pair: next(iter(pair)))
                out_p = self._write_period_output(period, "SMS", f"sms_{stem}.txt", "".join(b for _, b in entries))
                if out_p:
                    generated.append(out_p)
            return generated
        if ext in {".mbox", ".eml", ".msg", ".pst", ".ost"}:
            if ext == ".msg":
                by_month_m, err_m = self.outlook_extractor.extract_msg(
                    file_path, allowed_emails, disc_emails
                )
            elif ext in {".pst", ".ost"}:
                by_month_m, err_m = self.outlook_extractor.extract_pst_or_ost(
                    file_path, allowed_emails, disc_emails
                )
            else:
                by_month_m, err_m = self.comm_extractor.extract_emails(
                    file_path, allowed_emails, disc_emails
                )
            if err_m:
                self._log_extraction_warning(f"{fname} -> {err_m}")
            for period, blocks in sorted(by_month_m.items()):
                out_p = self._write_period_output(
                    period, "Emails", f"emails_{stem}.txt", "".join(blocks)
                )
                if out_p:
                    generated.append(out_p)
            return generated

        if ext == ".json":
            if fname.lower() in {"user_info.json", "group_info.json"}:
                return []
            if not self._is_chat_file_allowed_by_whitelist(file_path, allowed_titles):
                return []
            buckets, err_j = self.chat_extractor.extract_json_chat(
                file_path, target_phones, allowed_emails, disc_phones, disc_emails,
                allowed_names=allowed_names,
            )
            if err_j:
                self._log_extraction_warning(f"{fname} -> {err_j}")
            for period, txt in sorted(buckets.items()):
                out_p = self._write_period_output(
                    period, "Chats", f"chat_{parent_tag}_{stem}.txt", txt
                )
                if out_p:
                    generated.append(out_p)
            return generated

        if ext == ".vtt":
            if not self._is_chat_file_allowed_by_whitelist(file_path, allowed_titles):
                return []
            vtt_txt, period = self.teams_extractor.extract_teams_vtt(file_path)
            if vtt_txt:
                out_p = self._write_period_output(
                    period, "Chats", f"chat_{stem}.txt", vtt_txt
                )
                if out_p:
                    generated.append(out_p)
            return generated
        return None
    def process_single_file(
        self, file_path: str, target_phones: Dict[str, str], allowed_emails: Set[str],
        already_extracted: Set[str], sms_processed: Set[str], disc_phones: Set[str], disc_emails: Set[str],
    ) -> List[str]:
        norm_p: str = os.path.normpath(file_path)
        if self.stop_event.is_set() or not os.path.isfile(norm_p):
            return []
        fname: str = os.path.basename(norm_p)
        stem, ext_raw = os.path.splitext(fname)
        ext: str = ext_raw.lower()
        generated: List[str] = []

        if ext == ".zip":
            with self._zip_lock:
                if norm_p not in self.skipped_zip_files:
                    self.skipped_zip_files.append(norm_p)
            self._log_extraction_warning(f"[ARCHIVE ZIP IGNORÉE] '{fname}' -> archive non analysée par sécurité, décompressez-la.")
            with self._write_lock:
                already_extracted.add(norm_p)
            return []
        if self.config.ignore_google_chat_images and ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            if "google chat" in norm_p.lower():
                with self._write_lock:
                    already_extracted.add(norm_p)
                return []

        special = self._extract_chat_or_comm(norm_p, ext, target_phones, allowed_emails, sms_processed, disc_phones, disc_emails)
        if special is not None:
            with self._write_lock:
                already_extracted.add(norm_p)
            return special

        raw_txt: Optional[str] = None
        err_msg: Optional[str] = None
        category: str = "Documents"
        if ext == ".pdf":
            category, (raw_txt, err_msg) = "PDF", self.office_extractor.extract_pdf(norm_p, fname)
        elif ext in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}:
            category, (raw_txt, err_msg) = "Images", self.office_extractor.extract_image(norm_p)
        elif ext == ".docx":
            raw_txt, err_msg = self.office_extractor.extract_docx(norm_p)
        elif ext == ".odt":
            raw_txt, err_msg = self.office_extractor.extract_odt(norm_p)
        elif ext == ".rtf":
            raw_txt, err_msg = self.office_extractor.extract_rtf(norm_p)
        elif ext in {".xlsx", ".xls"}:
            raw_txt, err_msg = self.office_extractor.extract_xlsx(norm_p)
        elif ext == ".pptx":
            raw_txt, err_msg = self.office_extractor.extract_pptx(norm_p)
        elif ext in {".html", ".htm"}:
            with open(norm_p, "r", encoding="utf-8", errors="ignore") as f_h:
                raw_h: str = f_h.read()
            if self.chat_extractor.is_messenger_html_file(norm_p, raw_h):
                if not self._is_chat_file_allowed_by_whitelist(norm_p, self.load_allowed_chat_titles()):
                    with self._write_lock:
                        already_extracted.add(norm_p)
                    return []
                buckets = self.chat_extractor.extract_messenger_html(norm_p, raw_h, allowed_names=self.load_allowed_chat_names())
                for period, txt in sorted(buckets.items()):
                    out_p = self._write_period_output(period, "Chats", f"chat_{stem}.txt", txt)
                    if out_p:
                        generated.append(out_p)
                with self._write_lock:
                    already_extracted.add(norm_p)
                return generated
            raw_txt, err_msg = self.office_extractor.extract_html(norm_p)
        elif ext == ".ics":
            category, (raw_txt, err_msg) = "Agendas", self.office_extractor.extract_ics(norm_p)
        elif ext in {".txt", ".md", ".csv", ".log"}:
            with open(norm_p, "r", encoding="utf-8", errors="ignore") as f_t:
                head_txt: str = f_t.read(8192)
            if self.chat_extractor.is_whatsapp_text_file(head_txt):
                if not self._is_chat_file_allowed_by_whitelist(norm_p, self.load_allowed_chat_titles()):
                    with self._write_lock:
                        already_extracted.add(norm_p)
                    return []
                with open(norm_p, "r", encoding="utf-8", errors="ignore") as f_all:
                    full_wa: str = f_all.read()
                buckets = self.chat_extractor.extract_whatsapp_text(norm_p, full_wa, allowed_names=self.load_allowed_chat_names())
                for period, txt in sorted(buckets.items()):
                    out_p = self._write_period_output(period, "Chats", f"chat_{stem}.txt", txt)
                    if out_p:
                        generated.append(out_p)
                with self._write_lock:
                    already_extracted.add(norm_p)
                return generated
            raw_txt, err_msg = self.office_extractor.extract_text_or_markdown(norm_p)
        elif ext in {".mp3", ".wav", ".ogg", ".m4a", ".flac"}:
            category, (raw_txt, err_msg) = "Audio", self.comm_extractor.extract_audio(norm_p)
        elif ext in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
            category, (raw_txt, err_msg) = "Videos", self.comm_extractor.extract_video(norm_p)
        elif ext == ".aup3":
            category, (raw_txt, err_msg) = "Audio", self.comm_extractor.extract_audacity_aup3(norm_p)
        else:
            self._log_extraction_warning(f"[FORMAT IGNORÉ] '{fname}' (extension non prise en charge).")
            with self._write_lock:
                already_extracted.add(norm_p)
            return []

        if err_msg:
            self._log_extraction_warning(f"{fname} -> {err_msg}")
        if raw_txt:
            self._collect_text_identifiers(raw_txt, disc_phones, disc_emails)
            period = DocumentTextUtils.resolve_file_period(raw_txt, fname, norm_p)
            out_p = self._write_period_output(period, category, f"{stem}.txt", raw_txt)
            if out_p:
                generated.append(out_p)
        with self._write_lock:
            already_extracted.add(norm_p)
        return generated

    def finalize_reports(self, discovered_phones: Set[str], discovered_emails: Set[str]) -> None:
        ignored_suffixes: Tuple[str, ...] = ("chat.google.com", "://google.com")
        clean_phones: Set[str] = set()
        clean_emails: Set[str] = set()
        for raw_p in discovered_phones:
            if "@" in raw_p:
                nm = DocumentTextUtils.normalize_identifier(raw_p)
                if nm and not nm.endswith(ignored_suffixes):
                    clean_emails.add(nm)
            else:
                np = self._normalize_any_phone(raw_p)
                if np:
                    clean_phones.add(np)
        for raw_e in discovered_emails:
            ne = DocumentTextUtils.normalize_identifier(raw_e)
            if ne and "@" in ne and not ne.endswith(ignored_suffixes):
                clean_emails.add(ne)

        if self.config.all_sms_numbers_file:
            if os.path.exists(self.config.all_sms_numbers_file):
                with open(self.config.all_sms_numbers_file, "r", encoding="utf-8", errors="ignore") as f_old:
                    for ln in f_old:
                        s = ln.strip()
                        if not s or s.startswith("#"):
                            continue
                        if "@" in s:
                            nm = DocumentTextUtils.normalize_identifier(s)
                            if nm and not nm.endswith(ignored_suffixes):
                                clean_emails.add(nm)
                        else:
                            np = self._normalize_any_phone(s)
                            if np:
                                clean_phones.add(np)
            os.makedirs(os.path.dirname(os.path.abspath(self.config.all_sms_numbers_file)), exist_ok=True)
            DocumentTextUtils.atomic_write_text(
                self.config.all_sms_numbers_file,
                "# NUMÉROS DÉTECTÉS\n" + "".join(f"{p}\n" for p in sorted(clean_phones)),
            )

        if self.config.all_emails_file:
            if os.path.exists(self.config.all_emails_file):
                with open(self.config.all_emails_file, "r", encoding="utf-8", errors="ignore") as f_old_e:
                    for ln in f_old_e:
                        s = ln.strip()
                        if s and not s.startswith("#") and "@" in s and not s.endswith(ignored_suffixes):
                            clean_emails.add(s)
            os.makedirs(os.path.dirname(os.path.abspath(self.config.all_emails_file)), exist_ok=True)
            DocumentTextUtils.atomic_write_text(
                self.config.all_emails_file,
                "# E-MAILS DÉTECTÉS\n" + "".join(f"{e}\n" for e in sorted(clean_emails)),
            )

        if self.config.extraction_report_file:
            os.makedirs(os.path.dirname(os.path.abspath(self.config.extraction_report_file)), exist_ok=True)
            body: str = "\n".join(self._warnings) if self._warnings else "Aucune anomalie détectée."
            DocumentTextUtils.atomic_write_text(
                self.config.extraction_report_file,
                f"# RAPPORT D'EXTRACTION\n{body}\n",
            )
