# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import tempfile
from typing import Dict, Set
import unittest
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.extraction_runner import DocumentExtractionRunner
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.first_name_suggester import MissingFirstNamesSuggester


class TestEdgeCasesAndAudio(unittest.TestCase):
    """
    Tests de robustesse sur les fichiers corrompus, le découpage multi-lots
    (batch_01/batch_02) et la suggestion automatique de prénoms.
    """

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_edge_audio_")
        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("jean\nclaire\nsophie\n")
        with open(os.path.join(self.tmp_dir, "villes_masquees.txt"), "w", encoding="utf-8") as f:
            f.write("caen\n")
        with open(os.path.join(self.tmp_dir, "contacts.txt"), "w", encoding="utf-8") as f:
            f.write("Jean Dupont = Jean D.\nClaire Bernard = Claire B.\n")

        self.ini_path: str = os.path.join(self.tmp_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f_ini:
            f_ini.write(
                "[files]\n"
                "first_names_file = prenoms.txt\n"
                "locations_file = villes_masquees.txt\n"
                "suggested_first_names_file = output_contacts/.intermediates/suggested_first_names.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = fichiers_sources\n"
                "transcriptions_dir = transcriptions\n"
                "results_dir = resultats_anonymisation\n"
                "contacts_file = contacts.txt\n"
                "manual_contacts_file = manual_contacts.txt\n"
                "discovered_contacts_file = discovered_email_contacts.txt\n"
                "discovered_chats_file = discovered_chat_contacts.txt\n"
                "audit_report_file = residual_names_audit.txt\n"
                "audit_copy_file = residual_names_copy.txt\n"
                "[anonymization]\n"
                "file_prefix = anonymized_\n"
                "max_batch_bytes = 184320\n"
                "files_per_folder = 10\n"
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_corrupted_archives_and_unsupported_binary_files(self) -> None:
        """Vérifie que les archives corrompues et binaires inconnus sont ignorés sans crash."""
        src_dir = os.path.join(self.tmp_dir, "fichiers_sources", "Divers")
        os.makedirs(src_dir, exist_ok=True)
        with open(os.path.join(src_dir, "corrompu.pdf"), "wb") as f_pdf:
            f_pdf.write(b"NOT_A_VALID_PDF_HEADER")
        with open(os.path.join(src_dir, "inconnu.bin"), "wb") as f_bin:
            f_bin.write(b"\x00\x01\x02\x03")

        cfg = PipelineConfig(self.ini_path)
        os.makedirs(cfg.transcriptions_dir, exist_ok=True)
        extractor = DocumentExtractionRunner(cfg)
        already: Set[str] = set()
        sms_done: Set[str] = set()
        disc_phones: Dict[str, str] = {}
        disc_emails: Dict[str, str] = {}
        for fname in os.listdir(src_dir):
            extractor.process_single_file(
                os.path.join(src_dir, fname),
                {},
                set(),
                already,
                sms_done,
                disc_phones,
                disc_emails,
            )
        self.assertTrue(os.path.isdir(cfg.transcriptions_dir))
    def test_large_chunk_splitting_multi_batch_and_first_name_suggester(self) -> None:
        """Vérifie le découpage > 32 Ko, la rotation de dossiers batch_01/batch_02 et les suggestions."""
        with open(self.ini_path, "r", encoding="utf-8") as f:
            ini_content = f.read()
        with open(self.ini_path, "w", encoding="utf-8") as f:
            f.write(
                ini_content.replace("max_batch_bytes = 184320", "max_batch_bytes = 35000")
                .replace("files_per_folder = 10", "files_per_folder = 1")
            )

        cfg = PipelineConfig(self.ini_path)
        runner = DocumentAnonymizationRunner(cfg)

        trans_doc_dir = os.path.join(self.tmp_dir, "transcriptions", "2024-06", "Documents")
        os.makedirs(trans_doc_dir, exist_ok=True)
        paragraph = (
            "Compte rendu détaillé avec Jean Dupont et Claire Bernard "
            "concernant le suivi administratif et médical du dossier. " * 12 + "\n"
        )
        for idx in (1, 2):
            with open(os.path.join(trans_doc_dir, f"gros_document_{idx}.txt"), "w", encoding="utf-8") as f:
                f.write(paragraph * 35)

        runner.run()

        lot1_dir = os.path.join(self.tmp_dir, "resultats_anonymisation", "batch_01")
        lot2_dir = os.path.join(self.tmp_dir, "resultats_anonymisation", "batch_02")
        self.assertTrue(os.path.isdir(lot1_dir))
        self.assertTrue(os.path.isdir(lot2_dir))

        from google_contacts_parser.pipeline_runner import ContactsPipelineRunner
        c_cfg = ContactsConfig(self.ini_path)
        os.makedirs(c_cfg.csv_directory, exist_ok=True)
        with open(os.path.join(c_cfg.csv_directory, "contacts_test.csv"), "w", encoding="utf-8", newline="") as f_csv:
            f_csv.write(
                "First Name,Last Name,E-mail 1 - Value\n"
                "Xénophon,Valmont,xenophon@exemple.fr\n"
                "Jean,Dupont,jean@exemple.fr\n"
                "Zéphyrine,Moreau,zephyrine@exemple.fr\n"
            )
        ContactsPipelineRunner(config=c_cfg).run_all()
        sug_file = os.path.join(
            self.tmp_dir, "output_contacts", ".intermediates", "suggested_first_names.txt"
        )
        self.assertTrue(os.path.exists(sug_file))
        with open(sug_file, "r", encoding="utf-8") as f:
            sug_txt = f.read()
        self.assertIn("xénophon", sug_txt)
        self.assertIn("zéphyrine", sug_txt)


if __name__ == "__main__":
    unittest.main()
