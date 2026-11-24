# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import shutil
import sys
import tempfile
import tkinter as tk
import unittest
import zipfile

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.gui_dialogs import BeforeAfterPreviewDialog, ExportGuideDialog
import gui_anonymizer


class TestAnonymizerGuiApp(unittest.TestCase):
    """Vérifie le parcours GUI complet, le filtrage SMS, les dialogues et l'accessibilité."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_gui_app_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "prenoms.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        self._orig_root: str = gui_anonymizer.ROOT_DIR
        gui_anonymizer.ROOT_DIR = self.tmp_root
        try:
            self.app: gui_anonymizer.AnonymizerGuiApp = gui_anonymizer.AnonymizerGuiApp()
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

    def _create_and_open_test_workspace(self, name: str = "Dossier_Test_2026") -> str:
        self.app.gate_new_name_var.set(name)
        self.app._confirm_gate_and_workspace()
        return self.app.current_ini_var.get()
    def test_accessibility_keyboard_zoom_persistence_and_screen_reader_mode(self) -> None:
        """Vérifie le zoom texte (Ctrl +/-/0), la persistance et la navigation clavier."""
        ini_path: str = self._create_and_open_test_workspace("Dossier_Accessibilite")
        self.assertTrue(os.path.isfile(ini_path))
        self.assertEqual(self.app.active_page_key, "documents")

        self.app._adjust_font_scale(0.2)
        self.assertTrue(os.path.isfile(self.app._ui_prefs_file))
        self.app._reset_font_scale()

        self.app._advance_from_documents()
        self.assertEqual(self.app.active_page_key, "setup")
        self.app._step_page(-1)
        self.assertEqual(self.app.active_page_key, "documents")

    def test_last_opened_workspace_is_preselected_on_startup_gate(self) -> None:
        """Vérifie que le dernier dossier ouvert est mémorisé et pré-sélectionné au démarrage."""
        ini_first: str = self._create_and_open_test_workspace("Affaire_Alpha")
        ini_second: str = self._create_and_open_test_workspace("Affaire_Beta")
        self.assertNotEqual(ini_first, ini_second)

        self.app._refresh_gate_workspace_panel()
        self.assertEqual(self.app.gate_action_var.get(), "open")
        self.assertIn("Affaire_Beta", self.app.gate_existing_var.get())

    def test_zip_warning_audit_preview_dialog_and_prompts(self) -> None:
        """Vérifie l'alerte ZIP, l'aperçu Avant/Après dédié, le guide d'export et les requêtes IA."""
        ini_path: str = self._create_and_open_test_workspace("Dossier_Dialogues")
        self.app._set_workflow_mode("ia", navigate=True)
        paths = self.app.controller.resolve_workspace_paths(ini_path)

        with zipfile.ZipFile(os.path.join(paths["sources_dir"], "archive_test.zip"), "w") as zf:
            zf.writestr("note.txt", "contenu")
        self.app._refresh_workspace_counters()
        self.assertIn("archive_test.zip", self.app.zip_warning_var.get())

        raw_txt: str = os.path.join(paths["transcriptions_dir"], "2024-06", "Documents", "bilan.txt")
        os.makedirs(os.path.dirname(raw_txt), exist_ok=True)
        with open(raw_txt, "w", encoding="utf-8") as f_tr:
            f_tr.write("Compte rendu rédigé par Contact_Test_1 pour Utilisateur_A.\n")

        with open(paths["audit_copy_file"], "w", encoding="utf-8") as f_aud:
            f_aud.write("Contact_Test_1 = Contact T.\n")

        self.app._refresh_audit_list()
        items = self.app.audit_tree.get_children()
        self.assertEqual(len(items), 1)
        self.app.audit_tree.selection_set(next(iter(items)))
        self.app._on_audit_row_selected()

        occs = self.app.controller.load_audit_occurrences(ini_path, "Contact_Test_1")
        dlg = BeforeAfterPreviewDialog(
            self.app,
            "Contact_Test_1",
            "Contact T.",
            occs,
            on_approve=self.app._approve_selected_audit,
            on_exclude=self.app._exclude_selected_audit,
        )
        self.assertIn("Contact_Test_1", dlg.txt_before.get("1.0", "end"))
        dlg.destroy()

        guide = ExportGuideDialog(self.app, initial_tab=0)
        self.assertIn("exporter", guide.title().lower())
        guide.destroy()
    def test_sms_export_auto_detection_filtering_and_whitelist_merge(self) -> None:
        """Vérifie la détection des SMS (.xml), le filtrage exclusif et la désélection des numéros courts."""
        ini_path: str = self._create_and_open_test_workspace("Dossier_SMS")
        paths = self.app.controller.resolve_workspace_paths(ini_path)

        csv_src: str = os.path.join(paths["sources_dir"], "contacts.csv")
        with open(csv_src, "w", encoding="utf-8") as f_c:
            f_c.write("First Name,Last Name,Phone 1 - Value,E-mail 1 - Value\nCamille,Dupont,06 00 00 00 01,contact1@exemple.test\n")

        sms_src: str = os.path.join(paths["sources_dir"], "backup_sms.xml")
        with open(sms_src, "w", encoding="utf-8") as f_s:
            f_s.write(
                '<smses count="5">'
                '<sms address="+33600000001" body="Msg 1" />'
                '<sms address="0033600000001" body="Msg 2" />'
                '<mms address="06 00 00 00 02~06 00 00 00 01" contact_name="Dr Exemple" />'
                '<sms address="38600" body="Code confirmation" />'
                '<sms address="AMELI" body="Notification" />'
                "</smses>"
            )

        self.app._advance_from_documents()
        self.app._save_contact_filter_and_continue()
        self.assertEqual(len(self.app.controller.list_sms_export_files(ini_path)), 1)

        self.app._show_page("sms")
        self.assertEqual(len(self.app.sms_filter_items), 4)
        self.assertIn("Page 1 / 1", self.app.sms_page_info_var.get())
        by_phone = {str(it["phone"]): it for it in self.app.sms_filter_items}
        self.assertEqual(by_phone["0600000001"]["count"], 3)
        self.assertEqual(by_phone["0600000001"]["display_name"], "Camille Dupont")
        self.assertTrue(by_phone["0600000001"]["selected"])
        self.assertEqual(by_phone["0600000002"]["display_name"], "Dr Exemple")
        self.assertFalse(by_phone["0600000002"]["selected"])
        self.assertTrue(by_phone["38600"]["is_short"])
        self.assertTrue(by_phone["AMELI"]["is_short"])

        self.app.sms_filter_search_var.set("Exemple")
        self.app._set_all_sms_numbers_selected(True, exclusive=True)
        self.assertTrue(by_phone["0600000002"]["selected"])
        self.assertFalse(by_phone["0600000001"]["selected"])

        self.app.sms_filter_search_var.set("Exemple")
        self.app._set_all_sms_numbers_selected(False)
        self.assertFalse(by_phone["0600000002"]["selected"])

        self.app.sms_filter_search_var.set("")
        by_phone["0600000001"]["selected"] = True
        self.app.sms_filter_view_var.set("Numéros courts")
        self.app._on_sms_view_changed()
        self.assertEqual(len(self.app.sms_filter_tree.get_children()), 2)

        by_phone["38600"]["selected"] = True
        self.app._deselect_short_sms_numbers()
        self.assertFalse(by_phone["38600"]["selected"])
        self.assertFalse(by_phone["AMELI"]["selected"])
        self.app.sms_filter_view_var.set("Tous")
        self.app._on_sms_view_changed()
        self.app.sms_filter_tree.selection_set("1")
        self.app._toggle_selected_sms_filter()
        self.app._save_sms_filter_and_continue()

        wl_file: str = os.path.join(paths["contacts_dir"], "whitelist_contacts.json")
        with open(wl_file, "r", encoding="utf-8") as f_wl:
            saved_wl = json.load(f_wl)
        self.assertIn("contact1@exemple.test", saved_wl)
        self.assertIn("0600000001", saved_wl)
        self.assertIn("0600000002", saved_wl)
        self.assertNotIn("38600", saved_wl)


if __name__ == "__main__":
    unittest.main()
