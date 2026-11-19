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
    Valide les expressions régulières de masquage (NIR, IBAN, adresses, codes d'accès,
    CNI 12 chiffres, transactions, réunions, dates de naissance et établissements),
    la tolérance OCR, les titres avec prénom et l'audit.
    """

    def test_sensitive_regex_patterns(self) -> None:
        """
        Vérifie la détection des numéros NIR, IBAN, CNI 12 chiffres, transactions,
        réunions, dates de naissance, établissements et SMS.
        """
        self.assertIsNotNone(DocumentTextUtils.REGEX_SSN.search("NIR : 1 90 01 75 001 002 03"))
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_IBAN.search("FR76 3000 1007 9412 3456 7890 185")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_ISOLATED_12_DIGITS.search("Titre n° 123456789012 valide")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_ID_DOC_DATES.search("Délivrée le 15/04/2018 et valable jusqu'au 14/04/2033")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_BANK_TX_AND_CARDS.search("Carte terminant par 4921, transaction n° TX987654, don de 50 euros")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_MEETING_IDS.search("ID de réunion : 845 1234 5678, code secret : 948271")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_BIRTH_DATE.search("Née le 14/07/2015 à Lyon")
        )
        self.assertIsNotNone(
            DocumentTextUtils.REGEX_FACILITIES_AND_ZONES.search("Admission au CHU Côte de Nacre et Gare de Lyon")
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
        Vérifie le masquage complet : noms collés OCR, titres avec prénom,
        adresses, dates de naissance (y compris liste personnalisée), NIR et IBAN.
        """
        with tempfile.TemporaryDirectory(prefix="test_doc_anon_") as tmp_dir:
            with open(os.path.join(tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
                f.write("jean\nevelyne\nalice\npaul\ncharlotte\nnadia\n")
            with open(os.path.join(tmp_dir, "villes_masquees.txt"), "w", encoding="utf-8") as f:
                f.write("caen\nsaint-jean-de-luz\n")
            with open(os.path.join(tmp_dir, "contacts.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "Jean Dupont = Jean D.\n"
                    "Alice Mercier = Alice M.\n"
                    "Jean De La Tour = Jean D. L. T.\n"
                    "Paul Grand = Paul G.\n"
                )

            config = PipelineConfig(os.path.join(tmp_dir, "config.ini"))
            config.masked_birth_dates = ["02/05/2013", "10/10/1980"]
            config.custom_birth_date_pattern = (
                PipelineConfig._compile_custom_dates_pattern(
                    config.masked_birth_dates
                )
            )
            runner = DocumentAnonymizationRunner(config)

            doc_dir = os.path.join(tmp_dir, "transcriptions", "2024-05", "Documents")
            os.makedirs(doc_dir, exist_ok=True)
            sample_file = os.path.join(doc_dir, "note_reunion.txt")

            raw_text = (
                "Réunion avec Jean Dupont, Docteur Evelyne Marneau et Jean De La Tour.\n"
                "Échanges avec Jean-Eudes Lemoine, Jean Eudes Mercier et Dr Jean Philippe Bernard.\n"
                "Famille Vasseur suivie par DrLAMOTTE, adresse RuedelaCabottiere.\n"
                "En-tête OCR collé : MMEAlice Mercier habitant 12 bis avenue Victor Hugo\n"
                "Déplacement prévu à Caen et Saint-Jean-de-Luz, rendez-vous CHU Caen.\n"
                "Enfant : 02/05/2013, ISO 2013-05-02, ICS 20130502 et ddn 14/09/2015.\n"
                "Mère née 10.10.1980, titre 123456789012 délivrée le 01/03/2020.\n"
                "Véhicule immatriculé AB-123-CD et ancien 1234 AB 75.\n"
                "Carte ************2922, commande n° P16048112, don de 140,00 €.\n"
                "Visio 832 1462 0148, passcode GihJ2Q.\n"
                "SaisieparCharlotte Lemaitre et audition de B. Nadia.\n"
                "Digicode : A1234 et dossier n° 2025-07-29-04.\n"
                "MRZ : IDFRADUPONT<<<<<<<<<<<<<<<<<<<8010104F3110145\n"
                "Texte courant à préserver : une grande fenêtre et un grand merci à Paul Grand.\n"
                "NIR:184117512345678 et IBAN FR76 3000 6000 0112 3456 7890 189.\n"
            )
            with open(sample_file, "w", encoding="utf-8") as f:
                f.write(raw_text)

            runner.run()

            lot_file = os.path.join(
                tmp_dir,
                "resultats_anonymisation",
                "lot_01",
                "anonymise_partie_001.txt",
            )
            self.assertTrue(os.path.exists(lot_file))
            with open(lot_file, "r", encoding="utf-8") as f:
                res_txt = f.read()

            self.assertIn("Jean D.", res_txt)
            self.assertIn("Docteur Evelyne M.", res_txt)
            self.assertIn("Jean D. L. T.", res_txt)
            self.assertIn("Jean-Eudes L.", res_txt)
            self.assertIn("Jean Eudes M.", res_txt)
            self.assertIn("Dr Jean Philippe B.", res_txt)
            self.assertIn("Famille V.", res_txt)
            self.assertIn("Dr L.", res_txt)
            self.assertIn("MME Alice M.", res_txt)
            self.assertIn("[ADRESSE_MASQUEE]", res_txt)
            self.assertNotIn("RuedelaCabottiere", res_txt)
            self.assertIn("[LIEU_MASQUE]", res_txt)
            self.assertIn("[ETABLISSEMENT_LIEU_MASQUE]", res_txt)
            self.assertNotIn("02/05/2013", res_txt)
            self.assertNotIn("2013-05-02", res_txt)
            self.assertNotIn("20130502", res_txt)
            self.assertNotIn("10.10.1980", res_txt)
            self.assertIn("[DATE_MASQUEE]", res_txt)
            self.assertIn("[JOUR_MOIS_MASQUES]/2015", res_txt)
            self.assertIn("[ID_CNI_PERMIS_MASQUE]", res_txt)
            self.assertIn("[DATE_TITRE_MASQUEE]", res_txt)
            self.assertIn("[PLAQUE_IMMAT_MASQUEE]", res_txt)
            self.assertIn("[REF_BANCAIRE_TX_MASQUEE]", res_txt)
            self.assertIn("[ID_REUNION_MASQUE]", res_txt)
            self.assertIn("Charlotte L.", res_txt)
            self.assertIn("B. Nadia", res_txt)
            self.assertIn("[CODE_ACCES_MASQUE]", res_txt)
            self.assertIn("[REF_ADMIN_MASQUEE]", res_txt)
            self.assertIn("[MRZ_IDENTITE_MASQUEE]", res_txt)
            self.assertIn("une grande fenêtre", res_txt)
            self.assertIn("un grand merci", res_txt)
            self.assertIn("Paul G.", res_txt)
            self.assertIn("[NUM_SECU_MASQUE]", res_txt)
            self.assertIn("[IBAN_MASQUE]", res_txt)


if __name__ == "__main__":
    unittest.main()
