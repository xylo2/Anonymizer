# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import gui_anonymizer
from doc_anonymizer.gui_controller import AnonymizerGuiController


class TestAnonymizerGuiApp(unittest.TestCase):
    """Tests d'interface graphique (Tkinter) et de flux utilisateur complets."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_gui_app_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        with open(
            os.path.join(self.tmp_root, "data", "mots_exclus.txt"), "w", encoding="utf-8"
        ) as f_ex:
            f_ex.write("# Mots exclus\n")

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

    def test_navigation_and_guide_cards(self) -> None:
        """Vérifie la navigation entre les 4 pages et les 5 fiches du mode d'emploi."""
        self.assertEqual(self.app.active_page_key, "help")
        self.assertEqual(len(self.app.GUIDE_SECTIONS), 5)

        self.app._select_guide_card(4)
        self.assertIn("LICENCE LIBRE GNU GPL v3", self.app.guide_title_var.get())
        self.assertIn("Copyleft", self.app.guide_body_var.get())

        for page_key in ("setup", "run", "audit", "help"):
            self.app._show_page(page_key)
            self.assertEqual(self.app.active_page_key, page_key)

    def test_workspace_counters_multiple_csv_and_audit_editing(self) -> None:
        """Vérifie la création de dossier, le cumul de CSV, les compteurs et l'audit éditable."""
        with patch.object(gui_anonymizer.messagebox, "showinfo"):
            self.app.new_ws_name_var.set("Dossier_Enfant")
            self.app._create_new_workspace()

        self.assertIn("Dossier_Enfant", self.app.active_ws_badge_var.get())
        ini_path: str = self.app.current_ini_var.get()
        paths = self.app.controller.resolve_workspace_paths(ini_path)

        with open(os.path.join(paths["sources_dir"], "bilan.txt"), "w", encoding="utf-8") as f_doc:
            f_doc.write("Compte rendu de consultation.\n")

        dir_a: str = os.path.join(self.tmp_root, "src_a")
        dir_b: str = os.path.join(self.tmp_root, "src_b")
        os.makedirs(dir_a, exist_ok=True)
        os.makedirs(dir_b, exist_ok=True)
        csv_a: str = os.path.join(dir_a, "google.csv")
        csv_b: str = os.path.join(dir_b, "outlook.csv")
        for p_csv in (csv_a, csv_b):
            with open(p_csv, "w", encoding="utf-8") as f_c:
                f_c.write("Nom,Email\nCamille Durand,camille@exemple.fr\n")

        self.app.controller.import_contacts_csv(ini_path, csv_a)
        self.app.controller.import_contacts_csv(ini_path, csv_b)
        self.app._refresh_workspace_counters()

        self.assertIn("1 fichier(s)", self.app.docs_summary_var.get())
        self.assertIn("Carnets (.csv) chargés (2)", self.app.csv_summary_var.get())
        self.assertIn("google.csv", self.app.csv_summary_var.get())
        self.assertIn("outlook.csv", self.app.csv_summary_var.get())

        with open(paths["audit_copy_file"], "w", encoding="utf-8") as f_aud:
            f_aud.write("Cabinet Valois = C. V.\nOrthophoniste = Orthophoniste\n")

        self.app._refresh_audit_list()
        items = self.app.audit_tree.get_children()
        self.assertEqual(len(items), 2)

        first_item = next(iter(items))
        self.app.audit_tree.selection_set(first_item)
        self.app._on_audit_row_selected()
        self.assertEqual(self.app.audit_alias_edit_var.get(), "C. V.")

        self.app.audit_alias_edit_var.set("Cabinet_Avocat")
        self.app._approve_selected_audit()
        with open(paths["manual_contacts_file"], "r", encoding="utf-8") as f_man:
            self.assertIn("Cabinet Valois = Cabinet_Avocat", f_man.read())

        rem_items = self.app.audit_tree.get_children()
        self.assertEqual(len(rem_items), 1)
        self.app.audit_tree.selection_set(next(iter(rem_items)))
        self.app._exclude_selected_audit()
        with open(
            os.path.join(self.tmp_root, "data", "mots_exclus.txt"), "r", encoding="utf-8"
        ) as f_ex:
            self.assertIn("orthophoniste", f_ex.read())

        self.assertEqual(len(self.app.audit_tree.get_children()), 0)

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
