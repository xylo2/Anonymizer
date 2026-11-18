# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import time
from typing import Dict, List, Optional, Set, Tuple
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.text_utils import DocumentTextUtils


class DocumentExtractionRunner:
    """
    Orchestre l'étape 1 : inventaire des fichiers dans le répertoire
    sources configuré, extraction multi-formats et sauvegarde dans
    le dossier de transcriptions.
    """

    AUDIO_EXTS: Tuple[str, ...] = (
        ".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".amr",
    )
    IMAGE_EXTS: Tuple[str, ...] = (
        ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff",
    )
    HTML_EXTS: Tuple[str, ...] = (".html", ".htm")

    def __init__(self, config: PipelineConfig) -> None:
        """
        Initialise l'orchestrateur d'extraction.

        :param config: Instance de PipelineConfig.
        """
        self.config: PipelineConfig = config
        self.doc_extractor: OfficeAndDocumentExtractor = (
            OfficeAndDocumentExtractor(enable_ocr=config.enable_ocr)
        )
        self.comm_extractor: CommunicationExtractor = CommunicationExtractor(
            config=config, doc_extractor=self.doc_extractor
        )
        self.extraction_errors: List[str] = []

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
        if ext == ".xml":
            return "SMS"
        if ext == ".ics":
            return "Agendas"
        return "Documents"
    def _resolve_input_dir(self) -> str:
        """
        Résout le chemin complet du répertoire contenant les fichiers
        sources à traiter (ex: './fichiers sources').

        :return: Chemin normalisé du répertoire d'entrée.
        """
        if os.path.isabs(self.config.sources_dir):
            return os.path.normpath(self.config.sources_dir)
        return os.path.normpath(
            os.path.join(self.config.root_dir, self.config.sources_dir)
        )

    def collect_source_files(self) -> List[str]:
        """
        Parcourt uniquement le répertoire d'entrée configuré
        (sources_dir) pour lister tous les fichiers éligibles.

        :return: Liste triée des chemins de fichiers à analyser.
        """
        input_dir: str = self._resolve_input_dir()
        if not os.path.isdir(input_dir):
            os.makedirs(input_dir, exist_ok=True)
            print(
                f"[AVERTISSEMENT] Dossier '{input_dir}' créé : "
                "placez-y vos documents avant de relancer.",
                flush=True,
            )
            return []

        collected: List[str] = []
        excluded_files: Set[str] = {
            os.path.basename(self.config.contacts_file),
            os.path.basename(self.config.all_sms_numbers_file),
            os.path.basename(self.config.all_emails_file),
            os.path.basename(self.config.audit_report_file),
        }
        for root_path, dirs, files in os.walk(input_dir):
            dirs[:] = sorted(
                d
                for d in dirs
                if d not in self.config.ignored_dirs and not d.startswith(".")
            )
            for fname in sorted(files):
                if (
                    fname.startswith(".")
                    or fname in excluded_files
                    or fname.endswith(".py")
                    or fname.endswith(".ini")
                ):
                    continue
                collected.append(os.path.join(root_path, fname))
        return collected

    def _write_transcription_block(
        self,
        period: str,
        category: str,
        safe_base_name: str,
        content: str,
    ) -> str:
        """
        Écrit le contenu extrait dans transcriptions/AAAA-MM/Catégorie/.

        :param period: Période AAAA-MM.
        :param category: Catégorie thématique du document.
        :param safe_base_name: Nom de fichier assaini.
        :param content: Texte extrait prêt à enregistrer.
        :return: Chemin du fichier transcription généré.
        """
        target_dir: str = os.path.join(
            self.config.transcriptions_dir, period, category
        )
        os.makedirs(target_dir, exist_ok=True)
        out_path: str = os.path.join(target_dir, f"{safe_base_name}.txt")
        with open(out_path, "a", encoding="utf-8") as f_out:
            f_out.write(content)
        return out_path

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
        """
        Traite un fichier source et retourne la liste des transcriptions
        créées ou mises à jour pour permettre leur anonymisation immédiate.

        :param file_path: Chemin vers le fichier candidat.
        :param target_phones: Téléphones issus de contacts.txt.
        :param allowed_emails: E-mails issus de contacts.txt.
        :param already_extracted: Fichiers déjà traités.
        :param sms_processed: Clés SMS déjà extraites.
        :param discovered_phones: Collecteur des numéros rencontrés.
        :param discovered_emails: Collecteur des e-mails rencontrés.
        :return: Liste des chemins de transcriptions générées.
        """
        input_dir: str = self._resolve_input_dir()
        norm_rel: str = os.path.normpath(
            os.path.relpath(file_path, input_dir)
        )
        fname: str = os.path.basename(file_path)
        stem, ext_raw = os.path.splitext(fname)
        ext: str = ext_raw.lower()
        safe_stem: str = DocumentTextUtils.mask_identifiers_in_filename(
            stem, target_phones
        )
        category: str = self.categorize_extension(ext)
        generated_paths: List[str] = []

        if ext == ".xml":
            sms_by_month, xml_errors = self.comm_extractor.parse_sms_xml(
                xml_path=file_path,
                target_phones=target_phones,
                already_processed=sms_processed,
                discovered_phones=discovered_phones,
            )
            self.extraction_errors.extend(xml_errors)
            if sms_by_month:
                for period, entries in sorted(sms_by_month.items()):
                    entries.sort(key=lambda item: item)
                    merged_sms: str = "".join(block for _, block in entries)
                    out_p: str = self._write_transcription_block(
                        period, category, safe_stem, merged_sms
                    )
                    generated_paths.append(out_p)
                for num in target_phones:
                    key: str = f"{fname}|{num}"
                    if key not in sms_processed:
                        self.append_tracking_entry(
                            self.config.sms_tracking_file, key
                        )
                        sms_processed.add(key)
            return generated_paths

        if norm_rel in already_extracted:
            return []

        if ext in {".mbox", ".eml"}:
            emails_by_month, err = self.comm_extractor.extract_emails(
                file_path=file_path,
                allowed_emails=allowed_emails,
                discovered_emails=discovered_emails,
            )
            if err:
                self.extraction_errors.append(f"{norm_rel} -> {err}")
                return []
            if emails_by_month:
                for period, blocks in sorted(emails_by_month.items()):
                    out_p = self._write_transcription_block(
                        period, category, safe_stem, "".join(blocks)
                    )
                    generated_paths.append(out_p)
                self.append_tracking_entry(
                    self.config.extraction_tracking_file, norm_rel
                )
                already_extracted.add(norm_rel)
            return generated_paths
        extracted_text: Optional[str] = None
        err_msg: Optional[str] = None

        if ext == ".pdf":
            extracted_text, err_msg = self.doc_extractor.extract_pdf(
                file_path, fname
            )
        elif ext in {".txt", ".md"}:
            extracted_text, err_msg = (
                self.doc_extractor.extract_text_or_markdown(file_path)
            )
        elif ext in self.HTML_EXTS:
            extracted_text, err_msg = self.doc_extractor.extract_html(
                file_path
            )
        elif ext == ".rtf":
            extracted_text, err_msg = self.doc_extractor.extract_rtf(
                file_path
            )
        elif ext == ".docx":
            extracted_text, err_msg = self.doc_extractor.extract_docx(
                file_path
            )
        elif ext == ".odt":
            extracted_text, err_msg = self.doc_extractor.extract_odt(
                file_path
            )
        elif ext == ".xlsx":
            extracted_text, err_msg = self.doc_extractor.extract_xlsx(
                file_path
            )
        elif ext == ".pptx":
            extracted_text, err_msg = self.doc_extractor.extract_pptx(
                file_path
            )
        elif ext in self.IMAGE_EXTS:
            extracted_text, err_msg = self.doc_extractor.extract_image(
                file_path
            )
        elif ext == ".ics":
            extracted_text, err_msg = self.doc_extractor.extract_ics(file_path)
        elif ext in self.AUDIO_EXTS:
            extracted_text, err_msg = self.comm_extractor.extract_audio(
                file_path
            )
        elif ext == ".aup3":
            extracted_text, err_msg = (
                self.comm_extractor.extract_audacity_aup3(file_path)
            )
        else:
            return []

        if err_msg or not extracted_text:
            if err_msg:
                self.extraction_errors.append(f"{norm_rel} -> {err_msg}")
            return []

        period: str = DocumentTextUtils.resolve_file_period(
            extracted_text, fname, file_path
        )
        out_p = self._write_transcription_block(
            period, category, safe_stem, extracted_text
        )
        self.append_tracking_entry(
            self.config.extraction_tracking_file, norm_rel
        )
        already_extracted.add(norm_rel)
        return [out_p]

    def finalize_reports(
        self,
        discovered_phones: Set[str],
        discovered_emails: Set[str],
    ) -> None:
        """
        Écrit les listes d'identifiants découverts et le rapport d'erreurs.

        :param discovered_phones: Numéros rencontrés pendant l'extraction.
        :param discovered_emails: E-mails rencontrés pendant l'extraction.
        """
        if discovered_phones:
            with open(
                self.config.all_sms_numbers_file, "w", encoding="utf-8"
            ) as f_num:
                for num in sorted(discovered_phones):
                    f_num.write(f"{num}\n")
        if discovered_emails:
            with open(
                self.config.all_emails_file, "w", encoding="utf-8"
            ) as f_mail:
                for mail in sorted(discovered_emails):
                    f_mail.write(f"{mail}\n")

        if self.extraction_errors:
            report_path: str = os.path.join(
                self.config.transcriptions_dir, "rapport_extraction.txt"
            )
            with open(report_path, "w", encoding="utf-8") as f_err:
                for err in self.extraction_errors:
                    f_err.write(f"{err}\n")

    def run(self) -> None:
        """
        Exécute la phase autonome d'extraction multi-formats.
        """
        start_time: float = time.time()
        print("=== ÉTAPE 1 : EXTRACTION MULTI-FORMATS ===", flush=True)

        target_phones, allowed_emails = (
            DocumentTextUtils.load_filter_contacts(self.config.contacts_file)
        )
        if target_phones is None or allowed_emails is None:
            return

        os.makedirs(self.config.transcriptions_dir, exist_ok=True)
        already_extracted: Set[str] = self.load_tracking_set(
            self.config.extraction_tracking_file
        )
        sms_processed: Set[str] = self.load_tracking_set(
            self.config.sms_tracking_file
        )
        discovered_phones: Set[str] = set()
        discovered_emails: Set[str] = set()

        files: List[str] = self.collect_source_files()
        print(f"Inventaire : {len(files)} fichier(s) candidat(s).", flush=True)

        processed_count: int = 0
        for idx, file_path in enumerate(files, start=1):
            print(f"[{idx}/{len(files)}] Analyse : {file_path}", flush=True)
            created: List[str] = self.process_single_file(
                file_path=file_path,
                target_phones=target_phones,
                allowed_emails=allowed_emails,
                already_extracted=already_extracted,
                sms_processed=sms_processed,
                discovered_phones=discovered_phones,
                discovered_emails=discovered_emails,
            )
            if created:
                processed_count += 1

        self.finalize_reports(discovered_phones, discovered_emails)
        elapsed: float = time.time() - start_time
        print(
            f"\nExtraction terminée : {processed_count} fichier(s)"
            f" en {elapsed:.1f}s.",
            flush=True,
        )
