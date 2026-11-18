# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import os
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class TestDocAnonymizer(unittest.TestCase):
    """
    Valide les expressions régulières de masquage (NIR, IBAN, adresses, villes, SMS)
    ainsi que l'audit des noms résiduels et les variantes OCR.
    """

    def test_sensitive_regex_patterns(self) -> None:
        """
        Vérifie la détection des numéros NIR, IBAN, adresses postales (avec et sans numéro) et SMS.
        """
        self.assertIsNotNone(DocumentTextUtils.REGEX_SSN.search("NIR : 1 85 05 75 123 456 78"))
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_IBAN.search("FR76 3000 6000 0112 3456 7890 189")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_STREET_ADDRESS.search("Habite au 14 bis rue de la Paix")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_STREET_ADDRESS.search("Rendez-vous avenue Pierre Brossolette")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_POSTAL_CITY.search("75001 Paris")
        )

        group_addrs = DocumentTextUtils.split_sms_addresses("+33611223344~0655667788+33699887766")
        self.assertEqual(group_addrs, ["0611223344", "0655667788", "0699887766"])

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
    def test_anonymization_and_residual_audit(self) -> None:
        """
        Vérifie le remplacement des règles de contacts, les noms à particules,
        les variantes OCR, les villes du catalogue et l'audit résiduel.
        """
        with tempfile.TemporaryDirectory(prefix="test_doc_anon_") as tmp_dir:
            prenoms_path: str = os.path.join(tmp_dir, "prenoms.txt")
            with open(prenoms_path, "w", encoding="utf-8") as f_fn:
                f_fn.write("jean\nsophie\nluc\ncédric\nmartin\naurélie\nnathalie\n")

            contacts_path: str = os.path.join(tmp_dir, "contacts.txt")
            with open(contacts_path, "w", encoding="utf-8") as f_ct:
                f_ct.write("Jean Dupont = Jean D.\n")

            indexed_path: str = os.path.join(tmp_dir, "contacts_indexes.txt")
            with open(indexed_path, "w", encoding="utf-8") as f_idx:
                f_idx.write(
                    "0102030405 = Cédric Martin\n"
                    "0102030405 = Jean De La Tour\n"
                    "aurelie.mercier@exemple.fr = Aurélie Mercier\n"
                    "nathalie.valmont@exemple.fr = Nathalie Valmont\n"
                )

            anon_path: str = os.path.join(tmp_dir, "contacts_anonymises.txt")
            with open(anon_path, "w", encoding="utf-8") as f_ano:
                f_ano.write(
                    "0102030405 = Cédric M.\n"
                    "0102030405 = Jean D. L. T.\n"
                    "aurelie.mercier@exemple.fr = Aurélie M.\n"
                    "nathalie.valmont@exemple.fr = Nathalie V.\n"
                )

            trans_dir: str = os.path.join(tmp_dir, "transcriptions", "2024-05", "Documents")
            os.makedirs(trans_dir, exist_ok=True)
            sample_txt: str = os.path.join(trans_dir, "note_reunion.txt")
            with open(sample_txt, "w", encoding="utf-8") as f_txt:
                f_txt.write(
                    "Réunion avec Jean Dupont, M. Martin et Jean De La Tour.\n"
                    "La famille Mercier (et Mercter en OCR) et Mme Valmont habitent à Caen.\n"
                    "Rendez-vous rue du Pâturage à Trifouilly.\n"
                    "NIR:185057512345678 et IBAN FR7630006000011234567890189.\n"
                    "Mention phonétique : Luc Dubunt et Sophie Moreau.\n"
                )

            cfg_path: str = os.path.join(tmp_dir, "config.ini")
            with open(cfg_path, "w", encoding="utf-8") as f_cfg:
                f_cfg.write(
                    "[files]\nfirst_names_file = prenoms.txt\ninverted_output_file = contacts.txt\n"
                    "output_file = contacts_indexes.txt\nanonymized_output_file = contacts_anonymises.txt\n"
                    "[paths]\nroot_dir = .\ncontacts_file = contacts.txt\n"
                    "manual_contacts_file = contacts_manuels.txt\n"
                    "discovered_contacts_file = contacts_emails_decouverts.txt\n"
                    "transcriptions_dir = transcriptions\nresults_dir = resultats_anonymisation\n"
                    "audit_report_file = audit_noms_residuels.txt\n"
                    "audit_copy_file = audit_noms_residuels_copier.txt\n"
                    "[anonymization]\nmasked_locations = trifouilly\n"
                )

            config: PipelineConfig = PipelineConfig(config_path=cfg_path)
            runner: DocumentAnonymizationRunner = DocumentAnonymizationRunner(config=config)
            runner.run()

            lot_file: str = os.path.join(config.results_dir, "lot_01", "anonymise_partie_001.txt")
            self.assertTrue(os.path.exists(lot_file))
            with open(lot_file, "r", encoding="utf-8") as f_res:
                res_txt: str = f_res.read()

            self.assertIn("Jean D.", res_txt)
            self.assertIn("Cédric M.", res_txt)
            self.assertIn("Jean D. L. T.", res_txt)
            self.assertNotIn("Mercier", res_txt)
            self.assertNotIn("Mercter", res_txt)
            self.assertNotIn("Valmont", res_txt)
            self.assertNotIn("Caen", res_txt)
            self.assertNotIn("Trifouilly", res_txt)
            self.assertIn("[ADRESSE_MASQUEE]", res_txt)
            self.assertIn("[LIEU_MASQUE]", res_txt)
            self.assertNotIn("Jean Dupont", res_txt)
            self.assertNotIn("M. Martin", res_txt)
            self.assertNotIn("Jean De La Tour", res_txt)
            self.assertIn("NIR:[NUM_SECU_MASQUE]", res_txt)
            self.assertIn("[IBAN_MASQUE]", res_txt)

            with open(config.audit_report_file, "r", encoding="utf-8") as f_aud:
                audit_txt: str = f_aud.read()
            self.assertIn("Sophie Moreau", audit_txt)
            self.assertIn("Proche de 'Dupont'", audit_txt)


if __name__ == "__main__":
    unittest.main()
