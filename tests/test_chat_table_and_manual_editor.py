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


class TestChatTableAndManualEditor(unittest.TestCase):
    """Vérifie le rendu complet de l'étape 4 (Chats), des participants et de ensure_manual_contacts_file."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_chat_tbl_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "prenoms.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        self._orig_root: str = gui_anonymizer.ROOT_DIR
        gui_anonymizer.ROOT_DIR = self.tmp_root
        try:
            self.app = gui_anonymizer.AnonymizerGuiApp()
            self.app.withdraw()
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

    def test_chat_tree_rendering_participants_and_manual_file(self) -> None:
        ini_path: str = self.app.controller.create_workspace("Affaire_Chats_Complet")
        self.app._refresh_workspaces(select_ini=ini_path)
        paths = self.app.controller.resolve_workspace_paths(ini_path)

        man_file: str = self.app.controller.ensure_manual_contacts_file(ini_path)
        self.assertTrue(os.path.isfile(man_file))

        chat_dir: str = os.path.join(paths["sources_dir"], "chat_exports")
        os.makedirs(chat_dir, exist_ok=True)
        with open(os.path.join(chat_dir, "signal_conv.json"), "w", encoding="utf-8") as f_s:
            json.dump(
                {
                    "title": "Échange Signal",
                    "messages": [
                        {"source": "+33600000001", "sourceName": "Contact_Test_1", "timestamp": 1723723200000, "body": "Bonjour"},
                        {"source": "+33600000002", "sourceName": "Contact_Test_2", "timestamp": 1723723260000, "body": "Salut"},
                    ],
                },
                f_s,
            )

        self.app._show_page("chats")
        self.assertEqual(len(self.app.chat_filter_items), 1)
        rows = self.app.chat_filter_tree.get_children()
        self.assertEqual(len(rows), 1)
        vals = tuple(self.app.chat_filter_tree.item(next(iter(rows)), "values"))
        self.assertEqual(next(iter(vals)), "✓ Garder")
        joined_vals: str = " | ".join(str(v) for v in vals)
        self.assertIn("Contact_Test_1", joined_vals)
        self.assertIn("Contact_Test_2", joined_vals)


if __name__ == "__main__":
    unittest.main()
