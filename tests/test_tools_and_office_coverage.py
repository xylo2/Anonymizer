# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import tempfile
import unittest
from docx import Document as DocxDocument
import openpyxl
from pptx import Presentation
import pymupdf
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.manual_contacts_importer import (
    ManualContactsAutoCompleter as AuditManualImporter,
)
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.deduplicator import ContactsDeduplicator
import lancer_documents
from tools.completer_contacts_manuels import ManualContactsAutoCompleter
from tools.generate_pdf_guide import MarkdownPdfConverter
from tools.restaurer_noms_transcriptions import TranscriptionNameRestorer
from tools.sync_contacts import ContactsSynchronizer


class TestToolsAndOfficeCoverage(unittest.TestCase):
    """
    Couvre les extracteurs bureautiques (PDF natif, DOCX, XLSX, PPTX, RTF),
    la reprise JSON de l'audit, l'import haute confiance et les outils CLI (tools/).
    """

    def setUp(self) -> None:
        """Prépare un répertoire temporaire isolé."""
        self.test_dir: str = tempfile.mkdtemp(prefix="test_cov_")
        self.ini_path: str = os.path.join(self.test_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f:
            f.write(
                "[files]\n"
                "first_names_file = prenoms.txt\n"
                "locations_file = villes_masquees.txt\n"
                "surname_collisions_file = collisions_noms.txt\n"
                "excluded_words_file = mots_exclus.txt\n"
                "anonymized_output_file = contacts_anonymises.txt\n"
                "deduplicated_output_file = contacts_dedoublonnes.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = fichiers sources\n"
                "transcriptions_dir = transcriptions\n"
                "results_dir = resultats_anonymisation\n"
                "contacts_file = contacts.txt\n"
                "manual_contacts_file = contacts_manuels.txt\n"
                "audit_report_file = audit_noms_residuels.txt\n"
                "audit_copy_file = audit_noms_residuels_copier.txt\n"
                "[extraction]\n"
                "enable_ocr = false\n"
                "enable_audio = false\n"
            )
        with open(
            os.path.join(self.test_dir, "prenoms.txt"), "w", encoding="utf-8"
        ) as f:
            f.write("jean\nmarie\naurelien\nclaire\n")
        self.config: PipelineConfig = PipelineConfig(self.ini_path)

    def tearDown(self) -> None:
        """Supprime le répertoire temporaire."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_office_and_pdf_extractors(self) -> None:
        """Vérifie l'extraction PDF natif, DOCX (paragraphes + tableaux), XLSX, PPTX et RTF."""
        extractor = OfficeAndDocumentExtractor(enable_ocr=False)

        pdf_path: str = os.path.join(self.test_dir, "compte_rendu.pdf")
        doc_pdf = pymupdf.open()
        page = doc_pdf.new_page()
        page.insert_text(
            (72, 72),
            "Compte rendu medical detaille pour le patient Jean Dupont.",
        )
        doc_pdf.save(pdf_path)
        doc_pdf.close()
        txt_pdf, err_pdf = extractor.extract_pdf(pdf_path, "compte_rendu.pdf")
        self.assertIsNone(err_pdf)
        assert txt_pdf is not None
        self.assertIn("Jean Dupont", txt_pdf)

        docx_path: str = os.path.join(self.test_dir, "note.docx")
        doc_w = DocxDocument()
        doc_w.add_paragraph("Suivi clinique de Marie Martin.")
        tbl = doc_w.add_table(rows=1, cols=2)
        tbl.rows[0].cells[0].text = "Date"
        tbl.rows[0].cells[1].text = "15/05/2024"
        doc_w.save(docx_path)
        txt_w, err_w = extractor.extract_docx(docx_path)
        self.assertIsNone(err_w)
        assert txt_w is not None
        self.assertIn("Marie Martin", txt_w)
        self.assertIn("Date | 15/05/2024", txt_w)

        xlsx_path: str = os.path.join(self.test_dir, "tableau.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = "Contacts"
        ws.append(["Nom", "Code"])
        ws.append(["Claire", 42.0])
        wb.save(xlsx_path)
        txt_x, err_x = extractor.extract_xlsx(xlsx_path)
        self.assertIsNone(err_x)
        assert txt_x is not None
        self.assertIn("Claire | 42", txt_x)

        pptx_path: str = os.path.join(self.test_dir, "slides.pptx")
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        tx_box = slide.shapes.add_textbox(0, 0, 5000000, 1000000)
        tx_box.text = "Synthese annuelle"
        prs.save(pptx_path)
        txt_p, err_p = extractor.extract_pptx(pptx_path)
        self.assertIsNone(err_p)
        assert txt_p is not None
        self.assertIn("Synthese annuelle", txt_p)

        rtf_path: str = os.path.join(self.test_dir, "courrier.rtf")
        with open(rtf_path, "w", encoding="utf-8") as f_r:
            f_r.write(r"{\rtf1\ansi Courrier certifie RTF.}")
        txt_r, err_r = extractor.extract_rtf(rtf_path)
        self.assertIsNone(err_r)
        assert txt_r is not None
        self.assertIn("Courrier certifie RTF.", txt_r)
    def test_state_resume_audit_importer_and_deduplicator(self) -> None:
        """Vérifie la reprise JSON, l'import haute confiance depuis l'audit et la fusion."""
        trans_dir: str = os.path.join(
            self.test_dir, "transcriptions", "2024-08", "Documents"
        )
        os.makedirs(trans_dir, exist_ok=True)
        f1: str = os.path.join(trans_dir, "doc1.txt")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("Document initial.\n")

        runner1 = DocumentAnonymizationRunner(self.config)
        runner1.run()
        self.assertEqual(runner1.audit.file_idx, 2)

        f2: str = os.path.join(trans_dir, "doc2.txt")
        with open(f2, "w", encoding="utf-8") as f:
            f.write("Second document.\n")

        runner2 = DocumentAnonymizationRunner(self.config)
        runner2.run()
        self.assertEqual(runner2.audit.file_idx, 3)

        with open(
            self.config.audit_report_file, "w", encoding="utf-8"
        ) as f_aud:
            f_aud.write(
                "Zéphyrin Valmont = A_MASQUER   # [  4x] doc1.txt\n"
                "Occasionnel Un = A_MASQUER   # [  1x] doc2.txt\n"
            )
        importer = AuditManualImporter(
            self.config, runner2.rules, min_occurrences=3
        )
        imported: int = importer.import_high_confidence_from_audit()
        self.assertEqual(imported, 1)
        with open(self.config.manual_contacts_file, "r", encoding="utf-8") as f_m:
            manual_txt: str = f_m.read()
        self.assertIn("Zéphyrin Valmont = Zéphyrin V.", manual_txt)
        self.assertNotIn("Occasionnel Un", manual_txt)

        c_cfg = ContactsConfig(self.ini_path)
        with open(
            c_cfg.anonymized_output_file, "w", encoding="utf-8"
        ) as f_anon:
            f_anon.write(
                "0611223344=Jean D.\n"
                "0611223344=Marie M.\n"
                "jean+impots@exemple.fr=Jean D.\n"
                "jean@exemple.fr=Jean D.\n"
            )
        read_c, written_c, merged_c = ContactsDeduplicator(c_cfg).process()
        self.assertEqual(read_c, 4)
        self.assertEqual(written_c, 2)
        self.assertEqual(merged_c, 1)

    def test_cli_tools_complete_sync_restore_and_pdf_guide(self) -> None:
        """Vérifie les outils tools/ (complétion manuelle, sync, restauration, PDF)."""
        ext_contacts: str = os.path.join(self.test_dir, "contacts_ext.txt")
        with open(ext_contacts, "w", encoding="utf-8") as f_ext:
            f_ext.write("Jean D.=0611223344\n")

        ContactsSynchronizer.merge_and_sync(
            source_path=ext_contacts,
            dest_path=self.config.contacts_file,
            preserve_manual_rules=True,
            manual_path=self.config.manual_contacts_file,
        )
        self.assertTrue(os.path.exists(self.config.contacts_file))
        self.assertTrue(os.path.exists(self.config.manual_contacts_file))

        with open(self.config.manual_contacts_file, "a", encoding="utf-8") as f_m:
            f_m.write("Aurélien Duval = \n")

        rc_cli: int = lancer_documents.main(
            ["-c", self.ini_path, "--complete-manual", "--dry-run"]
        )
        self.assertEqual(rc_cli, 0)

        done_c, _ = ManualContactsAutoCompleter(
            self.config, dry_run=False
        ).process()
        self.assertEqual(done_c, 1)
        with open(self.config.manual_contacts_file, "r", encoding="utf-8") as f_m:
            self.assertIn("Aurélien Duval = Aurélien D.", f_m.read())

        trans_bad_dir: str = os.path.join(
            self.test_dir, "transcriptions", "0000-00", "Documents"
        )
        os.makedirs(trans_bad_dir, exist_ok=True)
        bad_txt: str = os.path.join(
            trans_bad_dir, "facture_NUMERO_MASQUE.txt"
        )
        with open(bad_txt, "w", encoding="utf-8") as f_b:
            f_b.write(
                "========================================\n"
                "TEXTE : facture_2024-09-10_0611223344.txt\n"
                "----------------------------------------\n"
                "Contenu.\n"
            )
        moved: int = TranscriptionNameRestorer(
            self.config, dry_run=False
        ).run()
        self.assertEqual(moved, 1)
        expected_restored: str = os.path.join(
            self.test_dir,
            "transcriptions",
            "2024-09",
            "Documents",
            "facture_2024-09-10_0611223344.txt",
        )
        self.assertTrue(os.path.exists(expected_restored))

        md_sample: str = os.path.join(self.test_dir, "mini_guide.md")
        pdf_sample: str = os.path.join(self.test_dir, "mini_guide.pdf")
        with open(md_sample, "w", encoding="utf-8") as f_md:
            f_md.write("# Guide\n\n- Point **important**\n")
        MarkdownPdfConverter.convert(md_path=md_sample, pdf_path=pdf_sample)
        self.assertTrue(os.path.exists(pdf_sample))


if __name__ == "__main__":
    unittest.main()
