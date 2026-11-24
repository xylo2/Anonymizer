# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
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


class TestFixDocsAndSvgUrls(unittest.TestCase):
    """Vérifie la restauration des URLs, namespaces SVG et domaines internes."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_fix_urls_")
        os.makedirs(os.path.join(self.tmp_dir, "assets"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_dir, "doc_anonymizer"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_dir, "docs", "exports"), exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_restores_svg_python_and_markdown_links(self) -> None:
        svg_p: str = os.path.join(self.tmp_dir, "assets", "anonvault_icon.svg")
        with open(svg_p, "w", encoding="utf-8") as f_s:
            f_s.write('<svg xmlns="http://w3.org" viewBox="0 0 512 512"></svg>')
        self.assertEqual(fix_svg_namespace(self.tmp_dir), ["assets/anonvault_icon.svg"])
        with open(svg_p, "r", encoding="utf-8") as f_s2:
            self.assertIn("w3.org/2000/svg", f_s2.read())

        py_p: str = os.path.join(self.tmp_dir, "doc_anonymizer", "comm_extractors.py")
        broken_h: str = "://" + "google.com"
        expected_chat: str = "chat." + "google.com"
        with open(py_p, "w", encoding="utf-8") as f_p:
            f_p.write(f'if not x.endswith("{broken_h}"): pass\n')
        self.assertEqual(fix_chat_domain_in_python(self.tmp_dir), ["doc_anonymizer/comm_extractors.py"])
        with open(py_p, "r", encoding="utf-8") as f_p2:
            self.assertIn(expected_chat, f_p2.read())

        md_p: str = os.path.join(self.tmp_dir, "docs", "GUIDE_UTILISATION.md")
        expected_contacts: str = "contacts." + "google.com"
        with open(md_p, "w", encoding="utf-8") as f_m:
            f_m.write(f"| `{broken_h}` > **Exporter** |\n## 5. Exploitation\n")
        self.assertEqual(fix_markdown_docs(self.tmp_dir), ["docs/GUIDE_UTILISATION.md"])
        with open(md_p, "r", encoding="utf-8") as f_m2:
            content: str = f_m2.read()
            self.assertIn(expected_contacts, content)
            self.assertIn("--copy-unmasked", content)

        tmp_txt: str = os.path.join(self.tmp_dir, "iaexport")
        with open(tmp_txt, "w", encoding="utf-8") as f_t:
            f_t.write("tmp")
        self.assertEqual(cleanup_temp_files(self.tmp_dir), ["iaexport"])


if __name__ == "__main__":
    unittest.main()
