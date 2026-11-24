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


class TestAutoSurnameAndInitials(unittest.TestCase):
    """Vérifie le masquage automatique des noms (FR/EN/PT), titres et voies."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_auto_surnames_")
        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("camille\nleo\nléo\nmarie\nsophie\nclaire\n")
        with open(os.path.join(self.tmp_dir, "contacts.txt"), "w", encoding="utf-8") as f:
            f.write(
                "camille.valmont@exemple.fr=Camille V.\n"
                "marie.delacroix@exemple.fr=Marie D.\n"
                "sophie.moreau@exemple.fr=Sophie M.\n"
            )
        with open(os.path.join(self.tmp_dir, "manual_contacts.txt"), "w", encoding="utf-8") as f:
            f.write("# Vide volontairement\n")

        self.ini_path: str = os.path.join(self.tmp_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f_ini:
            f_ini.write(
                "[files]\nfirst_names_file = prenoms.txt\n"
                "[paths]\nroot_dir = .\nsources_dir = input_documents\n"
                "transcriptions_dir = extracted_texts\nresults_dir = anonymized_results\n"
                "contacts_file = contacts.txt\nmanual_contacts_file = manual_contacts.txt\n"
                "audit_report_file = audits/residual_names_audit.txt\n"
                "audit_copy_file = audits/residual_names_copy.txt\n"
            )
        self.config: PipelineConfig = PipelineConfig(self.ini_path)
        self.runner: DocumentAnonymizationRunner = DocumentAnonymizationRunner(self.config)
        self.runner.initialize()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_auto_extracted_surnames_and_glued_ocr(self) -> None:
        sample: str = (
            "Dossier VALMONT et CAMILLEVALMONT, ainsi que SOCIETEDELACROIX "
            "et MOREAUSOPHIE. Suivi par V. COLLIN et Claire MERCIER DUPONT."
        )
        out: str = self.runner.anonymize_text(sample)
        for forbidden in ("VALMONT", "DELACROIX", "MOREAU", "COLLIN", "MERCIER"):
            self.assertNotIn(forbidden, out)
        self.assertIn("V. C.", out)
        self.assertIn("Claire M. D.", out)

    def test_english_and_portuguese_titles_and_streets(self) -> None:
        sample: str = (
            "Meeting with Mrs. Henderson at 42 Baker Street, "
            "and Dra. Oliveira at Rua das Flores 15."
        )
        out: str = self.runner.anonymize_text(sample)
        self.assertIn("Mrs. H.", out)
        self.assertIn("Dra. O.", out)
        self.assertNotIn("Baker Street", out)
        self.assertNotIn("Rua das Flores", out)
        self.assertIn("[ADRESSE_MASQUEE]", out)


if __name__ == "__main__":
    unittest.main()
