# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import time
from typing import List
from doc_anonymizer.audit_state_manager import AuditAndStateManager
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_rules_loader import ContactRulesLoader
from doc_anonymizer.text_utils import DocumentTextUtils


class DocumentAnonymizationRunner:
    """
    Orchestre l'anonymisation par lots au fil de l'eau et l'audit
    en temps réel des noms propres résiduels.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self.config: PipelineConfig = config
        self.rules: ContactRulesLoader = ContactRulesLoader(config)
        self.audit: AuditAndStateManager = AuditAndStateManager(
            config, self.rules
        )
        self._initialized: bool = False
        self.current_chunk: List[str] = []
        self.current_size: int = 0
        self.current_batch_files: List[str] = []
        self.processed_in_session: int = 0

    def initialize(self) -> bool:
        """Charge les règles de contacts et l'état de reprise."""
        if self._initialized:
            return True
        if not self.rules.load_all():
            return False
        self.audit.load()
        self._initialized = True
        return True

    def _anonymize_text(self, text: str) -> str:
        """Applique toutes les règles de masquage sur un texte."""
        token: str = CommunicationExtractor.MAIN_CHARACTER_TOKEN
        text = text.replace(token, self.config.main_character_name)
        for pattern, alias in self.rules.compiled_rules:
            text = pattern.sub(alias, text)
        if self.config.mask_ssn:
            text = DocumentTextUtils.REGEX_SSN.sub("[NUM_SECU_MASQUE]", text)
        if self.config.mask_financial_and_admin_ids:
            text = DocumentTextUtils.REGEX_IBAN.sub("[IBAN_MASQUE]", text)
            text = DocumentTextUtils.REGEX_BIC.sub("[BIC_MASQUE]", text)
            text = DocumentTextUtils.REGEX_FISCAL_ID.sub(
                "[NUM_FISCAL_MASQUE]", text
            )
            text = DocumentTextUtils.REGEX_FRANCE_TRAVAIL.sub(
                "[ID_FRANCE_TRAVAIL_MASQUE]", text
            )
            text = DocumentTextUtils.REGEX_CAF_ALLOCATAIRE.sub(
                "[NUM_ALLOCATAIRE_MASQUE]", text
            )
        text = DocumentTextUtils.REGEX_PHONE.sub(
            lambda m: self.audit.pseudonymize_id(m.group(0), "TEL"), text
        )
        text = DocumentTextUtils.REGEX_EMAIL.sub(
            lambda m: self.audit.pseudonymize_id(m.group(0), "EMAIL"), text
        )
        if self.config.mask_addresses:
            text = DocumentTextUtils.REGEX_STREET_ADDRESS.sub(
                "[ADRESSE_MASQUEE]", text
            )
            text = DocumentTextUtils.REGEX_POSTAL_CITY.sub(
                "[LIEU_MASQUE]", text
            )
        for loc_pattern in self.rules.location_rules:
            text = loc_pattern.sub("[LIEU_MASQUE]", text)
        return text

    def _anonymize_display_path(self, trans_path: str) -> str:
        """Masque les données sensibles dans le chemin affiché."""
        folder, fname = os.path.split(trans_path)
        masked: str = fname
        if self.config.mask_ssn:
            masked = DocumentTextUtils.REGEX_SSN.sub("NUM_SECU_MASQUE", masked)
        if self.config.mask_financial_and_admin_ids:
            masked = DocumentTextUtils.REGEX_IBAN.sub("IBAN_MASQUE", masked)
        masked = DocumentTextUtils.REGEX_PHONE.sub(
            lambda m: self.audit.pseudonymize_id(m.group(0), "TEL"), masked
        )
        masked = DocumentTextUtils.REGEX_EMAIL.sub(
            lambda m: self.audit.pseudonymize_id(m.group(0), "EMAIL"), masked
        )
        for pattern, alias in self.rules.compiled_rules:
            masked = pattern.sub(alias, masked)
        for loc_pattern in self.rules.location_rules:
            masked = loc_pattern.sub("LIEU_MASQUE", masked)
        return os.path.join(folder, masked)

    def flush_batch(self) -> None:
        """Écrit le lot courant, sauvegarde l'état et actualise l'audit."""
        if not self.current_chunk:
            self.audit.write_report()
            return
        batch_num: int = (
            (self.audit.file_idx - 1) // self.config.files_per_folder
        ) + 1
        sub_folder: str = f"lot_{batch_num:02d}"
        batch_dir: str = os.path.join(self.config.results_dir, sub_folder)
        os.makedirs(batch_dir, exist_ok=True)
        out_name: str = (
            f"{self.config.file_prefix}partie_{self.audit.file_idx:03d}.txt"
        )
        with open(
            os.path.join(batch_dir, out_name), "w", encoding="utf-8"
        ) as f_out:
            f_out.write("".join(self.current_chunk))

        self.audit.already_processed.update(self.current_batch_files)
        self.audit.file_idx += 1
        self.audit.written_batches += 1
        self.current_chunk = []
        self.current_size = 0
        self.current_batch_files = []

        self.audit.save()
        count: int = self.audit.write_report()
        rel: str = os.path.join(sub_folder, out_name)
        print(
            f"    [+] Lot généré : {rel} (Audit : {count} nom(s))",
            flush=True,
        )

    def anonymize_single_file(
        self, trans_path: str, force_reprocess: bool = False
    ) -> bool:
        """Anonymise un fichier transcription et l'ajoute au lot courant."""
        if not self._initialized and not self.initialize():
            return False
        norm_path: str = os.path.normpath(trans_path)
        if (
            not force_reprocess
            and norm_path in self.audit.already_processed
        ):
            return False
        if not os.path.exists(trans_path):
            return False

        with open(trans_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_content: str = f.read()

        display_path: str = self._anonymize_display_path(trans_path)
        sep: str = "#" * 72
        header: str = (
            f"{sep}\n# SOURCE TRANSCRIPTION : {display_path}\n{sep}\n"
        )
        anonymized: str = self._anonymize_text(header + raw_content)
        self.audit.scan_residual_names(anonymized, display_path)

        block_bytes: int = len(anonymized.encode("utf-8"))
        if self.current_chunk and (
            self.current_size + block_bytes > self.config.max_batch_bytes
        ):
            self.flush_batch()
        self.current_chunk.append(anonymized)
        self.current_size += block_bytes
        self.current_batch_files.append(norm_path)
        self.processed_in_session += 1
        return True

    def finalize(self, start_time: float) -> None:
        """Clôture le dernier lot et affiche le bilan final."""
        self.flush_batch()
        count: int = self.audit.write_report()
        elapsed: float = time.time() - start_time
        print(
            f"\n[100.0%] Terminé ({self.processed_in_session} fichier(s)"
            f" anonymisé(s) en {elapsed:.1f}s).",
            flush=True,
        )
        print(
            f" * Lots totaux : {self.audit.written_batches} dans"
            f" '{self.config.results_dir}/lot_XX/'",
            flush=True,
        )
        print(
            f" * Audit       : {count} nom(s) dans"
            f" '{self.config.audit_report_file}'",
            flush=True,
        )

    def run(self) -> None:
        """Exécute l'anonymisation autonome des transcriptions en attente."""
        start_time: float = time.time()
        print("=== ÉTAPE 2 : ANONYMISATION & AUDIT ===", flush=True)
        if not self.initialize():
            return
        trans_dir: str = self.config.transcriptions_dir
        if not os.path.exists(trans_dir):
            print(f"Erreur : '{trans_dir}' introuvable.", flush=True)
            return

        all_txts: List[str] = sorted(
            os.path.join(rp, fn)
            for rp, _, files in os.walk(trans_dir)
            for fn in files
            if fn.lower().endswith(".txt")
            and fn != "rapport_extraction.txt"
            and not fn.startswith(".")
        )
        pending: List[str] = [
            f
            for f in all_txts
            if os.path.normpath(f) not in self.audit.already_processed
        ]
        total: int = len(pending)
        for idx, trans_path in enumerate(pending, start=1):
            if idx % 10 == 0 or idx == total or idx == 1:
                pct: float = (idx / total) * 100
                print(
                    f"    ... [{pct:5.1f}% | {idx}/{total}] ...",
                    flush=True,
                )
            self.anonymize_single_file(trans_path)

        self.finalize(start_time)
