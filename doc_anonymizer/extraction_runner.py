import hashlib
import os
import threading
from typing import Any, Dict, List, Optional, Set, Tuple
from doc_anonymizer.chat_extractors import MultiPlatformChatExtractor
from doc_anonymizer.comm_cache_index import CommunicationExtractionCache
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.duplicate_files_manager import DuplicateFilesManager
from doc_anonymizer.extraction_helpers import (
    ExtractionFilterLoader,
    ExtractionReportWriter,
)
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
        self.filter_loader: ExtractionFilterLoader = ExtractionFilterLoader(config)
        self.report_writer: ExtractionReportWriter = ExtractionReportWriter(config)
        audits_dir: str = os.path.dirname(
            os.path.abspath(config.extraction_report_file)
        )
        self.comm_cache: CommunicationExtractionCache = (
            CommunicationExtractionCache(audits_dir)
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
    def load_all_filter_contacts(self) -> Tuple[Dict[str, str], Set[str]]:
        return self.filter_loader.load_all_filter_contacts()

    def _write_period_output(
        self, period: str, category: str, out_name: str, text: str
    ) -> Optional[str]:
        cleaned: str = DocumentTextUtils.clean_extracted_text(text)
        if not cleaned:
            return None
        digest: str = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
        with self._write_lock:
            if digest in self._seen_content_hashes:
                return None
            self._seen_content_hashes.add(digest)
        out_dir: str = os.path.join(
            self.config.transcriptions_dir, period or "Date_Inconnue", category
        )
        os.makedirs(out_dir, exist_ok=True)
        safe_fn: str = DocumentTextUtils.sanitize_filename_component(out_name)
        out_path: str = os.path.join(out_dir, safe_fn)
        DocumentTextUtils.atomic_write_text(out_path, cleaned + "\n")
        return out_path

    def _collect_text_identifiers(
        self, text: str, phones_out: Set[str], emails_out: Set[str]
    ) -> None:
        with self._write_lock:
            for m_p in DocumentTextUtils.REGEX_PHONE.finditer(text):
                np: str = ExtractionFilterLoader.normalize_any_phone(m_p.group(0))
                if np:
                    phones_out.add(np)
            for m_e in DocumentTextUtils.REGEX_EMAIL.finditer(text):
                ne: str = DocumentTextUtils.normalize_identifier(m_e.group(0))
                if ne and not ne.endswith(ExtractionReportWriter.IGNORED_SUFFIXES):
                    emails_out.add(ne)

    def _extract_sms_cached(
        self, file_path: str, stem: str, target_phones: Dict[str, str],
        sms_processed: Set[str], disc_phones: Set[str], disc_emails: Set[str],
    ) -> List[str]:
        def _build_sms_index() -> Dict[str, Any]:
            class _CatchAllPhones(dict):  # type: ignore[type-arg]
                def __contains__(self, k: object) -> bool:
                    return True

                def __getitem__(self, k: str) -> str:
                    return f"__NUM_{k}__"

            local_p: Set[str] = set()
            local_e: Set[str] = set()
            by_m, errs = self.comm_extractor.parse_sms_xml(
                file_path, _CatchAllPhones(), set(), local_p, local_e
            )
            return {
                "by_month": {k: [list(x) for x in v] for k, v in by_m.items()},
                "errors": errs,
                "phones": sorted(local_p),
                "emails": sorted(local_e),
            }
        cached = self.comm_cache.get_or_build(file_path, "sms_xml", _build_sms_index)
        for e in cached.get("errors", []):
            self._log_extraction_warning(str(e))
        disc_phones.update(cached.get("phones", []))
        disc_emails.update(cached.get("emails", []))

        fname: str = os.path.basename(file_path)
        by_month_all: Dict[str, List[Any]] = cached.get("by_month", {})
        by_month_filt: Dict[str, List[Tuple[int, str]]] = {}

        for period, entries in by_month_all.items():
            kept: List[Tuple[int, str]] = []
            for ts_ms, raw_blk in entries:
                blk: str = str(raw_blk)
                if not target_phones:
                    clean_b: str = blk.replace("__NUM_", "").replace("__", "")
                    kept.append((int(ts_ms), clean_b))
                    continue
                matched_aliases: List[str] = []
                for ph, alias in target_phones.items():
                    marker: str = f"__NUM_{ph}__"
                    if marker in blk:
                        sms_processed.add(f"{fname}|{ph}")
                        if alias not in matched_aliases:
                            matched_aliases.append(alias)
                if matched_aliases:
                    clean_b = blk
                    for ph, alias in target_phones.items():
                        clean_b = clean_b.replace(f"__NUM_{ph}__", alias)
                    clean_b = clean_b.replace("__NUM_", "").replace("__", "")
                    kept.append((int(ts_ms), clean_b))
            if kept:
                by_month_filt[period] = kept

        generated: List[str] = []
        for period, entries in sorted(by_month_filt.items()):
            entries.sort(key=lambda pair: next(iter(pair)))
            out_p = self._write_period_output(
                period, "SMS", f"sms_{stem}.txt",
                "".join(b for _, b in entries),
            )
            if out_p:
                generated.append(out_p)
        return generated
    def _extract_chat_or_comm(
        self, file_path: str, ext: str, target_phones: Dict[str, str],
        allowed_emails: Set[str], sms_processed: Set[str],
        disc_phones: Set[str], disc_emails: Set[str],
    ) -> Optional[List[str]]:
        fname: str = os.path.basename(file_path)
        stem, _ = os.path.splitext(fname)
        parent_tag: str = DocumentTextUtils.sanitize_filename_component(
            os.path.basename(os.path.dirname(file_path))
        )
        allowed_names: Optional[Set[str]] = self.filter_loader.load_allowed_chat_names()
        allowed_titles: Optional[Set[str]] = (
            self.filter_loader.load_allowed_chat_titles()
        )
        generated: List[str] = []
        if ext == ".xml":
            return self._extract_sms_cached(
                file_path, stem, target_phones,
                sms_processed, disc_phones, disc_emails,
            )

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
            if not self.filter_loader.is_chat_file_allowed_by_whitelist(
                file_path, allowed_titles
            ):
                return []
            import json

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f_j:
                    payload_j = json.load(f_j)
            except Exception:
                payload_j = None
            if payload_j is not None and self.teams_extractor.is_teams_json_payload(payload_j):
                buckets = self.teams_extractor.extract_teams_json(
                    file_path, payload_j, disc_emails
                )
                err_j = None
            else:
                buckets, err_j = self.chat_extractor.extract_json_chat(
                    file_path, target_phones, allowed_emails, disc_phones,
                    disc_emails, allowed_names=allowed_names,
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
            if not self.filter_loader.is_chat_file_allowed_by_whitelist(
                file_path, allowed_titles
            ):
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
        self, file_path: str, target_phones: Dict[str, str],
        allowed_emails: Set[str], already_extracted: Set[str],
        sms_processed: Set[str], disc_phones: Set[str], disc_emails: Set[str],
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
            self._log_extraction_warning(
                f"[ARCHIVE ZIP IGNORÉE] '{fname}' -> "
                "archive non analysée par sécurité, décompressez-la."
            )
            with self._write_lock:
                already_extracted.add(norm_p)
            return []
        if self.config.ignore_google_chat_images and ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            if "google chat" in norm_p.lower():
                with self._write_lock:
                    already_extracted.add(norm_p)
                return []

        special = self._extract_chat_or_comm(
            norm_p, ext, target_phones, allowed_emails,
            sms_processed, disc_phones, disc_emails,
        )
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
                if not self.filter_loader.is_chat_file_allowed_by_whitelist(
                    norm_p, self.filter_loader.load_allowed_chat_titles()
                ):
                    with self._write_lock:
                        already_extracted.add(norm_p)
                    return []
                buckets = self.chat_extractor.extract_messenger_html(
                    norm_p, raw_h,
                    allowed_names=self.filter_loader.load_allowed_chat_names(),
                )
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
                if not self.filter_loader.is_chat_file_allowed_by_whitelist(
                    norm_p, self.filter_loader.load_allowed_chat_titles()
                ):
                    with self._write_lock:
                        already_extracted.add(norm_p)
                    return []
                with open(norm_p, "r", encoding="utf-8", errors="ignore") as f_all:
                    full_wa: str = f_all.read()
                buckets = self.chat_extractor.extract_whatsapp_text(
                    norm_p, full_wa,
                    allowed_names=self.filter_loader.load_allowed_chat_names(),
                )
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

    def finalize_reports(
        self, discovered_phones: Set[str], discovered_emails: Set[str]
    ) -> None:
        self.report_writer.finalize_reports(
            discovered_phones, discovered_emails, self._warnings
        )
