# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
import subprocess
import sys
from typing import List, Optional, Set, Tuple

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from tools.fix_docs_and_svg_urls import (
    cleanup_temp_files,
    fix_chat_domain_in_python,
    fix_markdown_docs,
    fix_svg_namespace,
)

EXC_PREFIXES = (
    "AssertionError", "AttributeError", "TypeError", "ValueError",
    "KeyError", "IndexError", "OSError", "FileNotFoundError",
    "RuntimeError", "ImportError", "ZeroDivisionError", "Exception",
)


def copy_to_clipboard(text: str) -> bool:
    """Copie une chaîne UTF-8 dans le presse-papiers système."""
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


def _read_source_snippet(rel_file: str, line_num: int) -> str:
    """Lit la ligne exacte de l'assertion ou de l'erreur dans le projet."""
    full_path: str = os.path.join(ROOT_DIR, rel_file)
    if not os.path.isfile(full_path):
        return ""
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f_in:
            all_lines: List[str] = f_in.read().splitlines()
        if 1 <= line_num <= len(all_lines):
            return all_lines[line_num - 1].strip()[:140]
    except OSError:
        pass
    return ""


def _clean_noise_banners(text: str) -> str:
    """Supprime les bannières répétitives et sauts de ligne échappés."""
    cleaned: str = re.sub(r"[#=-]{6,}", "", text)
    cleaned = cleaned.replace("\\n", " | ")
    cleaned = re.sub(r"(?:\s*\|\s*){2,}", " | ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def extract_warnings_and_console_errors(raw_output: str) -> str:
    """Détecte et dédoublonne les avertissements Python en console."""
    warn_re = re.compile(
        r"(?:ResourceWarning|DeprecationWarning|RuntimeWarning|UserWarning|SyntaxWarning)\s*:.*"
    )
    found: List[str] = []
    seen: Set[str] = set()
    for ln in raw_output.splitlines():
        s: str = ln.strip()
        if warn_re.search(s) and s not in seen:
            seen.add(s)
            found.append(s)
    return "\n".join(found)
def _parse_failure_block(blk: List[str], root_prefix: str) -> Optional[Tuple[str, str]]:
    """Retourne (signature_erreur, ligne_formatée) pour un bloc FAIL/ERROR."""
    file_line_re = re.compile(r'File "([^"]+)", line (\d+)')
    header: str = ""
    project_locs: List[str] = []
    exc_lines: List[str] = []
    in_exc: bool = False
    for ln in blk:
        s: str = ln.strip().replace(root_prefix, "").replace(root_prefix.replace("\\", "/"), "")
        if s.startswith(("FAIL:", "ERROR:")):
            header = s
        elif s.startswith('File "'):
            m_fl = file_line_re.search(s)
            if m_fl and "unittest" not in m_fl.group(1):
                project_locs.append(f"{m_fl.group(1)}:{m_fl.group(2)}")
        elif s.startswith(EXC_PREFIXES):
            in_exc = True
            exc_lines.append(s)
        elif in_exc and s and not s.startswith(("Ran ", "FAILED", "OK")):
            exc_lines.append(s)
    if not header:
        return None
    loc_str: str = " -> ".join(dict.fromkeys(project_locs[-2:])) or "inconnu"
    snippet: str = ""
    if project_locs:
        f_part, l_part = next(iter(project_locs)).rsplit(":", 1)
        if l_part.isdigit():
            snippet = _read_source_snippet(f_part, int(l_part))
    exc_msg: str = _clean_noise_banners(" ".join(exc_lines)) or "Échec sans détail"
    if len(exc_msg) > 460:
        exc_msg = exc_msg[:220] + " [...] " + exc_msg[-220:]
    code_hint: str = f" | Code: `{snippet}`" if snippet else ""
    sig: str = f"{loc_str}|{exc_msg[:120]}"
    return sig, f"{header} | {loc_str}{code_hint} | {exc_msg}"


def compact_error_report(raw_output: str) -> str:
    """Extrait les blocs FAIL/ERROR avec déduplication [DOUBLON]."""
    lines: List[str] = raw_output.splitlines()
    summary_footer: List[str] = [
        ln.strip() for ln in lines if ln.strip().startswith(("Ran ", "FAILED", "OK"))
    ]
    blocks: List[List[str]] = []
    current: List[str] = []
    in_block: bool = False
    for ln in lines:
        s: str = ln.strip()
        if ln.startswith("=" * 20):
            if current:
                blocks.append(current)
                current = []
            in_block = True
            continue
        if in_block:
            if ln.startswith("-" * 20):
                continue
            if s.startswith(("[OK]", "[ÉCHEC]", "[INFO]", "[CONFIG]", "[INIT", "=== ", "Coverage.py")):
                if current:
                    blocks.append(current)
                    current = []
                in_block = False
                continue
            current.append(ln)
    if current:
        blocks.append(current)
    root_prefix: str = ROOT_DIR.rstrip("\\/") + os.sep
    seen_sigs: Set[str] = set()
    compact_lines: List[str] = []
    for blk in blocks:
        parsed = _parse_failure_block(blk, root_prefix)
        if not parsed:
            continue
        sig, formatted = parsed
        if sig in seen_sigs:
            header_only: str = next(iter(formatted.split(" | ")))
            compact_lines.append(f"[DOUBLON] {header_only}")
        else:
            seen_sigs.add(sig)
            compact_lines.append(formatted)
    if summary_footer:
        compact_lines.append(summary_footer[-1])
    return "\n".join(compact_lines).strip()
def extract_coverage_section(raw_output: str) -> str:
    """Extrait la couverture globale, les modules incomplets (< 100%) et leurs lignes."""
    lines: List[str] = raw_output.splitlines()
    start_idx: int = next(
        (i for i, ln in enumerate(lines) if "=== 3. COUVERTURE" in ln), -1
    )
    if start_idx < 0:
        return ""
    header_line: str = lines[start_idx].strip()
    global_line: str = ""
    incomplete_rows: List[str] = []
    missing_lines: List[str] = []
    in_missing: bool = False

    for ln in lines[start_idx + 1 :]:
        s: str = ln.strip()
        if s.startswith("=== CHRONOMÉTRAGE"):
            break
        if s.startswith("COUVERTURE GLOBALE"):
            global_line = s
            continue
        if s == "Lignes non couvertes :":
            in_missing = True
            continue
        if in_missing:
            if s.startswith("- "):
                missing_lines.append(s)
        elif "|" in s and not s.startswith("Module"):
            parts: List[str] = [p.strip() for p in s.split("|")]
            pct_col: str = next(iter(parts[1:2]), "")
            if len(parts) >= 4 and pct_col != "100.0%":
                incomplete_rows.append(s)

    out_parts: List[str] = [header_line]
    if global_line:
        out_parts.append(global_line)
    if incomplete_rows:
        out_parts.append("\nModules incomplets (< 100%) :")
        out_parts.extend(incomplete_rows)
    if missing_lines:
        out_parts.append("\nLignes non couvertes :")
        out_parts.extend(missing_lines)
    return "\n".join(out_parts).strip()


def _extract_str_arg(argv: List[str], flag: str) -> Optional[str]:
    if flag in argv:
        idx: int = argv.index(flag)
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return None


def main() -> int:
    """Exécute la réparation d'URLs, les tests et exporte rapports et couverture."""
    fix_svg_namespace(ROOT_DIR)
    fix_chat_domain_in_python(ROOT_DIR)
    fix_markdown_docs(ROOT_DIR)
    cleanup_temp_files(ROOT_DIR)

    use_clip: bool = "--no-clipboard" not in sys.argv
    report_file: Optional[str] = _extract_str_arg(sys.argv, "--report-file")
    coverage_file: Optional[str] = _extract_str_arg(sys.argv, "--coverage-file")
    max_err_val: str = _extract_str_arg(sys.argv, "--max-errors") or "5"
    interactive_pause: bool = (
        use_clip and report_file is None and sys.stdin is not None and sys.stdin.isatty()
    )
    if use_clip:
        os.system("cls" if os.name == "nt" else "clear")

    runner_script: str = os.path.join(ROOT_DIR, "tests", "run_all_tests.py")
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    cmd: List[str] = [sys.executable, "-u", runner_script, "--max-errors", max_err_val]
    if "--fast" in sys.argv:
        cmd.append("--fast")
    proc = subprocess.Popen(
        cmd, cwd=ROOT_DIR, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    captured_lines: List[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        captured_lines.append(line)
    returncode: int = proc.wait()
    combined: str = "".join(captured_lines).strip()
    has_failure: bool = any(
        ln.strip().startswith(("FAIL:", "ERROR:", "FAILED")) for ln in combined.splitlines()
    )
    console_issues: str = extract_warnings_and_console_errors(combined)
    timing_lines: List[str] = [
        ln.strip() for ln in combined.splitlines()
        if ln.strip().startswith(("TEMPS TESTS :", "1.", "2.", "3.", "4.", "5."))
    ]
    cov_section: str = extract_coverage_section(combined)
    ok_all: bool = returncode == 0 and not has_failure and not console_issues

    if ok_all:
        summary_lines: List[str] = [
            ln.strip() for ln in combined.splitlines()
            if ln.strip().startswith(("Ran ", "OK", "TOTAL", "COUVERTURE GLOBALE"))
        ] + timing_lines
        payload_out: str = "\n".join(summary_lines) if summary_lines else "OK : Tous les tests sont passés."
    else:
        sections: List[str] = []
        if returncode != 0 or has_failure:
            sections.append(compact_error_report(combined))
        if console_issues:
            sections.append(f"WARNINGS / ERREURS CONSOLE DÉTECTÉS :\n{console_issues}")
        if timing_lines:
            sections.append("\n".join(timing_lines))
        payload_out = "\n\n".join(sec for sec in sections if sec).strip()

    if report_file:
        with open(report_file, "w", encoding="utf-8") as f_rep:
            f_rep.write(payload_out)
    if coverage_file:
        with open(coverage_file, "w", encoding="utf-8") as f_cov:
            f_cov.write(cov_section if ok_all else "")
    if use_clip and copy_to_clipboard(payload_out):
        label: str = "Résumé copié." if ok_all else f"{len(payload_out)} car. copiés."
        print(f"\n[PRESSE-PAPIERS] {label}", flush=True)

    exit_code: int = 0 if ok_all else (returncode or 1)
    if interactive_pause:
        try:
            input("\nAppuyez sur Entrée pour fermer cette fenêtre...")
        except EOFError:
            pass
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
