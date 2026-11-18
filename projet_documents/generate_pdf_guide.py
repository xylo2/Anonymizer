# Commandes pip à exécuter : pip install pymupdf

import argparse
import html
import io
import os
from pathlib import Path
import re
from typing import List, Optional
import pymupdf


def _format_inline_markdown(text: str) -> str:
    """
    Convertit la mise en forme Markdown en ligne (gras, italique, code, liens).

    :param text: Ligne de texte brute.
    :return: Chaîne HTML échappée et formatée.
    """
    escaped: str = html.escape(text)
    escaped = re.sub(
        r"`([^`]+)`",
        r"<code style='background:#f1f5f9;padding:1px 4px;border-radius:3px;"
        r"font-family:monospace;font-size:9pt;'>\1</code>",
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r"<a href='\2' style='color:#1d4ed8;'>\1</a>",
        escaped,
    )
    return escaped


def markdown_to_styled_html(md_text: str) -> str:
    """
    Transforme le contenu Markdown en document HTML stylisé prêt pour PyMuPDF.

    :param md_text: Contenu complet du fichier Markdown.
    :return: Code HTML complet avec feuilles de style intégrées.
    """
    html_parts: List[str] = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>",
        "body { font-family: sans-serif; font-size: 10pt; color: #1e293b; line-height: 1.45; }",
        "h1 { color: #0f172a; font-size: 17pt; border-bottom: 2px solid #2563eb; padding-bottom: 4px; }",
        "h2 { color: #1e3a8a; font-size: 13pt; margin-top: 16px; border-bottom: 1px solid #cbd5e1; }",
        "h3 { color: #1d4ed8; font-size: 11pt; margin-top: 12px; }",
        "h4 { color: #334155; font-size: 10pt; margin-top: 10px; }",
        "pre { background: #f8fafc; border: 1px solid #cbd5e1; border-left: 3px solid #2563eb; "
        "padding: 8px; font-family: monospace; font-size: 8.5pt; white-space: pre-wrap; }",
        "blockquote { background: #eff6ff; border-left: 3px solid #3b82f6; padding: 6px 10px; margin: 8px 0; }",
        "ul, ol { margin-top: 4px; margin-bottom: 8px; padding-left: 20px; }",
        "li { margin-bottom: 3px; }",
        "hr { border: 0; border-top: 1px solid #e2e8f0; margin: 12px 0; }",
        "</style></head><body>",
    ]

    in_code_block: bool = False
    code_lines: List[str] = []
    list_mode: str = ""

    def _close_list() -> None:
        nonlocal list_mode
        if list_mode:
            html_parts.append(f"</{list_mode}>")
            list_mode = ""

    def _flush_code_block() -> None:
        nonlocal in_code_block, code_lines
        if in_code_block:
            code_body: str = html.escape("\n".join(code_lines))
            html_parts.append(f"<pre>{code_body}</pre>")
            code_lines = []
            in_code_block = False

    for raw_line in md_text.splitlines():
        stripped: str = raw_line.strip()

        if stripped.startswith("```"):
            _close_list()
            if in_code_block:
                _flush_code_block()
            else:
                in_code_block = True
            continue

        if in_code_block:
            if stripped == "---" or re.match(r"^#{1,4}\s+", stripped):
                _flush_code_block()
            else:
                code_lines.append(raw_line)
                continue

        if not stripped:
            _close_list()
            continue

        if stripped == "---":
            _close_list()
            html_parts.append("<hr>")
            continue

        if stripped.startswith("# "):
            _close_list()
            html_parts.append(f"<h1>{_format_inline_markdown(stripped[2:])}</h1>")
        elif stripped.startswith("## "):
            _close_list()
            html_parts.append(f"<h2>{_format_inline_markdown(stripped[3:])}</h2>")
        elif stripped.startswith("### "):
            _close_list()
            html_parts.append(f"<h3>{_format_inline_markdown(stripped[4:])}</h3>")
        elif stripped.startswith("#### "):
            _close_list()
            html_parts.append(f"<h4>{_format_inline_markdown(stripped[5:])}</h4>")
        elif stripped.startswith("> "):
            _close_list()
            html_parts.append(f"<blockquote>{_format_inline_markdown(stripped[2:])}</blockquote>")
        elif re.match(r"^[\*\-]\s+", stripped):
            if list_mode != "ul":
                _close_list()
                list_mode = "ul"
                html_parts.append("<ul>")
            item_txt: str = re.sub(r"^[\*\-]\s+", "", stripped)
            html_parts.append(f"<li>{_format_inline_markdown(item_txt)}</li>")
        elif re.match(r"^\d+\.\s+", stripped):
            if list_mode != "ol":
                _close_list()
                list_mode = "ol"
                html_parts.append("<ol>")
            item_txt = re.sub(r"^\d+\.\s+", "", stripped)
            html_parts.append(f"<li>{_format_inline_markdown(item_txt)}</li>")
        else:
            _close_list()
            html_parts.append(f"<p>{_format_inline_markdown(stripped)}</p>")

    _flush_code_block()
    _close_list()
    html_parts.append("</body></html>")
    return "\n".join(html_parts)


