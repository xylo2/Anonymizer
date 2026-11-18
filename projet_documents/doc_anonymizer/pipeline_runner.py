# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import time
from typing import List, Set
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.extraction_runner import DocumentExtractionRunner
from doc_anonymizer.power_manager import SystemSleepInhibitor
from doc_anonymizer.text_utils import DocumentTextUtils


class DocAnonymizerPipelineRunner:
    """
    Ordonnanceur au fil de l'eau pour doc_anonymizer : extrait chaque document
    et lance immédiatement son anonymisation sans attendre la fin du lot global,
    tout en empêchant la mise en veille sous Windows et Linux.
    """

    def __init__(
        self, config: PipelineConfig, prevent_sleep: bool = True
    ) -> None:
        """
        Initialise l'ordonnanceur avec la configuration et le maintien d'éveil.

        :param config: Instance de PipelineConfig.
        :param prevent_sleep: Empêche la mise en veille OS durant l'exécution.
        """
        self.config: PipelineConfig = config
        self.prevent_sleep: bool = prevent_sleep

    def run_all(self) -> None:
        """
        Exécute l'extraction et l'anonymisation au fil de l'eau avec
        sauvegarde propre en cas d'interruption clavier (Ctrl+C).
        """
        start_time: float = time.perf_counter()
        wall_start: float = time.time()

        with SystemSleepInhibitor(enabled=self.prevent_sleep):
            print("=== PIPELINE DOC_ANONYMIZER (AU FIL DE L'EAU) ===", flush=True)
            extractor: DocumentExtractionRunner = DocumentExtractionRunner(
                config=self.config
            )
            anonymizer: DocumentAnonymizationRunner = (
                DocumentAnonymizationRunner(config=self.config)
            )
            if not anonymizer.initialize():
                return

            target_phones, allowed_emails = (
                DocumentTextUtils.load_filter_contacts(
                    self.config.contacts_file
                )
            )
            if target_phones is None or allowed_emails is None:
                return

            os.makedirs(self.config.transcriptions_dir, exist_ok=True)
            already_extracted: Set[str] = extractor.load_tracking_set(
                self.config.extraction_tracking_file
            )
            sms_processed: Set[str] = extractor.load_tracking_set(
                self.config.sms_tracking_file
            )
            discovered_phones: Set[str] = set()
            discovered_emails: Set[str] = set()

            try:
                files: List[str] = extractor.collect_source_files()
                total_files: int = len(files)
                print(
                    f"Inventaire : {total_files} fichier(s) source(s) "
                    "détecté(s).",
                    flush=True,
                )

                for idx, file_path in enumerate(files, start=1):
                    print(
                        f"\n[{idx}/{total_files}] Extraction : {file_path}",
                        flush=True,
                    )
                    generated_txts: List[str] = extractor.process_single_file(
                        file_path=file_path,
                        target_phones=target_phones,
                        allowed_emails=allowed_emails,
                        already_extracted=already_extracted,
                        sms_processed=sms_processed,
                        discovered_phones=discovered_phones,
                        discovered_emails=discovered_emails,
                    )
                    for trans_txt in generated_txts:
                        print(
                            f"    -> Anonymisation immédiate : {trans_txt}",
                            flush=True,
                        )
                        anonymizer.anonymize_single_file(
                            trans_txt, force_reprocess=True
                        )

                for root_path, _, existing_files in os.walk(
                    self.config.transcriptions_dir
                ):
                    for fname in sorted(existing_files):
                        if (
                            fname == "rapport_extraction.txt"
                            or fname.startswith(".")
                            or not fname.lower().endswith(".txt")
                        ):
                            continue
                        full_trans: str = os.path.join(root_path, fname)
                        anonymizer.anonymize_single_file(full_trans)

                extractor.finalize_reports(discovered_phones, discovered_emails)
                anonymizer.finalize(wall_start)

            except KeyboardInterrupt:
                print(
                    "\n[INTERROMPU] Ctrl+C détecté : sauvegarde des lots "
                    "déjà anonymisés en cours...",
                    flush=True,
                )
                extractor.finalize_reports(discovered_phones, discovered_emails)
                anonymizer.flush_batch()
                raise

        elapsed: float = time.perf_counter() - start_time
        print(
            f"\nPipeline au fil de l'eau terminé en {elapsed:.1f}s.",
            flush=True,
        )
