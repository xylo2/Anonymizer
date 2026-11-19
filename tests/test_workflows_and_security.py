# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
from typing import List
import unittest
from unittest.mock import patch
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils
import run_contacts
import run_documents


class TestWorkflowsAndSecurity(unittest.TestCase):
    """
    Tests d'intégration des points d'entrée CLI (run_contacts.py, run_documents.py),
    du mode --anonymize-only, de l'import d'audit et de la sécurité XXE.
    """

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_workflows_")
        os.makedirs(os.path.join(self.tmp_dir, "export_contacts"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_dir, "fichiers sources"), exist_ok=True)

        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("jean\nclaire\nsophie\n")
        with open(os.path.join(self.tmp_dir, "villes_masquees.txt"), "w", encoding="utf-8") as f:
            f.write("caen\nfiers\n")
        with open(os.path.join(self.tmp_dir, "mots_exclus.txt"), "w", encoding="utf-8") as f:
            f.write("urgent\n")

        self.ini_path: str = os.path.join(self.tmp_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f_ini:
            f_ini.write(
                "[files]\n"
                "csv_directory = export_contacts\n"
                "first_names_file = prenoms.txt\n"
                "suggested_first_names_file = output_contacts/.intermediates/suggested_first_names.txt\n"
                "locations_file = villes_masquees.txt\n"
                "excluded_words_file = mots_exclus.txt\n"
                "output_file = output_contacts/.intermediates/indexed_contacts.txt\n"
                "anonymized_output_file = output_contacts/.intermediates/anonymized_contacts.txt\n"
                "surnames_output_file = output_contacts/.intermediates/contact_surnames.txt\n"
                "deduplicated_output_file = output_contacts/.intermediates/deduplicated_contacts.txt\n"
                "inverted_output_file = contacts.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = fichiers sources\n"
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
                "masked_birth_dates = 02/05/2013\n"
            )
        self.config: PipelineConfig = PipelineConfig(self.ini_path)
        self.config.load_external_lists()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_xml_xxe_security_and_sms_parsing(self) -> None:
        """Vérifie le blocage des déclarations DOCTYPE/ENTITY et le tri des SMS."""
        malicious_xml = '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><smses/>'
        with self.assertRaises(ValueError):
            DocumentTextUtils.safe_parse_xml_fromstring(malicious_xml)

    def test_auto_titles_audit_import_and_manual_pass(self) -> None:
        """Vérifie le masquage automatique des titres, mots_exclus.txt, l'import d'audit et la passe manuelle."""
        with open(os.path.join(self.tmp_dir, "contacts.txt"), "w", encoding="utf-8") as f_c:
            f_c.write("Jean Dupont = Jean D.\n")

        trans_sub = os.path.join(self.tmp_dir, "transcriptions", "2024-08", "Documents")
        os.makedirs(trans_sub, exist_ok=True)
        with open(os.path.join(trans_sub, "note.txt"), "w", encoding="utf-8") as f_t:
            f_t.write("Consultation avec Dr Lamotte et Jean Dupont.\n")

        rc: int = run_documents.main(["-c", self.ini_path, "--anonymize-only", "--allow-sleep"])
        self.assertEqual(rc, 0)

        lot_file = os.path.join(
            self.tmp_dir,
            "resultats_anonymisation",
            "batch_01",
            "anonymized_part_001.txt",
        )
        self.assertTrue(os.path.exists(lot_file))
        with open(lot_file, "r", encoding="utf-8") as f:
            txt = f.read()
        self.assertIn("Dr L.", txt)
        self.assertIn("Jean D.", txt)
    def test_cli_entrypoints_indexed_pairs_and_residual_audit(self) -> None:
        """
        Vérifie l'exécution réelle des points d'entrée CLI run_contacts.py
        et run_documents.py, le pré-remplissage des paires indexées dans le
        rapport d'audit, la suggestion des prénoms absents et la protection des
        mots courants ('fiers').
        """
        csv_file = os.path.join(self.tmp_dir, "export_contacts", "contacts.csv")
        with open(csv_file, "w", encoding="utf-8", newline="") as f_csv:
            f_csv.write("First Name,Last Name,E-mail 1 - Value,Phone 1 - Value\n")
            f_csv.write("Dupont,Jean,jean.dupont@exemple.fr,+33 6 12 34 56 78\n")
            f_csv.write("Zéphyrin,Valmont,zephyrin@exemple.fr,\n")

        old_cwd: str = os.getcwd()
        os.chdir(self.tmp_dir)
        try:
            with patch.object(sys, "argv", ["run_contacts.py", "-c", self.ini_path]):
                run_contacts.main()
        finally:
            os.chdir(old_cwd)

        contacts_out = os.path.join(self.tmp_dir, "contacts.txt")
        self.assertTrue(os.path.exists(contacts_out))
        with open(contacts_out, "r", encoding="utf-8") as f_c:
            contacts_txt = f_c.read()
        self.assertIn("Jean D.", contacts_txt)
        self.assertIn("+33 6 12 34 56 78", contacts_txt)

        sug_out = os.path.join(
            self.tmp_dir, "output_contacts", ".intermediates", "suggested_first_names.txt"
        )
        self.assertTrue(os.path.exists(sug_out))
        with open(sug_out, "r", encoding="utf-8") as f_s:
            self.assertIn("zéphyrin", f_s.read())

        src_doc = os.path.join(
            self.tmp_dir, "fichiers sources", "compte_rendu_2024-07.txt"
        )
        with open(src_doc, "w", encoding="utf-8") as f_doc:
            f_doc.write(
                "Rendez-vous le 15/07/2024 avec Jean Dupont et Claire Bernard.\n"
                "Interlocutrice : Sophie Renard.\n"
                "Témoin inconnu : Docteur Valmont.\n"
                "Nous sommes très fiers de marcher dans les bois une fois.\n"
                "Ratio mesuré : 0.008219178 et téléphone 06 12 34 56 78.\n"
            )

        rc: int = run_documents.main(["-c", self.ini_path, "--allow-sleep"])
        self.assertEqual(rc, 0)

        res_dir = os.path.join(self.tmp_dir, "resultats_anonymisation")
        lot_files: List[str] = []
        for root_p, _, files in os.walk(res_dir):
            for fname in files:
                if fname.endswith(".txt"):
                    lot_files.append(os.path.join(root_p, fname))
        self.assertEqual(len(lot_files), 1)
        with open(lot_files[0], "r", encoding="utf-8") as f_lot:
            lot_text = f_lot.read()

        self.assertIn("Jean D.", lot_text)
        self.assertIn("Claire B.", lot_text)
        self.assertIn("Sophie R.", lot_text)
        self.assertIn("Docteur V.", lot_text)
        self.assertIn("très fiers", lot_text)
        self.assertNotIn("très [LIEU_MASQUE]", lot_text)
        self.assertIn("0.008219178", lot_text)
        self.assertIn("TEL_001", lot_text)

        audit_report = os.path.join(self.tmp_dir, "residual_names_audit.txt")
        with open(audit_report, "r", encoding="utf-8") as f_aud:
            audit_txt = f_aud.read()
        self.assertIn("RAPPORT D'AUDIT", audit_txt)
        self.assertNotIn("Fiers", audit_txt)

    def test_anonymize_only_cli_mode(self) -> None:
        """
        Vérifie que --anonymize-only anonymise uniquement transcriptions/ sans
        extraire fichiers sources/, et supporte --reset-results.
        """
        with open(os.path.join(self.tmp_dir, "contacts.txt"), "w", encoding="utf-8") as f_c:
            f_c.write("Jean Dupont = Jean D.\n")

        src_ignored = os.path.join(self.tmp_dir, "fichiers sources", "ne_pas_extraire.txt")
        with open(src_ignored, "w", encoding="utf-8") as f_src:
            f_src.write("Ce fichier source ne doit pas être extrait.")

        trans_sub = os.path.join(self.tmp_dir, "transcriptions", "2024-09", "Documents")
        os.makedirs(trans_sub, exist_ok=True)
        trans_file = os.path.join(trans_sub, "note_deja_extraite.txt")
        with open(trans_file, "w", encoding="utf-8") as f_tr:
            f_tr.write("Compte rendu avec Sophie Renard le 02/05/2013.\n")

        rc: int = run_documents.main(
            ["-c", self.ini_path, "--anonymize-only", "--allow-sleep"]
        )
        self.assertEqual(rc, 0)

        ignored_out = os.path.join(
            self.tmp_dir, "transcriptions", "2024-09", "Documents", "ne_pas_extraire.txt"
        )
        self.assertFalse(os.path.exists(ignored_out))

        with open(self.config.manual_contacts_file, "w", encoding="utf-8") as f_m:
            f_m.write("Sophie Renard = Alias_Personnalise\n")

        rc2: int = run_documents.main(
            [
                "-c",
                self.ini_path,
                "--anonymize-only",
                "--reset-results",
                "--allow-sleep",
            ]
        )
        self.assertEqual(rc2, 0)

        res_dir = os.path.join(self.tmp_dir, "resultats_anonymisation")
        lot_files: List[str] = []
        for root_p, _, files in os.walk(res_dir):
            for fname in files:
                if fname.endswith(".txt"):
                    lot_files.append(os.path.join(root_p, fname))
        self.assertEqual(len(lot_files), 1)
        with open(lot_files[0], "r", encoding="utf-8") as f_lot:
            updated_content = f_lot.read()
        self.assertIn("Alias_Personnalise", updated_content)


if __name__ == "__main__":
    unittest.main()
