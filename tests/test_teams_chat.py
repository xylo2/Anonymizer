# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import json
import os
import shutil
import tempfile
import unittest
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner


class TestTeamsChatExtraction(unittest.TestCase):
    """
    Valide l'extraction et l'anonymisation des exports Microsoft Teams
    (JSON export personnel / Graph API et transcriptions WebVTT .vtt).
    """

    def setUp(self) -> None:
        """Prépare un répertoire temporaire isolé."""
        self.test_dir: str = tempfile.mkdtemp(prefix="test_teams_")
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
                "[extraction]\n"
                "enable_ocr = false\n"
                "enable_audio = false\n"
            )
        with open(os.path.join(self.test_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("jean\nsophie\nclaire\n")
        with open(os.path.join(self.test_dir, "contacts.txt"), "w", encoding="utf-8") as f:
            f.write("jean.dupont@exemple.fr = Jean D.\n")

    def tearDown(self) -> None:
        """Supprime le répertoire temporaire."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    def test_teams_json_and_vtt_end_to_end(self) -> None:
        """
        Vérifie l'extraction multi-mois d'un export JSON Teams (avec HTML <at> et pièce jointe),
        d'une transcription de réunion .vtt et l'anonymisation des intervenants.
        """
        teams_dir: str = os.path.join(self.test_dir, "fichiers sources", "Teams")
        os.makedirs(teams_dir, exist_ok=True)

        teams_payload = {
            "userId": "8:orgid:1234",
            "exportDate": "2024-11-20T10:00:00Z",
            "conversations": [
                {
                    "id": "19:abc@thread.v2",
                    "displayName": "Canal Projet RH",
                    "MessageList": [
                        {
                            "id": "1001",
                            "displayName": "Sophie Martin",
                            "from": "8:orgid:sophie.martin@entreprise.fr",
                            "messagetype": "RichText/Html",
                            "originalarrivaltime": "2024-11-05T14:12:30.000Z",
                            "content": "<p>Bonjour <at>Jean Dupont</at>, ci-joint le bilan.</p>",
                            "properties": {
                                "files": '[{"fileName": "bilan_2024.pdf"}]'
                            },
                        },
                        {
                            "id": "1002",
                            "displayName": "Système",
                            "messagetype": "ThreadActivity/AddMember",
                            "originalarrivaltime": "2024-11-05T14:13:00.000Z",
                            "content": "<addmember>...</addmember>",
                        },
                    ],
                }
            ],
        }
        with open(os.path.join(teams_dir, "messages.json"), "w", encoding="utf-8") as f_js:
            json.dump(teams_payload, f_js, ensure_ascii=False)

        vtt_content: str = (
            "WEBVTT\n\n"
            "00:00:10.000 --> 00:00:14.500\n"
            "<v Claire Bernard>Bonjour à tous, on démarre le point.</v>\n\n"
            "00:00:15.000 --> 00:00:19.000\n"
            "<v Jean Dupont>Parfait Claire Bernard, merci.</v>\n"
        )
        with open(
            os.path.join(teams_dir, "Reunion_Hebdo_2024-11-06.vtt"),
            "w",
            encoding="utf-8",
        ) as f_vtt:
            f_vtt.write(vtt_content)

        config = PipelineConfig(self.ini_path)
        DocAnonymizerPipelineRunner(config=config, prevent_sleep=False).run_all()

        chats_dir: str = os.path.join(config.transcriptions_dir, "2024-11", "Chats")
        self.assertTrue(os.path.isdir(chats_dir))

        result_files = [
            os.path.join(rp, fn)
            for rp, _, files in os.walk(config.results_dir)
            for fn in files
            if fn.endswith(".txt")
        ]
        self.assertTrue(result_files)
        merged: str = "\n".join(open(p, "r", encoding="utf-8").read() for p in result_files)

        self.assertIn("MICROSOFT TEAMS : Canal Projet RH", merged)
        self.assertIn("bilan_2024.pdf", merged)
        self.assertIn("TRANSCRIPTION RÉUNION TEAMS", merged)
        self.assertNotIn("Sophie Martin", merged)
        self.assertNotIn("Claire Bernard", merged)
        self.assertIn("Contact_Mail_001", merged)
        self.assertIn("Claire B.", merged)


if __name__ == "__main__":
    unittest.main()
