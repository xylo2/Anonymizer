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
    Valide les expressions régulières de masquage (NIR, IBAN, adresses, villes, SMS),
    la tolérance OCR, les automatisations ICS/MRZ/MIME et l'audit.
    """

    def test_sensitive_regex_patterns(self) -> None:
        """
        Vérifie la détection des numéros NIR, IBAN, adresses postales et SMS.
        """
        self.assertIsNotNone(DocumentTextUtils.REGEX_SSN.search("NIR : 1 85 05 75 123 456 78"))
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_IBAN.search("FR76 3000 6000 0112 3456 7890 189")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_STREET_ADDRESS.search("Habite au 14 bis rue de la Paix")
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
                "alice.pares@sept-lieues.com"
            )
        )
        self.assertTrue(ContactRulesLoader.is_one_edit_away("barriere", "barrere"))
        self.assertTrue(ContactRulesLoader.is_one_edit_away("lubrano", "lubrono"))
        self.assertFalse(ContactRulesLoader.is_one_edit_away("dupont", "durand"))
    def test_anonymization_ocr_glued_and_auto_pairs(self) -> None:
        """
        Vérifie le masquage des noms collés OCR, des confusions chiffres/lettres,
        des automatisations ICS/MRZ/MIME/Vinted, des lieux St/Sainte et des collisions lexicales.
        """
        with tempfile.TemporaryDirectory(prefix="test_doc_anon_") as tmp_dir:
            with open(os.path.join(tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f_fn:
                f_fn.write("jean\nsophie\nluc\ncédric\nmartin\naurélie\ncharlotte\nnassiba\ngabrielle\nphilippe\n")

            with open(os.path.join(tmp_dir, "villes_masquees.txt"), "w", encoding="utf-8") as f_loc:
                f_loc.write("boulon\nifs\nfresney-le-puceux\nboigny-sur-bionne\nsainte-honorine-du-fay\n")

            with open(os.path.join(tmp_dir, "contacts.txt"), "w", encoding="utf-8") as f_ct:
                f_ct.write(
                    "Jean Dupont = Jean D.\n"
                    "Aurélie Sobréro = Aurélie S.\n"
                    "Cédric Martin = Cédric M.\n"
                    "Jean De La Tour = Jean D. L. T.\n"
                    "Paul Grand = Paul G.\n"
                    "Elicap = Elicap\n"
                    "L'Observatoire du pain (opinionvalley) = L'Observatoire du pain (opinionvalley)\n"
                )

            trans_dir: str = os.path.join(tmp_dir, "transcriptions", "2024-05", "Documents")
            os.makedirs(trans_dir, exist_ok=True)
            sample_txt: str = os.path.join(trans_dir, "note_reunion.txt")
            with open(sample_txt, "w", encoding="utf-8") as f_txt:
                f_txt.write(
                    "Réunion avec Jean Dupont, M. Martin et Jean De La Tour.\n"
                    "En-tête OCR collé : MMESOBREROAURELIE habitant 12 rue des Lilas 14220 B0ULON et 1FS.\n"
                    "Mot de passe collé : 3005fresneylepuceux à Boigny-sur-Bionne et St Honorine du Fay.\n"
                    "Saisie par Charlotte HIVET et audition de ASMANE Nassiba.\n"
                    "Agenda ICS : RDV avec Philippe Foret\\, médecin Ramata DIA.\n"
                    "Liste MIME : \"chollier@exemple.fr Chollier\" et colis Vinted (vaubyessard).\n"
                    "MRZ : IDFRALM0V4FLX47<<<<<<<<<<<<<<<\n"
                    "Texte courant à préserver : une grande fenêtre et un grand merci à Paul Grand.\n"
                    "NIR:185057512345678 et IBAN FR7630006000011234567890189.\n"
                    "Mention phonétique : Luc Dubunt et Sophie Moreau.\n"
                )
            cfg_path: str = os.path.join(tmp_dir, "config.ini")
            with open(cfg_path, "w", encoding="utf-8") as f_cfg:
                f_cfg.write(
                    "[files]\nfirst_names_file = prenoms.txt\nlocations_file = villes_masquees.txt\n"
                    "inverted_output_file = contacts.txt\n"
                    "[paths]\nroot_dir = .\ncontacts_file = contacts.txt\n"
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
            self.assertIn("Cédric M.", res_txt)
            self.assertIn("Jean D. L. T.", res_txt)
            self.assertIn("Charlotte H.", res_txt)
            self.assertIn("A. Nassiba", res_txt)
            self.assertIn("Philippe F.,", res_txt)
            self.assertIn("Ramata D.", res_txt)
            self.assertIn('"EMAIL_001 C."', res_txt)
            self.assertIn("Vinted ([PSEUDO_MASQUE])", res_txt)
            self.assertIn("[MRZ_IDENTITE_MASQUEE]", res_txt)
            self.assertIn("une grande fenêtre et un grand merci à Paul G.", res_txt)
            self.assertNotIn("St Honorine du Fay", res_txt)
            self.assertNotIn("SOBRERO", res_txt)
            self.assertNotIn("HIVET", res_txt)
            self.assertNotIn("ASMANE", res_txt)
            self.assertNotIn("B0ULON", res_txt)
            self.assertNotIn("1FS", res_txt)
            self.assertNotIn("fresneylepuceux", res_txt)
            self.assertNotIn("Boigny-sur-Bionne", res_txt)
            self.assertIn("[ADRESSE_MASQUEE]", res_txt)
            self.assertIn("[LIEU_MASQUE]", res_txt)
            self.assertIn("NIR:[NUM_SECU_MASQUE]", res_txt)
            self.assertIn("[IBAN_MASQUE]", res_txt)

            runner.audit.scan_residual_names(
                "Mention phonétique : M. Dubunt, M. Récap, M. Gabrielle, M. Saint-Martin-De-[LIEU_MASQUE].",
                "note_reunion.txt",
            )
            runner.audit.write_report()
            with open(config.audit_report_file, "r", encoding="utf-8") as f_aud:
                audit_txt: str = f_aud.read()
            self.assertRegex(audit_txt, r"Dubunt\s+=\s+D\.\s+#\s+\[\s*1x\]\s+\(Proche de 'Dupont'\)")
            self.assertNotIn("Elicap", audit_txt)
            self.assertNotIn("Saint-Martin-De", audit_txt)
            self.assertNotIn("Gabrielle", audit_txt)


if __name__ == "__main__":
    unittest.main()
