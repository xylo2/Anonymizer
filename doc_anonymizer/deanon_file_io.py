# Commandes pip à exécuter : pip install python-docx striprtf odfpy

import os
import shutil
from typing import Any, Callable, List


class DeanonFileIO:
    """
    Gère l'archivage des retours IA bruts, la lecture multi-formats (.txt, .md,
    .docx, .odt, .rtf) et l'exportation des fichiers suffixés '_nominatif'.
    """

    @staticmethod
    def unique_dest_path(out_dir: str, filename: str) -> str:
        candidate: str = os.path.join(out_dir, filename)
        if not os.path.exists(candidate):
            return candidate
        stem, ext = os.path.splitext(filename)
        idx: int = 2
        while True:
            alt: str = os.path.join(out_dir, f"{stem}_{idx}{ext}")
            if not os.path.exists(alt):
                return alt
            idx += 1

    @classmethod
    def archive_input_file(cls, source_path: str, archive_dir: str) -> str:
        os.makedirs(archive_dir, exist_ok=True)
        abs_src: str = os.path.abspath(source_path)
        abs_arch: str = os.path.abspath(archive_dir)
        if os.path.dirname(abs_src) == abs_arch:
            return abs_src
        dest_path: str = cls.unique_dest_path(abs_arch, os.path.basename(abs_src))
        shutil.copy2(abs_src, dest_path)
        return dest_path

    @staticmethod
    def read_document_text(file_path: str) -> str:
        _, ext_raw = os.path.splitext(file_path)
        ext: str = ext_raw.lower()
        if ext == ".docx":
            try:
                import docx
                doc = docx.Document(file_path)
                parts: List[str] = [p.text for p in doc.paragraphs if p.text.strip()]
                for tbl in doc.tables:
                    for row in tbl.rows:
                        parts.append(" | ".join(c.text.strip() for c in row.cells))
                return "\n".join(parts)
            except Exception:
                pass
        if ext == ".rtf":
            try:
                from striprtf.striprtf import rtf_to_text
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f_r:
                    return rtf_to_text(f_r.read())
            except Exception:
                pass
        if ext == ".odt":
            try:
                from odf.opendocument import load as load_odt
                from odf import teletype
                from odf.text import P as OdfP
                doc_odt = load_odt(file_path)
                return "\n".join(teletype.extractText(p) for p in doc_odt.getElementsByType(OdfP))
            except Exception:
                pass
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f_in:
            return f_in.read()

    @staticmethod
    def build_nominative_filename(source_path: str) -> str:
        base_name: str = os.path.basename(source_path)
        stem, ext = os.path.splitext(base_name)
        if not stem.lower().endswith("_nominatif"):
            stem = f"{stem}_nominatif"
        return f"{stem}{ext}"

    @classmethod
    def export_deanonymized_file(
        cls,
        source_path: str,
        out_dir: str,
        proposals: List[dict[str, Any]],
        replacer_fn: Callable[[str, List[dict[str, Any]]], str],
    ) -> str:
        os.makedirs(out_dir, exist_ok=True)
        out_filename: str = cls.build_nominative_filename(source_path)
        dest_path: str = cls.unique_dest_path(out_dir, out_filename)
        _, ext_raw = os.path.splitext(source_path)
        ext: str = ext_raw.lower()

        if ext == ".docx":
            try:
                import docx
                doc = docx.Document(source_path)
                for p in doc.paragraphs:
                    if p.text:
                        new_t: str = replacer_fn(p.text, proposals)
                        if new_t != p.text:
                            p.text = new_t
                for tbl in doc.tables:
                    for row in tbl.rows:
                        for cell in tbl.cells:
                            if cell.text:
                                new_c: str = replacer_fn(cell.text, proposals)
                                if new_c != cell.text:
                                    cell.text = new_c
                doc.save(dest_path)
                return dest_path
            except Exception:
                pass

        raw_txt: str = cls.read_document_text(source_path)
        updated_txt: str = replacer_fn(raw_txt, proposals)
        out_txt_path: str = dest_path if ext in {".txt", ".md", ".csv", ".html"} else f"{dest_path}.txt"
        if out_txt_path != dest_path and os.path.exists(out_txt_path):
            out_txt_path = cls.unique_dest_path(out_dir, os.path.basename(out_txt_path))
        with open(out_txt_path, "w", encoding="utf-8") as f_out:
            f_out.write(updated_txt)
        return out_txt_path
