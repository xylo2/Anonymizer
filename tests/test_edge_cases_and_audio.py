# Commandes pip à exécuter : Aucune dépendance externe requise

from email.message import EmailMessage
import os
import shutil
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from odf.opendocument import OpenDocumentText
from odf.text import P as OdfP
import pymupdf
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.first_name_suggester import MissingFirstNamesSuggester


class TestEdgeCasesAndAudio(unittest.TestCase):
    """
    Couvre les fichiers .eml avec pièce jointe PDF, les projets Audacity (.aup3),
    le découpage en tranches > 32 Ko, l'extraction ODT et les suggestions de prénoms.
    """

    def setUp(self) -> None:
        """Prépare un répertoire temporaire isolé."""
        self.test_dir: str = tempfile.mkdtemp(prefix="test_edge_adv_")
        self.ini_path: str = os.path.join(self.test_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f:
            f.write(
                "[files]\n"
                "first_names_file = prenoms.txt\n"
                "suggested_first_names_file = prenoms_suggeres.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = fichiers sources\n"
                "transcriptions_dir = transcriptions\n"
                "results_dir = resultats_anonymisation\n"
                "contacts_file = contacts.txt\n"
                "[extraction]\n"
                "enable_ocr = false\n"
                "enable_audio = true\n"
                "[anonymization]\n"
                "main_character_name = Utilisateur_Principal\n"
                "max_batch_bytes = 2500\n"
                "files_per_folder = 2\n"
            )
        with open(
            os.path.join(self.test_dir, "prenoms.txt"), "w", encoding="utf-8"
        ) as f:
            f.write("jean\nmarie\nsophie\n")
        self.config: PipelineConfig = PipelineConfig(self.ini_path)

    def tearDown(self) -> None:
        """Supprime le répertoire temporaire."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_eml_with_pdf_attachment_and_odt_extractor(self) -> None:
        """Vérifie l'extraction d'un .eml avec pièce jointe PDF et d'un fichier .odt."""
        doc_ext = OfficeAndDocumentExtractor(enable_ocr=False)

        odt_path: str = os.path.join(self.test_dir, "compte_rendu.odt")
        odt_doc = OpenDocumentText()
        p_elem = OdfP(text="Observation medicale ODT pour Sophie Martin.")
        odt_doc.text.addElement(p_elem)
        odt_doc.save(odt_path)
        txt_odt, err_odt = doc_ext.extract_odt(odt_path)
        self.assertIsNone(err_odt)
        assert txt_odt is not None
        self.assertIn("Sophie Martin", txt_odt)

        pdf_doc = pymupdf.open()
        page = pdf_doc.new_page()
        page.insert_text(
            (72, 72),
            "Ordonnance jointe au courriel pour Jean Dupont.",
        )
        pdf_bytes: bytes = pdf_doc.tobytes()
        pdf_doc.close()

        eml_path: str = os.path.join(self.test_dir, "message_2024-10.eml")
        msg = EmailMessage()
        msg["From"] = "Jean Dupont <jean.dupont@exemple.fr>"
        msg["To"] = "Sophie Martin <sophie.martin@exemple.fr>"
        msg["Date"] = "Tue, 15 Oct 2024 14:20:00 +0200"
        msg["Subject"] = "Ordonnance"
        msg.set_content("Bonjour Sophie, voici le document en piece jointe.")
        msg.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename="ordonnance.pdf",
        )
        with open(eml_path, "wb") as f_eml:
            f_eml.write(msg.as_bytes())

        comm_ext = CommunicationExtractor(self.config, doc_ext)
        discovered: set[str] = set()
        by_month, err_mail = comm_ext.extract_emails(
            eml_path, {"jean.dupont@exemple.fr"}, discovered
        )
        self.assertIsNone(err_mail)
        self.assertIn("2024-10", by_month)
        merged_mail: str = "".join(by_month["2024-10"])
        self.assertIn("voici le document en piece jointe", merged_mail)
        self.assertIn("Ordonnance jointe au courriel", merged_mail)
    def test_audacity_aup3_extraction_with_mock_whisper(self) -> None:
        """Vérifie la lecture SQLite d'un projet .aup3 et le nettoyage du WAV temporaire."""
        aup3_path: str = os.path.join(
            self.test_dir, "entretien_0612345678.aup3"
        )
        conn = sqlite3.connect(aup3_path)
        try:
            conn.execute(
                "CREATE TABLE sampleblocks (blockid INTEGER PRIMARY KEY, samples BLOB)"
            )
            samples = np.zeros(4410, dtype=np.float32).tobytes()
            conn.execute(
                "INSERT INTO sampleblocks (blockid, samples) VALUES (1, ?)",
                (samples,),
            )
            conn.commit()
        finally:
            conn.close()

        class _FakeWhisper:
            def transcribe(self, path: str, **kwargs):
                segs = [
                    SimpleNamespace(start=5.0, text="Bonjour docteur."),
                    SimpleNamespace(start=65.0, text="Tout va bien."),
                ]
                return segs, None

        doc_ext = OfficeAndDocumentExtractor(enable_ocr=False)
        comm_ext = CommunicationExtractor(self.config, doc_ext)
        comm_ext._whisper_model = _FakeWhisper()  # type: ignore[assignment]

        txt_aup, err_aup = comm_ext.extract_audacity_aup3(aup3_path)
        self.assertIsNone(err_aup)
        assert txt_aup is not None
        self.assertIn("AUDIO : entretien_0612345678.aup3", txt_aup)
        self.assertIn("0612345678", txt_aup)
        self.assertIn("[00:05] Bonjour docteur.", txt_aup)
        self.assertIn("[01:05] Tout va bien.", txt_aup)
        self.assertFalse(os.path.exists(f"{aup3_path}.tmp_extract.wav"))

    def test_large_chunk_splitting_multi_batch_and_first_name_suggester(self) -> None:
        """Vérifie le découpage > 32 Ko, la rotation de dossiers lot_01/lot_02 et les suggestions."""
        with open(self.config.contacts_file, "w", encoding="utf-8") as f_ct:
            f_ct.write("Jean Dupont = Jean D.\n")

        trans_dir: str = os.path.join(
            self.test_dir, "transcriptions", "2024-11", "Documents"
        )
        os.makedirs(trans_dir, exist_ok=True)
        for idx in range(1, 4):
            fpath: str = os.path.join(trans_dir, f"volumineux_{idx}.txt")
            line: str = (
                f"Ligne {idx} : entretien confidentiel avec Jean Dupont.\n"
            )
            with open(fpath, "w", encoding="utf-8") as f_big:
                f_big.write(line * 700)

        runner = DocumentAnonymizationRunner(self.config)
        runner.run()

        lot1_dir: str = os.path.join(self.config.results_dir, "lot_01")
        lot2_dir: str = os.path.join(self.config.results_dir, "lot_02")
        self.assertTrue(os.path.isdir(lot1_dir))
        self.assertTrue(os.path.isdir(lot2_dir))

        for lot_d in (lot1_dir, lot2_dir):
            for fn in os.listdir(lot_d):
                with open(
                    os.path.join(lot_d, fn), "r", encoding="utf-8"
                ) as f_res:
                    txt: str = f_res.read()
                    self.assertNotIn("Jean Dupont", txt)
                    self.assertIn("Jean D.", txt)

        csv_path: str = os.path.join(self.test_dir, "contacts.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f_csv:
            f_csv.write(
                "First Name,Last Name\n"
                "Apolline,Durand\n"
                "Jean,Martin\n"
                "Cabinet Medical,\n"
            )
        c_cfg = ContactsConfig(self.ini_path)
        suggester = MissingFirstNamesSuggester(c_cfg)
        sug_count: int = suggester.generate_suggestions_file([csv_path])
        self.assertEqual(sug_count, 1)
        with open(
            c_cfg.suggested_first_names_file, "r", encoding="utf-8"
        ) as f_s:
            sug_txt: str = f_s.read()
        self.assertIn("apolline", sug_txt)
        self.assertNotIn("cabinet", sug_txt)


if __name__ == "__main__":
    unittest.main()
