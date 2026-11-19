# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.power_manager import SystemSleepInhibitor
from doc_anonymizer.text_utils import DocumentTextUtils
import lancer_contacts
import lancer_documents


class TestWorkflowsAndSecurity(unittest.TestCase):
    """
    Vérifie les workflows complets (titres, audit, passe manuelle, CLI),
    la protection anti-XXE XML, le tri chronologique SMS, le maintien en éveil
    et la non-régression sur les faux positifs.
    """

    def setUp(self) -> None:
        """Prépare un environnement temporaire isolé avant chaque test."""
        self.test_dir: str = tempfile.mkdtemp(prefix="test_workflows_")
        self.ini_path: str = os.path.join(self.test_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f:
            f.write(
                "[files]\n"
                "csv_directory = export_contacts\n"
                "first_names_file = prenoms.txt\n"
                "locations_file = villes_masquees.txt\n"
                "surname_collisions_file = collisions_noms.txt\n"
                "excluded_words_file = mots_exclus.txt\n"
                "output_file = contacts_indexes.txt\n"
                "anonymized_output_file = contacts_anonymises.txt\n"
                "surnames_output_file = noms_famille_contacts.txt\n"
                "deduplicated_output_file = contacts_dedoublonnes.txt\n"
                "inverted_output_file = contacts.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = fichiers sources\n"
                "transcriptions_dir = transcriptions\n"
                "results_dir = resultats_anonymisation\n"
                "contacts_file = contacts.txt\n"
                "surnames_contacts_file = noms_famille_contacts.txt\n"
                "manual_contacts_file = contacts_manuels.txt\n"
                "discovered_contacts_file = contacts_emails_decouverts.txt\n"
                "audit_report_file = audit_noms_residuels.txt\n"
                "audit_copy_file = audit_noms_residuels_copier.txt\n"
                "[extraction]\n"
                "enable_ocr = false\n"
                "enable_audio = false\n"
                "[anonymization]\n"
                "main_character_name = Utilisateur_Principal\n"
                "masked_birth_dates = 02/05/2013\n"
            )

        with open(
            os.path.join(self.test_dir, "prenoms.txt"), "w", encoding="utf-8"
        ) as f:
            f.write("paul\njean\nsophie\nclaire\n")
        with open(
            os.path.join(self.test_dir, "villes_masquees.txt"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("caen\nfiers\n")
        with open(
            os.path.join(self.test_dir, "collisions_noms.txt"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("grand\npetit\n")
        with open(
            os.path.join(self.test_dir, "mots_exclus.txt"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("conge\nvacances\n")

        self.config: PipelineConfig = PipelineConfig(self.ini_path)
        self.config.load_external_lists()

    def tearDown(self) -> None:
        """Nettoie le répertoire temporaire après chaque test."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_auto_titles_audit_import_and_manual_pass(self) -> None:
        """
        Vérifie le masquage automatique des titres, mots_exclus.txt,
        l'audit des noms résiduels et la passe --manual-only.
        """
        trans_dir: str = os.path.join(
            self.test_dir, "transcriptions", "2024-06", "Documents"
        )
        os.makedirs(trans_dir, exist_ok=True)
        note_path: str = os.path.join(trans_dir, "compte_rendu.txt")
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(
                "Consultation avec le Dr Lamotte.\n"
                "Note sur Paul Conge et Paul Vacances.\n"
                "Rencontre avec Mme Dupuis.\n"
                "Rencontre avec Mme Dupuis.\n"
                "Rencontre avec Mme Dupuis.\n"
            )

        runner = DocumentAnonymizationRunner(self.config)
        runner.run()

        lot_file: str = os.path.join(
            self.test_dir,
            "resultats_anonymisation",
            "lot_01",
            "anonymise_partie_001.txt",
        )
        with open(lot_file, "r", encoding="utf-8") as f:
            content: str = f.read()

        self.assertIn("Dr L.", content)
        self.assertIn("Mme D.", content)
        self.assertIn("Paul Conge", content)

        with open(self.config.manual_contacts_file, "w", encoding="utf-8") as f:
            f.write("Paul Conge = Paul C.\n")

        manual_runner = DocumentAnonymizationRunner(
            self.config, manual_only=True
        )
        manual_runner.run_on_existing_results()

        with open(lot_file, "r", encoding="utf-8") as f:
            updated: str = f.read()
        self.assertIn("Paul C.", updated)

    def test_xml_xxe_security_and_sms_parsing(self) -> None:
        """
        Vérifie le blocage des déclarations DOCTYPE/ENTITY et le tri des SMS
        via le pipeline complet de bout en bout.
        """
        malicious_xml: str = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            "<smses><sms body='&xxe;'/></smses>"
        )
        with self.assertRaises(ValueError):
            DocumentTextUtils.safe_parse_xml_fromstring(malicious_xml)

        with open(self.config.contacts_file, "w", encoding="utf-8") as f_ct:
            f_ct.write("0612345678 = Contact T.\n")

        sources_dir: str = os.path.join(self.test_dir, "fichiers sources")
        os.makedirs(sources_dir, exist_ok=True)
        valid_sms: str = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<smses>\n"
            '  <sms address="0612345678" date="1700000200000" type="2" body="Second message" />\n'
            '  <sms address="0612345678" date="1700000100000" type="1" body="Premier message" />\n'
            "</smses>\n"
        )
        sms_path: str = os.path.join(sources_dir, "sms_export.xml")
        with open(sms_path, "w", encoding="utf-8") as f:
            f.write(valid_sms)

        rc: int = lancer_documents.main(["-c", self.ini_path, "--allow-sleep"])
        self.assertEqual(rc, 0)

        lot_file: str = os.path.join(
            self.test_dir,
            "resultats_anonymisation",
            "lot_01",
            "anonymise_partie_001.txt",
        )
        self.assertTrue(os.path.exists(lot_file))
        with open(lot_file, "r", encoding="utf-8") as f:
            sms_text: str = f.read()
        self.assertIn("Premier message", sms_text)
        self.assertIn("Second message", sms_text)
        self.assertLess(
            sms_text.index("Premier message"), sms_text.index("Second message")
        )
    def test_auto_titles_audit_import_and_manual_pass(self) -> None:
        """
        Vérifie le masquage automatique des titres, mots_exclus.txt,
        l'audit des noms résiduels et la passe --manual-only.
        """
        trans_dir: str = os.path.join(
            self.test_dir, "transcriptions", "2024-06", "Documents"
        )
        os.makedirs(trans_dir, exist_ok=True)
        note_path: str = os.path.join(trans_dir, "compte_rendu.txt")
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(
                "Consultation avec le Dr Lamotte.\n"
                "Note sur Paul Conge et Paul Vacances.\n"
                "Rencontre avec Mme Dupuis.\n"
                "Rencontre avec Mme Dupuis.\n"
                "Rencontre avec Mme Dupuis.\n"
            )

        runner = DocumentAnonymizationRunner(self.config)
        runner.run()

        lot_file: str = os.path.join(
            self.test_dir,
            "resultats_anonymisation",
            "lot_01",
            "anonymise_partie_001.txt",
        )
        with open(lot_file, "r", encoding="utf-8") as f:
            content: str = f.read()

        self.assertIn("Dr L.", content)
        self.assertIn("Mme D.", content)
        self.assertIn("Paul Conge", content)

        with open(self.config.manual_contacts_file, "w", encoding="utf-8") as f:
            f.write("Paul Conge = Paul C.\n")

        manual_runner = DocumentAnonymizationRunner(
            self.config, manual_only=True
        )
        manual_runner.run_on_existing_results()

        with open(lot_file, "r", encoding="utf-8") as f:
            updated: str = f.read()
        self.assertIn("Paul C.", updated)

    def test_xml_xxe_security_and_sms_parsing(self) -> None:
        """
        Vérifie le blocage des déclarations DOCTYPE/ENTITY et le tri des SMS
        via le pipeline complet de bout en bout.
        """
        malicious_xml: str = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            "<smses><sms body='&xxe;'/></smses>"
        )
        with self.assertRaises(ValueError):
            DocumentTextUtils.safe_parse_xml_fromstring(malicious_xml)

        with open(self.config.contacts_file, "w", encoding="utf-8") as f_ct:
            f_ct.write("0612345678 = Contact T.\n")

        sources_dir: str = os.path.join(self.test_dir, "fichiers sources")
        os.makedirs(sources_dir, exist_ok=True)
        valid_sms: str = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<smses>\n"
            '  <sms address="0612345678" date="1700000200000" type="2" body="Second message" />\n'
            '  <sms address="0612345678" date="1700000100000" type="1" body="Premier message" />\n'
            "</smses>\n"
        )
        sms_path: str = os.path.join(sources_dir, "sms_export.xml")
        with open(sms_path, "w", encoding="utf-8") as f:
            f.write(valid_sms)

        rc: int = lancer_documents.main(["-c", self.ini_path, "--allow-sleep"])
        self.assertEqual(rc, 0)

        lot_file: str = os.path.join(
            self.test_dir,
            "resultats_anonymisation",
            "lot_01",
            "anonymise_partie_001.txt",
        )
        self.assertTrue(os.path.exists(lot_file))
        with open(lot_file, "r", encoding="utf-8") as f:
            sms_text: str = f.read()
        self.assertIn("Premier message", sms_text)
        self.assertIn("Second message", sms_text)
        self.assertLess(
            sms_text.index("Premier message"), sms_text.index("Second message")
        )
