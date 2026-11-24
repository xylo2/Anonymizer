# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.contact_csv_importer import ContactCatalogImporter
from doc_anonymizer.gui_widgets import set_ui_font_scale
import gui_anonymizer


class TestPrewarmStep1CacheAndEntryFont(unittest.TestCase):
    """Vérifie le pré-scan silencieux, le cache de réouverture et le zoom des champs."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_prewarm_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "prenoms.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
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
        set_ui_font_scale(1.0)
        if hasattr(self, "app") and self.app is not None:
            try:
                self.app.destroy()
            except tk.TclError:
                pass
        gui_anonymizer.ROOT_DIR = self._orig_root
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_silent_prewarm_and_reopen_cache_skip(self) -> None:
        self.app.gate_new_name_var.set("Dossier_Test_2026")
        self.app._confirm_gate_and_workspace()
        ini_path: str = self.app.current_ini_var.get()
        paths = self.app.controller.resolve_workspace_paths(ini_path)

        ext_dir: str = os.path.join(self.tmp_root, "externe")
        os.makedirs(ext_dir, exist_ok=True)
        csv_p: str = os.path.join(ext_dir, "contacts.csv")
        with open(csv_p, "w", encoding="utf-8") as f_c:
            f_c.write("First Name,Last Name,E-mail 1 - Value\nCamille,Dupont,contact1@exemple.test\n")

        self.app._ingest_selected_paths([csv_p])
        cache_file: str = os.path.join(paths["workspace_root"], "audits", ".step1_scan_cache.json")
        self.assertTrue(os.path.isfile(cache_file))

        with patch.object(ContactCatalogImporter, "import_contact_file") as mock_imp:
            self.app._show_page("documents")
            self.app._advance_from_documents()
            mock_imp.assert_not_called()

        self.assertEqual(self.app.active_page_key, "setup")

    def test_entry_font_scales_with_ui_zoom(self) -> None:
        set_ui_font_scale(1.3)
        self.assertIn("14", str(self.app.entry_gate_new.cget("font")))


if __name__ == "__main__":
    unittest.main()
