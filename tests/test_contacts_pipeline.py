# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import os
import sys
import tempfile
import unittest
from typing import List

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common.core_utils import SharedCoreUtils
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.pipeline_runner import ContactsPipelineRunner
from google_contacts_parser.text_utils import ContactTextUtils


class TestContactsPipeline(unittest.TestCase):
    """
    Valide le socle commun, les règles de détection d'entités,
    la résolution d'homonymes, l'export des noms de famille et le pipeline complet.
    """

    def test_shared_normalization_and_duration(self) -> None:
        """
        Vérifie la normalisation des téléphones français, des alias e-mails
        et le formatage humain des durées en secondes, minutes et heures.
        """
        self.assertEqual(SharedCoreUtils.normalize_identifier("+33 6 12 34 56 78"), "0612345678")
        self.assertEqual(SharedCoreUtils.normalize_identifier("0033612345678"), "0612345678")
        self.assertEqual(
            SharedCoreUtils.normalize_email_alias("Jean.Dupont+impots@Gmail.com"),
            "jean.dupont@gmail.com",
        )
        self.assertEqual(SharedCoreUtils.format_duration(42.34), "42.3s")
        self.assertEqual(SharedCoreUtils.format_duration(169.1), "2 min 49s")
        self.assertEqual(SharedCoreUtils.format_duration(3912.0), "1 h 05 min 12s")

    def test_entity_and_location_rules(self) -> None:
        """
        Vérifie la distinction personne/société et l'abréviation des lieux.
        """
        first_names = {"jean", "marie", "sophie"}
        prefixes = {"cabinet", "mairie"}
        keywords = {"communication", "immobilier"}

        self.assertTrue(
            ContactTextUtils.is_non_person_entity(
                "Cabinet AnonVault", "0102030405", prefixes, keywords, first_names
            )
        )
        self.assertTrue(
            ContactTextUtils.is_non_person_entity(
                "Société Générale", "contact@sg.fr", prefixes, keywords, first_names
            )
        )
        self.assertFalse(
            ContactTextUtils.is_non_person_entity(
                "Jean Dupont", "0601020304", prefixes, keywords, first_names
            )
        )
        self.assertEqual(
            ContactTextUtils.abbreviate_locations_in_text("Agence Caen-Sud", {"caen"}),
            "Agence C.-Sud",
        )
    def test_full_contacts_pipeline_homonyms_and_dedup(self) -> None:
        """
        Exécute le pipeline complet sur un CSV contenant des homonymes,
        une société, un nom à collision lexicale et l'export contact_surnames.txt
        au format unifié Identifiant_Brut = Alias.
        """
        with tempfile.TemporaryDirectory(prefix="test_contacts_") as tmp_dir:
            export_dir: str = os.path.join(tmp_dir, "export_contacts")
            os.makedirs(export_dir, exist_ok=True)

            prenoms_path: str = os.path.join(tmp_dir, "prenoms.txt")
            with open(prenoms_path, "w", encoding="utf-8") as f_fn:
                f_fn.write("jean\nmarie\n")

            collisions_path: str = os.path.join(tmp_dir, "collisions_noms.txt")
            with open(collisions_path, "w", encoding="utf-8") as f_col:
                f_col.write("grand\nblanc\n")

            csv_path: str = os.path.join(export_dir, "contacts_test.csv")
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f_csv:
                f_csv.write(
                    "First Name,Last Name,E-mail 1 - Value,Phone 1 - Value\n"
                    "Jean,Dupont,jean.dupont@exemple.fr,06 01 02 03 04\n"
                    "Jean,Durand,jean.durand@exemple.fr,06 05 06 07 08\n"
                    "Jean,Dumont,jean.dumont@exemple.fr,06 09 10 11 12\n"
                    "Jean,Grand,jean.grand@exemple.fr,\n"
                    "Cabinet Alpha,,contact@alpha-conseil.fr,\n"
                    "Gaspard,Moreau,gaspard.moreau@exemple.fr,\n"
                )

            cfg_path: str = os.path.join(tmp_dir, "config.ini")
            with open(cfg_path, "w", encoding="utf-8") as f_cfg:
                f_cfg.write(
                    "[files]\n"
                    "csv_directory = export_contacts\n"
                    "csv_prefixes = contacts\n"
                    "first_names_file = prenoms.txt\n"
                    "suggested_first_names_file = prenoms_suggeres.txt\n"
                    "surname_collisions_file = collisions_noms.txt\n"
                    "surnames_output_file = noms_famille_contacts.txt\n"
                    "output_file = contacts_indexes.txt\n"
                    "anonymized_output_file = contacts_anonymises.txt\n"
                    "deduplicated_output_file = contacts_dedoublonnes.txt\n"
                    "inverted_output_file = contacts.txt\n"
                    "[formatting]\n"
                    "clean_phone_spaces = true\n"
                    "[anonymizer]\n"
                    "ignored_domains = gmail, exemple\n"
                    "entity_prefixes = cabinet\n"
                )

            config: ContactsConfig = ContactsConfig(config_path=cfg_path)
            ContactsPipelineRunner(config=config).run_all()

            self.assertTrue(os.path.exists(config.inverted_output_file))
            with open(config.inverted_output_file, "r", encoding="utf-8") as f_out:
                content: str = f_out.read()

            self.assertIn("0601020304=Jean D.", content)
            self.assertIn("jean.durand@exemple.fr=Jean Du.", content)
            self.assertIn("jean.dumont@exemple.fr=Jean Du-2", content)
            self.assertIn("contact@alpha-conseil.fr=Cabinet Alpha (Alpha Conseil)", content)

            self.assertTrue(os.path.exists(config.surnames_output_file))
            with open(config.surnames_output_file, "r", encoding="utf-8") as f_sur:
                sur_content: str = f_sur.read()
            self.assertIn("Dupont = D.", sur_content)
            self.assertIn("Durand = Du.", sur_content)
            self.assertIn("Dumont = Du-2", sur_content)
            self.assertNotIn("Grand = G.", sur_content)
            self.assertNotIn("Moreau = M.", sur_content)


if __name__ == "__main__":
    unittest.main()
