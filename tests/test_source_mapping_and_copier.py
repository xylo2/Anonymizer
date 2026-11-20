# Commandes pip à exécuter : Aucune dépendance externe requise

import json
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
import run_documents


class TestSourceMappingAndCopier(unittest.TestCase):
    """
    Valide la génération du dictionnaire JSON (source_files_mapping.json) reliant
    les fichiers anonymisés aux transcriptions extraites et aux sources brutes,
    ainsi que la copie sélective via run_documents.py --copy-unmasked.
    """

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_src_map_")
        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("camille\njean\n")
        with open(os.path.join(self.tmp_dir, "contacts.txt"), "w", encoding="utf-8") as f:
            f.write("Camille Dupont = Camille D.\n")

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

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_mapping_json_creation_and_unmasked_copy_cli(self) -> None:
        """
        Vérifie la création de source_files_mapping.json et la copie des
        transcriptions brutes via run_documents.py --copy-unmasked.
        """
        raw_src_dir: str = os.path.join(self.config.sources_dir, "Audio")
        os.makedirs(raw_src_dir, exist_ok=True)
        orig_audio: str = os.path.join(raw_src_dir, "Camille Dupont 20260910.mp3")
        with open(orig_audio, "wb") as f_aud:
            f_aud.write(b"FAKE_MP3")

        trans_sub: str = os.path.join(self.config.transcriptions_dir, "2026-09", "Audio")
        os.makedirs(trans_sub, exist_ok=True)
        extracted_txt: str = os.path.join(trans_sub, "Camille Dupont 20260910.txt")
        with open(extracted_txt, "w", encoding="utf-8") as f_tr:
            f_tr.write(
                "========================================\n"
                "AUDIO : Camille Dupont 20260910.mp3\n"
                "----------------------------------------\n"
                "[00:01] Bonjour Camille Dupont.\n"
            )

        runner = DocumentAnonymizationRunner(self.config)
        runner.run()

        mapping_path: str = os.path.join(
            os.path.dirname(self.config.audit_report_file),
            "source_files_mapping.json",
        )
        self.assertTrue(os.path.exists(mapping_path))
        with open(mapping_path, "r", encoding="utf-8") as f_map:
            mapping_data = json.load(f_map)

        files_dict = mapping_data["files"]
        self.assertEqual(len(files_dict), 1)
        anon_key: str = next(iter(files_dict.keys()))
        self.assertIn("Camille D.", anon_key)
        self.assertEqual(files_dict[anon_key]["extracted_file"], os.path.normpath(extracted_txt))
        self.assertEqual(files_dict[anon_key]["original_source_file"], os.path.normpath(orig_audio))

        list_md: str = os.path.join(self.tmp_dir, "a_revoir.md")
        with open(list_md, "w", encoding="utf-8") as f_md:
            f_md.write(f"* `{anon_key}`\n")

        out_copy_dir: str = os.path.join(self.tmp_dir, "copie_bruts_cli")
        rc: int = run_documents.main(
            [
                "-c",
                self.ini_path,
                "--copy-unmasked",
                list_md,
                "--unmasked-dir",
                out_copy_dir,
            ]
        )
        self.assertEqual(rc, 0)
        copied_file: str = os.path.join(out_copy_dir, "2026-09", "Audio", "Camille Dupont 20260910.txt")
        self.assertTrue(os.path.exists(copied_file))


if __name__ == "__main__":
    unittest.main()
