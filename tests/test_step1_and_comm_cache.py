import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.duplicate_files_manager import DuplicateFilesManager
from doc_anonymizer.extraction_runner import DocumentExtractionRunner
from doc_anonymizer.gui_controller import AnonymizerGuiController


class TestStep1AndCommCache(unittest.TestCase):
    """Vérifie le cache des doublons à la réouverture et l'indexation SMS."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_step1_cache_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "prenoms.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        self.ctrl = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_step1_duplicate_scan_skips_recheck_when_unchanged(self) -> None:
        ini_p: str = self.ctrl.create_workspace("Dossier_Cache_Doublons")
        ext_dir: str = os.path.join(self.tmp_root, "archives_ext")
        os.makedirs(ext_dir, exist_ok=True)
        for name in ("copie_1.txt", "copie_2.txt"):
            with open(os.path.join(ext_dir, name), "w", encoding="utf-8") as f_t:
                f_t.write("Contenu identique pour test cache doublons.\n")

        self.ctrl.register_or_copy_sources(ini_p, [ext_dir], copy_external=False)
        _, _, dups_1 = self.ctrl.ws_manager.scan_workspace_step1(ini_p)
        self.assertEqual(len(dups_1), 2)

        with patch.object(DuplicateFilesManager, "find_duplicate_items") as mock_dup:
            _, _, dups_2 = self.ctrl.ws_manager.scan_workspace_step1(ini_p)
            mock_dup.assert_not_called()
            self.assertEqual(len(dups_2), 2)

        with open(os.path.join(ext_dir, "nouveau.txt"), "w", encoding="utf-8") as f_n:
            f_n.write("Nouveau fichier modifiant le dossier.\n")
        _, _, dups_3 = self.ctrl.ws_manager.scan_workspace_step1(ini_p)
        self.assertEqual(len(dups_3), 2)

    def test_sms_extraction_uses_disk_index_cache(self) -> None:
        ini_p: str = self.ctrl.create_workspace("Dossier_Cache_SMS")
        paths = self.ctrl.resolve_workspace_paths(ini_p)
        sms_xml: str = os.path.join(paths["sources_dir"], "sms_test.xml")
        with open(sms_xml, "w", encoding="utf-8") as f_s:
            f_s.write(
                '<smses><sms address="0600000001" date="1718442000000" '
                'type="1" body="Message SMS mis en cache." /></smses>'
            )
        cfg = PipelineConfig(ini_p)
        runner = DocumentExtractionRunner(cfg)
        out_1 = runner.process_single_file(sms_xml, {}, set(), set(), set(), set(), set())
        self.assertEqual(len(out_1), 1)
