import configparser
import os
import shutil
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.gui_controller import AnonymizerGuiController
from google_contacts_parser.config_manager import ContactsConfig
import run_documents


class TestWithContactsWithoutCsv(unittest.TestCase):
    """Vérifie --with-contacts sans carnet CSV/vCard et la migration INI."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_no_csv_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        with open(os.path.join(self.tmp_root, "data", "prenoms.txt"), "w", encoding="utf-8") as f_p:
            f_p.write("camille\nmarc\n")
        self.ctrl = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_with_contacts_succeeds_without_csv_and_migrates_ini(self) -> None:
        ini_path: str = self.ctrl.create_workspace("Dossier_Sans_Carnet")
        cfg = configparser.ConfigParser()
        cfg.read(ini_path, encoding="utf-8")
        cfg.set("files", "csv_directory", os.path.join(self.tmp_root, "input_contacts"))
        with open(ini_path, "w", encoding="utf-8") as f_ini:
            cfg.write(f_ini)

        direct_cfg = ContactsConfig(ini_path)
        expected_in_contacts: str = os.path.normpath(
            os.path.join(os.path.dirname(ini_path), "input_contacts")
        )
        self.assertEqual(os.path.normpath(direct_cfg.csv_directory), expected_in_contacts)

        paths = self.ctrl.resolve_workspace_paths(ini_path)
        cfg_reloaded = configparser.ConfigParser()
        cfg_reloaded.read(ini_path, encoding="utf-8")
        self.assertEqual(
            os.path.normpath(cfg_reloaded.get("files", "csv_directory")),
            os.path.normpath(paths["input_contacts_dir"]),
        )

        note_p: str = os.path.join(paths["sources_dir"], "2025-01_note.txt")
        with open(note_p, "w", encoding="utf-8") as f_n:
            f_n.write("Échange avec Camille Dupont (06 11 22 33 44).\n")

        rc: int = run_documents.main(["-c", ini_path, "--with-contacts", "--allow-sleep"])
        self.assertEqual(rc, 0)

        lot_files = [
            os.path.join(rp, fn)
            for rp, _, files in os.walk(paths["results_dir"])
            for fn in files
            if fn.endswith(".txt")
        ]
        self.assertEqual(len(lot_files), 1)
        with open(next(iter(lot_files)), "r", encoding="utf-8") as f_lot:
            content: str = f_lot.read()
        self.assertIn("Camille D.", content)
        self.assertIn("TEL_001", content)


if __name__ == "__main__":
    unittest.main()
