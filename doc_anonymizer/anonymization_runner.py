# Commandes pip à exécuter : Aucune dépendance externe requise

from concurrent.futures import ThreadPoolExecutor
import os
import time
from typing import Dict, List, Optional, Tuple
from doc_anonymizer.audit_state_manager import AuditAndStateManager
from doc_anonymizer.batch_writer import AnonymizedBatchWriter
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_rules_loader import ContactRulesLoader
from doc_anonymizer.deanon_vault import DeanonVaultManager
from doc_anonymizer.manual_contacts_importer import AuditManualContactsImporter
from doc_anonymizer.sensitive_masker import SensitiveTextMasker
from doc_anonymizer.source_mapping_manager import SourceMappingManager
from doc_anonymizer.text_utils import DocumentTextUtils


class DocumentAnonymizationRunner:
    """Orchestre le masquage des transcriptions, les lots, le coffre et l'audit."""

    SAFE_UPPER_WORDS = SensitiveTextMasker.SAFE_UPPER_WORDS
    VERBS_AND_PRONOUNS_FOLLOWING_FIRSTNAME = (
        SensitiveTextMasker.VERBS_AND_PRONOUNS_FOLLOWING_FIRSTNAME
    )
    CASE_SENSITIVE_LOCATIONS = SensitiveTextMasker.CASE_SENSITIVE_LOCATIONS

    def __init__(self, config: PipelineConfig, manual_only: bool = False) -> None:
        self.config: PipelineConfig = config
        self.manual_only: bool = manual_only
        self.rules: ContactRulesLoader = ContactRulesLoader(
            config, manual_only=manual_only
        )
        self.audit: AuditAndStateManager = AuditAndStateManager(config, self.rules)
        self.source_mapper: SourceMappingManager = SourceMappingManager(config)
        vault_path: str = os.path.join(
            os.path.dirname(config.audit_report_file), "deanon_vault.json"
        )
        self.vault: DeanonVaultManager = DeanonVaultManager(vault_path)
        self.masker: SensitiveTextMasker = SensitiveTextMasker(
            config, self.rules, manual_only=manual_only, vault=self.vault
        )
        self.batch_writer: AnonymizedBatchWriter = AnonymizedBatchWriter(
            config, self.audit, self.source_mapper
        )
        self.processed_in_session: int = 0
    @property
    def current_chunk(self) -> List[str]:
        return self.batch_writer.current_chunk

    @property
    def current_size(self) -> int:
        return self.batch_writer.current_size

    def set_skipped_zips(self, skipped_zips: List[str]) -> None:
        self.audit.stats["zip_ignores"] = list(skipped_zips)

    def initialize(self) -> bool:
        if not self.rules.load_all():
            return False
        self.audit.load()
        self.source_mapper.load()
        self.vault.load()
        self.masker.sync_dynamic_counters()
        self.masker.compile_patterns()
        print(
            f"[INIT ANONYMIZER] État chargé : {len(self.audit.already_processed)} "
            f"fichier(s) déjà traité(s), prochain index de lot = {self.audit.file_idx}.",
            flush=True,
        )
        return True

    def anonymize_text(
        self, text: str, stats_collector: Optional[Dict[str, int]] = None
    ) -> str:
        return self.masker.anonymize_text(text, stats_collector=stats_collector)

    def flush_batch(self) -> None:
        self.batch_writer.flush()
        self.vault.save()

    def _anonymize_file_worker(
        self, norm_path: str
    ) -> Optional[Tuple[str, str, str, str, Dict[str, int]]]:
        try:
            with open(norm_path, "r", encoding="utf-8", errors="ignore") as f_in:
                raw_text: str = f_in.read()
        except OSError as exc:
            print(f"[AVERTISSEMENT] Lecture impossible '{norm_path}' : {exc}", flush=True)
            return None
        file_stats: Dict[str, int] = {}
        anon_text: str = self.anonymize_text(raw_text, stats_collector=file_stats)
        anon_header_path: str = self.anonymize_text(norm_path)
        return norm_path, raw_text, anon_text, anon_header_path, file_stats
    def _commit_anonymized_result(
        self, item: Tuple[str, str, str, str, Dict[str, int]]
    ) -> None:
        norm_path, raw_text, anon_text, anon_header_path, file_stats = item
        self.source_mapper.register_entry(
            anonymized_path=anon_header_path,
            extracted_path=norm_path,
            raw_text=raw_text,
        )
        if not self.manual_only:
            self.audit.scan_residual_names(anon_text, norm_path)
        ds = self.audit.stats
        ds["documents_traites"] = int(ds.get("documents_traites", 0)) + 1
        for k in ("noms_masques", "coordonnees_masquees", "identifiants_masques", "lieux_dates_masques"):
            ds[k] = int(ds.get(k, 0)) + file_stats.get(k, 0)
        header: str = f"\n{'#' * 72}\n# SOURCE TRANSCRIPTION : {anon_header_path}\n{'#' * 72}\n"
        self.batch_writer.add_block(f"{header}{anon_text}\n", anon_header_path)
        self.audit.already_processed.add(norm_path)
        self.processed_in_session += 1

    def _process_single_file(self, norm_path: str) -> bool:
        res = self._anonymize_file_worker(norm_path)
        if res is None:
            return False
        self._commit_anonymized_result(res)
        return True

    def anonymize_single_file(
        self, transcription_path: str, force_reprocess: bool = False
    ) -> bool:
        norm_path: str = os.path.normpath(transcription_path)
        if not force_reprocess and norm_path in self.audit.already_processed:
            return False
        return self._process_single_file(norm_path)

    def finalize(self, start_time: float) -> None:
        self.flush_batch()
        count: int = self.audit.write_report()
        self.audit.save()
        self.vault.save()
        if not self.manual_only:
            imported = AuditManualContactsImporter(
                self.config, self.rules, min_occurrences=3
            ).import_high_confidence_from_audit()
            if imported > 0:
                print(
                    f"[AUTO-IMPORT] {imported} règle(s) haute confiance ajoutée(s) "
                    f"dans '{self.config.manual_contacts_file}'.",
                    flush=True,
                )
        elapsed: float = time.time() - start_time
        total_lots: int = max(0, self.audit.file_idx - 1)
        print(
            f"\n[100.0%] Terminé ({self.processed_in_session} fichier(s) anonymisé(s) en {elapsed:.1f}s).\n"
            f" * Lots totaux  : {total_lots} dans '{self.config.results_dir}/batch_XX/'\n"
            f" * Audit détail : {count} nom(s) dans '{self.config.audit_report_file}'\n"
            f" * Audit copier : {count} nom(s) dans '{self.config.audit_copy_file}'",
            flush=True,
        )

    def run(self) -> None:
        t0: float = time.time()
        if not self.initialize():
            return
        os.makedirs(self.config.results_dir, exist_ok=True)
        pending: List[str] = []
        for root_p, _, files in os.walk(self.config.transcriptions_dir):
            for fname in sorted(files):
                if (
                    fname in {"rapport_extraction.txt", "extraction_report.txt"}
                    or fname.startswith(".")
                    or not fname.lower().endswith(".txt")
                ):
                    continue
                norm_p: str = os.path.normpath(os.path.join(root_p, fname))
                if norm_p not in self.audit.already_processed:
                    pending.append(norm_p)
        if pending:
            workers: int = min(6, max(1, os.cpu_count() or 2), len(pending))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for res in pool.map(self._anonymize_file_worker, pending):
                    if res is not None:
                        self._commit_anonymized_result(res)
        self.finalize(t0)

    def run_on_existing_results(self) -> None:
        t0: float = time.time()
        if not self.initialize():
            return
        updated_files: int = 0
        for root_p, _, files in os.walk(self.config.results_dir):
            for fname in sorted(files):
                if not fname.endswith(".txt"):
                    continue
                full_p: str = os.path.join(root_p, fname)
                with open(full_p, "r", encoding="utf-8", errors="ignore") as f_in:
                    lines: List[str] = f_in.readlines()
                content: str = "".join(lines)
                new_lines: List[str] = [
                    ln if ln.startswith(("# SOURCE TRANSCRIPTION :", "########"))
                    else self.anonymize_text(ln)
                    for ln in lines
                ]
                new_content: str = "".join(new_lines)
                if new_content != content:
                    DocumentTextUtils.atomic_write_text(full_p, new_content)
                    updated_files += 1
        self.vault.save()
        print(f"[MANUAL-ONLY] {updated_files} lot(s) mis à jour en {time.time() - t0:.1f}s.", flush=True)
