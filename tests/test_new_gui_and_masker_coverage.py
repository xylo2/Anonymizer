import os
import shutil
import sys
import tempfile
import tkinter as tk
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_rules_loader import ContactRulesLoader
from doc_anonymizer.gui_tree_columns import TreeviewColumnLayoutManager
from doc_anonymizer.sensitive_masker import SensitiveTextMasker
import gui_anonymizer


class TestNewGuiAndMaskerCoverage(unittest.TestCase):
    """Couvre doublons, colonnes, scroll, champ recherche et SensitiveTextMasker."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_cov_gui_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        with open(os.path.join(self.tmp_root, "data", "prenoms.txt"), "w", encoding="utf-8") as f_p:
            f_p.write("camille\nmarc\nsophie\n")
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

    def test_gui_duplicates_columns_entry_and_scroll(self) -> None:
        try:
            app = self._new_app()
        except tk.TclError as exc:
            self.skipTest(f"Environnement headless : {exc}")

        try:
            ini_p: str = app.controller.create_workspace("Dossier_Doublons_Cov")
            app._refresh_workspaces(select_ini=ini_p)
            paths = app.controller.resolve_workspace_paths(ini_p)
            for sub in ("Archive_A", "Archive_B"):
                folder = os.path.join(paths["sources_dir"], sub)
                os.makedirs(folder, exist_ok=True)
                with open(os.path.join(folder, "piece.txt"), "w", encoding="utf-8") as f_t:
                    f_t.write("Contenu identique pour test doublons.\n")

            app._advance_from_documents()
            self.assertEqual(app.active_page_key, "duplicates")
            app.dup_priority_folder_var.set("Archive_B")
            app._prioritize_duplicate_folder()
            app._ignore_duplicate_folder()
            app.page_scroller._on_shift_wheel(type("Ev", (), {"delta": 120})())
            app.page_scroller.reset_scroll()

            app._show_page("setup")
            app.update_idletasks()
            app.contact_filter_search_var.set("Camille")
            app.ent_contact_search._sync_visual()
            app.ent_contact_search._btn_clear.invoke()
            self.assertEqual(app.contact_filter_search_var.get(), "")

            mgr = TreeviewColumnLayoutManager.attach_to_tree(app.contacts_filter_tree)
            for col in ("phones", "emails", "alias"):
                mgr.toggle_column_visibility(col)
            mgr.toggle_column_visibility("keep")
            self.assertEqual(mgr.get_visible_columns(), ["keep"])
            self.assertEqual(mgr.auto_fit_column("inexistante"), 0)
            mgr.reset_to_default()
        finally:
            app.destroy()

    def test_sensitive_masker_dynamic_counters_and_manual_only(self) -> None:
        ini_p: str = os.path.join(self.tmp_root, "masker_test.ini")
        with open(ini_p, "w", encoding="utf-8") as f_ini:
            f_ini.write(
                "[files]\nfirst_names_file = data/prenoms.txt\n"
                "[paths]\nroot_dir = .\ncontacts_file = contacts.txt\n"
                "manual_contacts_file = manual.txt\n"
            )
        with open(os.path.join(self.tmp_root, "contacts.txt"), "w", encoding="utf-8") as f_c:
            f_c.write("Camille Dupont = Camille D.\n")
        with open(os.path.join(self.tmp_root, "manual.txt"), "w", encoding="utf-8") as f_m:
            f_m.write("Société Secrète = ENTITE_01\n")

        cfg = PipelineConfig(ini_p)
        rules = ContactRulesLoader(cfg)
        rules.load_all()
        masker = SensitiveTextMasker(cfg, rules)
        masker.dynamic_tokens = {"EMAIL:a@b.fr": "EMAIL_004", "TEL:0600000001": "TEL_007"}
        masker.sync_dynamic_counters()
        self.assertEqual((masker.email_counter, masker.phone_counter), (5, 8))
        self.assertEqual(masker.anonymize_text(""), "")

        manual_rules = ContactRulesLoader(cfg, manual_only=True)
        manual_rules.load_all()
        manual_masker = SensitiveTextMasker(cfg, manual_rules, manual_only=True)
        out_m: str = manual_masker.anonymize_text("Contrat avec Société Secrète et Camille Dupont.")
        self.assertIn("ENTITE_01", out_m)
        self.assertIn("Camille Dupont", out_m)


if __name__ == "__main__":
    unittest.main()
