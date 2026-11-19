# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import shutil
import tempfile
from typing import List
import unittest
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner


class TestMultiChatExtractors(unittest.TestCase):
    """
    Tests de bout en bout pour l'extraction multi-mois et l'anonymisation des
    4 plateformes de messagerie : Google Chat, WhatsApp, Messenger et Signal.
    """

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_multichat_")
        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("sophie\njean\nclaire\nmarc\n")
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
                "audit_report_file = residual_names_audit.txt\n"
                "audit_copy_file = residual_names_copy.txt\n"
                "[extraction]\n"
                "enable_ocr = false\n"
                "enable_audio = false\n"
                "extraction_workers = 2\n"
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _build_google_chat_sample(self) -> None:
        gchat_dir = os.path.join(
            self.tmp_dir, "fichiers_sources", "Takeout", "Google Chat", "Groups", "DM_Alpha"
        )
        os.makedirs(gchat_dir, exist_ok=True)
        with open(os.path.join(gchat_dir, "group_info.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "Équipe Projet", "members": []}, f)
        with open(os.path.join(gchat_dir, "messages.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "messages": [
                        {
                            "creator": {"name": "Sophie Martin", "email": "sophie.martin@exemple.fr"},
                            "created_date": "Tuesday, May 14, 2024 at 10:15:00 AM UTC",
                            "text": "Bonjour Jean Dupont, rendez-vous confirmé.",
                        }
                    ]
                },
                f,
            )

    def _build_whatsapp_sample(self) -> None:
        wa_dir = os.path.join(self.tmp_dir, "fichiers_sources", "WhatsApp")
        os.makedirs(wa_dir, exist_ok=True)
        wa_file = os.path.join(wa_dir, "Discussion WhatsApp avec Claire Bernard.txt")
        with open(wa_file, "w", encoding="utf-8") as f:
            f.write(
                "12/06/2024, 14:20 - Claire Bernard: Bonjour, voici mon numéro 06 11 22 33 44.\n"
                "Ligne supplémentaire du message.\n"
                "12/06/2024, 14:25 - Jean Dupont: Bien reçu Claire Bernard.\n"
            )

    def _build_messenger_sample(self) -> None:
        fb_dir = os.path.join(
            self.tmp_dir, "fichiers_sources", "Facebook", "messages", "inbox", "claire_123"
        )
        os.makedirs(fb_dir, exist_ok=True)
        with open(os.path.join(fb_dir, "message_1.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "title": "Claire Bernard",
                    "participants": [{"name": "Claire Bernard"}, {"name": "Jean Dupont"}],
                    "messages": [
                        {
                            "sender_name": "Claire Bernard",
                            "timestamp_ms": 1720526400000,
                            "content": "Réunion prévue à Caen demain.",
                        }
                    ],
                },
                f,
            )

    def _build_signal_sample(self) -> None:
        sig_dir = os.path.join(self.tmp_dir, "fichiers_sources", "Signal")
        os.makedirs(sig_dir, exist_ok=True)
        with open(os.path.join(sig_dir, "signal_backup.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "messages": [
                        {
                            "sourceName": "Marc Lefevre",
                            "timestamp": 1723723200000,
                            "body": "Document envoyé par Signal.",
                        }
                    ]
                },
                f,
            )
    def test_all_four_chat_platforms_end_to_end(self) -> None:
        """
        Vérifie l'extraction multi-mois et l'anonymisation simultanées de
        Google Chat, WhatsApp, Messenger et Signal ainsi que la découverte
        automatique des contacts de chats dans discovered_chat_contacts.txt.
        """
        self._build_google_chat_sample()
        self._build_whatsapp_sample()
        self._build_messenger_sample()
        self._build_signal_sample()

        config = PipelineConfig(self.ini_path)
        DocAnonymizerPipelineRunner(config=config, prevent_sleep=False).run_all()

        chat_trans_2024_06 = os.path.join(self.tmp_dir, "transcriptions", "2024-06", "Chats")
        chat_trans_2024_07 = os.path.join(self.tmp_dir, "transcriptions", "2024-07", "Chats")
        chat_trans_2024_08 = os.path.join(self.tmp_dir, "transcriptions", "2024-08", "Chats")
        self.assertTrue(os.path.isdir(chat_trans_2024_06))
        self.assertTrue(os.path.isdir(chat_trans_2024_07))
        self.assertTrue(os.path.isdir(chat_trans_2024_08))

        discovered_chats_path = os.path.join(self.tmp_dir, "discovered_chat_contacts.txt")
        self.assertTrue(os.path.exists(discovered_chats_path))
        with open(discovered_chats_path, "r", encoding="utf-8") as f_dc:
            dc_txt = f_dc.read()
        self.assertIn("Claire Bernard = Claire B.", dc_txt)
        self.assertIn("Marc Lefevre = Marc L.", dc_txt)

        res_dir = os.path.join(self.tmp_dir, "resultats_anonymisation")
        all_lots: List[str] = []
        for root_p, _, files in os.walk(res_dir):
            for fname in files:
                if fname.endswith(".txt"):
                    with open(os.path.join(root_p, fname), "r", encoding="utf-8") as f:
                        all_lots.append(f.read())
        merged = "\n".join(all_lots)

        self.assertIn("GOOGLE CHAT : Équipe Projet", merged)
        self.assertIn("WHATSAPP : Claire B.", merged)
        self.assertIn("MESSENGER : Claire B.", merged)
        self.assertIn("SIGNAL : signal_backup", merged)

        self.assertNotIn("Claire Bernard", merged)
        self.assertNotIn("Marc Lefevre", merged)
        self.assertIn("Claire B.", merged)
        self.assertIn("Marc L.", merged)
        self.assertIn("TEL_001", merged)
        self.assertNotIn("06 11 22 33 44", merged)
        self.assertIn("[LIEU_MASQUE]", merged)


if __name__ == "__main__":
    unittest.main()
