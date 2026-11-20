# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import tkinter as tk
import unittest
import zipfile
from unittest.mock import patch

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import gui_anonymizer
from doc_anonymizer.dossier_exporter import LawyerDossierExporter


class TestLawyerDossierExporter(unittest.TestCase):
    """Tests unitaires et d'interface pour l'export du Pack Avocat."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_lawyer_pack_")
        self.res_dir: str = os.path.join(self.tmp_root, "anonymized_results", "batch_01")
        self.exp_dir: str = os.path.join(self.tmp_root, "pack_avocat")
        os.makedirs(self.res_dir, exist_ok=True)

        batch_txt: str = os.path.join(self.res_dir, "anonymized_part_001.txt")
        with open(batch_txt, "w", encoding="utf-8") as f_out:
            f_out.write(
                "==================================================\n"
                "DOCUMENT : 2024-09_attestation_ecole.pdf\n"
                "==================================================\n"
                "Attestation concernant l'enfant Camille D. en classe de CP.\n\n"
                "==================================================\n"
                "DOCUMENT : 2024-05_compte_rendu_bilan.pdf\n"
                "==================================================\n"
                "Bilan rédigé par Dr M. le 15/05/2024.\n"
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_export_chronological_order_and_files(self) -> None:
        """Vérifie le tri chronologique (2024-05 avant 2024-09), le bordereau CSV et le ZIP."""
        exporter = LawyerDossierExporter(
            results_dir=os.path.join(self.tmp_root, "anonymized_results"),
            export_dir=self.exp_dir,
        )
        count, out_dir = exporter.export_lawyer_pack()
        self.assertEqual(count, 2)
        self.assertEqual(out_dir, self.exp_dir)

        bordereau_csv: str = os.path.join(self.exp_dir, "Bordereau_des_Pieces.csv")
        self.assertTrue(os.path.isfile(bordereau_csv))
        with open(bordereau_csv, "r", encoding="utf-8-sig") as f_csv:
            rows = [line.strip() for line in f_csv if line.strip()]
        self.assertEqual(len(rows), 3)
        self.assertIn("Pièce n°001;2024-05;2024-05_compte_rendu_bilan.pdf", rows[1])
        self.assertIn("Pièce n°002;2024-09;2024-09_attestation_ecole.pdf", rows[2])

        zip_path: str = os.path.join(self.exp_dir, "Pack_Avocat_Complet.zip")
        self.assertTrue(os.path.isfile(zip_path))
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            self.assertIn("Bordereau_des_Pieces.csv", names)
            self.assertTrue(any("Piece_001_2024-05" in n for n in names))
            self.assertTrue(any("Piece_002_2024-09" in n for n in names))

    def test_gui_export_lawyer_pack_button(self) -> None:
        """Vérifie le déclenchement du Pack Avocat depuis l'interface graphique."""
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        with open(
            os.path.join(self.tmp_root, "data", "mots_exclus.txt"), "w", encoding="utf-8"
        ) as f_ex:
            f_ex.write("# Mots exclus\n")

        orig_root: str = gui_anonymizer.ROOT_DIR
        gui_anonymizer.ROOT_DIR = self.tmp_root
        try:
            try:
                app = gui_anonymizer.AnonymizerGuiApp()
                app.withdraw()
            except tk.TclError as exc:
                self.skipTest(f"Environnement sans affichage graphique : {exc}")

            try:
                with patch.object(gui_anonymizer.messagebox, "showinfo"):
                    app.new_ws_name_var.set("Dossier_Juridique")
                    app._create_new_workspace()

                ini_path: str = app.current_ini_var.get()
                paths = app.controller.resolve_workspace_paths(ini_path)
                batch_dir = os.path.join(paths["results_dir"], "batch_01")
                os.makedirs(batch_dir, exist_ok=True)
                with open(
                    os.path.join(batch_dir, "anonymized_part_001.txt"), "w", encoding="utf-8"
                ) as f_b:
                    f_b.write(
                        "==================================================\n"
                        "DOCUMENT : 2024-06_courrier.pdf\n"
                        "==================================================\n"
                        "Courrier de Camille D.\n"
                    )

                with patch.object(gui_anonymizer.messagebox, "showinfo"), patch.object(
                    app, "_open_path_in_os"
                ) as mock_open:
                    app._export_lawyer_pack()
                    mock_open.assert_called_once()

                ws_dir: str = os.path.dirname(os.path.abspath(ini_path))
                pack_dir: str = os.path.join(ws_dir, "pack_avocat")
                self.assertTrue(
                    os.path.isfile(os.path.join(pack_dir, "Bordereau_des_Pieces.csv"))
                )
                self.assertTrue(
                    os.path.isfile(os.path.join(pack_dir, "Pack_Avocat_Complet.zip"))
                )
            finally:
                app.destroy()
        finally:
            gui_anonymizer.ROOT_DIR = orig_root


if __name__ == "__main__":
    unittest.main()
