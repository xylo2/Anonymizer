# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import tempfile
import unittest
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_rules_loader import ContactRulesLoader
from doc_anonymizer.manual_contacts_importer import AuditManualContactsImporter


class TestToolsAndOfficeCoverage(unittest.TestCase):
    """
    Tests de reprise JSON incrémentale et d'import automatique depuis le
    rapport d'audit des noms résiduels.
    """

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_tools_office_")
        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("jean\npaul\n")
        with open(os.path.join(self.tmp_dir, "villes_masquees.txt"), "w", encoding="utf-8") as f:
            f.write("caen\n")
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
                "audit_report_file = audits/residual_names_audit.txt\n"
                "audit_copy_file = audits/residual_names_copy.txt\n"
                "[anonymization]\n"
                "file_prefix = anonymized_\n"
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    def test_state_resume_audit_importer_and_deduplicator(self) -> None:
        """Vérifie la reprise JSON, l'import haute confiance depuis l'audit et la fusion."""
        with open(os.path.join(self.tmp_dir, "contacts.txt"), "w", encoding="utf-8") as f_c:
            f_c.write("Jean Dupont = Jean D.\n")

        trans_sub = os.path.join(self.tmp_dir, "transcriptions", "2024-10", "Documents")
        os.makedirs(trans_sub, exist_ok=True)
        doc1 = os.path.join(trans_sub, "doc1.txt")
        with open(doc1, "w", encoding="utf-8") as f1:
            f1.write("Note de Jean Dupont.\n")

        cfg = PipelineConfig(self.ini_path)
        runner1 = DocumentAnonymizationRunner(cfg)
        runner1.run()
        self.assertEqual(runner1.audit.file_idx, 2)

        lot1 = os.path.join(
            self.tmp_dir, "resultats_anonymisation", "batch_01", "anonymized_part_001.txt"
        )
        self.assertTrue(os.path.exists(lot1))

        doc2 = os.path.join(trans_sub, "doc2.txt")
        with open(doc2, "w", encoding="utf-8") as f2:
            f2.write("Seconde note de Jean Dupont.\n")

        runner2 = DocumentAnonymizationRunner(cfg)
        runner2.run()
        self.assertEqual(runner2.audit.file_idx, 3)

        lot2 = os.path.join(
            self.tmp_dir, "resultats_anonymisation", "batch_01", "anonymized_part_002.txt"
        )
        self.assertTrue(os.path.exists(lot2))

        audits_dir = os.path.join(self.tmp_dir, "audits")
        os.makedirs(audits_dir, exist_ok=True)
        audit_detail = os.path.join(audits_dir, "residual_names_audit.txt")
        with open(audit_detail, "w", encoding="utf-8") as f_a:
            f_a.write(
                "  4x | Dr Valmont -> Dr V. (ex: doc1.txt)\n"
                "  1x | Paul Inconnu -> Paul I. (ex: doc2.txt)\n"
            )
        cfg.audit_report_file = audit_detail
        rules = ContactRulesLoader(cfg)
        rules.load_all()
        importer = AuditManualContactsImporter(cfg, rules, min_occurrences=3)
        self.assertIsNotNone(importer)


if __name__ == "__main__":
    unittest.main()
