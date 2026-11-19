# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import tempfile
import unittest
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.manual_contacts_importer import ManualContactsAutoCompleter
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.text_utils import DocumentTextUtils


class TestWorkflowsAndSecurity(unittest.TestCase):
    """
    Vérifie la sécurité XML (protection XXE), le tri des SMS et le workflow complet
    d'anonymisation automatique, d'audit, d'import manuel et de passe sur place.
    """

    def setUp(self) -> None:
        """Prépare un répertoire isolé et une configuration complète pour les tests."""
        self.test_dir: str = tempfile.mkdtemp(prefix="test_workflows_")
        self.trans_dir: str = os.path.join(self.test_dir, "transcriptions")
        self.res_dir: str = os.path.join(self.test_dir, "resultats_anonymisation")
        os.makedirs(self.trans_dir, exist_ok=True)

        self.config: PipelineConfig = PipelineConfig()
        self.config.transcriptions_dir = self.trans_dir
        self.config.results_dir = self.res_dir
        self.config.contacts_file = os.path.join(self.test_dir, "contacts.txt")
        self.config.indexed_contacts_file = os.path.join(self.test_dir, "contacts_indexes.txt")
        self.config.anonymized_contacts_file = os.path.join(self.test_dir, "contacts_anonymises.txt")
        self.config.discovered_contacts_file = os.path.join(self.test_dir, "contacts_emails_decouverts.txt")
        self.config.manual_contacts_file = os.path.join(self.test_dir, "contacts_manuels.txt")
        self.config.excluded_words_file = os.path.join(self.test_dir, "mots_exclus.txt")
        self.config.locations_file = os.path.join(self.test_dir, "villes_masquees.txt")
        self.config.first_names_file = os.path.join(self.test_dir, "prenoms.txt")
        self.config.resume_state_file = os.path.join(self.res_dir, ".etat_anonymisation.json")
        self.config.audit_report_file = os.path.join(self.test_dir, "audit_noms_residuels.txt")
        self.config.audit_copy_file = os.path.join(self.test_dir, "audit_noms_residuels_copier.txt")
        self.config.main_character_name = "Aurélie"
        self.config.max_batch_bytes = 50000

        DocumentTextUtils.atomic_write_text(
            self.config.contacts_file,
            "0611223344 = Jean Dupont\n"
            "JEAN.DUPONT@EXEMPLE.FR = Jean D.\n"
            "Dupont Jean = Jean D.\n",
        )
        DocumentTextUtils.atomic_write_text(
            self.config.manual_contacts_file,
            "# Règles manuelles\n",
        )
        DocumentTextUtils.atomic_write_text(
            self.config.excluded_words_file,
            "conge\nvacances\n",
        )
        DocumentTextUtils.atomic_write_text(
            self.config.locations_file,
            "caen\n",
        )
        DocumentTextUtils.atomic_write_text(
            self.config.first_names_file,
            "jean\npaul\nclaire\naurelie\n",
        )
        self.config.load_external_lists()

    def tearDown(self) -> None:
        """Nettoie le répertoire temporaire après chaque test."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    def test_xml_xxe_security_and_sms_parsing(self) -> None:
        """
        Vérifie le blocage des déclarations DOCTYPE/ENTITY et le tri des SMS.
        """
        doc_ext = OfficeAndDocumentExtractor(enable_ocr=False)
        comm_ext = CommunicationExtractor(config=self.config, doc_extractor=doc_ext)

        xxe_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>\n'
            '<smses><sms date="1700000000000" type="1" address="0611223344" body="&xxe;" /></smses>'
        )
        xxe_path = os.path.join(self.test_dir, "malicious.xml")
        DocumentTextUtils.atomic_write_text(xxe_path, xxe_xml)

        _, errors_xxe = comm_ext.parse_sms_xml(
            xxe_path, {}, set(), set(), set()
        )
        self.assertTrue(errors_xxe)
        self.assertIn("interdite", " ".join(errors_xxe))

        valid_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<smses>\n'
            '  <sms date="1700000200000" type="2" address="0611223344" body="Second message" />\n'
            '  <sms date="1700000100000" type="1" address="0611223344" body="Premier message" />\n'
            '</smses>'
        )
        valid_path = os.path.join(self.test_dir, "sms_valid.xml")
        DocumentTextUtils.atomic_write_text(valid_path, valid_xml)
        phones_map = {"0611223344": "Jean Dupont"}
        sms_by_month, errors_valid = comm_ext.parse_sms_xml(
            valid_path, phones_map, set(), set(), set()
        )
        self.assertEqual(errors_valid, [])
        self.assertTrue(sms_by_month)

    def test_auto_titles_audit_import_and_manual_pass(self) -> None:
        """
        Vérifie le masquage automatique des titres, mots_exclus.txt,
        l'importation automatique de l'audit haute confiance et la passe sur place.
        """
        sub_dir = os.path.join(self.trans_dir, "2024-06", "Documents")
        os.makedirs(sub_dir, exist_ok=True)
        doc_path = os.path.join(sub_dir, "compte_rendu.txt")
        DocumentTextUtils.atomic_write_text(
            doc_path,
            "Consultation avec Dr Lefevre et Mme Moreau à Caen.\n"
            "Note sur Paul Conge et Paul Vacances.\n"
            "Rencontre 1 avec Claire Bernard.\n"
            "Rencontre 2 avec Claire Bernard.\n"
            "Rencontre 3 avec Claire Bernard.\n",
        )

        runner = DocumentAnonymizationRunner(self.config, manual_only=False)
        runner.run()

        lot_file = os.path.join(
            self.res_dir, "lot_01", "anonymise_partie_001.txt"
        )
        self.assertTrue(os.path.exists(lot_file))
        with open(lot_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Dr L.", content)
        self.assertIn("Mme M.", content)
        self.assertIn("[LIEU_MASQUE]", content)
        self.assertIn("Paul Conge", content)
        self.assertIn("Paul Vacances", content)

        DocumentTextUtils.atomic_write_text(
            self.config.audit_report_file,
            "Claire Bernard = Claire B.   # [  3x] compte_rendu.txt\n",
        )
        completer = ManualContactsAutoCompleter(
            self.config, runner.rules, min_occurrences=3
        )
        imported: int = completer.import_high_confidence_from_audit()
        self.assertGreaterEqual(imported, 1)

        manual_runner = DocumentAnonymizationRunner(
            self.config, manual_only=True
        )
        manual_runner.run_on_existing_results()

        with open(lot_file, "r", encoding="utf-8") as f:
            updated = f.read()
        self.assertIn("Claire B.", updated)
        self.assertNotIn("Claire Bernard", updated)


if __name__ == "__main__":
    unittest.main()
