# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import gui_anonymizer


class TestWorkspaceSettingsButtonVisibility(unittest.TestCase):
    """Vérifie le masquage du bouton Paramètres sur la page 0 (gate) et son affichage dès qu'un dossier est ouvert."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.app = gui_anonymizer.AnonymizerGuiApp()
        self.app.controller.workspaces_base_dir = self._tmp_dir.name

    def tearDown(self) -> None:
        try:
            self.app.destroy()
        except Exception:
            pass
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
