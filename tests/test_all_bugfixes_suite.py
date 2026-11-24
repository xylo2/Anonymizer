# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_csv_importer import ContactCatalogImporter
from doc_anonymizer.dossier_exporter import LawyerDossierExporter
from doc_anonymizer.extraction_runner import DocumentExtractionRunner
from doc_anonymizer.text_utils import DocumentTextUtils


class TestAllBugfixesSuite(unittest.TestCase):
    """Vérifie tous les correctifs appliqués : filtrage WhatsApp/Messenger, SMS internationaux, contacts.txt, dates."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_all_bugfixes_")
        os.makedirs(os.path.join(self.tmp_dir, "input_documents"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_dir, "input_contacts"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_dir, "contacts"), exist_ok=True)
        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("camille\nmarc\nsophie\n")

        self.ini_path: str = os.path.join(self.tmp_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f_ini:
            f_ini.write(
                "[files]\n"
                "first_names_file = prenoms.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = input_documents\n"
                "transcriptions_dir = extracted_texts\n"
                "results_dir = anonymized_results\n"
                "contacts_file = contacts/contacts.txt\n"
                "selected_extraction_contacts_file = contacts/selected_extraction_contacts.txt\n"
                "manual_contacts_file = contacts/contacts_manuels.txt\n"
                "[extraction]\n"
                "enable_ocr = false\n"
                "enable_audio = false\n"
            )
        self.config: PipelineConfig = PipelineConfig(self.ini_path)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_whatsapp_and_messenger_respect_contact_whitelist(self) -> None:
        """Vérifie que seuls les contacts cochés dans whitelist_contacts.json sont extraits pour WhatsApp/Messenger."""
        wl_path: str = os.path.join(self.tmp_dir, "contacts", "whitelist_contacts.json")
        with open(wl_path, "w", encoding="utf-8") as f_wl:
            json.dump(["Camille Dupont"], f_wl)

        wa_kept: str = os.path.join(self.config.sources_dir, "Discussion WhatsApp avec Camille Dupont.txt")
        with open(wa_kept, "w", encoding="utf-8") as f_w1:
            f_w1.write("12/06/2024, 10:00 - Camille Dupont: Message pertinent à garder.\n")

        wa_ignored: str = os.path.join(self.config.sources_dir, "Discussion WhatsApp avec Marc Lefevre.txt")
        with open(wa_ignored, "w", encoding="utf-8") as f_w2:
            f_w2.write("12/06/2024, 11:00 - Marc Lefevre: Message hors dossier à ignorer.\n")

        fb_ignored: str = os.path.join(self.config.sources_dir, "messenger_marc.json")
        with open(fb_ignored, "w", encoding="utf-8") as f_fb:
            json.dump({"title": "Marc Lefevre", "messages": [{"sender_name": "Marc Lefevre", "timestamp_ms": 1718186400000, "content": "Privé"}]}, f_fb)

        runner = DocumentExtractionRunner(self.config)
        already: set[str] = set()
        sms_done: set[str] = set()
        phones: set[str] = set()
        emails: set[str] = set()

        out_kept = runner.process_single_file(wa_kept, {}, set(), already, sms_done, phones, emails)
        out_ign_wa = runner.process_single_file(wa_ignored, {}, set(), already, sms_done, phones, emails)
        out_ign_fb = runner.process_single_file(fb_ignored, {}, set(), already, sms_done, phones, emails)

        self.assertEqual(len(out_kept), 1)
        self.assertEqual(out_ign_wa, [])
        self.assertEqual(out_ign_fb, [])
    def test_international_and_short_sms_numbers_and_catalog_merge(self) -> None:
        """Vérifie la prise en charge des numéros internationaux/courts et la non-destruction de contacts.txt."""
        contacts_txt: str = os.path.join(self.tmp_dir, "contacts", "contacts.txt")
        with open(contacts_txt, "w", encoding="utf-8") as f_ct:
            f_ct.write("Sophie Martin = Sophie M.\n")

        paths = {
            "input_contacts_dir": os.path.join(self.tmp_dir, "input_contacts"),
            "contacts_dir": os.path.join(self.tmp_dir, "contacts"),
            "mapping_file": os.path.join(self.tmp_dir, "contacts", "mapping.json"),
            "contacts_file": contacts_txt,
            "selected_extraction_contacts_file": self.config.selected_extraction_contacts_file,
        }
        csv_src: str = os.path.join(self.tmp_dir, "new_contacts.csv")
        with open(csv_src, "w", encoding="utf-8") as f_csv:
            f_csv.write("First Name,Last Name,Phone 1 - Value\nCamille,Dupont,+32 470 12 34 56\n")

        importer = ContactCatalogImporter(paths, self.ini_path)
        importer.import_contact_file(csv_src)

        with open(contacts_txt, "r", encoding="utf-8") as f_ct_after:
            ct_content: str = f_ct_after.read()
        self.assertIn("Sophie Martin = Sophie M.", ct_content)
        self.assertIn("+32470123456 = Camille D.", ct_content)

        runner = DocumentExtractionRunner(self.config)
        target_phones, _ = runner.load_all_filter_contacts()
        self.assertIn("+32470123456", target_phones)

    def test_period_detection_and_lawyer_chronology_avoids_contract_id_false_positive(self) -> None:
        """Vérifie que les identifiants 8 chiffres et références contrat 2023-01 ne faussent pas la date."""
        self.assertIsNone(DocumentTextUtils.detect_period_in_text("SIRET 20240512987654"))
        self.assertEqual(DocumentTextUtils.detect_period_in_text("IMG_20240512_140000.jpg"), "2024-05")

        resolved = LawyerDossierExporter._resolve_piece_date(
            parent_period="Documents",
            filename="avenant.txt",
            body="Contrat cadre n° 2023-01 — Fait à Lyon le 15/06/2024.",
        )
        self.assertEqual(resolved, "2024-06")


if __name__ == "__main__":
    unittest.main()
