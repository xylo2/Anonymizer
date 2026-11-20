# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.gui_controller import AnonymizerGuiController


class TestAnonymizerGuiController(unittest.TestCase):
    """Vérifie la gestion multi-dossiers, l'import CSV et la validation de l'audit."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_gui_ctrl_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        with open(
            os.path.join(self.tmp_root, "data", "mots_exclus.txt"), "w", encoding="utf-8"
        ) as f_ex:
            f_ex.write("# Mots exclus\n")
        self.ctrl: AnonymizerGuiController = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_workspace_creation_csv_import_and_audit_actions(self) -> None:
        """Vérifie la création d'un dossier isolé et le traitement des lignes d'audit."""
        ini_path: str = self.ctrl.create_workspace("Dossier Prud'hommes 2026")
        self.assertTrue(os.path.isfile(ini_path))

        workspaces = self.ctrl.list_workspaces()
        self.assertEqual(len(workspaces), 1)
        ws_label, _ = workspaces[0]
        self.assertEqual(ws_label, "Dossier_Prud_hommes_2026")

        src_csv: str = os.path.join(self.tmp_root, "contacts_export.csv")
        with open(src_csv, "w", encoding="utf-8") as f_csv:
            f_csv.write("Nom,Email\nJean Dupont,jean@exemple.fr\n")
        imported_csv: str = self.ctrl.import_contacts_csv(ini_path, src_csv)
        self.assertTrue(os.path.isfile(imported_csv))

        paths = self.ctrl.resolve_workspace_paths(ini_path)
        with open(paths["audit_copy_file"], "w", encoding="utf-8") as f_aud:
            f_aud.write("Marc Lefevre = Marc L.\nTribunal Judiciaire = T. J.\n")

        cands = self.ctrl.load_audit_candidates(ini_path)
        self.assertEqual(len(cands), 2)

        self.ctrl.approve_audit_mask(ini_path, "Marc Lefevre", "Marc L.")
        with open(paths["manual_contacts_file"], "r", encoding="utf-8") as f_man:
            self.assertIn("Marc Lefevre = Marc L.", f_man.read())

        self.ctrl.exclude_audit_false_positive(ini_path, "Tribunal Judiciaire")
        with open(
            os.path.join(self.tmp_root, "data", "mots_exclus.txt"), "r", encoding="utf-8"
        ) as f_ex:
            excl_txt: str = f_ex.read()
        self.assertIn("tribunal", excl_txt)
        self.assertIn("judiciaire", excl_txt)

        self.assertEqual(self.ctrl.load_audit_candidates(ini_path), [])


if __name__ == "__main__":
    unittest.main()