def convert_md_to_pdf(
    md_path: str = "GUIDE_UTILISATION.md",
    pdf_path: Optional[str] = None,
    footer_label: Optional[str] = None,
) -> None:
    """
    Génère un fichier PDF mis en page et paginé à partir d'un fichier Markdown.

    :param md_path: Chemin vers le fichier Markdown source.
    :param pdf_path: Chemin de sortie du fichier PDF (déduit du .md si omis).
    :param footer_label: Libellé affiché avant le numéro de page.
    """
    src_path: Path = Path(md_path)
    if not src_path.exists():
        raise FileNotFoundError(f"Le fichier '{md_path}' est introuvable.")

    resolved_pdf: str = pdf_path if pdf_path else str(src_path.with_suffix(".pdf"))
    resolved_label: str = footer_label if footer_label else src_path.stem

    md_text: str = src_path.read_text(encoding="utf-8")

    styled_html: str = markdown_to_styled_html(md_text)
    page_rect = pymupdf.paper_rect("a4")
    margin: float = 42.0
    footer_height: float = 24.0
    content_rect = pymupdf.Rect(
        margin,
        margin,
        page_rect.width - margin,
        page_rect.height - margin - footer_height,
    )

    pdf_buffer = io.BytesIO()
    story = pymupdf.Story(html=styled_html)
    writer = pymupdf.DocumentWriter(pdf_buffer)
    more: bool = True
    while more:
        device = writer.begin_page(page_rect)
        more, _ = story.place(content_rect)
        story.draw(device, None)
        writer.end_page()
    writer.close()

    doc = pymupdf.open(stream=pdf_buffer.getvalue(), filetype="pdf")
    total_pages: int = len(doc)
    for page_idx in range(total_pages):
        page = doc[page_idx]
        footer_rect = pymupdf.Rect(
            margin,
            page_rect.height - margin - 14.0,
            page_rect.width - margin,
            page_rect.height - margin + 6.0,
        )
        page.insert_textbox(
            footer_rect,
            f"{resolved_label} - Page {page_idx + 1} / {total_pages}",
            fontsize=8.5,
            fontname="helv",
            color=(0.45, 0.5, 0.58),
            align=pymupdf.TEXT_ALIGN_CENTER,
        )

    doc.save(resolved_pdf)
    doc.close()

    print(
        f"PDF paginé généré avec succès : {os.path.abspath(resolved_pdf)}",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    """
    Analyse les arguments de ligne de commande pour la conversion Markdown -> PDF.

    :return: Espace de noms contenant les chemins d'entrée et de sortie.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Convertit un fichier Markdown en PDF mis en page et paginé."
    )
    parser.add_argument(
        "input_md",
        nargs="?",
        default="GUIDE_UTILISATION.md",
        help="Chemin du fichier Markdown source (défaut : GUIDE_UTILISATION.md).",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Chemin du fichier PDF de sortie (défaut : même nom que le .md).",
    )
    parser.add_argument(
        "-t", "--title",
        default=None,
        help="Libellé affiché en pied de page avant le numéro de page.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Point d'entrée principal de l'utilitaire de génération PDF.
    """
    args: argparse.Namespace = parse_args()
    convert_md_to_pdf(
        md_path=args.input_md,
        pdf_path=args.output,
        footer_label=args.title,
    )


if __name__ == "__main__":
    main()
