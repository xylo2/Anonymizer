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


class TestMinMessagesFilter(unittest.TestCase):
    """Vérifie le filtre par nombre minimum de messages sur Contacts, SMS et Chats."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_min_msgs_")
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

    def test_contacts_sms_and_chat_min_messages_filter(self) -> None:
        ini_p: str = self.app.controller.create_workspace("Dossier_Filtre_Messages")
        self.app._refresh_workspaces(select_ini=ini_p)
        paths = self.app.controller.resolve_workspace_paths(ini_p)

        audits_dir: str = os.path.join(paths["workspace_root"], "audits")
        os.makedirs(audits_dir, exist_ok=True)
        with open(os.path.join(audits_dir, ".sms_numbers_cache.json"), "w", encoding="utf-8") as f_sc:
            json.dump({"signature": [], "stats": {"0600000002": {"count": 7}}}, f_sc)
        with open(os.path.join(audits_dir, ".chats_filter_cache.json"), "w", encoding="utf-8") as f_cc:
            json.dump({"signature": [], "metas": [{"participants": ["Contact_Test_3"], "count": 14}]}, f_cc)

        with open(paths["mapping_file"], "w", encoding="utf-8") as f_m:
            json.dump(
                {
                    "Contact_Test_1": {"alias": "Contact T.", "real_name": "Contact_Test_1"},
                    "0600000002": {"alias": "Contact T-2", "real_name": "Contact_Test_2"},
                    "Contact_Test_3": {"alias": "Contact T-3", "real_name": "Contact_Test_3"},
                },
                f_m,
            )

        self.app._refresh_contact_filter_list()
        self.app.contact_min_msg_var.set("≥ 5 msgs")
        self.app._on_contact_view_changed()
        self.assertEqual(len(self.app.contacts_filter_tree.get_children()), 2)

        self.app._set_all_contacts_selected(False)
        self.app._set_all_contacts_selected(True)
        by_c = {it["display_name"]: it for it in self.app.contact_filter_items}
        self.assertFalse(by_c["Contact_Test_1"]["selected"])
        self.assertTrue(by_c["Contact_Test_2"]["selected"])
        self.assertTrue(by_c["Contact_Test_3"]["selected"])

        self.app.sms_filter_items = [
            {"phone": "0600000001", "display_name": "Contact_Test_1", "count": 1, "is_short": False, "selected": False},
            {"phone": "0600000002", "display_name": "Contact_Test_2", "count": 5, "is_short": False, "selected": False},
            {"phone": "0600000003", "display_name": "Contact_Test_3", "count": 12, "is_short": False, "selected": False},
        ]
        self.app.sms_min_msg_var.set("≥ 5 msgs")
        self.app._on_sms_view_changed()
        self.assertEqual(len(self.app.sms_filter_tree.get_children()), 2)
        self.app._set_all_sms_numbers_selected(True)
        self.assertEqual([it["selected"] for it in self.app.sms_filter_items], [False, True, True])

        self.app.chat_filter_items = [
            {"platform": "WhatsApp", "conversation": "Conv_A", "participants": ["Utilisateur_A"], "participants_display": "Utilisateur_A", "count": 2, "selected": False},
            {"platform": "Signal", "conversation": "Conv_B", "participants": ["Contact_Test_1"], "participants_display": "Contact_Test_1", "count": 15, "selected": False},
        ]
        self.app.chat_min_msg_var.set("≥ 10 msgs")
        self.app._on_chat_view_changed()
        self.assertEqual(len(self.app.chat_filter_tree.get_children()), 1)
        self.app._set_all_chats_selected(True)
        self.assertEqual([it["selected"] for it in self.app.chat_filter_items], [False, True])


if __name__ == "__main__":
    unittest.main()
