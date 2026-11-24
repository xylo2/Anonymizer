# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from tools import install_desktop_shortcut as shortcut_mod


class TestInstallDesktopShortcut(unittest.TestCase):
    """Vérifie la création des lanceurs Windows (.lnk) et Linux (.desktop) avec icône."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_shortcut_")
        self.desktop_dir: str = os.path.join(self.tmp_dir, "Desktop")
        os.makedirs(self.desktop_dir, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_create_linux_desktop_entry(self) -> None:
        png_p: str = os.path.join(self.tmp_dir, "anonvault_icon.png")
        with open(png_p, "wb") as f_p:
            f_p.write(b"PNG")
        created: str = shortcut_mod.create_linux_desktop_entry(self.desktop_dir, png_p)
        self.assertTrue(os.path.isfile(created))
        with open(created, "r", encoding="utf-8") as f_in:
            txt: str = f_in.read()
        self.assertIn("Name=AnonVault — Pièces protégées", txt)
        self.assertIn(f"Icon={png_p}", txt)

    def test_create_windows_shortcut_invokes_powershell(self) -> None:
        ico_p: str = os.path.join(self.tmp_dir, "anonvault_icon.ico")
        with open(ico_p, "wb") as f_i:
            f_i.write(b"ICO_DATA")
        with patch("subprocess.run") as mock_run:
            lnk_p: str = shortcut_mod.create_windows_shortcut(self.desktop_dir, ico_p)
        self.assertEqual(mock_run.call_count, 2)
        self.assertTrue(lnk_p.endswith("AnonVault - Pièces protégées.lnk"))


if __name__ == "__main__":
    unittest.main()
