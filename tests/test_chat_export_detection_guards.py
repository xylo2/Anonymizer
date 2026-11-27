import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.chat_filter_manager import ChatFilterManager
from doc_anonymizer.contact_csv_importer import ContactCatalogImporter
from doc_anonymizer.gui_controller import AnonymizerGuiController


class TestChatExportDetectionGuards(unittest.TestCase):
    """Vérifie la détection robuste des exports de messageries."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_chat_guards_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "prenoms.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        self.ctrl = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_large_header_messenger_and_whatsapp_ampm_detected(self) -> None:
        ini_p: str = self.ctrl.create_workspace("Dossier_Chats_Test")
        paths = self.ctrl.resolve_workspace_paths(ini_p)
        chat_mgr = ChatFilterManager(paths, ContactCatalogImporter(paths, ini_p))

        wa_p: str = os.path.join(paths["sources_dir"], "whatsapp_ampm.txt")
        with open(wa_p, "w", encoding="utf-8-sig") as f_w:
            f_w.write("\u200e[12/06/2024, 10:15:02 AM] Utilisateur_A: Bonjour\n")

        msg_dir: str = os.path.join(paths["sources_dir"], "Groupe_Long")
        os.makedirs(msg_dir, exist_ok=True)
        msg_p: str = os.path.join(msg_dir, "message_1.json")
        participants = [{"name": f"Membre_{idx}_{'x' * 40}"} for idx in range(250)]
        payload = {
            "participants": participants,
            "title": "Groupe_Long",
            "messages": [{"sender_name": "Membre_1", "timestamp_ms": 1700000000000, "content": "Test"}],
        }
        with open(msg_p, "w", encoding="utf-8") as f_m:
            json.dump(payload, f_m)

        found = chat_mgr.list_export_files()
        self.assertIn(os.path.normpath(wa_p), found)
        self.assertIn(os.path.normpath(msg_p), found)

        audits_dir: str = os.path.join(paths["workspace_root"], "audits")
        os.makedirs(audits_dir, exist_ok=True)
        with open(os.path.join(audits_dir, "ignored_duplicates.json"), "w", encoding="utf-8") as f_ig:
            json.dump({"ignored_paths": [wa_p, msg_p]}, f_ig)

        self.assertEqual(len(chat_mgr.list_export_files()), 2)


if __name__ == "__main__":
    unittest.main()
