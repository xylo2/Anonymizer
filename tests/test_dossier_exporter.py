# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.dossier_exporter import LawyerDossierExporter


class TestLawyerDossierExporter(unittest.TestCase):
    """Tests unitaires pour le Pack Avocat nominatif, médias originaux et filtrage IA."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_lawyer_pack_")
        self.res_dir: str = os.path.join(self.tmp_root, "anonymized_results")
        self.trans_dir: str = os.path.join(self.tmp_root, "extracted_texts")
        self.src_dir: str = os.path.join(self.tmp_root, "input_documents")
        self.exp_dir: str = os.path.join(self.tmp_root, "pack_avocat")
        os.makedirs(self.res_dir, exist_ok=True)
        os.makedirs(self.src_dir, exist_ok=True)

        orig_audio: str = os.path.join(self.src_dir, "2024-05_enregistrement_entretien.mp3")
        with open(orig_audio, "wb") as f_a:
            f_a.write(b"FAKE_AUDIO_DATA")

        audio_trans_dir: str = os.path.join(self.trans_dir, "2024-05", "Audio")
        os.makedirs(audio_trans_dir, exist_ok=True)
        self.audio_txt: str = os.path.join(audio_trans_dir, "2024-05_enregistrement_entretien.txt")
        with open(self.audio_txt, "w", encoding="utf-8") as f_t:
            f_t.write("[00:01] Entretien nominatif avec Camille Dupont.\n")

        doc_trans_dir: str = os.path.join(self.trans_dir, "2024-09", "PDF")
        os.makedirs(doc_trans_dir, exist_ok=True)
        self.doc_txt: str = os.path.join(doc_trans_dir, "2024-09_attestation_ecole.txt")
        with open(self.doc_txt, "w", encoding="utf-8") as f_d:
            f_d.write("Attestation nominative pour Camille Dupont.\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_nominative_pack_includes_original_audio_and_transcription(self) -> None:
        """Vérifie la copie côte à côte de l'audio original et de sa transcription nominative."""
        exporter = LawyerDossierExporter(
            results_dir=self.res_dir,
            export_dir=self.exp_dir,
            transcriptions_dir=self.trans_dir,
            sources_dir=self.src_dir,
        )
        count, _ = exporter.export_lawyer_pack()
        self.assertEqual(count, 2)

        zip_path: str = os.path.join(self.exp_dir, "Pack_Avocat_Complet.zip")
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            self.assertTrue(any("Piece_001_2024-05" in n and n.endswith("_ORIGINAL.mp3") for n in names))
            self.assertTrue(any("Piece_001_2024-05" in n and n.endswith("_TRANSCRIPTION.txt") for n in names))
            self.assertTrue(any("Piece_002_2024-09" in n and n.endswith(".txt") for n in names))

    def test_selective_export_with_ai_selected_files(self) -> None:
        """Vérifie le filtrage sélectif du Pack Avocat selon la liste retenue par l'IA."""
        exporter = LawyerDossierExporter(
            results_dir=self.res_dir,
            export_dir=self.exp_dir,
            transcriptions_dir=self.trans_dir,
            sources_dir=self.src_dir,
            selected_extracted_files={self.doc_txt},
        )
        count, _ = exporter.export_lawyer_pack()
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
