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
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner


class TestCalendarIcsEndToEnd(unittest.TestCase):
    """Vérifie l'extraction et l'anonymisation de bout en bout d'un agenda .ics."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_ics_e2e_")
        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("camille\nmarc\n")
        with open(os.path.join(self.tmp_dir, "villes.txt"), "w", encoding="utf-8") as f:
            f.write("lyon\n")
        self.ini_path: str = os.path.join(self.tmp_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f_ini:
            f_ini.write(
                "[files]\n"
                "first_names_file = prenoms.txt\n"
                "locations_file = villes.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = input_documents\n"
                "transcriptions_dir = extracted_texts\n"
                "results_dir = anonymized_results\n"
                "contacts_file = contacts.txt\n"
                "[extraction]\n"
                "enable_ocr = false\n"
                "enable_audio = false\n"
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_ics_calendar_extraction_and_anonymization(self) -> None:
        """Vérifie qu'un export agenda .ics est classé dans Agendas/ et anonymisé."""
        src_dir: str = os.path.join(self.tmp_dir, "input_documents")
        os.makedirs(src_dir, exist_ok=True)
        ics_path: str = os.path.join(src_dir, "agenda_medical.ics")
        with open(ics_path, "w", encoding="utf-8") as f_ics:
            f_ics.write(
                "BEGIN:VCALENDAR\n"
                "BEGIN:VEVENT\n"
                "DTSTART:20240615T090000Z\n"
                "SUMMARY:Bilan orthophonique Camille Dupont\n"
                "DESCRIPTION:Rendez-vous avec Dr Valmont à Lyon\n"
                "END:VEVENT\n"
                "END:VCALENDAR\n"
            )

        cfg = PipelineConfig(self.ini_path)
        DocAnonymizerPipelineRunner(config=cfg, prevent_sleep=False).run_all()

        agenda_dir: str = os.path.join(cfg.transcriptions_dir, "2024-06", "Agendas")
        self.assertTrue(os.path.isdir(agenda_dir))

        chunks: list[str] = []
        for rp, _, files in os.walk(cfg.results_dir):
            for fn in files:
                if fn.endswith(".txt"):
                    with open(os.path.join(rp, fn), "r", encoding="utf-8") as f_res:
                        chunks.append(f_res.read())
        res_txt: str = "\n".join(chunks)
        self.assertIn("Camille D.", res_txt)
        self.assertIn("Dr V.", res_txt)
        self.assertNotIn("Camille Dupont", res_txt)


if __name__ == "__main__":
    unittest.main()
