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

from tools import run_tests_clip as rtc


class TestRunnerAndUrlsGuard(unittest.TestCase):
    """Vérifie run_tests_clip (déduplication, warnings, couverture) et les règles d'affichage."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_runner_guard_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_compact_error_report_deduplicates_and_extracts_warnings(self) -> None:
        raw_out: str = (
            "======================================================================\n"
            "ERROR: test_one (tests.test_demo.Suite)\n"
            "----------------------------------------------------------------------\n"
            "Traceback (most recent call last):\n"
            f'  File "{os.path.join(ROOT_DIR, "tools", "run_tests_clip.py")}", line 10\n'
            "ValueError: boom_identique\n"
            "======================================================================\n"
            "ERROR: test_two (tests.test_demo.Suite)\n"
            "----------------------------------------------------------------------\n"
            "Traceback (most recent call last):\n"
            f'  File "{os.path.join(ROOT_DIR, "tools", "run_tests_clip.py")}", line 10\n'
            "ValueError: boom_identique\n"
            "----------------------------------------------------------------------\n"
            "Ran 2 tests in 0.01s\n"
            "FAILED (errors=2)\n"
        )
        compacted: str = rtc.compact_error_report(raw_out)
        self.assertIn("ERROR: test_one", compacted)
        self.assertIn("[DOUBLON] ERROR: test_two", compacted)
        self.assertIn("FAILED (errors=2)", compacted)

        warn_sample: str = (
            "sample.py:12: ResourceWarning: unclosed file\n"
            "sample.py:12: ResourceWarning: unclosed file\n"
            "sample.py:20: DeprecationWarning: old call\n"
        )
        warns: str = rtc.extract_warnings_and_console_errors(warn_sample)
        self.assertEqual(len(warns.splitlines()), 2)
    def test_extract_coverage_section_and_main_writes_report_files(self) -> None:
        fake_stdout: str = (
            "  [OK] test_demo (1 test(s))\n"
            "=== 3. COUVERTURE (1 tests unitaires + .mbox) ===\n"
            "Module | Couv. | Statut | Lignes\n"
            "COUVERTURE GLOBALE | 92.5%\n"
            "=== CHRONOMÉTRAGE DES TESTS ===\n"
            "TEMPS TESTS : Unitaires 0.10s | Intégration .mbox 0.05s | Total 0.15s\n"
        )
        cov_txt: str = rtc.extract_coverage_section(fake_stdout)
        self.assertIn("COUVERTURE GLOBALE | 92.5%", cov_txt)
        self.assertNotIn("CHRONOMÉTRAGE", cov_txt)

        rep_file: str = os.path.join(self.tmp_dir, "rep.txt")
        cov_file: str = os.path.join(self.tmp_dir, "cov.txt")

        class _FakeProc:
            def __init__(self) -> None:
                self.stdout = iter(fake_stdout.splitlines(keepends=True))

            def wait(self) -> int:
                return 0

        argv_test = [
            "run_tests_clip.py",
            "--no-clipboard",
            "--report-file",
            rep_file,
            "--coverage-file",
            cov_file,
        ]
        with patch.object(sys, "argv", argv_test), patch(
            "subprocess.Popen", return_value=_FakeProc()
        ):
            rc: int = rtc.main()

        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(rep_file))
        self.assertTrue(os.path.isfile(cov_file))
        with open(cov_file, "r", encoding="utf-8") as f_c:
            self.assertIn("92.5%", f_c.read())

    def test_python_sources_contain_no_literal_triple_backticks(self) -> None:
        """Garantit l'absence de triples backticks littéraux qui cassent les blocs IA."""
        triple_bt: str = chr(96) * 3
        for folder in ("common", "doc_anonymizer", "google_contacts_parser", "tools", "tests"):
            base_p: str = os.path.join(ROOT_DIR, folder)
            if not os.path.isdir(base_p):
                continue
            for rp, _, files in os.walk(base_p):
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    fp: str = os.path.join(rp, fn)
                    with open(fp, "r", encoding="utf-8", errors="replace") as f_in:
                        self.assertNotIn(triple_bt, f_in.read(), f"Triple backtick littéral dans {fp}")


if __name__ == "__main__":
    unittest.main()
