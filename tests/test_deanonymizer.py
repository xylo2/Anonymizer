# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import shutil
import sys
import tempfile
import unittest
import docx

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.deanon_vault import DeanonVaultManager
from doc_anonymizer.gui_controller import AnonymizerGuiController


class TestDocumentDeanonymizer(unittest.TestCase):
    """Vérifie le coffre de réversibilité, les balises numérotées et l'export _nominatif."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_deanon_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "collisions_noms.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        with open(os.path.join(self.tmp_root, "data", "prenoms.txt"), "w", encoding="utf-8") as f_p:
            f_p.write("camille\nmarc\nleo\nsophie\n")
        with open(os.path.join(self.tmp_root, "data", "villes_masquees.txt"), "w", encoding="utf-8") as f_v:
            f_v.write("Ville-Alpha\nBourg-Beta\n")
        self.ctrl = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_vault_roundtrip_with_numbered_placeholders_and_auto_names(self) -> None:
        """Vérifie la réversibilité complète via audits/deanon_vault.json et balises numérotées."""
        ini_path: str = self.ctrl.create_workspace("Dossier_Vault_Complet")
        with open(ini_path, "a", encoding="utf-8") as f_ini:
            f_ini.write(
                "\n[anonymization]\n"
                "numbered_placeholders = true\n"
                "masked_birth_dates = 15/06/2015, 01/01/1985\n"
            )

        cfg = PipelineConfig(ini_path)
        runner = DocumentAnonymizationRunner(cfg)
        runner.initialize()

        raw_doc: str = (
            "Camille Dupont (née le 01/01/1985 — mail : camille.dupont@exemple.fr — tél : 06 11 22 33 44) "
            "et Marc Lefevre résident au 12 avenue Victor Hugo à Ville-Alpha et travaillent à Bourg-Beta. "
            "Suivi de Léo Dupont (15/06/2015) par Dr Valmont."
        )
        anon_doc: str = runner.anonymize_text(raw_doc)
        runner.vault.save()

        reloaded_vault = DeanonVaultManager(runner.vault.vault_path)
        reloaded_vault.load()
        self.assertEqual(reloaded_vault.get_or_create_numbered_token("LIEU", "Ville-Alpha", "Lieu"), "[LIEU_01]")

        ai_reply: str = os.path.join(self.tmp_root, "synthese_ia.md")
        with open(ai_reply, "w", encoding="utf-8") as f_ai:
            f_ai.write(f"Synthèse IA :\n{anon_doc}\n")

        proposals, _, archived = self.ctrl.analyze_ai_files_for_deanonymization(ini_path, [ai_reply])
        exported, out_dir = self.ctrl.export_deanonymized_ai_files(ini_path, archived, proposals)
        self.assertEqual(len(exported), 1)
        with open(os.path.join(out_dir, "synthese_ia_nominatif.md"), "r", encoding="utf-8") as f_out:
            restored: str = f_out.read()

        self.assertIn("Camille Dupont", restored)
        self.assertIn("Marc Lefevre", restored)
        self.assertIn("Léo Dupont", restored)
        self.assertIn("Dr Valmont", restored)
        self.assertIn("01/01/1985", restored)
        self.assertIn("15/06/2015", restored)
        self.assertIn("12 avenue Victor Hugo", restored)
        self.assertIn("Ville-Alpha", restored)
        self.assertIn("Bourg-Beta", restored)
        self.assertIn("camille.dupont@exemple.fr", restored)
        self.assertIn("06 11 22 33 44", restored)

    def test_probable_choices_doc_dates_locations_and_archived_listing(self) -> None:
        ini_path: str = self.ctrl.create_workspace("Dossier_Retour_IA")
        paths = self.ctrl.resolve_workspace_paths(ini_path)

        with open(paths["mapping_file"], "w", encoding="utf-8") as f_m:
            json.dump(
                {
                    "Camille Dupont": {"alias": "Camille D.", "real_name": "Camille Dupont"},
                    "Sophie Roussel": {"alias": "Sophie R.", "real_name": "Sophie Roussel"},
                    "Léo Dupont": {"alias": "Léo D.", "real_name": "Léo Dupont"},
                },
                f_m,
            )
        with open(paths["manual_contacts_file"], "w", encoding="utf-8") as f_man:
            f_man.write("Marc Lefevre = Marc L.\n15/06/2015 = [DATE_MASQUEE]\n")

        src_map_path: str = os.path.join(os.path.dirname(paths["audit_report_file"]), "source_files_mapping.json")
        with open(src_map_path, "w", encoding="utf-8") as f_sm:
            json.dump(
                {
                    "files": {
                        "extracted_texts/2024-08/Audio/Léo_D._20240801.txt": {
                            "extracted_file": os.path.join(paths["transcriptions_dir"], "2024-08", "Audio", "Léo_Dupont_20240801.txt"),
                            "original_source_file": os.path.join(paths["sources_dir"], "Léo_Dupont_20240801.mp3"),
                            "batch_file": "",
                        }
                    }
                },
                f_sm,
            )

        external_dir: str = os.path.join(self.tmp_root, "telechargements_ia")
        os.makedirs(external_dir, exist_ok=True)
        ai_md: str = os.path.join(external_dir, "bilan_ia.md")
        with open(ai_md, "w", encoding="utf-8") as f_md:
            f_md.write(
                "# Bilan\n"
                "Camille D. et Marc L. accompagnent Léo (13 ans) né le [JOUR_MOIS_MASQUES]/2015 chez le Dr R. à [LIEU_MASQUE] "
                "malgré les cris et [ADRESSE_MASQUEE].\n"
                "Pièce clé : `# SOURCE TRANSCRIPTION : extracted_texts/2024-08/Audio/Léo_D._20240801.txt`.\n"
            )

        ai_docx: str = os.path.join(external_dir, "note.docx")
        doc = docx.Document()
        doc.add_paragraph("Suivi de Camille D. avec Dr R.")
        doc.save(ai_docx)

        proposals, _, archived = self.ctrl.analyze_ai_files_for_deanonymization(ini_path, [ai_md, ai_docx])
        self.assertEqual(len(archived), 2)
        self.assertEqual(len(self.ctrl.list_archived_ai_files(ini_path)), 2)
        by_tok = {p["token"]: p for p in proposals}

        self.assertNotIn("cris", by_tok)
        self.assertEqual(by_tok["Camille D."]["proposed"], "Camille Dupont")
        self.assertEqual(by_tok["Marc L."]["proposed"], "Marc Lefevre")
        self.assertEqual(by_tok["Léo"]["proposed"], "Léo Dupont")
        self.assertEqual(by_tok["[JOUR_MOIS_MASQUES]/2015"]["proposed"], "15/06/2015")
        self.assertIn("Ville-Alpha", by_tok["[LIEU_MASQUE]"]["alternatives"])
        self.assertIn("Léo_Dupont_20240801", by_tok["extracted_texts/2024-08/Audio/Léo_D._20240801.txt"]["proposed"])

        dr_alts = by_tok["Dr R."]["alternatives"]
        self.assertIn("Dr Roussel", dr_alts)
        self.assertIn("choix probable", by_tok["Dr R."]["status"])

        by_tok["Dr R."]["proposed"] = "Dr Roussel"
        by_tok["Dr R."]["apply"] = True
        by_tok["[LIEU_MASQUE]"]["proposed"] = "Ville-Alpha"
        by_tok["[LIEU_MASQUE]"]["apply"] = True
        by_tok["[ADRESSE_MASQUEE]"]["proposed"] = "12 rue des Lilas"
        by_tok["[ADRESSE_MASQUEE]"]["apply"] = True

        exported, out_dir = self.ctrl.export_deanonymized_ai_files(ini_path, archived, proposals)
        self.assertEqual(len(exported), 2)
        with open(os.path.join(out_dir, "bilan_ia_nominatif.md"), "r", encoding="utf-8") as f_res:
            res_txt: str = f_res.read()
        self.assertIn("né le 15/06/2015 chez le Dr Roussel à Ville-Alpha", res_txt)
        self.assertIn("Léo_Dupont_20240801", res_txt)


if __name__ == "__main__":
    unittest.main()
