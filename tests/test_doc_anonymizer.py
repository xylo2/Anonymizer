# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_rules_loader import ContactRulesLoader
from doc_anonymizer.discovered_contacts_builder import DiscoveredEmailContactsBuilder
from doc_anonymizer.text_utils import DocumentTextUtils


class TestDocAnonymizer(unittest.TestCase):
    """
    Valide les expressions régulières de masquage (NIR, IBAN, adresses, codes d'accès),
    la tolérance OCR, les titres avec prénom, les collisions externes et l'audit.
    """

    def test_sensitive_regex_patterns(self) -> None:
        """
        Vérifie la détection des numéros NIR, IBAN, adresses sans numéro,
        digicodes, références administratives et SMS.
        """
        self.assertIsNotNone(DocumentTextUtils.REGEX_SSN.search("NIR : 1 90 01 75 001 002 03"))
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_IBAN.search("FR76 3000 1007 9412 3456 7890 185")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_STREET_ADDRESS.search("Habite au 14 bis rue de la Paix")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_STREET_ADDRESS.search("Rendez-vous Rue de la Cabottière")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_ACCESS_CODES.search("Le digicode : 1985B et mot de passe : secret123")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_ADMIN_REFS.search("Dossier sinistre n° 250522760 et affaire RG D 15/613")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_POSTAL_CITY.search("75001 Paris")
        )

        group_addrs = DocumentTextUtils.split_sms_addresses("+33600000001~0600000002+33600000003")
        self.assertEqual(group_addrs, ["0600000001", "0600000002", "0600000003"])

    def test_period_detection_priority(self) -> None:
        """
        Vérifie la détection de la période AAAA-MM dans les noms de fichiers et contenus.
        """
        self.assertEqual(
            DocumentTextUtils.detect_period_in_text("Facture_2023-09-14_client.pdf"),
            "2023-09",
        )
        self.assertEqual(
            DocumentTextUtils.detect_period_in_text("Courrier du 12 octobre 2022"),
            "2022-10",
        )

    def test_rcs_emails_filtered_from_discovered_and_one_edit_ocr(self) -> None:
        """
        Vérifie le filtrage RCS Google et la tolérance OCR à 1 lettre d'écart.
        """
        self.assertFalse(
            DiscoveredEmailContactsBuilder.is_valid_discoverable_email(
                "=====@://google.com"
            )
        )
        self.assertTrue(
            DiscoveredEmailContactsBuilder.is_valid_discoverable_email(
                "alice.martin@exemple-fictif.fr"
            )
        )
        self.assertTrue(ContactRulesLoader.is_one_edit_away("barriere", "barrere"))
        self.assertTrue(ContactRulesLoader.is_one_edit_away("durand", "durond"))
        self.assertFalse(ContactRulesLoader.is_one_edit_away("dupont", "martin"))
    def test_anonymization_ocr_glued_and_auto_pairs(self) -> None:
        """
        Vérifie le masquage des noms collés OCR, des titres avec prénom,
        des noms de famille extraits des contacts, des codes d'accès et du mojibake.
        """
        with tempfile.TemporaryDirectory(prefix="test_doc_anon_") as tmp_dir:
            with open(os.path.join(tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f_fn:
                f_fn.write("jean\nsophie\nluc\ncédric\nmartin\nalice\ncharlotte\nnadia\nevelyne\nphilippe\n")

            with open(os.path.join(tmp_dir, "villes_masquees.txt"), "w", encoding="utf-8") as f_loc:
                f_loc.write("boulon\nifs\nfresney-le-puceux\nboigny-sur-bionne\nsainte-honorine-du-fay\n")

            with open(os.path.join(tmp_dir, "collisions_noms.txt"), "w", encoding="utf-8") as f_col:
                f_col.write("grand\nblanc\n")

            with open(os.path.join(tmp_dir, "noms_famille_contacts.txt"), "w", encoding="utf-8") as f_sur:
                f_sur.write("Valmont = V.\nDelacroix = D.\n")

            with open(os.path.join(tmp_dir, "contacts.txt"), "w", encoding="utf-8") as f_ct:
                f_ct.write(
                    "Jean Dupont = Jean D.\n"
                    "Alice Mercier = Alice M.\n"
                    "Cédric Martin = Cédric M.\n"
                    "Jean De La Tour = Jean D. L. T.\n"
                    "Paul Grand = Paul G.\n"
                )

            trans_dir: str = os.path.join(tmp_dir, "transcriptions", "2024-05", "Documents")
            os.makedirs(trans_dir, exist_ok=True)
            sample_txt: str = os.path.join(trans_dir, "note_reunion.txt")
            with open(sample_txt, "w", encoding="utf-8") as f_txt:
                f_txt.write(
                    "Réunion avec Jean Dupont, Docteur Evelyne Moreau et Jean De La Tour.\n"
                    "Famille Valm\ufffdnt suivie par Delacroix, adresse Rue de la Paix.\n"
                    "En-tête OCR collé : MMEMERCIERALICE habitant 12 rue des Lilas.\n"
                    "Déplacement prévu à B0ULON et 1FS.\n"
                    "Saisie par Charlotte LEFEBVRE et audition de BERNARD Nadia.\n"
                    "Digicode 1985 et dossier sinistre n° 999888777.\n"
                    "MRZ : IDFRA0000000000<<<<<<<<<<<<<<<\n"
                    "Texte courant à préserver : une grande fenêtre et un grand merci à Paul Grand.\n"
                    "NIR:190017500100203 et IBAN FR7630001007941234567890185.\n"
                )
            cfg_path: str = os.path.join(tmp_dir, "config.ini")
            with open(cfg_path, "w", encoding="utf-8") as f_cfg:
                f_cfg.write(
                    "[files]\nfirst_names_file = prenoms.txt\nlocations_file = villes_masquees.txt\n"
                    "surname_collisions_file = collisions_noms.txt\n"
                    "surnames_output_file = noms_famille_contacts.txt\n"
                    "inverted_output_file = contacts.txt\n"
                    "[paths]\nroot_dir = .\ncontacts_file = contacts.txt\n"
                    "surnames_contacts_file = noms_famille_contacts.txt\n"
                    "manual_contacts_file = contacts_manuels.txt\n"
                    "discovered_contacts_file = contacts_emails_decouverts.txt\n"
                    "transcriptions_dir = transcriptions\nresults_dir = resultats_anonymisation\n"
                    "audit_report_file = audit_noms_residuels.txt\n"
                    "audit_copy_file = audit_noms_residuels_copier.txt\n"
                )

            config: PipelineConfig = PipelineConfig(config_path=cfg_path)
            runner: DocumentAnonymizationRunner = DocumentAnonymizationRunner(config=config)
            runner.run()

            lot_file: str = os.path.join(config.results_dir, "lot_01", "anonymise_partie_001.txt")
            self.assertTrue(os.path.exists(lot_file))
            with open(lot_file, "r", encoding="utf-8") as f_res:
                res_txt: str = f_res.read()

            self.assertIn("Jean D.", res_txt)
            self.assertIn("Docteur Evelyne M.", res_txt)
            self.assertIn("Famille V. suivie par D.", res_txt)
            self.assertIn("[CODE_ACCES_MASQUE]", res_txt)
            self.assertIn("[REF_ADMIN_MASQUEE]", res_txt)
            self.assertNotIn("999888777", res_txt)
            self.assertIn("Jean D. L. T.", res_txt)
            self.assertIn("Charlotte L.", res_txt)
            self.assertIn("B. Nadia", res_txt)
            self.assertIn("une grande fenêtre et un grand merci à Paul G.", res_txt)
            self.assertNotIn("Valmont", res_txt)
            self.assertNotIn("Moreau", res_txt)
            self.assertNotIn("Delacroix", res_txt)
            self.assertNotIn("Paix", res_txt)
            self.assertIn("[ADRESSE_MASQUEE]", res_txt)
            self.assertIn("[LIEU_MASQUE]", res_txt)
            self.assertIn("NIR:[NUM_SECU_MASQUE]", res_txt)
            self.assertIn("[IBAN_MASQUE]", res_txt)


if __name__ == "__main__":
    unittest.main()
