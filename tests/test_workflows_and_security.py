# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import os
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from tools.completer_contacts_manuels import ManualContactsAutoCompleter


class TestWorkflowsAndSecurity(unittest.TestCase):
    """
    Valide la sécurité XML (XXE), l'extraction SMS, l'auto-complétion
    des contacts manuels et la passe --manual-only sur lots existants.
    """

    def test_xml_xxe_security_and_sms_parsing(self) -> None:
        """
        Vérifie le blocage des déclarations DOCTYPE/ENTITY et le tri des SMS.
        """
        with tempfile.TemporaryDirectory(prefix="test_sms_sec_") as tmp_dir:
            cfg = PipelineConfig(config_path=os.path.join(tmp_dir, "config.ini"))
            cfg.enable_ocr = False
            cfg.enable_audio = False
            comm = CommunicationExtractor(cfg, OfficeAndDocumentExtractor(enable_ocr=False))

            xxe_xml: str = os.path.join(tmp_dir, "malicious.xml")
            with open(xxe_xml, "w", encoding="utf-8") as f_xxe:
                f_xxe.write('<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe "test">]><smses></smses>')

            _, errors_xxe = comm.parse_sms_xml(xxe_xml, {"0611223344": "Alice B."}, set(), set())
            self.assertTrue(errors_xxe)
            self.assertIn("interdite", errors_xxe[0])

            valid_xml: str = os.path.join(tmp_dir, "sms_valid.xml")
            with open(valid_xml, "w", encoding="utf-8") as f_sms:
                f_sms.write(
                    '<smses>'
                    '<sms address="+33611223344~0699887766" date="1715769000000" type="1" body="Second message" />'
                    '<sms address="0611223344" date="1715765400000" type="2" body="Premier message" />'
                    '</smses>'
                )
            disc_phones = set()
            by_month, errors_ok = comm.parse_sms_xml(valid_xml, {"0611223344": "Alice B."}, set(), disc_phones)
            self.assertFalse(errors_ok)
            self.assertIn("2024-05", by_month)
            self.assertEqual(len(by_month["2024-05"]), 2)
            self.assertIn("0699887766", disc_phones)
    def test_manual_autocompleter_and_manual_only_pass(self) -> None:
        """
        Vérifie la complétion automatique de contacts_manuels.txt et son
        application directe sur des lots déjà générés (--manual-only).
        """
        with tempfile.TemporaryDirectory(prefix="test_manual_pass_") as tmp_dir:
            prenoms_path: str = os.path.join(tmp_dir, "prenoms.txt")
            with open(prenoms_path, "w", encoding="utf-8") as f_fn:
                f_fn.write("claire\npaul\n")

            contacts_path: str = os.path.join(tmp_dir, "contacts.txt")
            with open(contacts_path, "w", encoding="utf-8") as f_ct:
                f_ct.write("Paul Durand = Paul D.\n")

            manual_path: str = os.path.join(tmp_dir, "contacts_manuels.txt")
            with open(manual_path, "w", encoding="utf-8") as f_man:
                f_man.write("Claire Moreau = \n")

            cfg_path: str = os.path.join(tmp_dir, "config.ini")
            with open(cfg_path, "w", encoding="utf-8") as f_cfg:
                f_cfg.write(
                    "[files]\nfirst_names_file = prenoms.txt\ninverted_output_file = contacts.txt\n"
                    "[paths]\nroot_dir = .\ncontacts_file = contacts.txt\n"
                    "manual_contacts_file = contacts_manuels.txt\n"
                    "discovered_contacts_file = contacts_emails_decouverts.txt\n"
                    "transcriptions_dir = transcriptions\nresults_dir = resultats_anonymisation\n"
                    "audit_report_file = audit_noms_residuels.txt\n"
                    "audit_copy_file = audit_noms_residuels_copier.txt\n"
                )

            config = PipelineConfig(config_path=cfg_path)
            completed, _ = ManualContactsAutoCompleter(config=config, dry_run=False).process()
            self.assertEqual(completed, 1)

            with open(manual_path, "r", encoding="utf-8") as f_man_r:
                self.assertIn("Claire Moreau = Claire M.", f_man_r.read())

            lot_dir: str = os.path.join(config.results_dir, "lot_01")
            os.makedirs(lot_dir, exist_ok=True)
            lot_file: str = os.path.join(lot_dir, "anonymise_partie_001.txt")
            with open(lot_file, "w", encoding="utf-8") as f_lot:
                f_lot.write("Compte-rendu signé par Claire Moreau.\n")

            DocumentAnonymizationRunner(config=config, manual_only=True).run_on_existing_results()
            with open(lot_file, "r", encoding="utf-8") as f_lot_r:
                updated_txt: str = f_lot_r.read()
            self.assertIn("Claire M.", updated_txt)
            self.assertNotIn("Claire Moreau", updated_txt)


if __name__ == "__main__":
    unittest.main()
