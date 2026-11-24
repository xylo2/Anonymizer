# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.gui_controller import AnonymizerGuiController
from google_contacts_parser.config_manager import ContactsConfig


class TestAnonymizerGuiController(unittest.TestCase):
    """Vérifie le contrôleur métier : dossiers isolés, CSV arbitraires, ZIP, stats, Avant/Après et passerelle IA."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_gui_ctrl_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        with open(os.path.join(self.tmp_root, "data", "mots_exclus.txt"), "w", encoding="utf-8") as f_ex:
            f_ex.write("# Mots exclus\n")
        with open(os.path.join(self.tmp_root, "data", "prenoms.txt"), "w", encoding="utf-8") as f_pr:
            f_pr.write("camille\njean\nmarc\n")
        self.ctrl: AnonymizerGuiController = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_workspace_listing_zip_and_ai_bridge(self) -> None:
        """Vérifie la liste vide initiale, l'import de n'importe quel CSV, les ZIP et la résolution IA."""
        self.assertEqual(self.ctrl.list_workspaces(), [])

        ini_path: str = self.ctrl.create_workspace("Dossier_Prudhommes")
        self.assertEqual(len(self.ctrl.list_workspaces()), 1)
        paths = self.ctrl.resolve_workspace_paths(ini_path)

        arbitrary_csv: str = os.path.join(self.tmp_root, "export_gmail_2026.csv")
        with open(arbitrary_csv, "w", encoding="utf-8") as f_csv:
            f_csv.write("First Name,Last Name,E-mail 1 - Value\nCamille,Dupont,camille@exemple.fr\n")
        imported_csv: str = self.ctrl.import_contacts_csv(ini_path, arbitrary_csv)
        c_cfg = ContactsConfig(ini_path)
        self.assertEqual(c_cfg.get_csv_files(), [imported_csv])

        zip_file: str = os.path.join(paths["sources_dir"], "export_whatsapp.zip")
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("_chat.txt", "test")

        self.assertEqual(len(self.ctrl.detect_zip_files(ini_path)), 1)

        raw_txt: str = os.path.join(paths["transcriptions_dir"], "2024-06", "Documents", "mail_harcelement.txt")
        os.makedirs(os.path.dirname(raw_txt), exist_ok=True)
        with open(raw_txt, "w", encoding="utf-8") as f_t:
            f_t.write("Courriel envoyé par Marc Lefevre à Camille Dupont.\n")

        with open(paths["mapping_file"], "w", encoding="utf-8") as f_m:
            json.dump(
                {
                    "files": {
                        "extracted_texts/2024-06/Documents/mail_harcelement.txt": {
                            "extracted_file": raw_txt,
                            "original_source_file": "",
                            "batch_file": "",
                        }
                    }
                },
                f_m,
            )

        ai_reply: str = "# SOURCE TRANSCRIPTION : extracted_texts/2024-06/Documents/mail_harcelement.txt\n"
        resolved = self.ctrl.resolve_ai_selected_extracted_files(ini_path, ai_reply)
        self.assertEqual(resolved, {os.path.normpath(raw_txt)})

        occs = self.ctrl.load_audit_occurrences(ini_path, "Marc Lefevre")
        self.assertEqual(len(occs), 1)
        self.assertIn("Marc Lefevre", next(iter(occs))["raw_excerpt"])
        self.assertEqual(len(self.ctrl.AI_PROMPT_TEMPLATES), 6)


if __name__ == "__main__":
    unittest.main()
