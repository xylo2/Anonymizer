# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import tkinter as tk
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.gui_tree_columns import TreeviewColumnLayoutManager
import gui_anonymizer


class TestTreeColumnCustomization(unittest.TestCase):
    """Vérifie le déplacement, masquage, auto-ajustement, persistance et réinitialisation."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_tree_cols_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "prenoms.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        self._orig_root: str = gui_anonymizer.ROOT_DIR
        gui_anonymizer.ROOT_DIR = self.tmp_root

    def tearDown(self) -> None:
        gui_anonymizer.ROOT_DIR = self._orig_root
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _new_app(self) -> gui_anonymizer.AnonymizerGuiApp:
        app = gui_anonymizer.AnonymizerGuiApp()
        app.withdraw()
        app._sync_docs_tasks = True  # type: ignore[attr-defined]
        return app

    def test_reorder_hide_autofit_persist_and_reset(self) -> None:
        try:
            app1 = self._new_app()
        except tk.TclError as exc:
            self.skipTest(f"Environnement headless : {exc}")

        try:
            ini_p: str = app1.controller.create_workspace("Dossier_Test_2026")
            app1._refresh_workspaces(select_ini=ini_p)
            app1._show_page("setup")
            app1.update_idletasks()

            tree1 = app1.contacts_filter_tree
            tree1.insert(
                "", "end",
                values=("✓ Garder", "Contact_Test_1_Nom_Tres_Long_Pour_Test", "06 00 00 00 01", "contact1@exemple.test"),
            )
            mgr1 = TreeviewColumnLayoutManager.attach_to_tree(tree1)
            self.assertEqual(mgr1.get_visible_columns(), ["keep", "alias", "phones", "emails"])

            fitted_w: int = mgr1.auto_fit_column("alias")
            self.assertGreater(fitted_w, 180)
            self.assertEqual(int(tree1.column("alias", "width")), fitted_w)

            mgr1.toggle_column_visibility("emails")
            self.assertEqual(mgr1.get_visible_columns(), ["keep", "alias", "phones"])

            mgr1.move_column_to_x("phones", 10)
            self.assertEqual(mgr1.get_visible_columns(), ["phones", "keep", "alias"])
            self.assertTrue(os.path.isfile(app1._ui_prefs_file))
        finally:
            app1.destroy()

        app2 = self._new_app()
        try:
            app2._refresh_workspaces(select_ini=ini_p)
            app2._show_page("setup")
            app2.update_idletasks()
            tree2 = app2.contacts_filter_tree
            mgr2 = TreeviewColumnLayoutManager.attach_to_tree(tree2)
            self.assertEqual(mgr2.get_visible_columns(), ["phones", "keep", "alias"])
            self.assertEqual(int(tree2.column("alias", "width")), fitted_w)

            mgr2.reset_to_default()
            self.assertEqual(mgr2.get_visible_columns(), ["keep", "alias", "phones", "emails"])
            self.assertEqual(int(tree2.column("alias", "width")), 180)
        finally:
            app2.destroy()


if __name__ == "__main__":
    unittest.main()
