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

from doc_anonymizer.chat_prescanner import ChatContactPrescanner
from doc_anonymizer.contact_merger import ContactCatalogMerger


class TestChatContactPrescanner(unittest.TestCase):
    """Vérifie le pré-scan des chats/e-mails/SMS et leur fusion immédiate dans contacts.txt."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_prescanner_")
        self.src_dir: str = os.path.join(self.tmp_dir, "input_documents")
        self.out_dir: str = os.path.join(self.tmp_dir, "output_contacts")
        os.makedirs(self.src_dir, exist_ok=True)
        os.makedirs(self.out_dir, exist_ok=True)

        self.contacts_txt: str = os.path.join(self.out_dir, "contacts.txt")
        self.chats_txt: str = os.path.join(self.out_dir, "discovered_chat_contacts.txt")
        self.emails_txt: str = os.path.join(self.out_dir, "discovered_email_contacts.txt")

        with open(self.contacts_txt, "w", encoding="utf-8") as f_c:
            f_c.write("Jean Dupont = Jean D.\n")

        gchat_payload = {
            "messages": [
                {
                    "creator": {"name": "Jean Durand", "email": "jean.durand@exemple.fr"},
                    "created_date": "Tuesday, May 14, 2024 at 10:15:00 AM UTC",
                    "text": "Bonjour à tous",
                }
            ]
        }
        with open(os.path.join(self.src_dir, "messages.json"), "w", encoding="utf-8") as f_j:
            json.dump(gchat_payload, f_j, ensure_ascii=False)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_prescan_and_merge_into_contacts(self) -> None:
        """Vérifie que Jean Durand (chat) est découvert et fusionné en 'Jean Du.'."""
        prescanner = ChatContactPrescanner(
            sources_dir=self.src_dir,
            discovered_chats_file=self.chats_txt,
            discovered_emails_file=self.emails_txt,
            contacts_file=self.contacts_txt,
            known_first_names={"jean"},
        )
        added_chats, added_emails = prescanner.prescan_sources()
        self.assertGreaterEqual(added_chats, 1)
        self.assertGreaterEqual(added_emails, 1)

        merger = ContactCatalogMerger(
            contacts_file=self.contacts_txt,
            discovered_chats_file=self.chats_txt,
            discovered_emails_file=self.emails_txt,
            known_first_names={"jean"},
        )
        added_merged, _ = merger.merge_all()
        self.assertGreaterEqual(added_merged, 2)

        with open(self.contacts_txt, "r", encoding="utf-8") as f_res:
            content: str = f_res.read()
        self.assertIn("Jean Dupont = Jean D.", content)
        self.assertIn("Jean Durand = Jean Du.", content)
        self.assertIn("jean.durand@exemple.fr = Contact_Mail_001", content)


if __name__ == "__main__":
    unittest.main()
