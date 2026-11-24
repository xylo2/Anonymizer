# Commandes pip à exécuter : Aucune dépendance externe requise

import csv
import os
import shutil
import sys
import tempfile
from typing import List
import unittest
import docx

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.dossier_exporter import LawyerDossierExporter
from doc_anonymizer.gui_controller import AnonymizerGuiController
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner


class TestEndToEndBusinessWorkflows(unittest.TestCase):
    """Tests métier de bout en bout : isolation des dossiers et passerelle IA -> Pack Avocat."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_e2e_biz_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        with open(os.path.join(self.tmp_root, "data", "mots_exclus.txt"), "w", encoding="utf-8") as f_ex:
            f_ex.write("# Mots exclus\n")
        with open(os.path.join(self.tmp_root, "data", "prenoms.txt"), "w", encoding="utf-8") as f_pr:
            f_pr.write("camille\nmarc\nsophie\nclaire\n")
        with open(os.path.join(self.tmp_root, "data", "collisions_noms.txt"), "w", encoding="utf-8") as f_col:
            f_col.write("# Collisions\n")
        with open(os.path.join(self.tmp_root, "data", "villes_masquees.txt"), "w", encoding="utf-8") as f_vil:
            f_vil.write("lyon\nparis\n")
        self.ctrl: AnonymizerGuiController = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    @staticmethod
    def _read_all_txt_in_dir(folder_path: str) -> str:
        """Lit et concatène proprement tous les fichiers .txt d'un dossier."""
        chunks: List[str] = []
        for rp, _, files in os.walk(folder_path):
            for fn in sorted(files):
                if fn.endswith(".txt"):
                    with open(os.path.join(rp, fn), "r", encoding="utf-8") as f_in:
                        chunks.append(f_in.read())
        return "\n".join(chunks)

    def test_strict_workspace_isolation_between_two_cases(self) -> None:
        """Vérifie qu'aucun contact, audit ou texte ne fuite d'un dossier vers un autre."""
        ini_a: str = self.ctrl.create_workspace("Affaire_Sante_MDPH")
        ini_b: str = self.ctrl.create_workspace("Affaire_Prudhommes")
        paths_a = self.ctrl.resolve_workspace_paths(ini_a)
        paths_b = self.ctrl.resolve_workspace_paths(ini_b)

        with open(os.path.join(paths_a["sources_dir"], "2024-03_bilan.txt"), "w", encoding="utf-8") as f_a:
            f_a.write("Bilan médical de Camille Dupont réalisé par Dr Valmont à Lyon.\n")
        with open(os.path.join(paths_b["sources_dir"], "2024-04_avertissement.txt"), "w", encoding="utf-8") as f_b:
            f_b.write("Courrier RH de Marc Lefevre concernant le licenciement à Paris.\n")

        DocAnonymizerPipelineRunner(config=PipelineConfig(ini_a), prevent_sleep=False).run_all()
        DocAnonymizerPipelineRunner(config=PipelineConfig(ini_b), prevent_sleep=False).run_all()

        self.ctrl.approve_audit_mask(ini_a, "Dr Valmont", "Dr V.")

        res_a: str = self._read_all_txt_in_dir(paths_a["results_dir"])
        res_b: str = self._read_all_txt_in_dir(paths_b["results_dir"])

        self.assertIn("Camille D.", res_a)
        self.assertNotIn("Marc Lefevre", res_a)
        self.assertIn("Marc L.", res_b)
        self.assertNotIn("Camille Dupont", res_b)
        with open(paths_b["manual_contacts_file"], "r", encoding="utf-8") as f_man_b:
            manual_b_txt: str = f_man_b.read()
        self.assertNotIn("Dr Valmont", manual_b_txt)
    def test_ia_anonymization_audit_correction_and_filtered_lawyer_pack(self) -> None:
        """Vérifie la chaîne complète : anonymisation IA, correction d'audit et Pack Avocat sélectif."""
        ini_path: str = self.ctrl.create_workspace("Litige_Employeur")
        paths = self.ctrl.resolve_workspace_paths(ini_path)

        with open(os.path.join(paths["sources_dir"], "2024-05-10_mail_menace.eml"), "w", encoding="utf-8") as f_eml:
            f_eml.write(
                "From: Marc Lefevre <marc.lefevre@entreprise.fr>\n"
                "To: Camille Dupont <camille.dupont@perso.fr>\n"
                "Subject: Convocation\n"
                "Date: Fri, 10 May 2024 09:30:00 +0200\n\n"
                "Bonjour Camille Dupont, appelez-moi au 06 12 34 56 78 (NIR 2850575123456 42). Signé Kévin Garnier.\n"
            )
        with open(os.path.join(paths["sources_dir"], "2024-06-02_note_cantine.txt"), "w", encoding="utf-8") as f_nc:
            f_nc.write("Menu de la cantine scolaire du mois de juin 2024.\n")

        orig_mp3: str = os.path.join(paths["sources_dir"], "2024-05-15_entretien_rh.mp3")
        with open(orig_mp3, "wb") as f_mp3:
            f_mp3.write(b"ID3_AUDIO_EVIDENCE_BYTES")
        audio_txt_dir: str = os.path.join(paths["transcriptions_dir"], "2024-05", "Audio")
        os.makedirs(audio_txt_dir, exist_ok=True)
        audio_txt: str = os.path.join(audio_txt_dir, "2024-05-15_entretien_rh.txt")
        with open(audio_txt, "w", encoding="utf-8") as f_at:
            f_at.write("[00:12] Marc Lefevre menace Camille Dupont de sanction.\n")

        cfg = PipelineConfig(ini_path)
        DocAnonymizerPipelineRunner(config=cfg, prevent_sleep=False).run_all()

        self.ctrl.approve_audit_mask(ini_path, "Kévin Garnier", "Kévin G.")
        DocAnonymizerPipelineRunner(config=cfg, prevent_sleep=False).run_anonymize_only(reset_results=True)

        ia_text: str = self._read_all_txt_in_dir(paths["results_dir"])
        self.assertNotIn("Camille Dupont", ia_text)
        self.assertNotIn("Marc Lefevre", ia_text)
        self.assertNotIn("06 12 34 56 78", ia_text)
        self.assertNotIn("2850575123456", ia_text)
        self.assertIn("Kévin G.", ia_text)

        ai_selected_output: str = (
            "# SOURCE TRANSCRIPTION : extracted_texts/2024-05/Emails/emails_2024-05-10_mail_menace.txt\n"
            "# SOURCE TRANSCRIPTION : extracted_texts/2024-05/Audio/2024-05-15_entretien_rh.txt\n"
        )
        selected_files = self.ctrl.resolve_ai_selected_extracted_files(ini_path, ai_selected_output)
        self.assertEqual(len(selected_files), 2)

        export_dir: str = os.path.join(paths["workspace_root"], "pack_avocat")
        exporter = LawyerDossierExporter(
            results_dir=paths["results_dir"],
            export_dir=export_dir,
            transcriptions_dir=paths["transcriptions_dir"],
            sources_dir=paths["sources_dir"],
            mapping_file=paths["mapping_file"],
            selected_extracted_files=selected_files,
        )
        count, _ = exporter.export_lawyer_pack()
        self.assertEqual(count, 2)

        with open(os.path.join(export_dir, "Bordereau_des_Pieces.csv"), "r", encoding="utf-8-sig") as f_csv:
            rows = list(csv.DictReader(f_csv, delimiter=";"))
        self.assertEqual(len(rows), 2)
        self.assertTrue(any(r["Fichier média original joint"].endswith("_ORIGINAL.mp3") for r in rows))

        doc = docx.Document(os.path.join(export_dir, "Recueil_Chronologique_Avocat.docx"))
        full_docx: str = "\n".join(p.text for p in doc.paragraphs)
        self.assertIn("Camille Dupont", full_docx)
        self.assertIn("Marc Lefevre", full_docx)
        self.assertNotIn("cantine scolaire", full_docx)


if __name__ == "__main__":
    unittest.main()
