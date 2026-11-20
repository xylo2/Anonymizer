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
    """
    Vérifie que les noms de famille issus de contacts.txt, les formes OCR collées,
    les préfixes collés (SOCIETE...), les initiales (I. NOM) et les noms composés
    sont masqués automatiquement sans aucune ligne dans manual_contacts.txt.
    """

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_auto_surnames_")
        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("aurelie\naurélie\nalois\naloïs\nmarie\nnathalie\nnelly\n")
        with open(os.path.join(self.tmp_dir, "contacts.txt"), "w", encoding="utf-8") as f:
            f.write(
                "aurelie.sobrero@acoss.fr=Aurélie S.\n"
                "marie.tiengou@exemple.fr=Marie T.\n"
                "nathalie.bach@exemple.fr=Nathalie B.\n"
            )
        with open(os.path.join(self.tmp_dir, "manual_contacts.txt"), "w", encoding="utf-8") as f:
            f.write("# Vide volontairement\n")

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
                "manual_contacts_file = manual_contacts.txt\n"
                "audit_report_file = audits/residual_names_audit.txt\n"
                "audit_copy_file = audits/residual_names_copy.txt\n"
            )
        self.config: PipelineConfig = PipelineConfig(self.ini_path)
        self.runner: DocumentAnonymizationRunner = DocumentAnonymizationRunner(self.config)
        self.runner.initialize()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_auto_extracted_surnames_and_glued_ocr(self) -> None:
        """Vérifie le masquage automatique des noms seuls et collés issus de contacts.txt."""
        sample: str = (
            "Dossier SOBRERO et ALOiSSOBRERO, ainsi que SOCIETETIENGOU "
            "et BACHNATHALIE. Suivi par V. COLLIN et Nelly ABITBOL CANO."
        )
        out: str = self.runner.anonymize_text(sample)
        self.assertNotIn("SOBRERO", out)
        self.assertNotIn("TIENGOU", out)
        self.assertNotIn("BACH", out)
        self.assertNotIn("COLLIN", out)
        self.assertNotIn("ABITBOL", out)
        self.assertIn("V. C.", out)
        self.assertIn("Nelly A. C.", out)


if __name__ == "__main__":
    unittest.main()
