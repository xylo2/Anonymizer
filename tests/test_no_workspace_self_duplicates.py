import os
import shutil
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.gui_controller import AnonymizerGuiController


class TestNoWorkspaceSelfDuplicates(unittest.TestCase):
    """Vérifie que les liens externes SMS/Chats ne créent aucun doublon dans dossiers/."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_no_self_dup_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "prenoms.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        self.ctrl = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_linked_sms_and_chat_are_not_copied_nor_flagged_as_duplicates(self) -> None:
        ini_p: str = self.ctrl.create_workspace("Dossier_Test_2026")
        ext_dir: str = os.path.join(self.tmp_root, "donnees_externes")
        os.makedirs(ext_dir, exist_ok=True)

        sms_p: str = os.path.join(ext_dir, "sms_test.xml")
        with open(sms_p, "w", encoding="utf-8") as f_s:
            f_s.write('<smses><sms address="0600000001" body="Bonjour" /></smses>')
        wa_p: str = os.path.join(ext_dir, "chat_test.txt")
        with open(wa_p, "w", encoding="utf-8") as f_w:
            f_w.write("12/06/2024, 10:00 - Utilisateur_A: Salut\n")

        self.ctrl.register_or_copy_sources(ini_p, [ext_dir], copy_external=False)
        for _ in range(3):
            self.ctrl.ws_manager.auto_organize_dropped_files(ini_p, force=True)

        self.assertEqual(self.ctrl.load_duplicate_file_items(ini_p), [])
        self.assertEqual(len(self.ctrl.list_sms_export_files(ini_p)), 1)
        self.assertEqual(len(self.ctrl.list_chat_export_files(ini_p)), 1)


if __name__ == "__main__":
    unittest.main()
