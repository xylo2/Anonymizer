# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

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


class ContactsPipelineRunner:
    """
    Ordonnance l'exécution séquentielle des étapes de traitement des contacts :
    1. Extraction et indexation depuis les fichiers CSV Google Contacts / Outlook.
    2. Anonymisation des noms de famille et résolution des homonymes.
    3. Dédoublonnage et écriture directe au format unifié Identifiant_Brut = Alias.
    4. Génération d'un fichier de suggestions pour les prénoms absents de prenoms.txt.
    """

    def __init__(self, config: ContactsConfig) -> None:
        """
        Initialise l'ordonnanceur avec la configuration partagée par les modules.

        :param config: Instance de ContactsConfig contenant tous les chemins et règles.
        """
        self.config: ContactsConfig = config

    def _run_extraction(self) -> Tuple[int, List[str]]:
        """
        Exécute la première étape : lecture des CSV détectés et écriture du fichier indexé.

        :return: Tuple (nombre_correspondances, liste_fichiers_csv).
        """
        print("=== [1/3] EXTRACTION DES CONTACTS CSV ===")
        csv_files: List[str] = self.config.get_csv_files()
        if not csv_files:
            raise FileNotFoundError(
                f"Aucun fichier CSV correspondant trouvé dans '{self.config.csv_directory}'."
            )

        reader: GoogleContactsReader = GoogleContactsReader(config=self.config)
        writer: ContactsOutputWriter = ContactsOutputWriter(config=self.config)

        all_entries: List[Tuple[str, str]] = []
        for csv_path in csv_files:
            entries: List[Tuple[str, str]] = reader.parse_file(file_path=csv_path)
            all_entries.extend(entries)

        writer.write_entries(entries=all_entries)
        print(
            f"[OK] {len(all_entries)} correspondance(s) extraite(s) depuis {len(csv_files)} fichier(s) "
            f"-> '{self.config.output_file}'.\n"
        )
        return len(all_entries), csv_files

    def _run_anonymization(self) -> int:
        """
        Exécute la deuxième étape : anonymisation du fichier indexé.

        :return: Nombre de lignes écrites dans le fichier anonymisé.
        """
        print("=== [2/3] ANONYMISATION DES CONTACTS ===")
        anonymizer: ContactsAnonymizer = ContactsAnonymizer(config=self.config)
        count: int = anonymizer.process()
        print(f"[OK] {count} ligne(s) anonymisée(s) -> '{self.config.anonymized_output_file}'.\n")
        return count
    def _run_deduplication_and_export(self) -> Tuple[int, int, int]:
        """
        Exécute la troisième étape : suppression des doublons et écriture directe
        au format unifié Identifiant_Brut = Alias dans contacts.txt.

        :return: Tuple (lignes_lues, lignes_écrites, clés_fusionnées).
        """
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
        """
        Détecte les prénoms présents dans les CSV mais absents de prenoms.txt.

        :param csv_files: Liste des fichiers CSV analysés.
        :return: Nombre de prénoms suggérés.
        """
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

    def run_all(self) -> None:
        """
        Enchaîne les étapes du pipeline de bout en bout et affiche la durée totale.
        """
        start_time: float = time.perf_counter()
        _, csv_files = self._run_extraction()
        self._run_anonymization()
        self._run_deduplication_and_export()
        self._run_first_name_suggestions(csv_files=csv_files)
        elapsed_str: str = SharedCoreUtils.format_duration(
            time.perf_counter() - start_time
        )
        print(f"Pipeline complet terminé avec succès en {elapsed_str}.")
