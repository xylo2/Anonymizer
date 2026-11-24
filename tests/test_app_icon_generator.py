# Commandes pip à exécuter : pip install Pillow>=10.3.0

import os
import shutil
import sys
import tempfile
import tkinter as tk
import unittest
from PIL import Image

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import gui_anonymizer
from tools.generate_app_icon import AppIconGenerator


class TestAppIconGenerator(unittest.TestCase):
    """Vérifie la génération PNG/ICO d'AnonVault et son chargement dans la GUI."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_app_icon_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_export_vector_and_cropped_icons(self) -> None:
        png_p, ico_p = AppIconGenerator.export_icons(output_dir=self.tmp_dir)
        self.assertTrue(os.path.isfile(png_p))
        self.assertTrue(os.path.isfile(ico_p))
        with Image.open(png_p) as im:
            self.assertEqual(im.size, (512, 512))

        src_sample: str = os.path.join(self.tmp_dir, "sample_logo.png")
        sample = Image.new("RGBA", (200, 120), (255, 255, 255, 255))
        for x in range(60, 140):
            for y in range(20, 100):
                sample.putpixel((x, y), (37, 99, 235, 255))
        sample.save(src_sample)

        png_c, ico_c = AppIconGenerator.export_icons(
            output_dir=self.tmp_dir, base_name="custom_icon", source_image=src_sample
        )
        self.assertTrue(os.path.isfile(png_c))
        self.assertTrue(os.path.isfile(ico_c))

    def test_gui_loads_and_generates_window_icon(self) -> None:
        orig_root: str = gui_anonymizer.ROOT_DIR
        gui_anonymizer.ROOT_DIR = self.tmp_dir
        try:
            app = gui_anonymizer.AnonymizerGuiApp()
            app.withdraw()
        except tk.TclError as exc:
            gui_anonymizer.ROOT_DIR = orig_root
            self.skipTest(f"Environnement headless : {exc}")

        try:
            assets_dir: str = os.path.join(self.tmp_dir, "assets")
            self.assertTrue(os.path.isfile(os.path.join(assets_dir, "anonvault_icon.png")))
            self.assertTrue(os.path.isfile(os.path.join(assets_dir, "anonvault_icon.ico")))
            self.assertIsNotNone(getattr(app, "_app_icon_photo", None))
        finally:
            app.destroy()
            gui_anonymizer.ROOT_DIR = orig_root


if __name__ == "__main__":
    unittest.main()
