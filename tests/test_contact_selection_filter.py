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
from doc_anonymizer.gui_controller import AnonymizerGuiController
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner


class TestContactSelectionFilter(unittest.TestCase):
    """Vérifie le chargement multi-CSV, le cochage par défaut des nouveaux ajouts et la conservation reçus + envoyés."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_contact_sel_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        with open(os.path.join(self.tmp_root, "data", "prenoms.txt"), "w", encoding="utf-8") as f_p:
            f_p.write("camille\nmarc\nsophie\n")
        for fn in ("mots_exclus.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        self.ctrl: AnonymizerGuiController = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_newly_imported_csv_contacts_default_to_selected_without_overwriting_previous_choices(self) -> None:
        ini_path: str = self.ctrl.create_workspace("Affaire_Filtre_Multi_CSV")
        paths = self.ctrl.resolve_workspace_paths(ini_path)

        csv_1: str = os.path.join(self.tmp_root, "contacts_google.csv")
        with open(csv_1, "w", encoding="utf-8") as f_csv1:
            f_csv1.write(
                "First Name,Last Name,Phone 1 - Value,E-mail 1 - Value\n"
                "Camille,Dupont,06 11 22 33 44,camille.dupont@exemple.fr\n"
                "Marc,Lefevre,06 55 66 77 88,marc.lefevre@exemple.fr\n"
            )
        self.ctrl.import_contacts_csv(ini_path, csv_1)
        items_1 = self.ctrl.load_contact_filter_items(ini_path)
        for it in items_1:
            it["selected"] = str(it.get("display_name")) == "Camille Dupont"
        self.ctrl.save_contact_filter_selection(ini_path, items_1)

        csv_2: str = os.path.join(self.tmp_root, "contacts_outlook.csv")
        with open(csv_2, "w", encoding="utf-8") as f_csv2:
            f_csv2.write(
                "First Name,Last Name,Phone 1 - Value,E-mail 1 - Value\n"
                "Sophie,Martin,06 99 88 77 66,sophie.martin@exemple.fr\n"
            )
        self.ctrl.import_contacts_csv(ini_path, csv_2)

        items_2 = self.ctrl.load_contact_filter_items(ini_path)
        state_by_name = {str(it.get("display_name")): bool(it.get("selected")) for it in items_2}
        self.assertEqual(
            state_by_name,
            {"Camille Dupont": True, "Marc Lefevre": False, "Sophie Martin": True},
        )
        self.ctrl.save_contact_filter_selection(ini_path, items_2)

        sms_xml: str = os.path.join(paths["sources_dir"], "sms_2024-06.xml")
        with open(sms_xml, "w", encoding="utf-8") as f_xml:
            f_xml.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<smses>\n"
                '  <sms address="0611223344" date="1718442000000" type="1" body="SMS reçu pertinent de Camille." />\n'
                '  <sms address="0611223344" date="1718442300000" type="2" body="SMS envoyé par moi à Camille." />\n'
                '  <sms address="0655667788" date="1718442600000" type="1" body="SMS reçu hors sujet de Marc." />\n'
                "</smses>\n"
            )

        DocAnonymizerPipelineRunner(PipelineConfig(ini_path), prevent_sleep=False).run_all()

        merged_lots: str = ""
        for rp, _, files in os.walk(paths["results_dir"]):
            for fn in sorted(files):
                if fn.endswith(".txt"):
                    with open(os.path.join(rp, fn), "r", encoding="utf-8") as f_r:
                        merged_lots += f_r.read() + "\n"

        self.assertIn("SMS reçu pertinent de Camille.", merged_lots)
        self.assertIn("SMS envoyé par moi à Camille.", merged_lots)
        self.assertNotIn("hors sujet", merged_lots)


if __name__ == "__main__":
    unittest.main()
