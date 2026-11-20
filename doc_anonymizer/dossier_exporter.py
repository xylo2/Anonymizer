# Commandes pip à exécuter : pip install python-docx

import csv
import os
import re
import zipfile
from typing import Dict, List, Tuple

try:
    import docx
    from docx.shared import Pt, RGBColor
except ImportError:
    docx = None  # type: ignore[assignment]


class LawyerDossierExporter:
    """
    Génère à partir des lots anonymisés (anonymized_results/) un pack structuré
    et exploitable par un avocat ou un défenseur syndical :
    - Bordereau_des_Pieces.csv (numérotation officielle Pièce n°001, date, origine)
    - Recueil_Chronologique_Avocat.docx (sommaire + pièces séparées avec sauts de page)
    - Pieces_Numerotees/ + Pack_Avocat_Complet.zip
    """

    HEADER_RE = re.compile(
        r"={10,}\s*\n\s*(?:FICHIER|SOURCE|DOCUMENT)\s*:\s*(.+?)\s*\n\s*={10,}",
        re.IGNORECASE,
    )
    MONTH_RE = re.compile(r"(?:^|[^0-9])(20\d{2}[-/](?:0[1-9]|1[0-2]))(?:$|[^0-9])")

    def __init__(self, results_dir: str, export_dir: str) -> None:
        self.results_dir: str = results_dir
        self.export_dir: str = export_dir

    def collect_anonymized_pieces(self) -> List[Dict[str, str]]:
        """Découpe les lots anonymisés en pièces unitaires classées chronologiquement."""
        pieces: List[Dict[str, str]] = []
        if not self.results_dir or not os.path.isdir(self.results_dir):
            return pieces

        txt_files: List[str] = []
        for root_p, _, files in os.walk(self.results_dir):
            for fn in sorted(files):
                if fn.lower().endswith(".txt"):
                    txt_files.append(os.path.join(root_p, fn))

        raw_entries: List[Tuple[str, str, str]] = []
        for fpath in txt_files:
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f_in:
                    content: str = f_in.read()
            except OSError:
                continue

            matches = list(self.HEADER_RE.finditer(content))
            if not matches:
                m_date = self.MONTH_RE.search(os.path.basename(fpath))
                date_tag: str = m_date.group(1).replace("/", "-") if m_date else "0000-00"
                raw_entries.append((date_tag, os.path.basename(fpath), content.strip()))
                continue

            for idx, match in enumerate(matches):
                src_label: str = match.group(1).strip()
                start_pos: int = match.end()
                end_pos: int = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
                body: str = content[start_pos:end_pos].strip()
                if not body:
                    continue
                m_date = self.MONTH_RE.search(src_label) or self.MONTH_RE.search(body[:300])
                date_tag = m_date.group(1).replace("/", "-") if m_date else "0000-00"
                raw_entries.append((date_tag, src_label, body))

        raw_entries.sort(key=lambda item: (item[0], item[1].lower()))

        for num, (date_tag, src_label, body) in enumerate(raw_entries, start=1):
            clean_title: str = re.sub(r"[^\w\-. ]+", "_", os.path.basename(src_label)).strip("_")
            if not clean_title:
                clean_title = f"Document_{num:03d}"
            pieces.append(
                {
                    "numero": f"Pièce n°{num:03d}",
                    "code_fichier": f"Piece_{num:03d}_{date_tag}_{clean_title[:45]}.txt",
                    "date": date_tag if date_tag != "0000-00" else "Date non précisée",
                    "intitule": src_label,
                    "contenu": body,
                }
            )
        return pieces

    def export_lawyer_pack(self) -> Tuple[int, str]:
        """
        Génère le bordereau CSV, le recueil Word (.docx) paginé et l'archive ZIP.
        Retourne (nombre_de_pieces, chemin_du_dossier_export).
        """
        pieces: List[Dict[str, str]] = self.collect_anonymized_pieces()
        os.makedirs(self.export_dir, exist_ok=True)
        pieces_sub: str = os.path.join(self.export_dir, "Pieces_Numerotees")
        os.makedirs(pieces_sub, exist_ok=True)

        bordereau_csv: str = os.path.join(self.export_dir, "Bordereau_des_Pieces.csv")
        with open(bordereau_csv, "w", encoding="utf-8-sig", newline="") as f_csv:
            writer = csv.writer(f_csv, delimiter=";")
            writer.writerow(["Numéro de pièce", "Période (AAAA-MM)", "Intitulé / Source anonymisée", "Fichier associé"])
            for p in pieces:
                writer.writerow([p["numero"], p["date"], p["intitule"], p["code_fichier"]])
                p_path: str = os.path.join(pieces_sub, p["code_fichier"])
                with open(p_path, "w", encoding="utf-8") as f_p:
                    f_p.write(f"{p['numero']} — {p['date']} — {p['intitule']}\n")
                    f_p.write("=" * 70 + "\n\n")
                    f_p.write(p["contenu"] + "\n")

        docx_path: str = os.path.join(self.export_dir, "Recueil_Chronologique_Avocat.docx")
        if docx is not None:
            doc = docx.Document()
            title = doc.add_heading("RECUEIL CHRONOLOGIQUE DES PIÈCES ANONYMISÉES", level=0)
            if title.runs:
                title.runs[0].font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)

            doc.add_paragraph(
                f"Total des pièces classées chronologiquement : {len(pieces)}.\n"
                "Note : Les identités, coordonnées et identifiants personnels ont été remplacés par des alias stables."
            )

            doc.add_heading("Bordereau récapitulatif des pièces", level=1)
            table = doc.add_table(rows=1, cols=3)
            table.style = "Table Grid"
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = "N° Pièce"
            hdr_cells[1].text = "Date"
            hdr_cells[2].text = "Intitulé"
            for p in pieces:
                row_cells = table.add_row().cells
                row_cells[0].text = p["numero"]
                row_cells[1].text = p["date"]
                row_cells[2].text = p["intitule"]

            for p in pieces:
                doc.add_page_break()
                h = doc.add_heading(f"{p['numero']} ({p['date']}) — {p['intitule']}", level=2)
                if h.runs:
                    h.runs[0].font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
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
