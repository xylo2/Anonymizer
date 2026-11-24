# Commandes pip à exécuter : Aucune dépendance externe requise

import json
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


class TestGuiErgonomics(unittest.TestCase):
    """Vérifie navigation Alt+Flèches, progression %, tuiles et audit."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_gui_ergo_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        dict_files = (
            "mots_exclus.txt",
            "prenoms.txt",
            "collisions_noms.txt",
            "villes_masquees.txt",
        )
        for fn in dict_files:
            fpath: str = os.path.join(self.tmp_root, "data", fn)
            with open(fpath, "w", encoding="utf-8") as f_d:
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
    def test_step_navigation_progress_dashboard_and_audit(self) -> None:
        self.app.gate_new_name_var.set("Dossier_Test_2026")
        self.app._confirm_gate_and_workspace()
        self.assertEqual(self.app.active_page_key, "documents")

        self.app._step_page(1)
        self.assertEqual(self.app.active_page_key, "setup")
        self.app._step_page(-1)
        self.assertEqual(self.app.active_page_key, "documents")

        self.app._append_log("[2/4] Extrait : piece_test.pdf")
        self.assertIn("50 % (2/4)", self.app.run_progress_label_var.get())

        ini_p: str = self.app.current_ini_var.get()
        paths = self.app.controller.resolve_workspace_paths(ini_p)
        os.makedirs(paths["results_dir"], exist_ok=True)
        state_p: str = os.path.join(
            paths["results_dir"], ".anonymization_state.json"
        )
        with open(state_p, "w", encoding="utf-8") as f_st:
            json.dump(
                {
                    "compteur_paires": {
                        "Utilisateur_A": 7,
                        "Contact_Test_1": 2,
                    },
                    "stats_anonymisation": {
                        "documents_traites": 12,
                        "noms_masques": 34,
                        "coordonnees_masquees": 9,
                        "identifiants_masques": 3,
                        "lieux_dates_masques": 15,
                    },
                },
                f_st,
            )
        self.app._refresh_dashboard_cards()
        self.assertEqual(self.app.stat_vars["docs"].get(), "12")
        self.assertEqual(self.app.stat_vars["names"].get(), "34")
        self.assertEqual(self.app.stat_vars["coords"].get(), "9")

        with open(paths["audit_copy_file"], "w", encoding="utf-8") as f_aud:
            f_aud.write(
                "Utilisateur_A = Utilisateur A.\n"
                "Contact_Test_1 = Contact T.\n"
            )
        self.app._refresh_audit_list()
        children = self.app.audit_tree.get_children()
        self.assertEqual(len(children), 2)
        first_vals = self.app.audit_tree.item(children[0], "values")
        self.assertEqual(first_vals, ("7x", "Utilisateur_A", "Utilisateur A."))
        self.app._exclude_selected_audit()
        self.assertEqual(len(self.app.audit_tree.get_children()), 1)


if __name__ == "__main__":
    unittest.main()
