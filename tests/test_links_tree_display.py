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

import gui_anonymizer


class TestLinksTreeDisplay(unittest.TestCase):
    """Vérifie le tableau structuré des emplacements référencés (Étape 1)."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_links_tree_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "prenoms.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        self._orig_root: str = gui_anonymizer.ROOT_DIR
        gui_anonymizer.ROOT_DIR = self.tmp_root
        try:
            self.app = gui_anonymizer.AnonymizerGuiApp()
            self.app.withdraw()
            self.app._sync_docs_tasks = True  # type: ignore[attr-defined]
        except tk.TclError as exc:
            gui_anonymizer.ROOT_DIR = self._orig_root
            shutil.rmtree(self.tmp_root, ignore_errors=True)
            self.skipTest(f"Environnement headless : {exc}")

    def tearDown(self) -> None:
        if hasattr(self, "app") and self.app is not None:
            try:
                self.app.destroy()
            except tk.TclError:
                pass
        gui_anonymizer.ROOT_DIR = self._orig_root
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_links_tree_columns_status_and_removal(self) -> None:
        self.app.gate_new_name_var.set("Dossier_Test_2026")
        self.app._confirm_gate_and_workspace()
        ini_path: str = self.app.current_ini_var.get()

        ext_folder: str = os.path.join(self.tmp_root, "Dossier_Sante_Test")
        os.makedirs(ext_folder, exist_ok=True)
        with open(os.path.join(ext_folder, "note.txt"), "w", encoding="utf-8") as f_n:
            f_n.write("Contenu test\n")

        self.app.controller.register_or_copy_sources(ini_path, [ext_folder], copy_external=False)
        self.app._refresh_workspace_counters()

        rows = self.app.links_tree.get_children()
        self.assertEqual(len(rows), 1)
        status_v, _storage_v, name_v, path_v = tuple(
            self.app.links_tree.item(next(iter(rows)), "values")
        )
        self.assertEqual(status_v, "✓ Actif")
        self.assertEqual(name_v, "Dossier_Sante_Test")
        self.assertEqual(path_v, os.path.normpath(ext_folder))

        self.app.links_tree.selection_set(next(iter(rows)))
        self.app._remove_selected_linked_source()
        self.assertEqual(len(self.app.links_tree.get_children()), 0)


if __name__ == "__main__":
    unittest.main()
