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

from doc_anonymizer.chat_filter_manager import ChatFilterManager
from doc_anonymizer.contact_csv_importer import ContactCatalogImporter
from doc_anonymizer.duplicate_files_manager import DuplicateFilesManager
from doc_anonymizer.sms_filter_manager import SmsFilterManager
import gui_anonymizer


class TestDuplicateFilesFeature(unittest.TestCase):
    """Vérifie la détection légère de doublons, le filtrage SMS/Chats et la GUI."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_dups_feat_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "prenoms.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        self.ws_dir: str = os.path.join(self.tmp_root, "Dossier_Test_2026")
        self.src_dir: str = os.path.join(self.ws_dir, "input_documents")
        os.makedirs(os.path.join(self.src_dir, "sous_dossier"), exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_large_files_duplicate_detection_cache_and_sms_chat_filtering(self) -> None:
        """Vérifie le cache SHA-256 et l'exclusion des doublons dans SMS et Chats."""
        payload_dup: bytes = b"HEADER_A_" + (b"X" * 150000) + b"_FOOTER_A"
        payload_diff: bytes = b"HEADER_A_" + (b"Y" * 150000) + b"_FOOTER_A"

        f1: str = os.path.join(self.src_dir, "piece_originale.bin")
        f2: str = os.path.join(self.src_dir, "sous_dossier", "piece_copie.bin")
        f3: str = os.path.join(self.src_dir, "piece_meme_taille_diff.bin")
        for path_p, data_b in ((f1, payload_dup), (f2, payload_dup), (f3, payload_diff)):
            with open(path_p, "wb") as f_out:
                f_out.write(data_b)

        sms_1: str = os.path.join(self.src_dir, "sms_a.xml")
        sms_2: str = os.path.join(self.src_dir, "sous_dossier", "sms_b.xml")
        sms_xml: str = '<smses><sms address="0600000001" body="Test" /></smses>'
        for sp in (sms_1, sms_2):
            with open(sp, "w", encoding="utf-8") as f_s:
                f_s.write(sms_xml)

        paths = {
            "workspace_root": self.ws_dir,
            "sources_dir": self.src_dir,
            "input_contacts_dir": os.path.join(self.ws_dir, "input_contacts"),
            "contacts_dir": os.path.join(self.ws_dir, "contacts"),
            "mapping_file": os.path.join(self.ws_dir, "contacts", "mapping.json"),
            "contacts_file": os.path.join(self.ws_dir, "contacts", "contacts.txt"),
            "selected_extraction_contacts_file": os.path.join(
                self.ws_dir, "contacts", "selected_extraction_contacts.txt"
            ),
        }
        mgr = DuplicateFilesManager(paths)
        items = mgr.find_duplicate_items()
        self.assertEqual(len(items), 4)
        self.assertTrue(os.path.isfile(mgr.cache_file))

        kept_c, ign_c = mgr.save_selection(items)
        self.assertEqual((kept_c, ign_c), (2, 2))

        importer = ContactCatalogImporter(paths, os.path.join(self.ws_dir, "config.ini"))
        sms_mgr = SmsFilterManager(paths, importer)
        chat_mgr = ChatFilterManager(paths, importer)
        self.assertEqual(len(sms_mgr.list_export_files()), 1)
        self.assertEqual(chat_mgr.list_export_files(), [])
    def test_gui_duplicates_page_flow_and_back_navigation(self) -> None:
        """Vérifie le parcours Pièces -> Doublons -> Contacts -> Retour -> Doublons."""
        orig_root: str = gui_anonymizer.ROOT_DIR
        gui_anonymizer.ROOT_DIR = self.tmp_root
        try:
            app = gui_anonymizer.AnonymizerGuiApp()
            app.withdraw()
            app._sync_docs_tasks = True  # type: ignore[attr-defined]
        except tk.TclError as exc:
            gui_anonymizer.ROOT_DIR = orig_root
            self.skipTest(f"Environnement headless : {exc}")

        try:
            app.gate_new_name_var.set("Dossier_Doublons_GUI")
            app._confirm_gate_and_workspace()
            paths = app.controller.resolve_workspace_paths(app.current_ini_var.get())

            for idx in (1, 2):
                p_doc: str = os.path.join(paths["sources_dir"], f"attestation_{idx}.txt")
                with open(p_doc, "w", encoding="utf-8") as f_t:
                    f_t.write("Document strictement identique pour Utilisateur_A.\n")

            app._advance_from_documents()
            self.assertEqual(app.active_page_key, "duplicates")
            self.assertEqual(len(app.duplicate_filter_tree.get_children()), 2)

            app._save_duplicates_and_continue()
            self.assertEqual(app.active_page_key, "setup")

            app._go_back_from_setup()
            self.assertEqual(app.active_page_key, "duplicates")
        finally:
            app.destroy()
            gui_anonymizer.ROOT_DIR = orig_root


if __name__ == "__main__":
    unittest.main()
