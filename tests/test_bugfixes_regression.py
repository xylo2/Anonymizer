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

from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.chat_prescanner import ChatContactPrescanner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.gui_controller import AnonymizerGuiController
from tools.restore_transcription_names import TranscriptionNameRestorer


class TestBugfixesRegression(unittest.TestCase):
    """Tests de non-régression pour les 4 correctifs critiques."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_bugfixes_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        with open(os.path.join(self.tmp_root, "data", "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("camille\nmarc\njean\n")
        with open(os.path.join(self.tmp_root, "data", "villes_masquees.txt"), "w", encoding="utf-8") as f:
            f.write("lyon\nherouville-saint-clair\n")
        with open(os.path.join(self.tmp_root, "data", "mots_exclus.txt"), "w", encoding="utf-8") as f:
            f.write("# Exclusions\n")
        with open(os.path.join(self.tmp_root, "data", "collisions_noms.txt"), "w", encoding="utf-8") as f:
            f.write("# Collisions\n")
        self.ctrl = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)
    def test_workspace_locations_config_key_and_filename(self) -> None:
        """Vérifie que create_workspace pointe vers locations_file = .../villes_masquees.txt."""
        ini_path = self.ctrl.create_workspace("Dossier_Villes")
        cfg = PipelineConfig(ini_path)
        self.assertIn("lyon", cfg.masked_locations)

        runner = DocumentAnonymizationRunner(cfg)
        runner.initialize()
        masked = runner.anonymize_text("Rendez-vous prévu à Lyon demain.")
        self.assertIn("[LIEU_MASQUE]", masked)

    def test_chat_prescanner_json_signature_fix(self) -> None:
        """Vérifie que _scan_json_file appelle correctement extract_json_chat."""
        src_dir = os.path.join(self.tmp_root, "input_documents")
        os.makedirs(src_dir, exist_ok=True)
        with open(os.path.join(src_dir, "messages.json"), "w", encoding="utf-8") as f_js:
            json.dump(
                {
                    "messages": [
                        {
                            "creator": {"name": "Marc Lefevre", "email": "marc.lefevre@exemple.fr"},
                            "created_date": "Monday, June 3, 2024 at 09:00:00 AM UTC",
                            "text": "Bonjour Camille",
                        }
                    ]
                },
                f_js,
            )

        out_dir = os.path.join(self.tmp_root, "output_contacts")
        prescanner = ChatContactPrescanner(
            sources_dir=src_dir,
            discovered_chats_file=os.path.join(out_dir, "discovered_chat_contacts.txt"),
            discovered_emails_file=os.path.join(out_dir, "discovered_email_contacts.txt"),
            known_first_names={"marc", "camille"},
        )
        added_chats, added_emails = prescanner.prescan_sources()
        self.assertGreaterEqual(added_chats, 1)
        self.assertGreaterEqual(added_emails, 1)
    def test_restore_transcription_names_sanitize_fix(self) -> None:
        """Vérifie que TranscriptionNameRestorer fonctionne sans AttributeError."""
        ini_path = self.ctrl.create_workspace("Dossier_Restore")
        cfg = PipelineConfig(ini_path)
        trans_dir = os.path.join(cfg.transcriptions_dir, "2024-06", "Audio")
        os.makedirs(trans_dir, exist_ok=True)

        masked_file = os.path.join(trans_dir, "note_NUMERO_MASQUE.txt")
        with open(masked_file, "w", encoding="utf-8") as f_tr:
            f_tr.write(
                "========================================\n"
                "AUDIO : Entretien_2024-06-15_Client.mp3\n"
                "----------------------------------------\n"
                "[00:01] Bonjour.\n"
            )

        restorer = TranscriptionNameRestorer(cfg, dry_run=False)
        moved = restorer.run()
        self.assertEqual(moved, 1)
        expected_file = os.path.join(trans_dir, "Entretien_2024-06-15_Client.txt")
        self.assertTrue(os.path.isfile(expected_file))


if __name__ == "__main__":
    unittest.main()
