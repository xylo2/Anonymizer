# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch
import zipfile

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import gui_anonymizer


class TestAnonymizerGuiApp(unittest.TestCase):
    """Tests d'interface graphique couvrant l'obligation de choix de dossier et les 2 modes."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_gui_app_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        with open(os.path.join(self.tmp_root, "data", "mots_exclus.txt"), "w", encoding="utf-8") as f_ex:
            f_ex.write("# Mots exclus\n")
        with open(os.path.join(self.tmp_root, "data", "prenoms.txt"), "w", encoding="utf-8") as f_pr:
            f_pr.write("camille\nmarc\n")

        self._orig_root: str = gui_anonymizer.ROOT_DIR
        gui_anonymizer.ROOT_DIR = self.tmp_root
        try:
            self.app: gui_anonymizer.AnonymizerGuiApp = gui_anonymizer.AnonymizerGuiApp()
            self.app.withdraw()
        except tk.TclError as exc:
            gui_anonymizer.ROOT_DIR = self._orig_root
            shutil.rmtree(self.tmp_root, ignore_errors=True)
            self.skipTest(f"Environnement sans affichage graphique (headless) : {exc}")

    def tearDown(self) -> None:
        if hasattr(self, "app") and self.app is not None:
            try:
                self.app.destroy()
            except tk.TclError:
                pass
        gui_anonymizer.ROOT_DIR = self._orig_root
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_startup_gate_requires_workspace_creation_or_selection(self) -> None:
        """Vérifie qu'on ne peut pas avancer sans créer/choisir un dossier, et la détection au redémarrage."""
        self.assertEqual(self.app.active_page_key, "gate")
        self.assertEqual(self.app.current_ini_var.get(), "")

        self.app._show_page("mode")
        self.assertEqual(self.app.active_page_key, "gate")

        with patch.object(gui_anonymizer.messagebox, "showwarning") as mock_warn:
            self.app.gate_new_name_var.set("")
            self.app._confirm_gate_and_workspace()
            mock_warn.assert_called_once()
        self.assertEqual(self.app.active_page_key, "gate")

        self.app.gate_new_name_var.set("Dossier_Initial")
        self.app._confirm_gate_and_workspace()
        self.assertEqual(self.app.active_page_key, "mode")
        self.assertTrue(os.path.isfile(self.app.current_ini_var.get()))

        app2 = gui_anonymizer.AnonymizerGuiApp()
        app2.withdraw()
        try:
            self.assertEqual(app2.gate_action_var.get(), "open")
            self.assertEqual(len(app2.workspaces), 1)
            app2._confirm_gate_and_workspace()
            self.assertEqual(app2.active_page_key, "mode")
        finally:
            app2.destroy()
    def test_zip_warning_audit_preview_dialog_and_prompts(self) -> None:
        """Vérifie l'alerte ZIP, l'aperçu Avant/Après dédié, le guide d'export et les requêtes IA."""
        self.app.gate_new_name_var.set("Dossier_Enfant")
        self.app._confirm_gate_and_workspace()
        self.app._set_workflow_mode("ia", navigate=True)

        ini_path: str = self.app.current_ini_var.get()
        paths = self.app.controller.resolve_workspace_paths(ini_path)

        with zipfile.ZipFile(os.path.join(paths["sources_dir"], "archive.zip"), "w") as zf:
            zf.writestr("note.txt", "contenu")
        self.app._refresh_workspace_counters()
        self.assertIn("archive.zip", self.app.zip_warning_var.get())

        raw_txt: str = os.path.join(paths["transcriptions_dir"], "2024-06", "Documents", "bilan.txt")
        os.makedirs(os.path.dirname(raw_txt), exist_ok=True)
        with open(raw_txt, "w", encoding="utf-8") as f_tr:
            f_tr.write("Compte rendu rédigé par Marc Lefevre pour Camille Dupont.\n")

        with open(paths["audit_copy_file"], "w", encoding="utf-8") as f_aud:
            f_aud.write("Marc Lefevre = Marc L.\n")

        self.app._refresh_audit_list()
        items = self.app.audit_tree.get_children()
        self.assertEqual(len(items), 1)
        self.app.audit_tree.selection_set(next(iter(items)))
        self.app._on_audit_row_selected()

        occs = self.app.controller.load_audit_occurrences(ini_path, "Marc Lefevre")
        dlg = gui_anonymizer.BeforeAfterPreviewDialog(self.app, "Marc Lefevre", "Marc L.", occs)
        self.assertIn("Marc Lefevre", dlg.txt_before.get("1.0", "end"))
        dlg.destroy()

        self.app._open_export_guide_dialog(initial_tab=0)
        guide_windows = [w for w in self.app.winfo_children() if isinstance(w, gui_anonymizer.tk.Toplevel)]
        self.assertTrue(guide_windows)
        for gw in guide_windows:
            gw.destroy()

        self.app._show_page("export")
        self.assertIn("droit médico-social", self.app.txt_prompt_preview.get("1.0", "end"))

    def test_stop_button_terminates_active_process(self) -> None:
        """Vérifie que le bouton Arrêter interrompt proprement le processus enfant."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        self.app.current_proc = mock_proc
        self.app._set_buttons_state(False)
        self.assertEqual(str(self.app.btn_stop["state"]), "normal")
        self.app._stop_current_job()
        mock_proc.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
