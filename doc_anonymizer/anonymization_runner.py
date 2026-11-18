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

    def __init__(
        self, config: PipelineConfig, manual_only: bool = False
    ) -> None:
        """
        Initialise le moteur d'anonymisation et le gestionnaire d'état.

        :param config: Instance de PipelineConfig.
        :param manual_only: Si True, utilise uniquement contacts_manuels.txt.
        """
        self.config: PipelineConfig = config
        self.manual_only: bool = manual_only
        self.rules: ContactRulesLoader = ContactRulesLoader(
            config, manual_only=manual_only
        )
        self.audit: AuditAndStateManager = AuditAndStateManager(
            config, self.rules
        )
        self._initialized: bool = False
        self.current_chunk: List[str] = []
        self.current_size: int = 0
        self.current_batch_files: List[str] = []
        self.processed_in_session: int = 0

    def initialize(self) -> bool:
        """
        Charge les règles de contacts et l'état de reprise.

        :return: True si l'initialisation a réussi, False sinon.
        """
        if self._initialized:
            return True
        if not self.rules.load_all():
            print(
                "[ERREUR ANONYMIZER] Chargement des règles impossible.",
                flush=True,
            )
            return False
        self.audit.load()
        print(
            f"[INIT ANONYMIZER] État chargé : "
            f"{len(self.audit.already_processed)} fichier(s) déjà traité(s), "
            f"prochain index de lot = {self.audit.file_idx}.",
            flush=True,
        )
        self._initialized = True
        return True

    def _anonymize_text(self, text: str) -> str:
        """
        Applique toutes les règles de masquage en O(N) via les arbres préfixes
        compilés (identifiants, adresses, noms, variantes collées, lieux).

        :param text: Texte brut à anonymiser.
        :return: Texte anonymisé.
        """
        token: str = CommunicationExtractor.MAIN_CHARACTER_TOKEN
        text = text.replace(token, self.config.main_character_name)

        if self.config.mask_ssn:
            text = DocumentTextUtils.REGEX_SSN.sub("[NUM_SECU_MASQUE]", text)
        if self.config.mask_financial_and_admin_ids:
            text = DocumentTextUtils.REGEX_IBAN.sub("[IBAN_MASQUE]", text)
            text = DocumentTextUtils.REGEX_BIC.sub("[BIC_MASQUE]", text)
            text = DocumentTextUtils.REGEX_FISCAL_ID.sub("[NUM_FISCAL_MASQUE]", text)
            text = DocumentTextUtils.REGEX_FRANCE_TRAVAIL.sub("[ID_FRANCE_TRAVAIL_MASQUE]", text)
            text = DocumentTextUtils.REGEX_CAF_ALLOCATAIRE.sub("[NUM_ALLOCATAIRE_MASQUE]", text)
        text = DocumentTextUtils.REGEX_EMAIL.sub(
            lambda m: self.audit.pseudonymize_id(m.group(0), "EMAIL"), text
        )
        text = DocumentTextUtils.REGEX_PHONE.sub(
            lambda m: self.audit.pseudonymize_id(m.group(0), "TEL"), text
        )
        if self.config.mask_urls:
            text = DocumentTextUtils.REGEX_URL.sub("[URL_MASQUEE]", text)

        if self.config.mask_addresses:
            text = DocumentTextUtils.REGEX_POSTAL_CITY.sub("[LIEU_MASQUE]", text)
            text = DocumentTextUtils.REGEX_STREET_ADDRESS.sub("[ADRESSE_MASQUEE]", text)

        if self.rules.combined_keyword_pattern is not None:
            text = self.rules.combined_keyword_pattern.sub(
                lambda m: self.rules.lookup_keyword_alias(m.group(0)), text
            )

        if self.rules.combined_glued_pattern is not None:
            text = self.rules.combined_glued_pattern.sub(
                lambda m: self.rules.lookup_glued_alias(m.group(0)), text
            )

        if self.rules.combined_location_pattern is not None:
            text = self.rules.combined_location_pattern.sub("[LIEU_MASQUE]", text)
        return text

    def _anonymize_display_path(self, trans_path: str) -> str:
        """
        Masque les données sensibles dans le chemin affiché.

        :param trans_path: Chemin vers le fichier transcription.
        :return: Chemin nettoyé de toute donnée personnelle.
        """
        folder, file_name = os.path.split(trans_path)
        masked: str = file_name
        if self.config.mask_ssn:
            masked = DocumentTextUtils.REGEX_SSN.sub("NUM_SECU_MASQUE", masked)
        if self.config.mask_financial_and_admin_ids:
            masked = DocumentTextUtils.REGEX_IBAN.sub("IBAN_MASQUE", masked)
        masked = DocumentTextUtils.REGEX_EMAIL.sub(
            lambda m: self.audit.pseudonymize_id(m.group(0), "EMAIL"), masked
        )
        masked = DocumentTextUtils.REGEX_PHONE.sub(
            lambda m: self.audit.pseudonymize_id(m.group(0), "TEL"), masked
        )
        if self.config.mask_urls:
            masked = DocumentTextUtils.REGEX_URL.sub("URL_MASQUEE", masked)
        if self.rules.combined_keyword_pattern is not None:
            masked = self.rules.combined_keyword_pattern.sub(
                lambda m: self.rules.lookup_keyword_alias(m.group(0)), masked
            )
        if self.rules.combined_glued_pattern is not None:
            masked = self.rules.combined_glued_pattern.sub(
                lambda m: self.rules.lookup_glued_alias(m.group(0)), masked
            )
        if self.rules.combined_location_pattern is not None:
            masked = self.rules.combined_location_pattern.sub("LIEU_MASQUE", masked)
        return os.path.join(folder, masked)

    def flush_batch(self) -> None:
        """
        Écrit le lot courant de façon atomique, sauvegarde l'état et actualise l'audit.
        """
        if not self.current_chunk:
            self.audit.save()
            self.audit.write_report()
            return
        batch_num: int = ((self.audit.file_idx - 1) // self.config.files_per_folder) + 1
        batch_dir: str = os.path.join(self.config.results_dir, f"lot_{batch_num:02d}")
        os.makedirs(batch_dir, exist_ok=True)
        out_name: str = f"{self.config.file_prefix}partie_{self.audit.file_idx:03d}.txt"
        full_out_path: str = os.path.join(batch_dir, out_name)
        DocumentTextUtils.atomic_write_text(full_out_path, "".join(self.current_chunk))

        self.audit.already_processed.update(self.current_batch_files)
        self.audit.file_idx += 1
        self.audit.written_batches += 1
        self.current_chunk = []
        self.current_size = 0
        self.current_batch_files = []

        self.audit.save()
        count: int = self.audit.write_report()
        print(f"    [+] LOT ÉCRIT : '{full_out_path}' (Audit : {count} nom(s))", flush=True)
    def anonymize_single_file(self, trans_path: str, force_reprocess: bool = False) -> bool:
        """
        Anonymise un fichier transcription et l'ajoute au lot courant.

        :param trans_path: Chemin vers le fichier transcription.
        :param force_reprocess: Force le retraitement même si déjà indexé.
        :return: True si le fichier a été anonymisé, False sinon.
        """
        if not self._initialized and not self.initialize():
            return False
        norm_path: str = os.path.normpath(trans_path)
        if not force_reprocess and norm_path in self.audit.already_processed:
            return False
        if not os.path.exists(trans_path):
            return False

        with open(trans_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_content: str = f.read()
        if not raw_content.strip():
            return False

        display_path: str = self._anonymize_display_path(trans_path)
        sep: str = "#" * 72
        header: str = f"{sep}\n# SOURCE TRANSCRIPTION : {display_path}\n{sep}\n"
        anonymized: str = self._anonymize_text(header + raw_content)
        self.audit.scan_residual_names(anonymized, display_path)

        block_bytes: int = len(anonymized.encode("utf-8"))
        max_files_per_batch: int = getattr(self.config, "max_batch_files", 50)
        if self.current_chunk and (
            self.current_size + block_bytes > self.config.max_batch_bytes
            or len(self.current_chunk) >= max_files_per_batch
        ):
            self.flush_batch()

        self.current_chunk.append(anonymized)
        self.current_size += block_bytes
        self.current_batch_files.append(norm_path)
        self.processed_in_session += 1
        return True

    def finalize(self, start_time: float) -> None:
        """
        Clôture le dernier lot et affiche le bilan final avec les deux audits.

        :param start_time: Horodatage de début de session.
        """
        self.flush_batch()
        count: int = self.audit.write_report()
        elapsed: float = time.time() - start_time
        print(f"\n[100.0%] Terminé ({self.processed_in_session} fichier(s) anonymisé(s) en {elapsed:.1f}s).", flush=True)
        print(f" * Lots totaux  : {self.audit.written_batches} dans '{self.config.results_dir}/lot_XX/'", flush=True)
        print(f" * Audit détail : {count} nom(s) dans '{self.config.audit_report_file}'", flush=True)
        print(f" * Audit copier : {count} nom(s) dans '{self.config.audit_copy_file}'", flush=True)

    def run_on_existing_results(self) -> None:
        """
        Ré-anonymise sur place les lots déjà présents en utilisant contacts_manuels.txt.
        """
        start_time: float = time.time()
        print("=== PASSE SUR PLACE : CONTACTS MANUELS SUR RÉSULTATS ===", flush=True)
        if not self.initialize():
            return
        res_dir: str = self.config.results_dir
        if not os.path.isdir(res_dir):
            print(f"Erreur : '{res_dir}' introuvable.", flush=True)
            return

        lot_files: List[str] = sorted(
            os.path.join(rp, fn)
            for rp, _, files in os.walk(res_dir)
            for fn in files
            if fn.lower().endswith(".txt") and not fn.startswith(".")
        )
        if not lot_files:
            print(f"Aucun fichier de lot trouvé dans '{res_dir}'.", flush=True)
            return

        self.audit.pair_counter.clear()
        self.audit.files_by_name.clear()
        self.audit.canonical_labels.clear()

        total: int = len(lot_files)
        for idx, lot_path in enumerate(lot_files, start=1):
            with open(lot_path, "r", encoding="utf-8", errors="ignore") as f_in:
                updated_content: str = self._anonymize_text(f_in.read())
            DocumentTextUtils.atomic_write_text(lot_path, updated_content)
            self.audit.scan_residual_names(updated_content, os.path.basename(lot_path))
            if idx % 10 == 0 or idx == total or idx == 1:
                print(f"    ... [{idx}/{total}] {os.path.basename(lot_path)}", flush=True)

        self.audit.save()
        count: int = self.audit.write_report()
        print(f"\n[100.0%] Passe manuelle terminée sur {total} lot(s) en {time.time() - start_time:.1f}s.", flush=True)
        print(f" * Audit détail : {count} nom(s) dans '{self.config.audit_report_file}'", flush=True)
        print(f" * Audit copier : {count} nom(s) dans '{self.config.audit_copy_file}'", flush=True)

    def run(self) -> None:
        """
        Exécute l'anonymisation autonome des transcriptions en attente.
        """
        if self.manual_only:
            self.run_on_existing_results()
            return
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
            if fn.lower().endswith(".txt") and fn != "rapport_extraction.txt" and not fn.startswith(".")
        )
        pending: List[str] = [f for f in all_txts if os.path.normpath(f) not in self.audit.already_processed]
        total: int = len(pending)
        for idx, trans_path in enumerate(pending, start=1):
            if idx % 10 == 0 or idx == total or idx == 1:
                print(f"    ... [{(idx / total) * 100:5.1f}% | {idx}/{total}] ...", flush=True)
            self.anonymize_single_file(trans_path)
        self.finalize(start_time)
