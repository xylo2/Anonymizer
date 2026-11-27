# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.dossier_exporter import LawyerDossierExporter
from doc_anonymizer.gui_controller import AnonymizerGuiController
from doc_anonymizer.linked_sources_manager import LinkedSourcesManager
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner


class TestLinkedSourcesReadOnly(unittest.TestCase):
    """Vérifie que les fichiers référencés ne sont jamais modifiés, renommés ni déplacés."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_linked_ro_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        with open(os.path.join(self.tmp_root, "data", "prenoms.txt"), "w", encoding="utf-8") as f_p:
            f_p.write("camille\nmarc\n")
        self.ctrl = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_linked_files_and_folders_are_never_modified_or_moved(self) -> None:
        ini_path: str = self.ctrl.create_workspace("Dossier_Liens_RO")
        paths = self.ctrl.resolve_workspace_paths(ini_path)

        external_repo: str = os.path.join(self.tmp_root, "mes_archives_personnelles")
        os.makedirs(external_repo, exist_ok=True)

        orig_note: str = os.path.join(external_repo, "2024-06_compte_rendu.txt")
        orig_note_content: str = "Compte rendu AnonVault de Camille Dupont.\n"
        with open(orig_note, "w", encoding="utf-8") as f_n:
            f_n.write(orig_note_content)
        orig_mtime: float = os.path.getmtime(orig_note)

        orig_csv: str = os.path.join(external_repo, "contacts_famille.csv")
        with open(orig_csv, "w", encoding="utf-8") as f_c:
            f_c.write("First Name,Last Name,E-mail 1 - Value\nCamille,Dupont,camille@exemple.fr\n")

        needs_prompt_unc, lbl_unc = LinkedSourcesManager.classify_storage_location(
            r"\\NAS-MAISON\Partage\Dossier", paths["workspace_root"]
        )
        self.assertTrue(needs_prompt_unc)
        self.assertIn("NAS", lbl_unc)

        added_links, copied_local = self.ctrl.register_or_copy_sources(
            ini_path, [external_repo], copy_external=False
        )
        self.assertEqual((added_links, copied_local), (1, 0))
        self.assertFalse(os.path.exists(os.path.join(paths["sources_dir"], "2024-06_compte_rendu.txt")))

        self.ctrl.auto_organize_dropped_files(ini_path)
        self.assertTrue(os.path.isfile(orig_csv))
        self.assertTrue(os.path.isfile(orig_note))

        cfg = PipelineConfig(ini_path)
        DocAnonymizerPipelineRunner(cfg, prevent_sleep=False).run_all()

        self.assertTrue(os.path.isfile(orig_note))
        self.assertEqual(os.path.getmtime(orig_note), orig_mtime)
        with open(orig_note, "r", encoding="utf-8") as f_check:
            self.assertEqual(f_check.read(), orig_note_content)

        src_map_file: str = os.path.join(
            os.path.dirname(paths["audit_report_file"]), "source_files_mapping.json"
        )
        exporter = LawyerDossierExporter(
            results_dir=paths["results_dir"],
            export_dir=os.path.join(paths["workspace_root"], "pack_avocat"),
            transcriptions_dir=paths["transcriptions_dir"],
            sources_dir=paths["sources_dir"],
            mapping_file=src_map_file,
        )
        pieces = exporter.collect_nominative_pieces()
        self.assertEqual(len(pieces), 2)
        orig_sources = {os.path.normpath(p["chemin_original_source"]) for p in pieces if p["chemin_original_source"]}
        self.assertIn(os.path.normpath(orig_note), orig_sources)


if __name__ == "__main__":
    unittest.main()
