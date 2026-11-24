# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.chat_prescanner import ChatContactPrescanner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.extraction_runner import DocumentExtractionRunner


class TestOutlookArchivesExtraction(unittest.TestCase):
    """Vérifie l'extraction et le pré-scan des archives Outlook (.msg, .pst, .ost)."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_outlook_")
        self.src_dir: str = os.path.join(self.tmp_dir, "input_documents")
        os.makedirs(self.src_dir, exist_ok=True)
        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("camille\nmarc\nsophie\n")
        self.ini_path: str = os.path.join(self.tmp_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f_ini:
            f_ini.write(
                "[files]\nfirst_names_file = prenoms.txt\n"
                "[paths]\nroot_dir = .\nsources_dir = input_documents\n"
                "transcriptions_dir = extracted_texts\nresults_dir = anonymized_results\n"
                "contacts_file = contacts.txt\n"
                "discovered_contacts_file = discovered_email_contacts.txt\n"
                "discovered_chats_file = discovered_chat_contacts.txt\n"
                "[extraction]\nenable_ocr = false\nenable_audio = false\n"
            )
        self.config: PipelineConfig = PipelineConfig(self.ini_path)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_msg_and_pst_extraction_and_prescan(self) -> None:
        msg_path: str = os.path.join(self.src_dir, "courriel_rh.msg")
        pst_path: str = os.path.join(self.src_dir, "archive_outlook.pst")
        for p in (msg_path, pst_path):
            with open(p, "wb") as f_bin:
                f_bin.write(b"FAKE_OUTLOOK_BINARY")

        class FakeMsg:
            def __init__(self, _p: str) -> None:
                self.sender = "Marc Lefevre <marc.lefevre@entreprise.fr>"
                self.to = "Camille Dupont <camille@perso.fr>"
                self.cc = ""
                self.subject = "Convocation entretien"
                self.date = "Mon, 10 Jun 2024 09:00:00 +0200"
                self.body = "Bonjour Camille, voici les éléments."
                self.attachments = []

            def close(self) -> None:
                pass

        class FakePstMsg:
            sender_name = "Sophie Martin"
            transport_headers = "From: Sophie Martin <sophie.martin@cabinet.fr>\r\n"
            subject = "Pièce archive PST"
            delivery_time = "2024-07-15 14:30:00"
            plain_text_body = "Contenu extrait depuis le fichier PST Outlook."
            number_of_attachments = 0

        class FakeRootFolder:
            number_of_sub_messages = 1
            number_of_sub_folders = 0

            def get_sub_message(self, _idx: int) -> FakePstMsg:
                return FakePstMsg()

        class FakePstFile:
            def open(self, _p: str) -> None:
                pass

            def get_root_folder(self) -> FakeRootFolder:
                return FakeRootFolder()

            def close(self) -> None:
                pass

        fake_extract_msg = types.SimpleNamespace(Message=FakeMsg)
        fake_pypff = types.SimpleNamespace(file=FakePstFile)

        with patch.dict(sys.modules, {"extract_msg": fake_extract_msg, "pypff": fake_pypff}):
            prescanner = ChatContactPrescanner(
                sources_dir=self.src_dir,
                discovered_chats_file=self.config.discovered_chats_file,
                discovered_emails_file=self.config.discovered_contacts_file,
            )
            _, added_emails = prescanner.prescan_sources()
            self.assertGreaterEqual(added_emails, 3)

            runner = DocumentExtractionRunner(self.config)
            already: set[str] = set()
            out_msg = runner.process_single_file(msg_path, {}, set(), already, set(), set(), set())
            out_pst = runner.process_single_file(pst_path, {}, set(), already, set(), set(), set())
            self.assertEqual(len(out_msg), 1)
            self.assertEqual(len(out_pst), 1)
            with open(next(iter(out_pst)), "r", encoding="utf-8") as f_res:
                self.assertIn("Contenu extrait depuis le fichier PST Outlook.", f_res.read())


if __name__ == "__main__":
    unittest.main()
