# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.gui_controller import AnonymizerGuiController
from doc_anonymizer.workspace_settings_dialog import WorkspaceSettingsManager


class TestWorkspaceSettings(unittest.TestCase):
    """Vérifie la lecture et l'enregistrement des paramètres de dossier dans config.ini."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_ws_settings_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "prenoms.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        self.ctrl = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_load_and_save_workspace_settings_roundtrip(self) -> None:
        ini_path: str = self.ctrl.create_workspace("Dossier_Parametres")
        defaults = WorkspaceSettingsManager.load_settings(ini_path)
        self.assertTrue(defaults["enable_ocr"])
        self.assertEqual(defaults["whisper_model"], "base")
        self.assertFalse(defaults["numbered_placeholders"])

        WorkspaceSettingsManager.save_settings(ini_path, {
            "masked_birth_dates": "14/07/1985, 02/05/2013",
            "extra_locations": "Ville-Alpha, Bourg-Beta",
            "numbered_placeholders": True,
            "mask_ssn": True,
            "mask_addresses": False,
            "mask_financial_and_admin_ids": True,
            "mask_urls": False,
            "enable_ocr": False,
            "enable_audio": True,
            "whisper_model": "small",
        })

        cfg = PipelineConfig(ini_path)
        self.assertEqual(cfg.masked_birth_dates, ["14/07/1985", "02/05/2013"])
        self.assertIn("ville-alpha", cfg.masked_locations)
        self.assertTrue(cfg.numbered_placeholders)
        self.assertFalse(cfg.mask_addresses)
        self.assertFalse(cfg.mask_urls)
        self.assertFalse(cfg.enable_ocr)
        self.assertEqual(cfg.whisper_model, "small")


if __name__ == "__main__":
    unittest.main()
