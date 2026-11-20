# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
import subprocess
import sys
from typing import List, Optional, Set, Tuple

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def copy_to_clipboard(text: str) -> bool:
    """Copie une chaîne UTF-8 dans le presse-papiers système sans altérer les accents."""
    if not text:
        return False
    if os.name == "nt":
        ps_script: str = (
            "[Console]::InputEncoding = [System.Text.Encoding]::UTF8; "
            "$txt = [Console]::In.ReadToEnd(); "
            "Set-Clipboard -Value $txt"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            input=text.encode("utf-8"),
            check=False,
        )
        return proc.returncode == 0
    cmd = ["pbcopy"] if sys.platform == "darwin" else ["xclip", "-selection", "clipboard"]
    try:
        proc = subprocess.run(cmd, input=text, text=True, encoding="utf-8", check=False)
        return proc.returncode == 0
    except FileNotFoundError:
        return False


def _read_source_snippet(rel_file: str, line_num: int, context: int = 3) -> str:
    """Lit les lignes autour d'une assertion dans un fichier test local."""
    full_path: str = os.path.join(ROOT_DIR, rel_file)
    if not os.path.isfile(full_path):
        return ""
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f_in:
            all_lines: List[str] = f_in.read().splitlines()
        start: int = max(0, line_num - 1)
        end: int = min(len(all_lines), line_num + context)
        snippet: str = " ".join(ln.strip() for ln in all_lines[start:end])
        return snippet[:240]
    except OSError:
        return ""


def _clean_noise_banners(text: str) -> str:
    """Supprime les bannières répétitives (#, =, -) et sauts de ligne échappés pour gagner en lisibilité."""
    cleaned: str = re.sub(r"[#=-]{6,}", "", text)
    cleaned = cleaned.replace("\\n", " | ")
    cleaned = re.sub(r"(?:\s*\|\s*){2,}", " | ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def compact_error_report(raw_output: str) -> str:
    """Réduit la taille du rapport d'erreurs unittest tout en gardant le contexte exact."""
    lines: List[str] = raw_output.splitlines()
    sep_idx: int = next((i for i, ln in enumerate(lines) if ln.startswith("=" * 20)), 0)
    relevant: List[str] = lines[sep_idx:]

    blocks: List[List[str]] = []
    current: List[str] = []
    for ln in relevant:
        if ln.startswith("=" * 20):
            if current:
                blocks.append(current)
                current = []
        elif ln.startswith("-" * 20):
            continue
        else:
            current.append(ln)
    if current:
        blocks.append(current)

    root_prefix: str = ROOT_DIR.rstrip("\\/") + os.sep
    py_lib_re = re.compile(r'File "[^"]*\\lib\\([^"]+)"')
    file_line_re = re.compile(r'File "([^"]+)", line (\d+)')
    seen_signatures: Set[str] = set()
    compact_lines: List[str] = []

    for blk in blocks:
        cleaned_blk: List[str] = []
        last_file_info: Optional[Tuple[str, int]] = None
        for idx, ln in enumerate(blk):
            s: str = ln.strip()
            if not s or s == "Traceback (most recent call last):":
                continue
            if idx == 1 and not s.startswith(("File ", "ERROR:", "FAIL:")):
                continue
            s = s.replace(root_prefix, "").replace(root_prefix.replace("\\", "/"), "")
            s = py_lib_re.sub(r'File "<stdlib>/\1"', s)
            m_fl = file_line_re.search(s)
            if m_fl:
                last_file_info = (m_fl.group(1), int(m_fl.group(2)))
            if s.startswith("AssertionError:"):
                s = _clean_noise_banners(s)
                if len(s) > 320:
                    s = s[:320] + "... [TRONQUÉ]"
            cleaned_blk.append(s)
        if not cleaned_blk:
            continue
        if last_file_info is not None:
            rel_path, line_num = last_file_info
            code_ctx: str = _read_source_snippet(rel_path, line_num, context=4)
            if code_ctx:
                cleaned_blk.append(f"CODE: {code_ctx}")
        sig: str = "|".join(cleaned_blk[-3:])
        if sig in seen_signatures and len(cleaned_blk) > 2:
            compact_lines.append(f"[DOUBLON] {cleaned_blk} -> {cleaned_blk[-1]}")
        else:
            seen_signatures.add(sig)
            compact_lines.append(" | ".join(cleaned_blk))

    return "\n".join(compact_lines).strip()


def main() -> int:
    """Exécute la suite de tests, compacte les erreurs et les copie dans le presse-papiers."""
    os.system("cls" if os.name == "nt" else "clear")
    runner_script: str = os.path.join(ROOT_DIR, "tests", "run_all_tests.py")
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.run(
        [sys.executable, runner_script],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    combined: str = "\n".join(
        part for part in (proc.stdout, proc.stderr) if part and part.strip()
    ).strip()

    if proc.returncode == 0:
        summary_lines = [
            ln for ln in combined.splitlines()
            if ln.startswith("Ran ") or ln.startswith("OK")
        ]
        print("\n".join(summary_lines) or "OK : Tous les tests sont passés.", flush=True)
        return 0

    compact_report: str = compact_error_report(combined)
    print(compact_report, flush=True)

    if copy_to_clipboard(compact_report):
        print(
            f"\n[PRESSE-PAPIERS] {len(compact_report)} car. copiés (Ctrl+V pour coller).",
            flush=True,
        )
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
