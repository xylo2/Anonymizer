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
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner
from tools.restore_transcription_names import TranscriptionNameRestorer


class TestBugfixesRegression(unittest.TestCase):
    """Tests de non-régression pour les correctifs critiques."""

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

    def test_audit_approve_and_exclude_do_not_crash_on_split(self) -> None:
        """Vérifie que approve_audit_mask et exclude_audit_false_positive fonctionnent sans AttributeError."""
        ini_path = self.ctrl.create_workspace("Dossier_Audit_Fix")
        paths = self.ctrl.resolve_workspace_paths(ini_path)
        with open(paths["manual_contacts_file"], "a", encoding="utf-8") as f_man:
            f_man.write("Claire Bernard = Claire B.\n")
        with open(paths["audit_copy_file"], "w", encoding="utf-8") as f_aud:
            f_aud.write("Marc Lefevre = Marc L.\nMotInutile = M.\n")

        self.ctrl.approve_audit_mask(ini_path, "Marc Lefevre", "Marc L.")
        self.ctrl.exclude_audit_false_positive(ini_path, "MotInutile")

        self.assertEqual(self.ctrl.load_audit_candidates(ini_path), [])
        with open(paths["manual_contacts_file"], "r", encoding="utf-8") as f_man:
            self.assertIn("Marc Lefevre = Marc L.", f_man.read())

    def test_incremental_extraction_tracking_saved_and_reused(self) -> None:
        """Vérifie que .extraction_state.txt est persisté et empêche la ré-extraction."""
        ini_path = self.ctrl.create_workspace("Dossier_Incremental")
        paths = self.ctrl.resolve_workspace_paths(ini_path)
        src_doc = os.path.join(paths["sources_dir"], "2024-07_rapport.txt")
        with open(src_doc, "w", encoding="utf-8") as f_src:
            f_src.write("Rapport AnonVault de Camille Dupont.\n")

        cfg = PipelineConfig(ini_path)
        DocAnonymizerPipelineRunner(config=cfg, prevent_sleep=False).run_extract_only()
        self.assertTrue(os.path.isfile(cfg.extraction_tracking_file))

        second_count: int = DocAnonymizerPipelineRunner(
            config=cfg, prevent_sleep=False
        ).run_extract_only()
        self.assertEqual(second_count, 0)

    def test_gui_cli_commands_and_text_birth_dates(self) -> None:
        """Vérifie build_cli_command et le masquage des dates de naissance en lettres."""
        from doc_anonymizer.teams_chat_extractor import TeamsChatExtractor
        from doc_anonymizer.text_utils import DocumentTextUtils

        ini_path = self.ctrl.create_workspace("Dossier_CLI_Check")
        self.assertTrue(self.ctrl.build_cli_command(ini_path, "contacts")[1].endswith("run_contacts.py"))
        self.assertTrue(self.ctrl.build_cli_command(ini_path, "full")[1].endswith("run_documents.py"))
        self.assertIn("--extract-only", self.ctrl.build_cli_command(ini_path, "extract_only"))

        runner = DocumentAnonymizationRunner(PipelineConfig(ini_path))
        runner.initialize()
        masked_birth = runner.anonymize_text("Enfant née le 14 juillet 2015 à Lyon.")
        self.assertIn("[JOUR_MOIS_MASQUES]/2015", masked_birth)
        self.assertNotIn("14 juillet", masked_birth)

        self.assertIsNotNone(DocumentTextUtils.REGEX_BIRTH_DATE.search("Né le 31/05/2015"))
        self.assertEqual(DocumentTextUtils.detect_period_in_text("Acte du 31/08/2024"), "2024-08")
        mk, ts = TeamsChatExtractor._parse_teams_timestamp("2024-10-31T14:05:00Z")
        self.assertEqual((mk, ts), ("2024-10", "2024-10-31 14:05:00"))


if __name__ == "__main__":
    unittest.main()
