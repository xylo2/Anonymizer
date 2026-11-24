# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.chat_filter_manager import ChatFilterManager
from doc_anonymizer.contact_csv_importer import ContactCatalogImporter
from doc_anonymizer.gui_controller import AnonymizerGuiController


class TestPerformanceOptimizations(unittest.TestCase):
    """Vérifie le cache disque des conversations et la commande mono-processus."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_perf_opt_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "prenoms.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        self.ctrl = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_chat_filter_disk_cache_and_single_process_cli_flag(self) -> None:
        ini_path: str = self.ctrl.create_workspace("Dossier_Perf_Test")
        paths = self.ctrl.resolve_workspace_paths(ini_path)

        cmd = self.ctrl.build_cli_command(ini_path, "full_with_contacts")
        self.assertIn("--with-contacts", cmd)
        self.assertTrue(any(p.endswith("run_documents.py") for p in cmd))

        wa_file: str = os.path.join(paths["sources_dir"], "chat_exports", "Discussion_Test.txt")
        os.makedirs(os.path.dirname(wa_file), exist_ok=True)
        with open(wa_file, "w", encoding="utf-8") as f_w:
            f_w.write("12/06/2024, 10:00 - Utilisateur_A: Bonjour\n12/06/2024, 10:01 - Contact_Test_1: Salut\n")

        importer = ContactCatalogImporter(paths, ini_path)
        chat_mgr = ChatFilterManager(paths, importer)
        items_1 = chat_mgr.load_conversation_filter_items()
        self.assertEqual(len(items_1), 1)
        self.assertTrue(os.path.isfile(chat_mgr._get_cache_file_path()))

        items_2 = chat_mgr.load_conversation_filter_items()
        first_1 = next(iter(items_1))
        first_2 = next(iter(items_2))
        self.assertEqual(first_2["conversation"], first_1["conversation"])


if __name__ == "__main__":
    unittest.main()
