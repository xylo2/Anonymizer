# Commandes pip à exécuter : pip install pymupdf pdfplumber

from typing import Any, List
import pymupdf

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore

from doc_anonymizer.text_utils import DocumentTextUtils


class PdfDocumentExtractor:
    """
    Extracteur PDF combinant PyMuPDF pour la vitesse et le rendu OCR haute
    définition, et pdfplumber (optionnel) pour l'extraction structurée des tableaux.
    """

    @staticmethod
    def _flatten_cell_text(cell: Any) -> str:
        """Convertit récursivement une cellule pdfplumber (str, list, None) en texte."""
        if cell is None:
            return ""
        if isinstance(cell, (list, tuple)):
            parts: List[str] = [
                PdfDocumentExtractor._flatten_cell_text(item) for item in cell
            ]
            return " ".join(p for p in parts if p).strip()
        return str(cell).replace("\n", " ").strip()

    @classmethod
    def _extract_tables_text(cls, pdf_path: str) -> str:
        """Extrait les tableaux via pdfplumber en aplatissant les cellules imbriquées."""
        if pdfplumber is None:
            return ""
        tables_blocks: List[str] = []
        try:
            with pdfplumber.open(pdf_path) as plumber_doc:
                for p_idx, p_page in enumerate(plumber_doc.pages):
                    tables = p_page.extract_tables() or []
                    for t_idx, table in enumerate(tables):
                        if not table:
                            continue
                        rows_txt: List[str] = []
                        for row in table:
                            if not isinstance(row, (list, tuple)):
                                flat_row = cls._flatten_cell_text(row)
                                if flat_row:
                                    rows_txt.append(flat_row)
                                continue
                            clean_cells: List[str] = [
                                cls._flatten_cell_text(c) for c in row
                            ]
                            if any(clean_cells):
                                rows_txt.append(" | ".join(clean_cells))
                        if rows_txt:
                            tables_blocks.append(
                                f"--- TABLEAU PAGE {p_idx + 1} (#{t_idx + 1}) ---\n"
                                + "\n".join(rows_txt)
                            )
        except Exception:
            pass
        return "\n\n".join(tables_blocks)

    @classmethod
    def extract(cls, pdf_path: str, ocr_engine: Any) -> str:
        """
        Extrait le texte natif, les tableaux structurés et applique l'OCR sur les
        pages scannées d'un fichier PDF.

        :param pdf_path: Chemin vers le fichier PDF.
        :param ocr_engine: Instance d'OcrEngineManager pour le repli OCR.
        :return: Texte complet extrait et nettoyé.
        """
        pages_text: List[str] = []
        doc = pymupdf.open(pdf_path)
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                native_txt: str = DocumentTextUtils.clean_extracted_text(
                    page.get_text("text")
                )
                if len(native_txt) >= 60:
                    pages_text.append(
                        f"--- PAGE {page_num + 1} ---\n{native_txt}"
                    )
                else:
                    pix = page.get_pixmap(dpi=250)
                    ocr_txt: str = ocr_engine.ocr_bytes(pix.tobytes("png"))
                    combined: str = (
                        ocr_txt if len(ocr_txt) > len(native_txt) else native_txt
                    )
                    if combined:
                        pages_text.append(
                            f"--- PAGE {page_num + 1} (OCR) ---\n{combined}"
                        )
        finally:
            doc.close()

        tables_text: str = cls._extract_tables_text(pdf_path)
        full_output: str = "\n\n".join(pages_text)
        if tables_text:
            full_output = f"{full_output}\n\n{tables_text}".strip()
        return full_output
