# Commandes pip à exécuter : Aucune dépendance externe requise

from concurrent.futures import ThreadPoolExecutor
import os
import re
import threading
import time
from typing import Dict, List, Optional, Set, Tuple
from common.core_utils import SharedCoreUtils
from doc_anonymizer.chat_extractors import MultiPlatformChatExtractor
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.text_utils import DocumentTextUtils


class DocumentExtractionRunner:
    """
    Orchestre l'étape 1 : inventaire des fichiers sources, extraction
    multi-formats parallèle et sauvegarde dans transcriptions/.
    """

    AUDIO_EXTS: Tuple[str, ...] = (
        ".wav", ".mp3", ".m4a", ".ogg", ".opus", ".flac", ".aac", ".amr",
    )
    IMAGE_EXTS: Tuple[str, ...] = (
        ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff",
    )
    HTML_EXTS: Tuple[str, ...] = (".html", ".htm")

    def __init__(
        self,
        config: PipelineConfig,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Initialise l'orchestrateur d'extraction et les verrous de concurrence.

        :param config: Instance de PipelineConfig.
        :param stop_event: Événement optionnel signalant un arrêt Ctrl+C.
        """
        self.config: PipelineConfig = config
        self.stop_event: threading.Event = stop_event or threading.Event()
        self.doc_extractor: OfficeAndDocumentExtractor = (
            OfficeAndDocumentExtractor(enable_ocr=config.enable_ocr)
        )
        self.comm_extractor: CommunicationExtractor = CommunicationExtractor(
            config=config,
            doc_extractor=self.doc_extractor,
            stop_event=self.stop_event,
        )
        self.chat_extractor: MultiPlatformChatExtractor = (
            MultiPlatformChatExtractor(config=config)
        )
        self.extraction_errors: List[str] = []
        self._io_lock: threading.Lock = threading.Lock()

    def get_worker_count(self) -> int:
        """
        Détermine le nombre optimal de threads pour l'extraction parallèle.

        :return: Nombre de workers (>= 1).
        """
        configured: int = getattr(self.config, "extraction_workers", 0)
        if configured >= 1:
            return configured
        cpu_total: int = os.cpu_count() or 2
        return max(1, min(4, cpu_total))

    @staticmethod
    def load_tracking_set(tracking_path: str) -> Set[str]:
        """
        Charge les identifiants déjà extraits depuis un fichier de suivi.

        :param tracking_path: Chemin vers le fichier de suivi.
        :return: Ensemble des clés enregistrées.
        """
        if not os.path.exists(tracking_path):
            return set()
        with open(tracking_path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    @staticmethod
    def append_tracking_entry(tracking_path: str, entry: str) -> None:
        """
        Ajoute une entrée dans le fichier de suivi.

        :param tracking_path: Chemin vers le fichier de suivi.
        :param entry: Identifiant unique traité.
        """
        parent_dir: str = os.path.dirname(tracking_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(tracking_path, "a", encoding="utf-8") as f:
            f.write(f"{entry}\n")

    @classmethod
    def categorize_extension(cls, ext: str) -> str:
        """
        Détermine le sous-dossier thématique associé à l'extension.

        :param ext: Extension en minuscules avec point initial.
        :return: Nom de la catégorie.
        """
        if ext == ".pdf":
            return "PDF"
        if ext in cls.AUDIO_EXTS or ext == ".aup3":
            return "Audio"
        if ext in cls.IMAGE_EXTS:
            return "Images"
        if ext in cls.HTML_EXTS:
            return "Web"
        if ext in {".mbox", ".eml"}:
            return "Emails"
        if ext in {".json", ".vtt"}:
            return "Chats"
        if ext == ".xml":
            return "SMS"
        if ext == ".ics":
            return "Agendas"
        return "Documents"

    @staticmethod
    def _sanitize_filesystem_stem(stem: str) -> str:
        """
        Nettoie uniquement les caractères interdits par le système de fichiers.

        :param stem: Nom de fichier sans extension.
        :return: Nom de fichier valide sur disque.
        """
        cleaned: str = re.sub(r'[<>:"/\\|?*]', "_", stem).strip()
        return cleaned or "document_sans_nom"

    def _resolve_input_dir(self) -> str:
        """
        Résout le chemin complet du répertoire contenant les fichiers sources.

        :return: Chemin normalisé du répertoire d'entrée.
        """
        if os.path.isabs(self.config.sources_dir):
            return os.path.normpath(self.config.sources_dir)
        return os.path.normpath(os.path.join(self.config.root_dir, self.config.sources_dir))

    def _file_priority_key(self, file_path: str) -> Tuple[int, int, str]:
        """
        Calcule une clé de priorité pour reporter les fichiers lourds à la fin.

        :param file_path: Chemin complet du fichier candidat.
        :return: Tuple (groupe_priorite, taille_octets, chemin_normalise).
        """
        if not self.config.defer_heavy_files:
            return (0, 0, file_path)
        _, ext_raw = os.path.splitext(file_path)
        ext: str = ext_raw.lower()
        try:
            size_bytes: int = os.path.getsize(file_path)
        except OSError:
            size_bytes = 0
        threshold_bytes: int = int(self.config.heavy_file_threshold_mb * 1024 * 1024)
        is_heavy_type: bool = ext in {".mbox", ".aup3"} or ext in self.AUDIO_EXTS
        return (1, size_bytes, file_path) if (is_heavy_type or size_bytes >= threshold_bytes) else (0, 0, file_path)
    @classmethod
    def _is_google_chat_image(cls, file_path: str, input_dir: str) -> bool:
        """
        Vérifie si le fichier est une image située dans un export Google Chat.

        :param file_path: Chemin complet du fichier candidat.
        :param input_dir: Répertoire racine des fichiers sources.
        :return: True s'il s'agit d'une image issue d'un dossier Google Chat.
        """
        _, ext_raw = os.path.splitext(file_path)
        if ext_raw.lower() not in cls.IMAGE_EXTS:
            return False
        rel_dir: str = os.path.dirname(os.path.relpath(file_path, input_dir))
        parts: List[str] = [p.lower() for p in re.split(r"[\\/]+", rel_dir) if p]
        if "google chat" in parts:
            return True
        parent_dir: str = os.path.dirname(file_path)
        return os.path.exists(os.path.join(parent_dir, "messages.json"))

    def collect_source_files(self) -> List[str]:
        """
        Parcourt le répertoire d'entrée configuré et ordonne les fichiers.

        :return: Liste ordonnée des chemins de fichiers à analyser.
        """
        input_dir: str = self._resolve_input_dir()
        if not os.path.isdir(input_dir):
            os.makedirs(input_dir, exist_ok=True)
            print(f"[AVERTISSEMENT] Dossier '{input_dir}' créé.", flush=True)
            return []

        collected: List[str] = []
        excluded_files: Set[str] = {
            os.path.basename(self.config.first_names_file),
            os.path.basename(self.config.locations_file),
            os.path.basename(self.config.excluded_words_file),
            os.path.basename(self.config.contacts_file),
            os.path.basename(self.config.manual_contacts_file),
            os.path.basename(self.config.discovered_contacts_file),
            os.path.basename(self.config.all_sms_numbers_file),
            os.path.basename(self.config.all_emails_file),
            os.path.basename(self.config.audit_report_file),
            os.path.basename(self.config.audit_copy_file),
        }
        ignore_gchat_imgs: bool = getattr(self.config, "ignore_google_chat_images", True)
        for root_path, dirs, files in os.walk(input_dir):
            dirs[:] = sorted(d for d in dirs if d not in self.config.ignored_dirs and not d.startswith("."))
            for file_name in sorted(files):
                if file_name.startswith(".") or file_name in excluded_files or file_name.endswith((".py", ".ini")):
                    continue
                full_path: str = os.path.join(root_path, file_name)
                if ignore_gchat_imgs and self._is_google_chat_image(full_path, input_dir):
                    continue
                collected.append(full_path)
        collected.sort(key=self._file_priority_key)
        return collected

    def _write_transcription_block(self, period: str, category: str, raw_base_name: str, content: str) -> str:
        """
        Écrit de façon thread-safe le contenu extrait dans transcriptions/AAAA-MM/Catégorie/.
        """
        target_dir: str = os.path.join(self.config.transcriptions_dir, period, category)
        out_path: str = os.path.join(target_dir, f"{raw_base_name}.txt")
        with self._io_lock:
            os.makedirs(target_dir, exist_ok=True)
            with open(out_path, "a", encoding="utf-8") as f_out:
                f_out.write(content)
        return out_path

    def _resolve_chat_output_stem(self, file_path: str, raw_stem: str) -> str:
        """
        Évite les collisions entre fichiers génériques (messages.json, message_1.html, _chat.txt).
        """
        low_stem: str = raw_stem.lower()
        if low_stem in {"messages", "_chat"} or low_stem.startswith("message_"):
            parent_name: str = os.path.basename(os.path.dirname(file_path))
            if parent_name:
                return self._sanitize_filesystem_stem(f"chat_{parent_name}_{raw_stem}")
        return raw_stem
    def _process_chat_or_archive(
        self, file_path: str, norm_rel: str, ext: str, raw_stem: str,
        target_phones: Dict[str, str], allowed_emails: Set[str],
        already_extracted: Set[str], discovered_phones: Set[str], discovered_emails: Set[str],
    ) -> Optional[List[str]]:
        """
        Traite les messageries (JSON, VTT, HTML, TXT) et invite à dézipper manuellement les .zip.
        """
        from doc_anonymizer.teams_chat_extractor import TeamsChatExtractor

        generated_paths: List[str] = []
        if ext == ".zip":
            msg: str = (
                f"Archive ZIP ignorée ('{norm_rel}') : veuillez dézipper "
                "manuellement l'archive dans le dossier des sources avant exécution."
            )
            print(f"[AVERTISSEMENT] {msg}", flush=True)
            with self._io_lock:
                self.extraction_errors.append(f"{norm_rel} -> {msg}")
            return []

        if ext == ".vtt":
            vtt_txt, vtt_err = TeamsChatExtractor(self.config).extract_teams_vtt(file_path)
            if self.stop_event.is_set() or vtt_err or not vtt_txt:
                if vtt_err and not self.stop_event.is_set():
                    with self._io_lock:
                        self.extraction_errors.append(f"{norm_rel} -> {vtt_err}")
                return []
            period: str = DocumentTextUtils.resolve_file_period(vtt_txt, os.path.basename(file_path), file_path)
            generated_paths.append(self._write_transcription_block(period, "Chats", raw_stem, vtt_txt))
            with self._io_lock:
                self.append_tracking_entry(self.config.extraction_tracking_file, norm_rel)
                already_extracted.add(norm_rel)
            return generated_paths

        if ext == ".json":
            local_phones, local_emails = set(), set()
            chats_by_month, chat_err = self.chat_extractor.extract_json_chat(
                file_path, target_phones, allowed_emails, local_phones, local_emails
            )
            if self.stop_event.is_set():
                return []
            with self._io_lock:
                discovered_phones.update(local_phones)
                discovered_emails.update(local_emails)
            if chat_err:
                with self._io_lock:
                    self.extraction_errors.append(f"{norm_rel} -> {chat_err}")
                return []
            if chats_by_month:
                chat_stem: str = self._resolve_chat_output_stem(file_path, raw_stem)
                for period, chat_block in sorted(chats_by_month.items()):
                    generated_paths.append(self._write_transcription_block(period, "Chats", chat_stem, chat_block))
                with self._io_lock:
                    self.append_tracking_entry(self.config.extraction_tracking_file, norm_rel)
                    already_extracted.add(norm_rel)
            return generated_paths

        if ext in self.HTML_EXTS:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f_html:
                raw_html: str = f_html.read()
            if self.chat_extractor.is_messenger_html_file(file_path, raw_html):
                fb_by_month = self.chat_extractor.extract_messenger_html(file_path, raw_html)
                if fb_by_month:
                    chat_stem = self._resolve_chat_output_stem(file_path, raw_stem)
                    for period, fb_block in sorted(fb_by_month.items()):
                        generated_paths.append(self._write_transcription_block(period, "Chats", chat_stem, fb_block))
                    with self._io_lock:
                        self.append_tracking_entry(self.config.extraction_tracking_file, norm_rel)
                        already_extracted.add(norm_rel)
                return generated_paths

        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f_txt:
                raw_txt: str = f_txt.read()
            if self.chat_extractor.is_whatsapp_text_file(raw_txt):
                wa_by_month = self.chat_extractor.extract_whatsapp_text(file_path, raw_txt)
                if wa_by_month:
                    chat_stem = self._resolve_chat_output_stem(file_path, raw_stem)
                    for period, wa_block in sorted(wa_by_month.items()):
                        generated_paths.append(self._write_transcription_block(period, "Chats", chat_stem, wa_block))
                    with self._io_lock:
                        self.append_tracking_entry(self.config.extraction_tracking_file, norm_rel)
                        already_extracted.add(norm_rel)
                return generated_paths
        return None
    def process_single_file(
        self, file_path: str, target_phones: Dict[str, str], allowed_emails: Set[str],
        already_extracted: Set[str], sms_processed: Set[str],
        discovered_phones: Set[str], discovered_emails: Set[str],
    ) -> List[str]:
        """Traite un fichier source (compatible exécution parallèle) et retourne les transcriptions."""
        if self.stop_event.is_set():
            return []
        input_dir: str = self._resolve_input_dir()
        norm_rel: str = os.path.normpath(os.path.relpath(file_path, input_dir))
        file_name: str = os.path.basename(file_path)
        stem, ext_raw = os.path.splitext(file_name)
        ext: str = ext_raw.lower()
        raw_stem: str = self._sanitize_filesystem_stem(stem)
        category: str = self.categorize_extension(ext)
        generated_paths: List[str] = []

        if ext == ".xml":
            local_phones, local_emails = set(), set()
            with self._io_lock:
                sms_snapshot: Set[str] = set(sms_processed)
            sms_by_month, xml_errors = self.comm_extractor.parse_sms_xml(
                file_path, target_phones, sms_snapshot, local_phones, local_emails
            )
            if self.stop_event.is_set():
                return []
            with self._io_lock:
                discovered_phones.update(local_phones)
                discovered_emails.update(local_emails)
                self.extraction_errors.extend(xml_errors)
            if sms_by_month:
                for period, entries in sorted(sms_by_month.items()):
                    entries.sort(key=lambda item: item)
                    generated_paths.append(
                        self._write_transcription_block(period, category, raw_stem, "".join(b for _, b in entries))
                    )
                with self._io_lock:
                    for num in local_phones:
                        key: str = f"{file_name}|{num}"
                        if num in target_phones and key not in sms_processed:
                            self.append_tracking_entry(self.config.sms_tracking_file, key)
                            sms_processed.add(key)
            return generated_paths

        with self._io_lock:
            if norm_rel in already_extracted:
                return []

        chat_res = self._process_chat_or_archive(
            file_path, norm_rel, ext, raw_stem, target_phones, allowed_emails,
            already_extracted, discovered_phones, discovered_emails,
        )
        if chat_res is not None:
            return chat_res

        if ext in {".mbox", ".eml"}:
            local_mail_disc: Set[str] = set()
            emails_by_month, err = self.comm_extractor.extract_emails(file_path, allowed_emails, local_mail_disc)
            if self.stop_event.is_set():
                return []
            with self._io_lock:
                discovered_emails.update(local_mail_disc)
            if err:
                with self._io_lock:
                    self.extraction_errors.append(f"{norm_rel} -> {err}")
                return []
            if emails_by_month:
                for period, blocks in sorted(emails_by_month.items()):
                    generated_paths.append(self._write_transcription_block(period, category, raw_stem, "".join(blocks)))
                with self._io_lock:
                    self.append_tracking_entry(self.config.extraction_tracking_file, norm_rel)
                    already_extracted.add(norm_rel)
            return generated_paths

        extractors_map = {
            ".pdf": lambda p: self.doc_extractor.extract_pdf(p, file_name),
            ".txt": self.doc_extractor.extract_text_or_markdown,
            ".md": self.doc_extractor.extract_text_or_markdown,
            ".rtf": self.doc_extractor.extract_rtf,
            ".docx": self.doc_extractor.extract_docx,
            ".odt": self.doc_extractor.extract_odt,
            ".xlsx": self.doc_extractor.extract_xlsx,
            ".pptx": self.doc_extractor.extract_pptx,
            ".ics": self.doc_extractor.extract_ics,
            ".aup3": self.comm_extractor.extract_audacity_aup3,
        }
        if ext in self.HTML_EXTS:
            extracted_text, err_msg = self.doc_extractor.extract_html(file_path)
        elif ext in self.IMAGE_EXTS:
            extracted_text, err_msg = self.doc_extractor.extract_image(file_path)
        elif ext in self.AUDIO_EXTS:
            extracted_text, err_msg = self.comm_extractor.extract_audio(file_path)
        elif ext in extractors_map:
            extracted_text, err_msg = extractors_map[ext](file_path)
        else:
            return []

        if self.stop_event.is_set() or err_msg or not extracted_text:
            if err_msg and not self.stop_event.is_set():
                with self._io_lock:
                    self.extraction_errors.append(f"{norm_rel} -> {err_msg}")
            return []

        period = DocumentTextUtils.resolve_file_period(extracted_text, file_name, file_path)
        out_p: str = self._write_transcription_block(period, category, raw_stem, extracted_text)
        with self._io_lock:
            self.append_tracking_entry(self.config.extraction_tracking_file, norm_rel)
            already_extracted.add(norm_rel)
        return [out_p]
    def load_all_filter_contacts(self) -> Tuple[Optional[Dict[str, str]], Optional[Set[str]]]:
        """Fusionne les téléphones et e-mails des trois fichiers de contacts."""
        target_phones, allowed_emails = DocumentTextUtils.load_filter_contacts(self.config.contacts_file)
        if target_phones is None or allowed_emails is None:
            return None, None
        for extra_path in (self.config.discovered_contacts_file, self.config.manual_contacts_file):
            if os.path.exists(extra_path):
                ex_phones, ex_emails = DocumentTextUtils.load_filter_contacts(extra_path)
                if ex_phones:
                    target_phones.update(ex_phones)
                if ex_emails:
                    allowed_emails.update(ex_emails)
        return target_phones, allowed_emails

    def finalize_reports(self, discovered_phones: Set[str], discovered_emails: Set[str]) -> None:
        """Écrit les rapports d'identifiants rencontrés et d'erreurs d'extraction."""
        existing_sms: Set[str] = self.load_tracking_set(self.config.all_sms_numbers_file)
        expanded: Set[str] = set()
        for raw_entry in existing_sms | discovered_phones:
            expanded.update(DocumentTextUtils.split_sms_addresses(raw_entry))

        clean_phones: Set[str] = {item for item in expanded if "@" not in item}
        migrated_emails: Set[str] = {
            item for item in expanded if "@" in item and not item.lower().endswith("://google.com")
        }
        if clean_phones or os.path.exists(self.config.all_sms_numbers_file):
            sms_dir: str = os.path.dirname(self.config.all_sms_numbers_file)
            if sms_dir:
                os.makedirs(sms_dir, exist_ok=True)
            with open(self.config.all_sms_numbers_file, "w", encoding="utf-8") as f_num:
                f_num.writelines(f"{num}\n" for num in sorted(clean_phones))

        merged_emails: Set[str] = self.load_tracking_set(self.config.all_emails_file) | discovered_emails | migrated_emails
        if merged_emails:
            mail_dir: str = os.path.dirname(self.config.all_emails_file)
            if mail_dir:
                os.makedirs(mail_dir, exist_ok=True)
            with open(self.config.all_emails_file, "w", encoding="utf-8") as f_mail:
                f_mail.writelines(f"{mail}\n" for mail in sorted(merged_emails))

        if self.extraction_errors:
            report_path: str = os.path.join(self.config.transcriptions_dir, "rapport_extraction.txt")
            with open(report_path, "w", encoding="utf-8") as f_err:
                f_err.writelines(f"{err}\n" for err in self.extraction_errors)

    def run(self) -> None:
        """Exécute la phase autonome d'extraction multi-formats en parallèle."""
        start_time: float = time.time()
        workers: int = self.get_worker_count()
        print(f"=== ÉTAPE 1 : EXTRACTION MULTI-FORMATS ({workers} worker(s)) ===", flush=True)
        target_phones, allowed_emails = self.load_all_filter_contacts()
        if target_phones is None or allowed_emails is None:
            return

        os.makedirs(self.config.transcriptions_dir, exist_ok=True)
        already_extracted: Set[str] = self.load_tracking_set(self.config.extraction_tracking_file)
        sms_processed: Set[str] = self.load_tracking_set(self.config.sms_tracking_file)
        discovered_phones, discovered_emails = set(), set()
        files: List[str] = self.collect_source_files()
        total: int = len(files)
        print(f"Inventaire : {total} fichier(s) candidat(s).", flush=True)
        processed_count: int = 0
        executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=workers)

        try:
            futures = {
                executor.submit(
                    self.process_single_file,
                    fp, target_phones, allowed_emails, already_extracted,
                    sms_processed, discovered_phones, discovered_emails
                ): fp
                for fp in files
            }
            pending_futures = set(futures.keys())
            while pending_futures:
                done_batch = [fut for fut in list(pending_futures) if fut.done()]
                if not done_batch:
                    time.sleep(0.1)
                    continue
                for future in done_batch:
                    pending_futures.remove(future)
                    fp: str = futures[future]
                    idx: int = total - len(pending_futures)
                    print(f"[{idx}/{total}] Terminé : {os.path.basename(fp)}", flush=True)
                    if future.result():
                        processed_count += 1
            executor.shutdown(wait=True)
        except KeyboardInterrupt:
            self.stop_event.set()
            executor.shutdown(wait=False, cancel_futures=True)
            raise

        self.finalize_reports(discovered_phones, discovered_emails)
        elapsed_str: str = SharedCoreUtils.format_duration(time.time() - start_time)
        print(f"\nExtraction terminée : {processed_count} fichier(s) en {elapsed_str}.", flush=True)
