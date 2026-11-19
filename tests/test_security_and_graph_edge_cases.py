# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import tempfile
import unittest
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.extraction_runner import DocumentExtractionRunner
import run_documents


class TestSecurityAndGraphEdgeCases(unittest.TestCase):
    """
    Tests sur la séparation des rapports e-mails/SMS, le filtrage des adresses
    RCS Google et la seconde passe automatique en mode --anonymize-only.
    """

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_sec_graph_")
        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("claire\njean\n")
        with open(os.path.join(self.tmp_dir, "villes_masquees.txt"), "w", encoding="utf-8") as f:
            f.write("caen\n")
        with open(os.path.join(self.tmp_dir, "contacts.txt"), "w", encoding="utf-8") as f:
            f.write("Jean Dupont = Jean D.\n")

        self.ini_path: str = os.path.join(self.tmp_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f_ini:
            f_ini.write(
                "[files]\n"
                "first_names_file = prenoms.txt\n"
                "locations_file = villes_masquees.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = fichiers_sources\n"
                "transcriptions_dir = transcriptions\n"
                "results_dir = resultats_anonymisation\n"
                "contacts_file = contacts.txt\n"
                "manual_contacts_file = manual_contacts.txt\n"
                "discovered_contacts_file = discovered_email_contacts.txt\n"
                "discovered_chats_file = discovered_chat_contacts.txt\n"
                "all_sms_numbers_file = audits/all_sms_numbers.txt\n"
                "all_emails_file = audits/all_found_emails.txt\n"
                "audit_report_file = audits/residual_names_audit.txt\n"
                "audit_copy_file = audits/residual_names_copy.txt\n"
                "[anonymization]\n"
                "file_prefix = anonymized_\n"
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    def test_finalize_reports_sms_migration_and_anonymize_only_second_pass(self) -> None:
        """
        Vérifie la séparation e-mails/téléphones dans finalize_reports (sans RCS Google)
        ainsi que le déclenchement de la seconde passe d'anonymisation en mode
        --anonymize-only lorsque discovered_email_contacts.txt est enrichi.
        """
        audits_dir = os.path.join(self.tmp_dir, "audits")
        os.makedirs(audits_dir, exist_ok=True)
        sms_file = os.path.join(audits_dir, "all_sms_numbers.txt")
        with open(sms_file, "w", encoding="utf-8") as f_sms:
            f_sms.write(
                "# Liste SMS\n"
                "06 11 22 33 44\n"
                "claire.bernard@exemple.fr\n"
            )

        cfg = PipelineConfig(self.ini_path)
        extractor = DocumentExtractionRunner(cfg)
        rcs_addr: str = "17056263240014326776379053" + "@" + "rcs.google.com"
        extractor.finalize_reports(
            discovered_phones={"0699887766"},
            discovered_emails={
                "claire.bernard@exemple.fr",
                rcs_addr,
            },
        )

        with open(cfg.all_sms_numbers_file, "r", encoding="utf-8") as f_sms_out:
            sms_txt = f_sms_out.read()
        self.assertIn("0611223344", sms_txt)
        self.assertIn("0699887766", sms_txt)
        self.assertNotIn("claire.bernard@exemple.fr", sms_txt)

        with open(cfg.all_emails_file, "r", encoding="utf-8") as f_mail_out:
            mail_txt = f_mail_out.read()
        self.assertIn("claire.bernard@exemple.fr", mail_txt)
        self.assertNotIn("rcs.google.com", mail_txt)

        with open(cfg.discovered_contacts_file, "w", encoding="utf-8") as f_disc:
            f_disc.write("Claire Bernard = Contact_Mail_001\n")

        trans_sub = os.path.join(self.tmp_dir, "transcriptions", "2024-12", "Emails")
        os.makedirs(trans_sub, exist_ok=True)
        with open(os.path.join(trans_sub, "mail_test.txt"), "w", encoding="utf-8") as f_tr:
            f_tr.write("Message de Claire Bernard (claire.bernard@exemple.fr).\n")

        rc: int = run_documents.main(
            ["-c", self.ini_path, "--anonymize-only", "--allow-sleep"]
        )
        self.assertEqual(rc, 0)

        lot_file = os.path.join(
            self.tmp_dir,
            "resultats_anonymisation",
            "batch_01",
            "anonymized_part_001.txt",
        )
        self.assertTrue(os.path.exists(lot_file))
        with open(lot_file, "r", encoding="utf-8") as f_lot:
            lot_txt = f_lot.read()
        self.assertIn("Contact_Mail_001", lot_txt)


if __name__ == "__main__":
    unittest.main()
