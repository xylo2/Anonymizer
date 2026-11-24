# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.contact_merger import ContactCatalogMerger


class TestContactCatalogMerger(unittest.TestCase):
    """Vérifie la fusion CSV + chats + e-mails et la résolution des homonymes."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_contact_merger_")
        self.contacts_txt: str = os.path.join(self.tmp_dir, "contacts.txt")
        self.chats_txt: str = os.path.join(self.tmp_dir, "discovered_chat_contacts.txt")
        self.emails_txt: str = os.path.join(self.tmp_dir, "discovered_email_contacts.txt")

        with open(self.contacts_txt, "w", encoding="utf-8") as f_c:
            f_c.write("Jean Dupont = Jean D.\njean.dupont@exemple.fr = Jean D.\n")
        with open(self.chats_txt, "w", encoding="utf-8") as f_ch:
            f_ch.write("Jean Durand = Jean D.\nClaire Bernard = Claire B.\n")
        with open(self.emails_txt, "w", encoding="utf-8") as f_em:
            f_em.write("externe@partenaire.org = Contact_Mail_001\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_merge_deduplicates_and_resolves_homonyms(self) -> None:
        """Vérifie que Jean Durand (chat) devient 'Jean Du.' sans écraser 'Jean D.' (CSV)."""
        merger = ContactCatalogMerger(
            contacts_file=self.contacts_txt,
            discovered_chats_file=self.chats_txt,
            discovered_emails_file=self.emails_txt,
            known_first_names={"jean", "claire"},
        )
        added, total = merger.merge_all()
        self.assertEqual(added, 3)
        self.assertEqual(total, 5)

        with open(self.contacts_txt, "r", encoding="utf-8") as f_out:
            merged_content: str = f_out.read()
        self.assertIn("Jean Dupont = Jean D.", merged_content)
        self.assertIn("Jean Durand = Jean Du.", merged_content)
        self.assertIn("Claire Bernard = Claire B.", merged_content)
        self.assertIn("externe@partenaire.org = Contact_Mail_001", merged_content)


if __name__ == "__main__":
    unittest.main()
