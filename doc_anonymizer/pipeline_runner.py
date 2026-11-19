# Commandes pip à exécuter : Aucune dépendance externe requise

from concurrent.futures import ThreadPoolExecutor
import os
import shutil
import threading
import time
from typing import List, Set
from common.core_utils import SharedCoreUtils
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.discovered_contacts_builder import (
    DiscoveredEmailContactsBuilder,
)
from doc_anonymizer.extraction_runner import DocumentExtractionRunner
from doc_anonymizer.power_manager import SystemSleepInhibitor


class DocAnonymizerPipelineRunner:
    """
    Ordonnanceur parallèle au fil de l'eau pour doc_anonymizer : extrait les
    documents sur plusieurs threads et anonymise chaque transcription dès qu'elle
    est prête sur le thread principal, avec arrêt immédiat sur Ctrl+C.
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
        self.stop_event: threading.Event = threading.Event()

    def _anonymize_pending_transcriptions(
        self, anonymizer: DocumentAnonymizationRunner
    ) -> int:
        """
        Parcourt le dossier transcriptions et anonymise immédiatement tout
        fichier déjà extrait mais absent de l'état d'anonymisation.

        :param anonymizer: Instance de DocumentAnonymizationRunner initialisée.
        :return: Nombre de transcriptions en attente anonymisées.
        """
        trans_dir: str = self.config.transcriptions_dir
        if not os.path.isdir(trans_dir):
            return 0

        pending_files: List[str] = []
        for root_path, _, existing_files in os.walk(trans_dir):
            for file_name in sorted(existing_files):
                if (
                    file_name == "rapport_extraction.txt"
                    or file_name.startswith(".")
                    or not file_name.lower().endswith(".txt")
                ):
                    continue
                full_trans: str = os.path.join(root_path, file_name)
                norm_trans: str = os.path.normpath(full_trans)
                if norm_trans not in anonymizer.audit.already_processed:
                    pending_files.append(full_trans)

        if not pending_files:
            return 0

        print(
            f"Rattrapage : {len(pending_files)} transcription(s) "
            "en attente d'anonymisation...",
            flush=True,
        )
        processed_count: int = 0
        for idx, trans_path in enumerate(pending_files, start=1):
            if self.stop_event.is_set():
                break
            if idx == 1 or idx % 25 == 0 or idx == len(pending_files):
                print(
                    f"    [Anonymisation {idx}/{len(pending_files)}] "
                    f"{os.path.basename(trans_path)}",
                    flush=True,
                )
            if anonymizer.anonymize_single_file(trans_path):
                processed_count += 1

        return processed_count

    def _reset_results_for_second_pass(self) -> None:
        """
        Nettoie intégralement les anciens lots et l'état JSON avant de relancer
        une passe complète avec les règles fraîchement découvertes.
        """
        res_dir: str = self.config.results_dir
        if os.path.isdir(res_dir):
            for entry in os.listdir(res_dir):
                full_p: str = os.path.join(res_dir, entry)
                if os.path.isdir(full_p) and entry.startswith("lot_"):
                    shutil.rmtree(full_p, ignore_errors=True)
                elif os.path.isfile(full_p) and entry.endswith(".txt"):
                    try:
                        os.remove(full_p)
                    except OSError:
                        pass
        if os.path.exists(self.config.resume_state_file):
            os.remove(self.config.resume_state_file)

    def _run_second_pass_with_discovered_emails(self) -> bool:
        """
        Génère contacts_emails_decouverts.txt depuis tous_emails_trouves.txt
        et exécute une seconde passe d'anonymisation si des règles ont été ajoutées.

        :return: True si une seconde passe a été exécutée, False sinon.
        """
        builder: DiscoveredEmailContactsBuilder = (
            DiscoveredEmailContactsBuilder(self.config)
        )
        added_count, total_count = builder.build_or_update()
        if added_count <= 0:
            return False

        pass_start: float = time.time()
        print(
            f"\n=== SECONDE PASSE D'ANONYMISATION ===\n"
            f"[CONTACTS DÉCOUVERTS] {added_count} nouvelle(s) règle(s) "
            f"ajoutée(s) dans '{self.config.discovered_contacts_file}' "
            f"(total : {total_count}).\n"
            "Relance complète de l'anonymisation sur les transcriptions...",
            flush=True,
        )
        self._reset_results_for_second_pass()
        second_anonymizer: DocumentAnonymizationRunner = (
            DocumentAnonymizationRunner(config=self.config)
        )
        if not second_anonymizer.initialize():
            return False

        self._anonymize_pending_transcriptions(second_anonymizer)
        second_anonymizer.finalize(pass_start)
        return True
    def run_all(self) -> None:
        """
        Exécute le rattrapage des transcriptions, l'extraction parallèle et
        l'anonymisation au fil de l'eau, avec arrêt immédiat sans blocage sur Ctrl+C.
        """
        start_time: float = time.perf_counter()
        wall_start: float = time.time()
        self.stop_event.clear()

        with SystemSleepInhibitor(enabled=self.prevent_sleep):
            print("=== PIPELINE DOC_ANONYMIZER (PARALLÈLE AU FIL DE L'EAU) ===", flush=True)
            print(f"[CONFIG] Fichier INI       : {self.config.config_path}", flush=True)
            print(f"[CONFIG] Contacts auto     : {self.config.contacts_file}", flush=True)
            print(f"[CONFIG] Contacts découverts : {self.config.discovered_contacts_file}", flush=True)
            print(f"[CONFIG] Contacts manuels  : {self.config.manual_contacts_file}", flush=True)
            print(f"[CONFIG] Sources           : {self.config.sources_dir}", flush=True)
            print(f"[CONFIG] Transcriptions    : {self.config.transcriptions_dir}", flush=True)
            print(f"[CONFIG] Résultats         : {self.config.results_dir}", flush=True)

            extractor: DocumentExtractionRunner = DocumentExtractionRunner(
                config=self.config, stop_event=self.stop_event
            )
            anonymizer: DocumentAnonymizationRunner = DocumentAnonymizationRunner(config=self.config)
            if not anonymizer.initialize():
                print("[ERREUR] Échec de l'initialisation de l'anonymiseur. Arrêt.", flush=True)
                return

            target_phones, allowed_emails = extractor.load_all_filter_contacts()
            if target_phones is None or allowed_emails is None:
                print("[ERREUR] Impossible de charger les filtres de contacts. Arrêt.", flush=True)
                return

            os.makedirs(self.config.transcriptions_dir, exist_ok=True)
            os.makedirs(self.config.results_dir, exist_ok=True)

            already_extracted: Set[str] = extractor.load_tracking_set(self.config.extraction_tracking_file)
            sms_processed: Set[str] = extractor.load_tracking_set(self.config.sms_tracking_file)
            discovered_phones: Set[str] = set()
            discovered_emails: Set[str] = set()
            workers: int = extractor.get_worker_count()
            executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=workers)

            try:
                self._anonymize_pending_transcriptions(anonymizer)
                files: List[str] = extractor.collect_source_files()
                total_files: int = len(files)
                print(f"Inventaire : {total_files} fichier(s) source(s) ({workers} thread(s)).", flush=True)

                futures = {
                    executor.submit(
                        extractor.process_single_file,
                        fp, target_phones, allowed_emails, already_extracted,
                        sms_processed, discovered_phones, discovered_emails
                    ): fp
                    for fp in files
                }
                pending_futures = set(futures.keys())
                while pending_futures:
                    done_batch = []
                    for fut in list(pending_futures):
                        if fut.done():
                            done_batch.append(fut)
                    if not done_batch:
                        time.sleep(0.1)
                        continue
                    for future in done_batch:
                        pending_futures.remove(future)
                        fp: str = futures[future]
                        generated_txts: List[str] = future.result()
                        idx: int = total_files - len(pending_futures)
                        print(f"[{idx}/{total_files}] Extrait : {os.path.basename(fp)}", flush=True)
                        for trans_txt in generated_txts:
                            ok: bool = anonymizer.anonymize_single_file(trans_txt, force_reprocess=True)
                            print(
                                f"    -> Anonymisation : {'OK' if ok else 'IGNORÉ'} "
                                f"(tampon : {len(anonymizer.current_chunk)} fichier(s), {anonymizer.current_size} octets)",
                                flush=True,
                            )

                executor.shutdown(wait=True)
                self._anonymize_pending_transcriptions(anonymizer)
                extractor.finalize_reports(discovered_phones, discovered_emails)
                anonymizer.finalize(wall_start)
                self._run_second_pass_with_discovered_emails()

            except KeyboardInterrupt:
                self.stop_event.set()
                executor.shutdown(wait=False, cancel_futures=True)
                print("\n[INTERROMPU] Ctrl+C détecté : sauvegarde des lots déjà anonymisés...", flush=True)
                extractor.finalize_reports(discovered_phones, discovered_emails)
                anonymizer.flush_batch()
                os._exit(130)

        elapsed_str: str = SharedCoreUtils.format_duration(time.perf_counter() - start_time)
        print(f"\nPipeline parallèle terminé en {elapsed_str}.", flush=True)
