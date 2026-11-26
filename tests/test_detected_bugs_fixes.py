import json
import os
import shutil
import sys
import tempfile
import tkinter as tk
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_csv_importer import build_person_initial_alias
from doc_anonymizer.extraction_runner import DocumentExtractionRunner
from doc_anonymizer.gui_controller import AnonymizerGuiController
from doc_anonymizer.text_utils import DocumentTextUtils
import gui_anonymizer


class TestDetectedBugsFixes(unittest.TestCase):
    """Couvre les correctifs des bugs détectés (compteur étape 1, extraction, GUI)."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_detected_bugs_")
        os.makedirs(os.path.join(self.tmp_dir, "data"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_dir, "input_documents"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_dir, "contacts"), exist_ok=True)
        with open(os.path.join(self.tmp_dir, "data", "prenoms.txt"), "w", encoding="utf-8") as f_p:
            f_p.write("camille\nmarc\nmarie-claire\njean-luc\nsophie\nclaire\n")
        for fn in ("mots_exclus.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_dir, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_step1_counter_keeps_total_after_auto_sorting_contacts_and_sms(self) -> None:
        """Vérifie que revenir à l'étape 1 après tri affiche le total global des pièces."""
        orig_root: str = gui_anonymizer.ROOT_DIR
        gui_anonymizer.ROOT_DIR = self.tmp_dir
        try:
            app = gui_anonymizer.AnonymizerGuiApp()
            app.withdraw()
            app._sync_docs_tasks = True  # type: ignore[attr-defined]
        except tk.TclError as exc:
            gui_anonymizer.ROOT_DIR = orig_root
            self.skipTest(f"Environnement headless : {exc}")

        try:
            app.gate_new_name_var.set("Dossier_Compteur")
            app._confirm_gate_and_workspace()
            paths = app.controller.resolve_workspace_paths(app.current_ini_var.get())

            for idx in (1, 2, 3):
                vcf_p: str = os.path.join(paths["sources_dir"], f"export_{idx}.vcf")
                with open(vcf_p, "w", encoding="utf-8") as f_v:
                    f_v.write(f"BEGIN:VCARD\nVERSION:3.0\nFN:Contact {idx}\nTEL:060000000{idx}\nEND:VCARD\n")
            sms_p: str = os.path.join(paths["sources_dir"], "sms.xml")
            with open(sms_p, "w", encoding="utf-8") as f_s:
                f_s.write('<smses><sms address="0611223344" body="Test" /></smses>')

            app._advance_from_documents()
            app._show_page("documents")
            summary: str = app.docs_summary_var.get()
            self.assertIn("4 fichier(s)", summary)
            self.assertIn("3 carnet(s)", summary)
            self.assertIn("1 SMS", summary)
        finally:
            app.destroy()
            gui_anonymizer.ROOT_DIR = orig_root

    def test_extraction_runner_full_pipeline_and_finalize_reports(self) -> None:
        """Vérifie l'extraction multi-formats et finalize_reports."""
        ini_path: str = os.path.join(self.tmp_dir, "config.ini")
        with open(ini_path, "w", encoding="utf-8") as f_ini:
            f_ini.write(
                "[files]\nfirst_names_file = data/prenoms.txt\n"
                "[paths]\nroot_dir = .\ncontacts_file = contacts/contacts.txt\n"
                "sources_dir = input_documents\ntranscriptions_dir = extracted_texts\n"
                "results_dir = anonymized_results\nall_sms_numbers_file = audits/sms.txt\n"
                "all_emails_file = audits/emails.txt\n"
            )
        src_dir: str = os.path.join(self.tmp_dir, "input_documents")
        with open(os.path.join(src_dir, "2024-06_note.txt"), "w", encoding="utf-8") as f_n:
            f_n.write("Note avec Camille Dupont au +32 470 12 34 56.\n")
        with open(os.path.join(src_dir, "messages.json"), "w", encoding="utf-8") as f_gc:
            json.dump(
                {"messages": [{"creator": {"name": "Sophie Martin", "email": "sophie@ex.fr"}, "created_date": "2024-06-01T10:00:00", "text": "Salut"}]},
                f_gc,
            )
        with open(os.path.join(src_dir, "message_1.json"), "w", encoding="utf-8") as f_fb:
            json.dump(
                {"title": "Claire Bernard", "participants": [{"name": "Claire Bernard"}], "messages": [{"sender_name": "Claire Bernard", "timestamp_ms": 1717236000000, "content": "Coucou"}]},
                f_fb,
            )

        cfg = PipelineConfig(ini_path)
        ext_runner = DocumentExtractionRunner(cfg)
        already: set[str] = set()
        sms_done: set[str] = set()
        disc_p: set[str] = set()
        disc_e: set[str] = set()
        for fp in ext_runner.collect_source_files():
            ext_runner.process_single_file(fp, {}, set(), already, sms_done, disc_p, disc_e)
        ext_runner.finalize_reports(disc_p, disc_e)

        self.assertEqual(len(already), 3)
        self.assertIn("+32470123456", disc_p)
        self.assertTrue(os.path.isfile(cfg.all_sms_numbers_file))
        self.assertTrue(os.path.isfile(cfg.all_emails_file))

    def test_gui_controller_workspace_helpers(self) -> None:
        """Vérifie les méthodes utilitaires d'AnonymizerGuiController."""
        ctrl = AnonymizerGuiController(self.tmp_dir)
        ini_path: str = ctrl.create_workspace("Test_Ctrl_Full")
        self.assertEqual(ctrl.detect_zip_files(ini_path), [])
        self.assertEqual(ctrl.load_contact_filter_items(ini_path), [])
        self.assertEqual(ctrl.list_sms_export_files(ini_path), [])
        self.assertEqual(ctrl.load_sms_number_filter_items(ini_path), [])
        _, script_path = ctrl.build_cli_command(ini_path, "full")[:2]
        self.assertTrue(script_path.endswith("run_documents.py"))

    def test_compound_particles_and_international_phones(self) -> None:
        """Vérifie le masquage des noms à particule et numéros internationaux."""
        self.assertEqual(build_person_initial_alias("", "", fallback="Marie-Claire De La Croix"), "Marie-Claire D. L. C.")
        self.assertEqual(build_person_initial_alias("Jean-Luc", "D'Artagnan"), "Jean-Luc D'A.")
        self.assertEqual(DocumentTextUtils.split_sms_addresses("+32 470 12 34 56~0032470123456"), ["+32470123456"])


if __name__ == "__main__":
    unittest.main()
