# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import sys
import tempfile
import tkinter as tk
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import gui_anonymizer


class TestWorkspaceSettingsButtonVisibility(unittest.TestCase):
    """Vérifie le masquage du bouton Paramètres sur la page 0 (gate)."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self._tmp_dir.name, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "prenoms.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self._tmp_dir.name, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        self._orig_root: str = gui_anonymizer.ROOT_DIR
        gui_anonymizer.ROOT_DIR = self._tmp_dir.name
        try:
            self.app = gui_anonymizer.AnonymizerGuiApp()
            self.app.withdraw()
        except tk.TclError as exc:
            gui_anonymizer.ROOT_DIR = self._orig_root
            self._tmp_dir.cleanup()
            self.skipTest(f"Environnement headless : {exc}")

    def tearDown(self) -> None:
        if hasattr(self, "app") and self.app is not None:
            try:
                self.app.destroy()
            except Exception:
                pass
        gui_anonymizer.ROOT_DIR = self._orig_root
        self._tmp_dir.cleanup()

    def test_settings_button_hidden_on_gate_and_visible_when_workspace_open(self) -> None:
        self.app._show_page("gate")
        self.app.update_idletasks()
        self.assertEqual(self.app.btn_workspace_settings.winfo_manager(), "")

        ini_path: str = self.app.controller.create_workspace("Affaire_Bouton_Params")
        self.app._refresh_workspaces(select_ini=ini_path)
        self.app._show_page("documents")
        self.app.update_idletasks()
        self.assertEqual(self.app.btn_workspace_settings.winfo_manager(), "pack")

        self.app._show_page("gate")
        self.app.update_idletasks()
        self.assertEqual(self.app.btn_workspace_settings.winfo_manager(), "")


if __name__ == "__main__":
    unittest.main()
