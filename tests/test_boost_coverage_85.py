# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.chat_prescanner import ChatContactPrescanner
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_rules_loader import ContactRulesLoader
from doc_anonymizer.manual_contacts_importer import AuditManualContactsImporter
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.teams_chat_extractor import TeamsChatExtractor
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.vcard_reader import VCardContactsReader
from tools.copy_unmasked_transcriptions import UnmaskedTranscriptionCopier


class TestBoostCoverage85(unittest.TestCase):
    """Couvre vCard (.vcf), AuditManualContactsImporter, ChatContactPrescanner, Teams, Audio et Copier."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_boost_cov_")
        os.makedirs(os.path.join(self.tmp_dir, "input_contacts"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_dir, "input_documents"), exist_ok=True)
        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("camille\njean\nsophie\nmarc\nclaire\n")
        with open(os.path.join(self.tmp_dir, "villes_masquees.txt"), "w", encoding="utf-8") as f:
            f.write("lyon\nparis\n")
        with open(os.path.join(self.tmp_dir, "mots_exclus.txt"), "w", encoding="utf-8") as f:
            f.write("tribunal\n")

        self.ini_path: str = os.path.join(self.tmp_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f_ini:
            f_ini.write(
                "[files]\n"
                "csv_directory = input_contacts\n"
                "first_names_file = prenoms.txt\n"
                "locations_file = villes_masquees.txt\n"
                "excluded_words_file = mots_exclus.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = input_documents\n"
                "transcriptions_dir = extracted_texts\n"
                "results_dir = anonymized_results\n"
                "contacts_file = contacts.txt\n"
                "manual_contacts_file = manual_contacts.txt\n"
                "discovered_contacts_file = discovered_email_contacts.txt\n"
                "discovered_chats_file = discovered_chat_contacts.txt\n"
                "audit_report_file = audits/residual_names_audit.txt\n"
                "audit_copy_file = audits/residual_names_copy.txt\n"
                "[extraction]\n"
                "enable_ocr = false\n"
                "enable_audio = true\n"
            )
        self.config: PipelineConfig = PipelineConfig(self.ini_path)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_vcard_reader_quoted_printable_folding_and_org(self) -> None:
        """Couvre VCardContactsReader (lignes dépliées, QUOTED-PRINTABLE, N, FN, ORG, TEL, EMAIL)."""
        vcf_path: str = os.path.join(self.tmp_dir, "input_contacts", "apple_contacts.vcf")
        with open(vcf_path, "w", encoding="utf-8") as f_vcf:
            f_vcf.write(
                "BEGIN:VCARD\n"
                "VERSION:3.0\n"
                "N:Dupont;Camille;Marie;;\n"
                "FN;ENCODING=QUOTED-PRINTABLE;CHARSET=UTF-8:Camille=20Dupont\n"
                "EMAIL;TYPE=INTERNET:camille.dupont@exemple.fr\n"
                "TEL;TYPE=CELL:+33 6 12 34\n"
                " 56 78\n"
                "END:VCARD\n"
                "BEGIN:VCARD\n"
                "VERSION:3.0\n"
                "ORG:Cabinet Médical;Lyon\n"
                "EMAIL:contact@cabinet-sante.fr\n"
                "END:VCARD\n"
            )

        c_cfg = ContactsConfig(self.ini_path)
        reader = VCardContactsReader(c_cfg)
        pairs = reader.parse_file(vcf_path)
        self.assertEqual(len(pairs), 3)
        mapped = dict(pairs)
        self.assertEqual(mapped.get("camille.dupont@exemple.fr"), "Camille-Marie Dupont")
        self.assertEqual(mapped.get("+33 6 12 3456 78"), "Camille-Marie Dupont")
        self.assertEqual(mapped.get("contact@cabinet-sante.fr"), "Cabinet Médical Lyon")
        self.assertEqual(reader.parse_file(os.path.join(self.tmp_dir, "inexistant.vcf")), [])
    def test_manual_contacts_importer_full_flow(self) -> None:
        """Couvre AuditManualContactsImporter (lecture audit, seuils, exclusions, écriture)."""
        os.makedirs(os.path.dirname(self.config.audit_report_file), exist_ok=True)
        with open(self.config.manual_contacts_file, "w", encoding="utf-8") as f_m:
            f_m.write("Jean Dupont = Jean D.\n")

        with open(self.config.audit_report_file, "w", encoding="utf-8") as f_aud:
            f_aud.write(
                "# Rapport\n"
                "Marc Valmont = A_MASQUER   # [  5x] doc1.txt\n"
                "Sophie Delacroix = Sophie D.   # [  4x] doc2.txt\n"
                "Jean Dupont = Jean D.   # [  8x] doc1.txt\n"
                "Tribunal Lyon = A_MASQUER   # [  6x] doc3.txt\n"
                "Claire Rare = A_MASQUER   # [  1x] doc4.txt\n"
            )

        rules = ContactRulesLoader(self.config)
        rules.load_all()
        importer = AuditManualContactsImporter(self.config, rules, min_occurrences=3)
        imported_count: int = importer.import_high_confidence_from_audit()
        self.assertEqual(imported_count, 2)

        with open(self.config.manual_contacts_file, "r", encoding="utf-8") as f_m:
            content: str = f_m.read()
        self.assertIn("Marc Valmont = Marc V.", content)
        self.assertIn("Sophie Delacroix = Sophie D.", content)
        self.assertNotIn("Tribunal Lyon", content)
        self.assertNotIn("Claire Rare", content)

    def test_chat_prescanner_vtt_sms_eml_and_teams_mentions(self) -> None:
        """Couvre ChatContactPrescanner (.vtt, .xml, .eml, JSON participants) et TeamsChatExtractor."""
        src_dir: str = self.config.sources_dir
        with open(os.path.join(src_dir, "reunion.vtt"), "w", encoding="utf-8") as f_vtt:
            f_vtt.write(
                "WEBVTT\n\n"
                "00:01:02.000 --> 00:01:05.000\n"
                "<v Claire Bernard>Contactez marc.lefevre@entreprise.fr svp.</v>\n"
            )
        with open(os.path.join(src_dir, "sms_export.xml"), "w", encoding="utf-8") as f_xml:
            f_xml.write('<smses><sms address="0601020304" contact_name="Sophie Renard" body="Salut" /></smses>')
        with open(os.path.join(src_dir, "courriel.eml"), "w", encoding="utf-8") as f_eml:
            f_eml.write("From: Alice Garnier <alice.garnier@domaine.fr>\nTo: bob@domaine.fr\nSubject: Test\n\nCorps.\n")
        with open(os.path.join(src_dir, "messenger.json"), "w", encoding="utf-8") as f_js:
            json.dump({"participants": [{"name": "Nicolas Moreau", "email": "nicolas@domaine.fr"}], "messages": []}, f_js)

        prescanner = ChatContactPrescanner(
            sources_dir=src_dir,
            discovered_chats_file=self.config.discovered_chats_file,
            discovered_emails_file=self.config.discovered_contacts_file,
            known_first_names={"claire", "sophie", "marc"},
        )
        added_chats, added_emails = prescanner.prescan_sources()
        self.assertGreaterEqual(added_chats, 2)
        self.assertGreaterEqual(added_emails, 3)

        teams_ext = TeamsChatExtractor(self.config)
        disc_dict: dict[str, str] = {}
        payload = [
            {
                "messageType": "message",
                "createdDateTime": "1730000000000",
                "from": {"user": {"displayName": "Marc Lefevre", "userPrincipalName": "marc@org.fr"}},
                "content": '<p>Bonjour <at email="claire@org.fr">Claire</at></p>',
                "attachments": [{"name": "rapport.pdf"}, "annexe.docx"],
                "mentions": [{"mentioned": {"user": {"email": "sophie@org.fr", "displayName": "Sophie"}}}],
            }
        ]
        rendered = teams_ext.extract_teams_json("flat_teams.json", payload, disc_dict)
        self.assertTrue(rendered)
        joined_teams: str = "\n".join(rendered.values())
        self.assertIn("rapport.pdf", joined_teams)
        self.assertIn("claire@org.fr", disc_dict)
    def test_comm_extractor_audio_and_aup3_with_mock_whisper(self) -> None:
        """Couvre CommunicationExtractor.extract_audio et extract_audacity_aup3 sans modèle réel."""
        office_ext = OfficeAndDocumentExtractor(config=self.config, enable_ocr=False)
        comm_ext = CommunicationExtractor(config=self.config, doc_extractor=office_ext)

        fake_seg = MagicMock()
        fake_seg.start = 65.0
        fake_seg.text = "Bonjour Camille Dupont, ceci est un test vocal."
        fake_model = MagicMock()
        fake_model.transcribe.return_value = ([fake_seg], None)
        comm_ext._whisper_model = fake_model

        mp3_path: str = os.path.join(self.tmp_dir, "appel_0612345678.mp3")
        with open(mp3_path, "wb") as f_mp3:
            f_mp3.write(b"FAKE_MP3")

        audio_txt, err_audio = comm_ext.extract_audio(mp3_path)
        self.assertIsNone(err_audio)
        assert audio_txt is not None
        self.assertIn("[01:05] Bonjour Camille Dupont", audio_txt)
        self.assertIn("0612345678", audio_txt)

        aup3_path: str = os.path.join(self.tmp_dir, "projet_audacity.aup3")
        conn = sqlite3.connect(aup3_path)
        conn.execute("CREATE TABLE sampleblocks (blockid INTEGER PRIMARY KEY, samples BLOB)")
        conn.execute("INSERT INTO sampleblocks (blockid, samples) VALUES (1, ?)", (b"\x00\x00\x80\x3f" * 100,))
        conn.commit()
        conn.close()

        aup3_txt, err_aup3 = comm_ext.extract_audacity_aup3(aup3_path)
        self.assertIsNone(err_aup3)
        assert aup3_txt is not None
        self.assertIn("AUDIO : projet_audacity.aup3", aup3_txt)

    def test_unmasked_copier_list_file_and_missing_targets(self) -> None:
        """Couvre extract_targets_from_list_file (Markdown, backticks, puces, en-têtes) et introuvables."""
        list_md: str = os.path.join(self.tmp_dir, "liste_ia.md")
        with open(list_md, "w", encoding="utf-8") as f_md:
            f_md.write(
                "// Commentaire ignoré\n"
                "# SOURCE TRANSCRIPTION : 2024-05/Documents/piece_1.txt\n"
                "- `2024-06/Emails/mail_2.txt`\n"
                "* Chats/chat_3.txt\n"
            )

        copier = UnmaskedTranscriptionCopier(
            config=self.config,
            output_dir=os.path.join(self.tmp_dir, "out_copies"),
        )
        targets = copier.extract_targets_from_list_file(list_md)
        self.assertEqual(
            targets,
            [
                "2024-05/Documents/piece_1.txt",
                "2024-06/Emails/mail_2.txt",
                "Chats/chat_3.txt",
            ],
        )
        copied, missing = copier.copy_from_targets(targets)
        self.assertEqual((copied, missing), (0, 3))


if __name__ == "__main__":
    unittest.main()
