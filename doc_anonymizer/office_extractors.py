# Commandes pip à exécuter :
# pip install pymupdf rapidocr-onnxruntime python-docx odfpy striprtf openpyxl python-pptx

from __future__ import annotations
import os
import re
from typing import TYPE_CHECKING, Any, List, Optional, Tuple
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils

if TYPE_CHECKING:
    from rapidocr_onnxruntime import RapidOCR


class OfficeAndDocumentExtractor:
    """
    Gère l'extraction de texte pour les formats PDF (natif + OCR paresseux),
    bureautiques (.docx, .odt, .rtf, .xlsx, .pptx), web (.html), texte brut,
    images et calendriers (.ics).
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        enable_ocr: bool = True,
    ) -> None:
        self.config: Optional[PipelineConfig] = config
        self.enable_ocr: bool = (
            config.enable_ocr if config is not None else enable_ocr
        )
        self._ocr_engine: Optional[RapidOCR] = None

    @property
    def ocr_engine(self) -> Optional[RapidOCR]:
        if not self.enable_ocr:
            return None
        if self._ocr_engine is None:
            from rapidocr_onnxruntime import RapidOCR

            print("Chargement du moteur OCR (RapidOCR)...", flush=True)
            self._ocr_engine = RapidOCR()
            print("[OK] Moteur OCR chargé.", flush=True)
        return self._ocr_engine

    def run_ocr_on_bytes(self, image_bytes: bytes) -> str:
        """Exécute la reconnaissance optique de caractères sur un tampon binaire."""
        engine: Optional[RapidOCR] = self.ocr_engine
        if not engine:
            return ""
        result, _ = engine(image_bytes)
        if not result:
            return ""
        lines: List[str] = []
        for item in result:
            if isinstance(item, str):
                lines.append(item)
            elif isinstance(item, (list, tuple)) and len(item) > 1 and isinstance(item[1], str):
                lines.append(item[1])
        return "\n".join(lines)

    def extract_pdf(
        self, pdf_source: Any, display_name: str, is_stream: bool = False
    ) -> Tuple[Optional[str], Optional[str]]:
        import pymupdf

        doc: Optional[Any] = None
        try:
            doc = (
                pymupdf.open(stream=pdf_source, filetype="pdf")
                if is_stream
                else pymupdf.open(pdf_source)
            )
            total_pages: int = len(doc)
            pages_text: List[str] = []
            for page_idx in range(total_pages):
                page = doc[page_idx]
                native_txt: str = page.get_text("text").strip()
                if len(native_txt) >= 30:
                    pages_text.append(f"--- Page {page_idx + 1} ---\n{native_txt}")
                elif self.enable_ocr:
                    print(f"    [OCR] {display_name} : page {page_idx + 1}/{total_pages}...", flush=True)
                    pix = page.get_pixmap(dpi=150)
                    ocr_txt: str = self.run_ocr_on_bytes(pix.tobytes("png"))
                    if ocr_txt.strip():
                        pages_text.append(f"--- Page {page_idx + 1} (OCR) ---\n{ocr_txt.strip()}")
            if not pages_text:
                return None, "PDF vide ou illisible"
            header: str = f"========================================\nDOCUMENT PDF : {display_name}\n----------------------------------------\n"
            return header + "\n\n".join(pages_text) + "\n\n", None
        except Exception as exc:
            return None, f"Erreur extraction PDF ({exc})"
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

    def extract_image(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        if not self.enable_ocr:
            return None, "OCR désactivé dans config.ini"
        file_name: str = os.path.basename(file_path)
        try:
            print(f"    [OCR] Image : {file_name}...", flush=True)
            with open(file_path, "rb") as f_img:
                ocr_txt: str = self.run_ocr_on_bytes(f_img.read()).strip()
            if not ocr_txt:
                return None, "Aucun texte détecté dans l'image"
            header: str = f"========================================\nIMAGE (OCR) : {file_name}\n----------------------------------------\n"
            return header + ocr_txt + "\n\n", None
        except Exception as exc:
            return None, f"Erreur OCR image ({exc})"
    def extract_docx(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        from docx import Document as DocxDocument

        file_name: str = os.path.basename(file_path)
        try:
            doc = DocxDocument(file_path)
            lines: List[str] = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    cells: List[str] = [c.text.strip().replace("\n", " ") for c in row.cells]
                    if any(cells):
                        lines.append(" | ".join(cells))
            if not lines:
                return None, "Document Word vide"
            header: str = f"========================================\nDOCUMENT WORD : {file_name}\n----------------------------------------\n"
            return header + "\n".join(lines) + "\n\n", None
        except Exception as exc:
            return None, f"Erreur extraction DOCX ({exc})"

    def extract_odt(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        from odf import teletype
        from odf.opendocument import load as load_odt
        from odf.text import P as OdfP

        file_name: str = os.path.basename(file_path)
        try:
            doc = load_odt(file_path)
            lines: List[str] = [
                teletype.extractText(p).strip()
                for p in doc.getElementsByType(OdfP)
                if teletype.extractText(p).strip()
            ]
            if not lines:
                return None, "Document ODT vide"
            header: str = f"========================================\nDOCUMENT ODT : {file_name}\n----------------------------------------\n"
            return header + "\n".join(lines) + "\n\n", None
        except Exception as exc:
            return None, f"Erreur extraction ODT ({exc})"

    def extract_rtf(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        from striprtf.striprtf import rtf_to_text

        file_name: str = os.path.basename(file_path)
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                plain: str = rtf_to_text(f.read()).strip()
            if not plain:
                return None, "Document RTF vide"
            header: str = f"========================================\nDOCUMENT RTF : {file_name}\n----------------------------------------\n"
            return header + plain + "\n\n", None
        except Exception as exc:
            return None, f"Erreur extraction RTF ({exc})"

    @staticmethod
    def _format_excel_cell(val: Any) -> str:
        if val is None:
            return ""
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val).strip()

    def extract_xlsx(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        import openpyxl

        file_name: str = os.path.basename(file_path)
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheets_out: List[str] = []
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows_txt: List[str] = []
                for row in ws.iter_rows(values_only=True):
                    vals: List[str] = [self._format_excel_cell(v) for v in row]
                    if any(vals):
                        rows_txt.append(" | ".join(vals))
                if rows_txt:
                    sheets_out.append(f"--- Feuille : {sheet_name} ---\n" + "\n".join(rows_txt))
            wb.close()
            if not sheets_out:
                return None, "Classeur Excel vide"
            header: str = f"========================================\nCLASSEUR EXCEL : {file_name}\n----------------------------------------\n"
            return header + "\n\n".join(sheets_out) + "\n\n", None
        except Exception as exc:
            return None, f"Erreur extraction XLSX ({exc})"

    def extract_pptx(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        from pptx import Presentation

        file_name: str = os.path.basename(file_path)
        try:
            prs = Presentation(file_path)
            slides_out: List[str] = []
            for idx, slide in enumerate(prs.slides, start=1):
                texts: List[str] = [sh.text.strip() for sh in slide.shapes if hasattr(sh, "text") and sh.text.strip()]
                if texts:
                    slides_out.append(f"--- Diapositive {idx} ---\n" + "\n".join(texts))
            if not slides_out:
                return None, "Présentation PPTX vide"
            header: str = f"========================================\nPRÉSENTATION PPTX : {file_name}\n----------------------------------------\n"
            return header + "\n\n".join(slides_out) + "\n\n", None
        except Exception as exc:
            return None, f"Erreur extraction PPTX ({exc})"

    def extract_html(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        file_name: str = os.path.basename(file_path)
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                plain: str = DocumentTextUtils.html_to_plain_text(f.read()).strip()
            if not plain:
                return None, "Page HTML vide"
            header: str = f"========================================\nPAGE WEB : {file_name}\n----------------------------------------\n"
            return header + plain + "\n\n", None
        except Exception as exc:
            return None, f"Erreur extraction HTML ({exc})"

    def extract_text_or_markdown(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        file_name: str = os.path.basename(file_path)
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content: str = f.read().strip()
            if not content:
                return None, "Fichier texte vide"
            header: str = f"========================================\nTEXTE : {file_name}\n----------------------------------------\n"
            return header + content + "\n\n", None
        except Exception as exc:
            return None, f"Erreur lecture texte ({exc})"

    def extract_ics(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        file_name: str = os.path.basename(file_path)
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                unfolded: str = re.sub(r"\r?\n[ \t]", "", f.read())
            events: List[str] = []
            current_ev: List[str] = []
            in_event: bool = False
            for line in unfolded.splitlines():
                if line.startswith("BEGIN:VEVENT"):
                    in_event = True
                    current_ev = []
                elif line.startswith("END:VEVENT"):
                    in_event = False
                    if current_ev:
                        events.append("\n".join(current_ev))
                elif in_event and any(line.startswith(k) for k in ("DTSTART", "DTEND", "SUMMARY", "DESCRIPTION", "LOCATION")):
                    current_ev.append(line)
            if not events:
                return None, "Aucun événement ICS trouvé"
            header: str = f"========================================\nAGENDA ICS : {file_name}\n----------------------------------------\n"
            return header + "\n---\n".join(events) + "\n\n", None
        except Exception as exc:
            return None, f"Erreur extraction ICS ({exc})"
