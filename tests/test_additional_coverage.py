# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard + dépendances du projet)

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.extractors.pdf_extractor import PdfDocumentExtractor
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.inverter import ContactsInverter
from tools.copy_unmasked_transcriptions import UnmaskedTranscriptionCopier
from tools.sync_contacts import ContactsSynchronizer


class TestAdditionalCoverage(unittest.TestCase):
    """
    Tests complémentaires couvrant les extracteurs bureautiques (DOCX, XLSX, PPTX, RTF,
    PdfDocumentExtractor), les pièces jointes PDF dans les e-mails, la protection XXE XML,
    ContactsInverter, ContactsSynchronizer et le repli de copie des transcriptions brutes.
    """

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_add_cov_")
        with open(os.path.join(self.tmp_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("camille\njean\nsophie\nmarc\n")
        with open(os.path.join(self.tmp_dir, "contacts.txt"), "w", encoding="utf-8") as f:
            f.write("Camille Dupont = Camille D.\nMarc Lefevre = Marc L.\n")

        self.ini_path: str = os.path.join(self.tmp_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f_ini:
            f_ini.write(
                "[files]\n"
                "first_names_file = prenoms.txt\n"
                "deduplicated_output_file = dedup.txt\n"
                "inverted_output_file = inverted_contacts.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = input_documents\n"
                "transcriptions_dir = extracted_texts\n"
                "results_dir = anonymized_results\n"
                "contacts_file = contacts.txt\n"
                "manual_contacts_file = manual_contacts.txt\n"
                "audit_report_file = audits/residual_names_audit.txt\n"
                "audit_copy_file = audits/residual_names_copy.txt\n"
                "[extraction]\n"
                "enable_ocr = false\n"
                "enable_audio = false\n"
            )
        self.config: PipelineConfig = PipelineConfig(self.ini_path)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    def test_office_formats_docx_xlsx_pptx_rtf(self) -> None:
        """Vérifie l'extraction complète des formats DOCX, XLSX, PPTX et RTF."""
        import docx
        import openpyxl
        from pptx import Presentation

        ext = OfficeAndDocumentExtractor(config=self.config, enable_ocr=False)

        docx_path: str = os.path.join(self.tmp_dir, "compte_rendu.docx")
        doc = docx.Document()
        doc.add_paragraph("Compte rendu AnonVault de Camille Dupont.")
        tbl = doc.add_table(rows=2, cols=2)
        tbl.cell(0, 0).text = "Date"
        tbl.cell(0, 1).text = "Observation"
        tbl.cell(1, 0).text = "12/05/2024"
        tbl.cell(1, 1).text = "Suivi orthophonique"
        doc.save(docx_path)

        txt_docx, err_docx = ext.extract_docx(docx_path)
        self.assertIsNone(err_docx)
        assert txt_docx is not None
        self.assertIn("Compte rendu AnonVault de Camille Dupont.", txt_docx)
        self.assertIn("12/05/2024 | Suivi orthophonique", txt_docx)

        xlsx_path: str = os.path.join(self.tmp_dir, "heures_sup.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = "Mai_2024"
        ws.append(["Employé", "Heures", "Code"])
        ws.append(["Marc Lefevre", 42.0, "HS"])
        wb.save(xlsx_path)

        txt_xlsx, err_xlsx = ext.extract_xlsx(xlsx_path)
        self.assertIsNone(err_xlsx)
        assert txt_xlsx is not None
        self.assertIn("Feuille : Mai_2024", txt_xlsx)
        self.assertIn("Marc Lefevre | 42 | HS", txt_xlsx)

        pptx_path: str = os.path.join(self.tmp_dir, "reunion.pptx")
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        if slide.shapes.title:
            slide.shapes.title.text = "Bilan Trimestriel"
        prs.save(pptx_path)

        txt_pptx, err_pptx = ext.extract_pptx(pptx_path)
        self.assertIsNone(err_pptx)
        assert txt_pptx is not None
        self.assertIn("Diapositive 1", txt_pptx)
        self.assertIn("Bilan Trimestriel", txt_pptx)

        rtf_path: str = os.path.join(self.tmp_dir, "courrier.rtf")
        with open(rtf_path, "w", encoding="utf-8") as f_rtf:
            f_rtf.write(r"{\rtf1\ansi Attestation officielle pour Camille Dupont.}")

        txt_rtf, err_rtf = ext.extract_rtf(rtf_path)
        self.assertIsNone(err_rtf)
        assert txt_rtf is not None
        self.assertIn("Attestation officielle pour Camille Dupont.", txt_rtf)
    def test_pdf_document_extractor_native_ocr_and_tables(self) -> None:
        """Vérifie PdfDocumentExtractor (texte natif, repli OCR et tableaux pdfplumber)."""
        import pymupdf

        pdf_path: str = os.path.join(self.tmp_dir, "mixte.pdf")
        pdf = pymupdf.open()
        p1 = pdf.new_page()
        p1.insert_text(
            (72, 72),
            "Page 1 contenant suffisamment de texte natif pour éviter le déclenchement OCR.",
        )
        pdf.new_page()
        pdf.save(pdf_path)
        pdf.close()

        fake_ocr = type("FakeOcr", (), {"ocr_bytes": lambda self, _b: "Texte OCR page 2"})()
        fake_page = type(
            "FakePage",
            (),
            {"extract_tables": lambda self: [[["Col1", ["SubA", "SubB"]], ["Val1", "Val2"]]]},
        )()
        fake_plumber_doc = type(
            "FakePlumberDoc",
            (),
            {
                "pages": [fake_page],
                "__enter__": lambda self: self,
                "__exit__": lambda self, *_a: None,
            },
        )()
        fake_plumber_mod = type(
            "FakePlumberMod", (), {"open": staticmethod(lambda _p: fake_plumber_doc)}
        )()

        with patch("doc_anonymizer.extractors.pdf_extractor.pdfplumber", fake_plumber_mod):
            extracted: str = PdfDocumentExtractor.extract(pdf_path, fake_ocr)

        self.assertIn("--- PAGE 1 ---", extracted)
        self.assertIn("--- PAGE 2 (OCR) ---", extracted)
        self.assertIn("Texte OCR page 2", extracted)
        self.assertIn("--- TABLEAU PAGE 1 (#1) ---", extracted)
        self.assertIn("Col1 | SubA SubB", extracted)

    def test_eml_with_pdf_attachment_and_sms_xxe_blocking(self) -> None:
        """Vérifie l'extraction d'une pièce jointe PDF dans un .eml et le blocage XXE XML."""
        from email.message import EmailMessage
        import pymupdf

        pdf_doc = pymupdf.open()
        page = pdf_doc.new_page()
        page.insert_text(
            (72, 72),
            "Ordonnance AnonVaulte jointe à l'e-mail pour Camille Dupont (document complet).",
        )
        pdf_bytes: bytes = pdf_doc.tobytes()
        pdf_doc.close()

        msg = EmailMessage()
        msg["From"] = "Marc Lefevre <marc.lefevre@exemple.fr>"
        msg["To"] = "Camille Dupont <camille.dupont@exemple.fr>"
        msg["Subject"] = "Pièce jointe AnonVaulte"
        msg["Date"] = "Mon, 10 Jun 2024 08:30:00 +0200"
        msg.set_content("Veuillez trouver ci-joint l'ordonnance.")
        msg.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename="ordonnance_2024.pdf",
        )

        eml_path: str = os.path.join(self.tmp_dir, "mail_pj.eml")
        with open(eml_path, "wb") as f_eml:
            f_eml.write(msg.as_bytes())

        office_ext = OfficeAndDocumentExtractor(config=self.config, enable_ocr=False)
        comm_ext = CommunicationExtractor(config=self.config, doc_extractor=office_ext)
        by_month, err = comm_ext.extract_emails(eml_path, set(), set())
        self.assertIsNone(err)
        self.assertIn("2024-06", by_month)
        joined: str = "\n".join(by_month["2024-06"])
        self.assertIn("Ordonnance AnonVaulte jointe", joined)

        xxe_xml: str = os.path.join(self.tmp_dir, "malicious_sms.xml")
        with open(xxe_xml, "w", encoding="utf-8") as f_xml:
            f_xml.write('<?xml version="1.0"?><!DOCTYPE sms [<!ENTITY xxe "boom">]><smses/>')
        _, xml_errs = comm_ext.parse_sms_xml(xxe_xml, {}, set(), set())
        self.assertTrue(xml_errs)
        first_err: str = next(iter(xml_errs))
        self.assertIn("DOCTYPE/ENTITY", first_err)
    def test_contacts_inverter_synchronizer_and_fallback_copier(self) -> None:
        """Vérifie ContactsInverter, ContactsSynchronizer et le repli de UnmaskedTranscriptionCopier."""
        c_cfg = ContactsConfig(self.ini_path)
        with open(c_cfg.deduplicated_output_file, "w", encoding="utf-8") as f_dedup:
            f_dedup.write("0601020304=Élodie M.\n0605060708=Alain B.\n")

        count_inv: int = ContactsInverter(c_cfg).process()
        self.assertEqual(count_inv, 2)
        with open(c_cfg.inverted_output_file, "r", encoding="utf-8") as f_inv:
            inv_lines = [ln.strip() for ln in f_inv if ln.strip()]
        self.assertEqual(inv_lines, ["Alain B.=0605060708", "Élodie M.=0601020304"])

        empty_src: str = os.path.join(self.tmp_dir, "vide_contacts.txt")
        with open(empty_src, "w", encoding="utf-8") as f_empty:
            f_empty.write("")
        with self.assertRaises(ValueError):
            ContactsSynchronizer.merge_and_sync(empty_src, os.path.join(self.tmp_dir, "dst.txt"))

        synced_dst: str = os.path.join(self.tmp_dir, "sub_sync", "contacts.txt")
        ContactsSynchronizer.merge_and_sync(c_cfg.inverted_output_file, synced_dst)
        self.assertTrue(os.path.isfile(synced_dst))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, "sub_sync", "manual_contacts.txt")))

        trans_dir: str = os.path.join(self.config.transcriptions_dir, "2024-07", "Documents")
        os.makedirs(trans_dir, exist_ok=True)
        raw_txt: str = os.path.join(trans_dir, "Compte_rendu_Camille_Dupont.txt")
        with open(raw_txt, "w", encoding="utf-8") as f_tr:
            f_tr.write("Texte original de Camille Dupont.\n")

        out_unmasked: str = os.path.join(self.tmp_dir, "copies_brutes")
        copier = UnmaskedTranscriptionCopier(
            config=self.config,
            output_dir=out_unmasked,
            mapping_file=os.path.join(self.tmp_dir, "absent_mapping.json"),
        )
        copied, missing = copier.copy_from_targets(["2024-07/Documents/Compte_rendu_Camille_D..txt"])
        self.assertEqual((copied, missing), (1, 0))
        self.assertTrue(
            os.path.isfile(os.path.join(out_unmasked, "2024-07", "Documents", "Compte_rendu_Camille_Dupont.txt"))
        )

    def test_manual_only_mode_updates_existing_batches(self) -> None:
        """Vérifie le mode manual_only=True sur des lots déjà générés."""
        batch_dir: str = os.path.join(self.config.results_dir, "batch_01")
        os.makedirs(batch_dir, exist_ok=True)
        lot_file: str = os.path.join(batch_dir, "anonymized_part_001.txt")
        with open(lot_file, "w", encoding="utf-8") as f_lot:
            f_lot.write("Rendez-vous confirmé avec OrganismeSecretDemain.\n")

        with open(self.config.manual_contacts_file, "w", encoding="utf-8") as f_man:
            f_man.write("OrganismeSecretDemain = ORGANISME_01\n")

        runner = DocumentAnonymizationRunner(self.config, manual_only=True)
        runner.run_on_existing_results()

        with open(lot_file, "r", encoding="utf-8") as f_lot:
            updated: str = f_lot.read()
        self.assertIn("ORGANISME_01", updated)
        self.assertNotIn("OrganismeSecretDemain", updated)


if __name__ == "__main__":
    unittest.main()
