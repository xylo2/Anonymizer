# Commandes pip à exécuter : pip install python-docx

import csv
import json
import os
import re
import shutil
import zipfile
from typing import Dict, List, Optional, Set, Tuple

try:
    import docx
    from docx.shared import Inches, Pt, RGBColor
except ImportError:
    docx = None  # type: ignore[assignment]


class LawyerDossierExporter:
    """
    Génère un Pack Avocat structuré, nominatif et chronologique à partir des
    transcriptions extraites (extracted_texts/) et des sources originales :
    - Bordereau_des_Pieces.csv (numérotation officielle, date, intitulé, média original joint)
    - Recueil_Chronologique_Avocat.docx (sommaire + pièces paginées + aperçu images)
    - Pieces_Numerotees/ : textes extraits/transcriptions/OCR + copies des médias originaux
      (audio et images) numérotés côte à côte
    - Pack_Avocat_Complet.zip
    Supporte également le filtrage sélectif via une liste de pièces issue du mode IA.
    """

    HEADER_RE = re.compile(
        r"={10,}\s*\n\s*(?:FICHIER|SOURCE|DOCUMENT)\s*:\s*(.+?)\s*\n\s*={10,}",
        re.IGNORECASE,
    )
    MONTH_RE = re.compile(r"(?:^|[^0-9])(20\d{2}[-/](?:0[1-9]|1[0-2]))(?:$|[^0-9])")
    AUDIO_EXTS: Set[str] = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aup3"}
    IMAGE_EXTS: Set[str] = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}

    def __init__(
        self,
        results_dir: str,
        export_dir: str,
        transcriptions_dir: Optional[str] = None,
        sources_dir: Optional[str] = None,
        mapping_file: Optional[str] = None,
        selected_extracted_files: Optional[Set[str]] = None,
    ) -> None:
        self.results_dir: str = results_dir
        self.export_dir: str = export_dir
        ws_root: str = os.path.dirname(os.path.abspath(results_dir))
        self.transcriptions_dir: str = transcriptions_dir or os.path.join(ws_root, "extracted_texts")
        self.sources_dir: str = sources_dir or os.path.join(ws_root, "input_documents")
        self.mapping_file: str = mapping_file or os.path.join(
            ws_root, "audits", "source_files_mapping.json"
        )
        self.selected_extracted_files: Optional[Set[str]] = (
            {os.path.normpath(p).lower() for p in selected_extracted_files}
            if selected_extracted_files is not None
            else None
        )

    def _load_source_lookup(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Charge les correspondances extracted_file -> original_source_file."""
        ext_to_orig: Dict[str, str] = {}
        stem_to_orig: Dict[str, str] = {}

        if os.path.isfile(self.mapping_file):
            try:
                with open(self.mapping_file, "r", encoding="utf-8") as f_in:
                    payload = json.load(f_in)
                files_map = payload.get("files", payload) if isinstance(payload, dict) else {}
                if isinstance(files_map, dict):
                    for meta in files_map.values():
                        if not isinstance(meta, dict):
                            continue
                        ext_f: str = str(meta.get("extracted_file") or "").strip()
                        orig_f: str = str(meta.get("original_source_file") or "").strip()
                        if ext_f and orig_f and os.path.isfile(orig_f):
                            ext_to_orig[os.path.normpath(ext_f).lower()] = orig_f
            except Exception:
                pass

        if os.path.isdir(self.sources_dir):
            for root_p, _, files in os.walk(self.sources_dir):
                for fn in sorted(files):
                    if fn.startswith("."):
                        continue
                    full_p: str = os.path.normpath(os.path.join(root_p, fn))
                    stem_low, _ = os.path.splitext(fn.lower())
                    stem_to_orig.setdefault(stem_low, full_p)

        return ext_to_orig, stem_to_orig
    @staticmethod
    def _detect_media_kind(orig_path: str, sub_category: str) -> str:
        """Retourne 'audio', 'image' ou 'document' selon le fichier source ou la catégorie."""
        ext: str = os.path.splitext(orig_path)[-1].lower() if orig_path else ""
        cat_low: str = (sub_category or "").lower()
        if ext in LawyerDossierExporter.AUDIO_EXTS or cat_low == "audio":
            return "audio"
        if ext in LawyerDossierExporter.IMAGE_EXTS or cat_low == "images":
            return "image"
        return "document"

    def collect_nominative_pieces(self) -> List[Dict[str, str]]:
        """
        Collecte les transcriptions nominatives depuis extracted_texts/ (ou à défaut
        depuis results_dir), associe le fichier média original et trie par date.
        """
        ext_to_orig, stem_to_orig = self._load_source_lookup()
        raw_entries: List[Tuple[str, str, str, str, str]] = []

        if os.path.isdir(self.transcriptions_dir):
            for root_p, _, files in os.walk(self.transcriptions_dir):
                sub_cat: str = os.path.basename(root_p)
                parent_period: str = os.path.basename(os.path.dirname(root_p))
                for fn in sorted(files):
                    if (
                        fn.startswith(".")
                        or fn in {"rapport_extraction.txt", "extraction_report.txt"}
                        or not fn.lower().endswith(".txt")
                    ):
                        continue
                    full_txt: str = os.path.normpath(os.path.join(root_p, fn))
                    if (
                        self.selected_extracted_files is not None
                        and full_txt.lower() not in self.selected_extracted_files
                    ):
                        continue
                    try:
                        with open(full_txt, "r", encoding="utf-8", errors="replace") as f_in:
                            body: str = f_in.read().strip()
                    except OSError:
                        continue
                    if not body:
                        continue

                    m_date = (
                        self.MONTH_RE.search(parent_period)
                        or self.MONTH_RE.search(fn)
                        or self.MONTH_RE.search(body[:300])
                    )
                    date_tag: str = m_date.group(1).replace("/", "-") if m_date else "0000-00"
                    stem_low, _ = os.path.splitext(fn.lower())
                    orig_path: str = ext_to_orig.get(full_txt.lower()) or stem_to_orig.get(stem_low, "")
                    media_kind: str = self._detect_media_kind(orig_path, sub_cat)
                    display_title: str = os.path.basename(orig_path) if orig_path else fn
                    raw_entries.append((date_tag, display_title, body, orig_path, media_kind))

        if not raw_entries and self.selected_extracted_files is None and os.path.isdir(self.results_dir):
            for root_p, _, files in os.walk(self.results_dir):
                for fn in sorted(files):
                    if not fn.lower().endswith(".txt"):
                        continue
                    fpath: str = os.path.join(root_p, fn)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="replace") as f_in:
                            content: str = f_in.read()
                    except OSError:
                        continue
                    matches = list(self.HEADER_RE.finditer(content))
                    if not matches:
                        m_d = self.MONTH_RE.search(fn)
                        d_tag: str = m_d.group(1).replace("/", "-") if m_d else "0000-00"
                        raw_entries.append((d_tag, fn, content.strip(), "", "document"))
                        continue
                    for idx, match in enumerate(matches):
                        src_label: str = match.group(1).strip()
                        start_pos: int = match.end()
                        end_pos: int = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
                        body_part: str = content[start_pos:end_pos].strip()
                        if not body_part:
                            continue
                        m_d = self.MONTH_RE.search(src_label) or self.MONTH_RE.search(body_part[:300])
                        d_tag = m_d.group(1).replace("/", "-") if m_d else "0000-00"
                        raw_entries.append((d_tag, src_label, body_part, "", "document"))

        raw_entries.sort(key=lambda item: (item[0], item[1].lower()))
        pieces: List[Dict[str, str]] = []
        for num, (date_tag, title_lbl, body, orig_path, media_kind) in enumerate(raw_entries, start=1):
            base_stem, _ = os.path.splitext(os.path.basename(title_lbl))
            clean_stem: str = re.sub(r"[^\w\-. ]+", "_", base_stem).strip("_") or f"Document_{num:03d}"
            clean_stem = clean_stem[:42]

            if media_kind == "audio":
                txt_filename: str = f"Piece_{num:03d}_{date_tag}_{clean_stem}_TRANSCRIPTION.txt"
            elif media_kind == "image":
                txt_filename = f"Piece_{num:03d}_{date_tag}_{clean_stem}_OCR.txt"
            else:
                txt_filename = f"Piece_{num:03d}_{date_tag}_{clean_stem}.txt"

            orig_copy_name: str = ""
            if orig_path and os.path.isfile(orig_path) and media_kind in {"audio", "image"}:
                orig_ext: str = os.path.splitext(orig_path)[-1].lower()
                orig_copy_name = f"Piece_{num:03d}_{date_tag}_{clean_stem}_ORIGINAL{orig_ext}"

            pieces.append(
                {
                    "numero": f"Pièce n°{num:03d}",
                    "code_fichier": txt_filename,
                    "fichier_original_copie": orig_copy_name,
                    "chemin_original_source": orig_path,
                    "type_media": media_kind,
                    "date": date_tag if date_tag != "0000-00" else "Date non précisée",
                    "intitule": title_lbl,
                    "contenu": body,
                }
            )
        return pieces

    def collect_anonymized_pieces(self) -> List[Dict[str, str]]:
        """Alias rétrocompatible vers collect_nominative_pieces()."""
        return self.collect_nominative_pieces()

    def export_lawyer_pack(self) -> Tuple[int, str]:
        """
        Génère le bordereau CSV, le recueil Word (.docx) paginé (avec aperçus d'images),
        le dossier Pieces_Numerotees/ (textes + originaux audio/image) et l'archive ZIP.
        """
        pieces: List[Dict[str, str]] = self.collect_nominative_pieces()
        if os.path.isdir(self.export_dir):
            shutil.rmtree(self.export_dir, ignore_errors=True)
        os.makedirs(self.export_dir, exist_ok=True)
        pieces_sub: str = os.path.join(self.export_dir, "Pieces_Numerotees")
        os.makedirs(pieces_sub, exist_ok=True)

        bordereau_csv: str = os.path.join(self.export_dir, "Bordereau_des_Pieces.csv")
        with open(bordereau_csv, "w", encoding="utf-8-sig", newline="") as f_csv:
            writer = csv.writer(f_csv, delimiter=";")
            writer.writerow([
                "Numéro de pièce",
                "Période (AAAA-MM)",
                "Type",
                "Intitulé / Fichier source",
                "Transcription / Texte OCR",
                "Fichier média original joint",
            ])
            for p in pieces:
                orig_copied: str = p["fichier_original_copie"]
                if orig_copied and p["chemin_original_source"] and os.path.isfile(p["chemin_original_source"]):
                    shutil.copy2(p["chemin_original_source"], os.path.join(pieces_sub, orig_copied))

                writer.writerow([
                    p["numero"],
                    p["date"],
                    p["type_media"].upper(),
                    p["intitule"],
                    p["code_fichier"],
                    orig_copied or "—",
                ])
                p_path: str = os.path.join(pieces_sub, p["code_fichier"])
                with open(p_path, "w", encoding="utf-8") as f_p:
                    f_p.write(f"{p['numero']} — {p['date']} — {p['intitule']}\n")
                    if orig_copied:
                        f_p.write(f"Média original joint : {orig_copied}\n")
                    f_p.write("=" * 70 + "\n\n")
                    f_p.write(p["contenu"] + "\n")

        docx_path: str = os.path.join(self.export_dir, "Recueil_Chronologique_Avocat.docx")
        if docx is not None:
            doc = docx.Document()
            title = doc.add_heading("RECUEIL CHRONOLOGIQUE DES PIÈCES DU DOSSIER", level=0)
            if title.runs:
                title.runs[0].font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)

            doc.add_paragraph(
                f"Total des pièces classées chronologiquement : {len(pieces)}.\n"
                "Note : Les enregistrements audio sont accompagnés de leur transcription intégrale "
                "et les images de leur extraction texte (OCR) ainsi que du fichier original numéroté."
            )

            doc.add_heading("Bordereau récapitulatif des pièces", level=1)
            table = doc.add_table(rows=1, cols=4)
            table.style = "Table Grid"
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = "N° Pièce"
            hdr_cells[1].text = "Date"
            hdr_cells[2].text = "Intitulé"
            hdr_cells[3].text = "Média original joint"
            for p in pieces:
                row_cells = table.add_row().cells
                row_cells[0].text = p["numero"]
                row_cells[1].text = p["date"]
                row_cells[2].text = p["intitule"]
                row_cells[3].text = p["fichier_original_copie"] or "—"

            for p in pieces:
                doc.add_page_break()
                h = doc.add_heading(f"{p['numero']} ({p['date']}) — {p['intitule']}", level=2)
                if h.runs:
                    h.runs[0].font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
                if p["fichier_original_copie"]:
                    note_p = doc.add_paragraph(
                        f"Pièce originale jointe dans Pieces_Numerotees/ : {p['fichier_original_copie']}"
                    )
                    if note_p.runs:
                        note_p.runs[0].bold = True
                if p["type_media"] == "image" and p["chemin_original_source"] and os.path.isfile(p["chemin_original_source"]):
                    try:
                        doc.add_picture(p["chemin_original_source"], width=Inches(5.6))
                    except Exception:
                        pass
                para = doc.add_paragraph(p["contenu"])
                para.style.font.size = Pt(10)

            doc.save(docx_path)

        zip_path: str = os.path.join(self.export_dir, "Pack_Avocat_Complet.zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(bordereau_csv, arcname="Bordereau_des_Pieces.csv")
            if os.path.isfile(docx_path):
                zf.write(docx_path, arcname="Recueil_Chronologique_Avocat.docx")
            for fn in sorted(os.listdir(pieces_sub)):
                zf.write(os.path.join(pieces_sub, fn), arcname=os.path.join("Pieces_Numerotees", fn))

        return len(pieces), self.export_dir
