# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import json
import os
import shutil
import tempfile
import unittest
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner


class TestGoogleChatPipeline(unittest.TestCase):
    """
    Valide l'extraction des exports Google Chat Takeout (messages.json + group_info.json),
    le classement chronologique par mois, la découverte des contacts et l'anonymisation.
    """

    def setUp(self) -> None:
        """Prépare un environnement temporaire isolé."""
        self.test_dir: str = tempfile.mkdtemp(prefix="test_gchat_")
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

    def test_google_chat_takeout_extraction_and_anonymization(self) -> None:
        """
        Vérifie l'extraction multi-mois d'un dossier Google Chat Takeout,
        l'ignorance des JSON non-chat et l'anonymisation complète.
        """
        chat_dir: str = os.path.join(
            self.test_dir, "fichiers sources", "Google Chat", "Groups", "DM_Test123"
        )
        os.makedirs(chat_dir, exist_ok=True)

        with open(os.path.join(chat_dir, "group_info.json"), "w", encoding="utf-8") as f_gi:
            json.dump(
                {
                    "name": "Projet Cabinet",
                    "members": [
                        {"name": "Jean Dupont", "email": "jean.dupont@exemple.fr"},
                        {"name": "Sophie Martin", "email": "sophie.martin@cabinet.fr"},
                    ],
                },
                f_gi,
            )
        with open(os.path.join(chat_dir, "messages.json"), "w", encoding="utf-8") as f_msg:
            json.dump(
                {
                    "messages": [
                        {
                            "creator": {
                                "name": "Sophie Martin",
                                "email": "sophie.martin@cabinet.fr",
                            },
                            "created_date": "mardi 14 mai 2024 à 10:15:00 UTC",
                            "text": "Bonjour Jean Dupont, voici le compte rendu.",
                            "attached_files": [{"original_name": "note_confidentielle.pdf"}],
                        },
                        {
                            "creator": {
                                "name": "Jean Dupont",
                                "email": "jean.dupont@exemple.fr",
                            },
                            "created_date": "jeudi 6 juin 2024 à 09:00:00 UTC",
                            "text": "Merci Sophie Martin, appelez-moi au 06 12 34 56 78.",
                        },
                    ]
                },
                f_msg,
            )

        with open(os.path.join(chat_dir, "user_info.json"), "w", encoding="utf-8") as f_ui:
            json.dump({"user": {"email": "jean.dupont@exemple.fr"}}, f_ui)

        config = PipelineConfig(self.ini_path)
        DocAnonymizerPipelineRunner(config=config, prevent_sleep=False).run_all()

        may_txt: str = os.path.join(
            config.transcriptions_dir, "2024-05", "Chats", "chat_DM_Test123_messages.txt"
        )
        june_txt: str = os.path.join(
            config.transcriptions_dir, "2024-06", "Chats", "chat_DM_Test123_messages.txt"
        )
        self.assertTrue(os.path.exists(may_txt))
        self.assertTrue(os.path.exists(june_txt))

        result_files = [
            os.path.join(rp, fn)
            for rp, _, files in os.walk(config.results_dir)
            for fn in files
            if fn.endswith(".txt")
        ]
        self.assertTrue(result_files)
        merged_res: str = "\n".join(
            open(p, "r", encoding="utf-8").read() for p in result_files
        )
        self.assertIn("GOOGLE CHAT : Projet Cabinet", merged_res)
        self.assertIn("note_confidentielle.pdf", merged_res)
        self.assertNotIn("Sophie Martin", merged_res)
        self.assertNotIn("06 12 34 56 78", merged_res)
        self.assertIn("TEL_001", merged_res)


if __name__ == "__main__":
    unittest.main()
