import os
import time
from typing import List, Tuple
from common.core_utils import SharedCoreUtils
from google_contacts_parser.anonymizer import ContactsAnonymizer
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.csv_reader import GoogleContactsReader
from google_contacts_parser.deduplicator import ContactsDeduplicator
from google_contacts_parser.first_name_suggester import MissingFirstNamesSuggester
from google_contacts_parser.output_writer import ContactsOutputWriter
from google_contacts_parser.vcard_reader import VCardContactsReader


class ContactsPipelineRunner:
    """
    Ordonnance l'exécution séquentielle des étapes de traitement des contacts :
    1. Extraction et indexation depuis les fichiers CSV et vCard (.vcf).
    2. Anonymisation des noms de famille et résolution des homonymes.
    3. Dédoublonnage et écriture directe au format unifié Identifiant_Brut = Alias.
    4. Génération d'un fichier de suggestions pour les prénoms absents de prenoms.txt.
    """

    def __init__(self, config: ContactsConfig) -> None:
        self.config: ContactsConfig = config

    def _run_extraction(self) -> Tuple[int, List[str]]:
        print("=== [1/3] EXTRACTION DES CONTACTS (CSV & vCard .vcf) ===")
        contact_files: List[str] = self.config.get_csv_files()
        if not contact_files:
            print(
                f"[INFO] Aucun carnet CSV ou vCard (.vcf) dans "
                f"'{self.config.csv_directory}' : étape CSV ignorée.\n"
            )
            return 0, []

        csv_reader: GoogleContactsReader = GoogleContactsReader(config=self.config)
        vcf_reader: VCardContactsReader = VCardContactsReader(config=self.config)
        writer: ContactsOutputWriter = ContactsOutputWriter(config=self.config)

        all_entries: List[Tuple[str, str]] = []
        for file_path in contact_files:
            if file_path.lower().endswith(".vcf"):
                entries: List[Tuple[str, str]] = vcf_reader.parse_file(file_path=file_path)
            else:
                entries = csv_reader.parse_file(file_path=file_path)
            all_entries.extend(entries)

        writer.write_entries(entries=all_entries)
        print(
            f"[OK] {len(all_entries)} correspondance(s) extraite(s) depuis {len(contact_files)} fichier(s) "
            f"-> '{self.config.output_file}'.\n"
        )
        return len(all_entries), contact_files
    def _run_anonymization(self) -> int:
        print("=== [2/3] ANONYMISATION DES CONTACTS ===")
        anonymizer: ContactsAnonymizer = ContactsAnonymizer(config=self.config)
        count: int = anonymizer.process()
        print(f"[OK] {count} ligne(s) anonymisée(s) -> '{self.config.anonymized_output_file}'.\n")
        return count

    def _run_deduplication_and_export(self) -> Tuple[int, int, int]:
        print("=== [3/3] DÉDOUBLONNAGE ET EXPORT UNIFIÉ ===")
        deduplicator: ContactsDeduplicator = ContactsDeduplicator(config=self.config)
        read_count, written_count, merged_count = deduplicator.process()
        removed_count: int = read_count - written_count

        if os.path.exists(self.config.deduplicated_output_file):
            with open(self.config.deduplicated_output_file, "r", encoding="utf-8") as f_in:
                lines: List[str] = sorted(
                    (ln.strip() for ln in f_in if ln.strip()),
                    key=lambda s: s.lower(),
                )
            SharedCoreUtils.atomic_write_text(
                target_path=self.config.inverted_output_file,
                content="\n".join(lines) + ("\n" if lines else ""),
                encoding="utf-8",
            )

        print(
            f"[OK] {read_count} ligne(s) -> {written_count} ligne(s) unifiée(s) "
            f"({removed_count} doublon(s) réduit(s), {merged_count} clé(s) fusionnée(s)) "
            f"-> '{self.config.inverted_output_file}'.\n"
        )
        return read_count, written_count, merged_count

    def _run_first_name_suggestions(self, csv_files: List[str]) -> int:
        if not csv_files:
            return 0
        suggester: MissingFirstNamesSuggester = MissingFirstNamesSuggester(
            config=self.config
        )
        count: int = suggester.generate_suggestions_file(csv_files=csv_files)
        if count > 0:
            print(
                f"[SUGGESTIONS PRÉNOMS] {count} prénom(s) absent(s) de "
                f"'{self.config.first_names_file}' enregistré(s) dans "
                f"'{self.config.suggested_first_names_file}'.\n"
            )
        return count

    def run_all(self) -> int:
        start_time: float = time.perf_counter()
        _, contact_files = self._run_extraction()
        if contact_files:
            self._run_anonymization()
            self._run_deduplication_and_export()
            self._run_first_name_suggestions(csv_files=contact_files)
        elapsed_str: str = SharedCoreUtils.format_duration(
            time.perf_counter() - start_time
        )
        print(f"Pipeline complet terminé avec succès en {elapsed_str}.")
        return 0
