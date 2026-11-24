# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.extractors.pdf_extractor import PdfDocumentExtractor


class TestOcrUnderscoreAndPhoneFixes(unittest.TestCase):
    """
    Vérifie les correctifs automatiques dans le code :
    - noms avec underscores dans les chemins de fichiers (Léo_Valmont, Sophie_VALMONT)
    - titres médicaux collés en OCR (DocteurLamotte, DrClaireMERCIER)
    - numéros dictés avec virgules ou slashs
    - aplatissement des cellules de tableaux imbriquées dans PdfDocumentExtractor
    """

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_ocr_fixes_")
        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("camille\nleo\nléo\nsophie\nclaire\nmarc\n")
        with open(os.path.join(self.tmp_dir, "contacts.txt"), "w", encoding="utf-8") as f:
            f.write("06 11 22 33 44=Camille D.\n")

        self.ini_path: str = os.path.join(self.tmp_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f_ini:
            f_ini.write(
                "[files]\n"
                "first_names_file = prenoms.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = input_documents\n"
                "transcriptions_dir = extracted_texts\n"
                "results_dir = anonymized_results\n"
                "contacts_file = contacts.txt\n"
                "audit_report_file = audits/residual_names_audit.txt\n"
                "audit_copy_file = audits/residual_names_copy.txt\n"
            )
        self.config: PipelineConfig = PipelineConfig(self.ini_path)
        self.runner: DocumentAnonymizationRunner = DocumentAnonymizationRunner(self.config)
        self.runner.initialize()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_underscore_filenames_and_glued_titles(self) -> None:
        """Vérifie le masquage des chemins avec underscores et titres OCR collés."""
        sample: str = (
            "extracted_texts\\2024-08\\Audio\\Léo_Valmont_20240801.txt\n"
            "extracted_texts\\2024-08\\Audio\\Sophie_VALMONT_20240802.txt\n"
            "Consultation DocteurLamotte et DrClaireMERCIER puis DUPONT DE TOUR Marc."
        )
        out: str = self.runner.anonymize_text(sample)
        self.assertNotIn("Valmont", out)
        self.assertNotIn("VALMONT", out)
        self.assertIn("Léo_V.", out)
        self.assertIn("Sophie_V.", out)
        self.assertIn("Docteur L.", out)
        self.assertIn("Dr Claire M.", out)
        self.assertIn("D. Marc", out)

    def test_whisper_comma_and_slash_phones(self) -> None:
        """Vérifie le masquage des numéros dictés avec virgules ou slashs."""
        sample: str = (
            "Appelez au 06, 11, 22, 33, 44 ou au 06/55/66/77/88 ou 01 23456789."
        )
        out: str = self.runner.anonymize_text(sample)
        self.assertIn("Camille D.", out)
        self.assertNotIn("06/55/66/77/88", out)
        self.assertNotIn("23456789", out)
        self.assertIn("TEL_001", out)
        self.assertIn("TEL_002", out)

    def test_pdf_nested_list_cell_flattening(self) -> None:
        """Vérifie que _flatten_cell_text gère les listes imbriquées sans TypeError."""
        nested = ["Ligne 1", ["Sous-cellule A", None, "Sous-cellule B"]]
        flat: str = PdfDocumentExtractor._flatten_cell_text(nested)
        self.assertEqual(flat, "Ligne 1 Sous-cellule A Sous-cellule B")


if __name__ == "__main__":
    unittest.main()
