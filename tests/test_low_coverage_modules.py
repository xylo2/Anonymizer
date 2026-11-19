# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import pymupdf
from common.core_utils import SharedCoreUtils
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.power_manager import SystemSleepInhibitor
from google_contacts_parser.geo_data import FrenchGeoCatalog
from tools.complete_manual_contacts import ManualContactsAutoCompleter
from tools.generate_pdf_guide import MarkdownPdfConverter


class TestLowCoverageModules(unittest.TestCase):
    """
    Cible les 6 modules sous les 70 % de couverture : power_manager,
    office_extractors, complete_manual_contacts, core_utils, geo_data
    et generate_pdf_guide.
    """

    def setUp(self) -> None:
        """Prépare un répertoire temporaire isolé."""
        self.test_dir: str = tempfile.mkdtemp(prefix="test_low_cov_")
        self.ini_path: str = os.path.join(self.test_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f:
            f.write(
                "[files]\n"
                "first_names_file = prenoms.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "manual_contacts_file = contacts_manuels.txt\n"
                "[extraction]\n"
                "enable_ocr = false\n"
            )
        with open(os.path.join(self.test_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("jean\nmarie\naurelien\n")
        self.config: PipelineConfig = PipelineConfig(self.ini_path)

    def tearDown(self) -> None:
        """Nettoie le répertoire temporaire."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_power_manager_and_core_utils_branches(self) -> None:
        """
        Couvre le repli Windows sans AwayMode, l'arrêt forcé kill() Linux
        et les primitives SharedCoreUtils (prevent_sleep, load_locations_set, atomic_write).
        """
        fake_kernel32 = MagicMock()
        fake_kernel32.SetThreadExecutionState.side_effect = [0, 1]
        with patch.object(os, "name", "nt"), patch(
            "ctypes.windll", create=True
        ) as mock_windll:
            mock_windll.kernel32 = fake_kernel32
            inh = SystemSleepInhibitor(enabled=True, refresh_interval=10.0)
            res: int = inh._apply_windows_state()
            self.assertEqual(res, 1)
            self.assertEqual(fake_kernel32.SetThreadExecutionState.call_count, 2)

            SharedCoreUtils.prevent_sleep(True)
            SharedCoreUtils.prevent_sleep(False)

        fake_proc = MagicMock()
        fake_proc.terminate.side_effect = RuntimeError("timeout")
        with patch.object(os, "name", "posix"), patch.object(
            sys, "platform", "linux"
        ), patch("shutil.which", return_value="/usr/bin/systemd-inhibit"), patch(
            "subprocess.Popen", return_value=fake_proc
        ):
            linux_inh = SystemSleepInhibitor(enabled=True)
            with linux_inh:
                pass
            fake_proc.kill.assert_called_once()

        locs_file: str = os.path.join(self.test_dir, "villes.txt")
        with open(locs_file, "w", encoding="utf-8") as f_l:
            f_l.write("# Commentaire\nHérouville-Saint-Clair\nCaen\n")
        loaded_locs = SharedCoreUtils.load_locations_set(locs_file)
        self.assertIn("caen", loaded_locs)
        self.assertIn("herouville-saint-clair", loaded_locs)
        self.assertEqual(SharedCoreUtils.normalize_token("  Été! "), "ete")
        self.assertEqual(SharedCoreUtils.normalize_identifier(""), "")

        geo_set = FrenchGeoCatalog.build_normalized_set({"Village-Test"})
        self.assertIn("villagetest", geo_set)
        self.assertIn("paris", geo_set)
        self.assertIn("normandie", geo_set)
    def test_office_extractors_ocr_mock_and_error_cases(self) -> None:
        """
        Couvre les branches OCR (PDF scanné et image) avec moteur mocké
        ainsi que les fichiers vides ou introuvables dans OfficeAndDocumentExtractor.
        """
        ext = OfficeAndDocumentExtractor(enable_ocr=True)
        ext._ocr_engine = lambda img_bytes: (  # type: ignore[assignment]
            ["Texte reconnu par OCR", "Ligne 2 OCR"],
            None,
        )

        img_path: str = os.path.join(self.test_dir, "scan.png")
        with open(img_path, "wb") as f_img:
            f_img.write(b"\x89PNG\(\r\\)n\x1a\nfake")
        txt_img, err_img = ext.extract_image(img_path)
        self.assertIsNone(err_img)
        assert txt_img is not None
        self.assertIn("Texte reconnu par OCR", txt_img)

        scanned_pdf: str = os.path.join(self.test_dir, "scan.pdf")
        doc = pymupdf.open()
        doc.new_page()
        doc.save(scanned_pdf)
        doc.close()
        txt_pdf, err_pdf = ext.extract_pdf(scanned_pdf, "scan.pdf")
        self.assertIsNone(err_pdf)
        assert txt_pdf is not None
        self.assertIn("(OCR)", txt_pdf)

        empty_txt: str = os.path.join(self.test_dir, "vide.txt")
        with open(empty_txt, "w", encoding="utf-8") as f_e:
            f_e.write("   \n")
        _, err_txt = ext.extract_text_or_markdown(empty_txt)
        self.assertIsNotNone(err_txt)

        empty_html: str = os.path.join(self.test_dir, "vide.html")
        with open(empty_html, "w", encoding="utf-8") as f_h:
            f_h.write("<html><script>var x=1;</script></html>")
        _, err_html = ext.extract_html(empty_html)
        self.assertIsNotNone(err_html)

        _, err_missing = ext.extract_docx(os.path.join(self.test_dir, "absent.docx"))
        self.assertIsNotNone(err_missing)

    def test_manual_completer_edge_cases_and_pdf_guide_markdown(self) -> None:
        """
        Couvre les variantes d'identifiants, noms inversés/composés et noms seuls
        dans ManualContactsAutoCompleter, ainsi que tous les éléments Markdown de
        MarkdownPdfConverter (titres H1-H4, citations, listes ol/ul, blocs code, HR).
        """
        with open(self.config.manual_contacts_file, "w", encoding="utf-8") as f_m:
            f_m.write(
                "# En-tête\n"
                "Dupont Jean = \n"
                "Jean-Marie De La Tour = \n"
                "contact.test@exemple.fr = \n"
                "06 11 22 33 44 = \n"
                "Aurélien = \n"
                "Entreprise = \n"
                " = ValeurDroiteSeule\n"
            )

        completer = ManualContactsAutoCompleter(self.config, dry_run=False)
        done, total = completer.process()
        self.assertEqual(total, 7)
        self.assertEqual(done, 7)

        with open(self.config.manual_contacts_file, "r", encoding="utf-8") as f_m:
            res_manual: str = f_m.read()
        self.assertIn("Dupont Jean = Jean D.", res_manual)
        self.assertIn("Jean-Marie De La Tour = Jean-Marie T.", res_manual)
        self.assertIn("contact.test@exemple.fr = Contact_Mail_001", res_manual)
        self.assertIn("06 11 22 33 44 = Contact_Tel_002", res_manual)
        self.assertIn("Aurélien = Aurélien X.", res_manual)
        self.assertIn("Entreprise = E.", res_manual)
        self.assertIn("ValeurDroiteSeule = V.", res_manual)

        rich_md: str = os.path.join(self.test_dir, "complet.md")
        rich_pdf: str = os.path.join(self.test_dir, "complet.pdf")
        with open(rich_md, "w", encoding="utf-8") as f_md:
            f_md.write(
                "# Titre 1\n## Titre 2\n### Titre 3\n#### Titre 4\n"
                "> Citation avec `code` et *italique* et [lien](https://exemple.fr)\n"
                "---\n"
                "- Puce 1\n- Puce 2\n\n"
                "1. Étape 1\n2. Étape 2\n\n"
                "```python\n# Commentaire préservé\n---\nx = 1\n```\n"
            )
        MarkdownPdfConverter.convert(md_path=rich_md, pdf_path=rich_pdf, footer_label="DocTest")
        self.assertTrue(os.path.exists(rich_pdf))


if __name__ == "__main__":
    unittest.main()
