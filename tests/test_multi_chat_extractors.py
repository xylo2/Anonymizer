# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import json
import os
import shutil
import tempfile
import unittest
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner


class TestMultiChatExtractors(unittest.TestCase):
    """
    Valide l'extraction et l'anonymisation des conversations Google Chat,
    WhatsApp (.txt), Messenger (JSON Meta avec mojibake) et Signal (JSON).
    """

    def setUp(self) -> None:
        """Prépare un environnement temporaire isolé."""
        self.test_dir: str = tempfile.mkdtemp(prefix="test_multichat_")
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
            f.write("jean\nsophie\nclaire\nmarc\n")
        with open(os.path.join(self.test_dir, "contacts.txt"), "w", encoding="utf-8") as f:
            f.write(
                "jean.dupont@exemple.fr = Jean D.\n"
                "0612345678 = Marc L.\n"
            )

    def tearDown(self) -> None:
        """Supprime le répertoire temporaire."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_all_four_chat_platforms_end_to_end(self) -> None:
        """
        Vérifie l'extraction multi-mois et l'anonymisation simultanées de
        Google Chat, WhatsApp, Messenger et Signal.
        """
        sources: str = os.path.join(self.test_dir, "fichiers sources")

        # 1. Google Chat Takeout
        gchat_dir: str = os.path.join(sources, "Google Chat", "Groups", "DM_Alpha")
        os.makedirs(gchat_dir, exist_ok=True)
        with open(os.path.join(gchat_dir, "group_info.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "name": "Équipe Projet",
                    "members": [
                        {"name": "Jean Dupont", "email": "jean.dupont@exemple.fr"},
                        {"name": "Sophie Martin", "email": "sophie.martin@cabinet.fr"},
                    ],
                },
                f,
            )
        with open(os.path.join(gchat_dir, "messages.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "messages": [
                        {
                            "creator": {"name": "Sophie Martin", "email": "sophie.martin@cabinet.fr"},
                            "created_date": "mardi 14 mai 2024 à 10:15:00 UTC",
                            "text": "Bonjour Jean Dupont, rendez-vous confirmé.",
                        }
                    ]
                },
                f,
            )
        # 2. WhatsApp export (.txt)
        wa_dir: str = os.path.join(sources, "WhatsApp")
        os.makedirs(wa_dir, exist_ok=True)
        with open(
            os.path.join(wa_dir, "Discussion WhatsApp avec Claire Bernard.txt"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(
                "12/06/2024, 14:20 - Claire Bernard : Bonjour, voici mon numéro 06 99 88 77 66.\n"
                "Ligne supplémentaire du message.\n"
                "12/06/2024, 14:25 - Jean Dupont : Bien reçu Claire Bernard.\n"
            )

        # 3. Messenger export (JSON Meta avec encodage Latin-1 simulé)
        fb_dir: str = os.path.join(sources, "Messenger", "inbox", "claire_123")
        os.makedirs(fb_dir, exist_ok=True)
        fb_payload = {
            "title": "Claire Bernard",
            "participants": [{"name": "Claire Bernard"}, {"name": "Jean Dupont"}],
            "messages": [
                {
                    "sender_name": "Claire Bernard",
                    "timestamp_ms": 1720519200000,
                    "content": "Réunion prévue à Caen demain.".encode("utf-8").decode("latin-1"),
                }
            ],
        }
        with open(os.path.join(fb_dir, "message_1.json"), "w", encoding="utf-8") as f:
            json.dump(fb_payload, f, ensure_ascii=False)

        # 4. Signal export (JSON)
        sig_dir: str = os.path.join(sources, "Signal")
        os.makedirs(sig_dir, exist_ok=True)
        with open(os.path.join(sig_dir, "signal_backup.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "title": "Conversation Signal",
                    "messages": [
                        {
                            "source": "+33612345678",
                            "sourceName": "Marc Lefevre",
                            "timestamp": 1723716000000,
                            "body": "Document envoyé par Signal.",
                        }
                    ],
                },
                f,
            )

        config = PipelineConfig(self.ini_path)
        DocAnonymizerPipelineRunner(config=config, prevent_sleep=False).run_all()

        self.assertTrue(os.path.isdir(os.path.join(config.transcriptions_dir, "2024-05", "Chats")))
        self.assertTrue(os.path.isdir(os.path.join(config.transcriptions_dir, "2024-06", "Chats")))
        self.assertTrue(os.path.isdir(os.path.join(config.transcriptions_dir, "2024-07", "Chats")))
        self.assertTrue(os.path.isdir(os.path.join(config.transcriptions_dir, "2024-08", "Chats")))

        result_files = [
            os.path.join(rp, fn)
            for rp, _, files in os.walk(config.results_dir)
            for fn in files
            if fn.endswith(".txt")
        ]
        self.assertTrue(result_files)
        merged: str = "\n".join(open(p, "r", encoding="utf-8").read() for p in result_files)

        self.assertIn("GOOGLE CHAT : Équipe Projet", merged)
        self.assertIn("WHATSAPP : Claire B.", merged)
        self.assertIn("MESSENGER : Claire B.", merged)
        self.assertIn("SIGNAL : Conversation Signal", merged)
        self.assertNotIn("Sophie Martin", merged)
        self.assertNotIn("Claire Bernard", merged)
        self.assertNotIn("Marc Lefevre", merged)
        self.assertNotIn("06 99 88 77 66", merged)


if __name__ == "__main__":
    unittest.main()
