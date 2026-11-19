# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

from email.message import EmailMessage
import json
import os
import shutil
import tempfile
import unittest
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.extraction_runner import DocumentExtractionRunner
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.teams_chat_extractor import TeamsChatExtractor
import run_documents


class TestSecurityAndGraphEdgeCases(unittest.TestCase):
    """
    Couvre les EML encodés en Latin-1/Windows-1252, le format Microsoft Graph
    API Teams, la migration des identifiants et la seconde passe --anonymize-only.
    """

    def setUp(self) -> None:
        """Prépare un répertoire temporaire isolé."""
        self.test_dir: str = tempfile.mkdtemp(prefix="test_sec_graph_")
        self.ini_path: str = os.path.join(self.test_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f:
            f.write(
                "[files]\n"
                "first_names_file = prenoms.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = fichiers sources\n"
                "transcriptions_dir = transcriptions\n"
                "results_dir = resultats_anonymisation\n"
                "contacts_file = contacts.txt\n"
                "manual_contacts_file = contacts_manuels.txt\n"
                "discovered_contacts_file = contacts_emails_decouverts.txt\n"
                "all_emails_file = tous_emails_trouves.txt\n"
                "all_sms_numbers_file = tous_numeros_sms.txt\n"
                "[extraction]\n"
                "enable_ocr = false\n"
                "enable_audio = false\n"
            )
        with open(os.path.join(self.test_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("jean\nsophie\nclaire\n")
        with open(os.path.join(self.test_dir, "contacts.txt"), "w", encoding="utf-8") as f:
            f.write("jean.dupont@exemple.fr = Jean D.\n")
        self.config: PipelineConfig = PipelineConfig(self.ini_path)

    def tearDown(self) -> None:
        """Nettoie le répertoire temporaire."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_latin1_eml_and_teams_graph_api_extraction(self) -> None:
        """
        Vérifie la lecture d'un courriel .eml encodé en ISO-8859-1 et
        l'extraction d'un export JSON issu de l'API Microsoft Graph Teams.
        """
        eml_path: str = os.path.join(self.test_dir, "courriel_latin1.eml")
        msg = EmailMessage()
        msg["From"] = "Jean Dupont <jean.dupont@exemple.fr>"
        msg["To"] = "Claire Bernard <claire.bernard@exemple.fr>"
        msg["Date"] = "Mon, 02 Dec 2024 11:00:00 +0100"
        msg["Subject"] = "Compte rendu médical"
        msg.set_content("Présence confirmée à l'hôpital.", charset="iso-8859-1")
        with open(eml_path, "wb") as f_eml:
            f_eml.write(msg.as_bytes())

        doc_ext = OfficeAndDocumentExtractor(enable_ocr=False)
        comm_ext = CommunicationExtractor(self.config, doc_ext)
        discovered: set[str] = set()
        by_month_eml, err_eml = comm_ext.extract_emails(
            eml_path, {"jean.dupont@exemple.fr"}, discovered
        )
        self.assertIsNone(err_eml)
        self.assertIn("2024-12", by_month_eml)
        self.assertIn("Présence confirmée à l'hôpital.", "".join(by_month_eml["2024-12"]))

        graph_payload = {
            "value": [
                {
                    "createdDateTime": "2024-12-03T09:30:00Z",
                    "from": {
                        "user": {
                            "displayName": "Sophie Martin",
                            "userPrincipalName": "sophie.martin@entreprise.fr",
                        }
                    },
                    "body": {
                        "contentType": "html",
                        "content": "<div>Bonjour <at>Jean Dupont</at>, point validé.</div>",
                    },
                }
            ]
        }
        self.assertTrue(TeamsChatExtractor.is_teams_json_payload(graph_payload))

        json_path: str = os.path.join(self.test_dir, "graph_chat.json")
        with open(json_path, "w", encoding="utf-8") as f_js:
            json.dump(graph_payload, f_js)

        teams_ext = TeamsChatExtractor(self.config)
        by_month = teams_ext.extract_teams_json(json_path, graph_payload, discovered)

        self.assertIn("2024-12", by_month)
        self.assertIn("MICROSOFT TEAMS : graph_chat", by_month["2024-12"])
        self.assertIn("@Jean Dupont", by_month["2024-12"])
        self.assertIn("sophie.martin@entreprise.fr|Sophie Martin", discovered)
    def test_finalize_reports_sms_migration_and_anonymize_only_second_pass(self) -> None:
        """
        Vérifie la séparation e-mails/téléphones dans finalize_reports (sans RCS Google)
        et le déclenchement de la seconde passe en mode --anonymize-only.
        """
        with open(self.config.all_sms_numbers_file, "w", encoding="utf-8") as f_sms:
            f_sms.write(
                "+33 6 12 34 56 78~claire.bernard@exemple.fr\n"
                "bot@://google.com\n"
            )

        extractor = DocumentExtractionRunner(self.config)
        extractor.finalize_reports(discovered_phones={"0699887766"}, discovered_emails=set())

        with open(self.config.all_sms_numbers_file, "r", encoding="utf-8") as f_sms_out:
            phones_txt: str = f_sms_out.read()
        self.assertIn("0612345678", phones_txt)
        self.assertIn("0699887766", phones_txt)
        self.assertNotIn("@", phones_txt)

        with open(self.config.all_emails_file, "r", encoding="utf-8") as f_mail_out:
            mails_txt: str = f_mail_out.read()
        self.assertIn("claire.bernard@exemple.fr", mails_txt)
        self.assertNotIn("google.com", mails_txt)

        trans_dir: str = os.path.join(self.config.transcriptions_dir, "2024-12", "Emails")
        os.makedirs(trans_dir, exist_ok=True)
        with open(os.path.join(trans_dir, "mail_test.txt"), "w", encoding="utf-8") as f_tr:
            f_tr.write("Message de Claire Bernard (claire.bernard@exemple.fr).\n")

        rc: int = run_documents.main(
            ["-c", self.ini_path, "--anonymize-only", "--allow-sleep"]
        )
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(self.config.discovered_contacts_file))

        lot_file: str = os.path.join(
            self.config.results_dir, "lot_01", "anonymise_partie_001.txt"
        )
        with open(lot_file, "r", encoding="utf-8") as f_lot:
            lot_txt: str = f_lot.read()
        self.assertNotIn("Claire Bernard", lot_txt)
        self.assertIn("Contact_Mail_001", lot_txt)


if __name__ == "__main__":
    unittest.main()
