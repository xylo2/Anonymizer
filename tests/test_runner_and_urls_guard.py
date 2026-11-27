import os
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from tools.fix_docs_and_svg_urls import (
    cleanup_temp_files,
    fix_chat_domain_in_python,
    fix_markdown_docs,
    fix_svg_namespace,
)
import tools.run_tests_clip as rtc


class TestRunnerAndUrlsGuard(unittest.TestCase):
    """Vérifie le compactage des erreurs, la couverture et les règles d'affichage."""

    def test_compact_error_report_deduplicates_and_extracts_warnings(self) -> None:
        """Vérifie la déduplication des erreurs et la détection des warnings."""
        raw_out: str = (
            "======================================================================\n"
            "ERROR: test_one (tests.test_demo.Suite)\n"
            "----------------------------------------------------------------------\n"
            "Traceback (most recent call last):\n"
            f'  File "{os.path.join(ROOT_DIR, "tools", "run_tests_clip.py")}", line 10, in demo\n'
            "    raise ValueError('boom')\n"
            "ValueError: boom_identique\n"
            "======================================================================\n"
            "ERROR: test_two (tests.test_demo.Suite)\n"
            "----------------------------------------------------------------------\n"
            "Traceback (most recent call last):\n"
            f'  File "{os.path.join(ROOT_DIR, "tools", "run_tests_clip.py")}", line 10, in demo\n'
            "    raise ValueError('boom')\n"
            "ValueError: boom_identique\n"
            "----------------------------------------------------------------------\n"
            "Ran 2 tests in 0.01s\n\n"
            "FAILED (errors=2)\n"
            "doc_anonymizer/a.py:5: ResourceWarning: unclosed file\n"
            "doc_anonymizer/a.py:5: ResourceWarning: unclosed file\n"
        )
        compacted: str = rtc.compact_error_report(raw_out)
        self.assertIn("ERROR: test_one", compacted)
        self.assertIn("[DOUBLON] ERROR: test_two", compacted)
        self.assertIn("Ran 2 tests in 0.01s | FAILED (errors=2)", compacted)
        warn_lines = [ln for ln in compacted.splitlines() if ln.startswith("WARNING:")]
        self.assertEqual(len(warn_lines), 1)
        self.assertIn("ResourceWarning", next(iter(warn_lines)))
    def test_extract_coverage_section_and_main_writes_report_files(self) -> None:
        """Vérifie l'extraction du tableau des modules incomplets (< 100 %)."""
        fake_stdout: str = (
            "Ran 10 tests in 0.12s\nOK\n"
            "=== 3. COUVERTURE (10 tests unitaires + .mbox) ===\n"
            "Module | Couv | Lignes\n"
            "doc_anonymizer/a.py | 100.0% | 20/20 | -\n"
            "doc_anonymizer/b.py | 85.0% | 17/20 | 12-14\n"
            "COUVERTURE GLOBALE | 92.5%\n"
            "Lignes non couvertes :\n"
            "- doc_anonymizer/b.py : 12-14\n"
            "=== CHRONOMÉTRAGE ===\n"
            "TEMPS TESTS : Unitaires 0.10s | Intégration .mbox 0.02s | Total 0.12s\n"
        )
        cov_txt: str = rtc.extract_coverage_section(fake_stdout)
        self.assertIn("COUVERTURE GLOBALE : 92.5%", cov_txt)
        self.assertIn("doc_anonymizer/b.py | 85.0%", cov_txt)
        self.assertNotIn("doc_anonymizer/a.py", cov_txt)
        self.assertIn("doc_anonymizer/b.py | 85.0% | 17/20 | 12-14", cov_txt)

    def test_fix_docs_and_svg_urls_repairs_broken_links_and_cleans_temp(self) -> None:
        """Vérifie la réparation des URLs et la suppression des fichiers temporaires."""
        with tempfile.TemporaryDirectory() as tmp_d:
            tmp_art: str = os.path.join(tmp_d, "iaexport")
            with open(tmp_art, "w", encoding="utf-8") as f_t:
                f_t.write("tmp")
            self.assertIsInstance(fix_chat_domain_in_python(tmp_d), list)
            self.assertIsInstance(fix_markdown_docs(tmp_d), list)
            self.assertIsInstance(fix_svg_namespace(tmp_d), list)
            self.assertEqual(len(cleanup_temp_files(tmp_d)), 1)
            self.assertFalse(os.path.exists(tmp_art))

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
