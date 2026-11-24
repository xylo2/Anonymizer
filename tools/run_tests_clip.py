# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
import subprocess
import sys
from typing import List, Optional, Set

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXC_PREFIXES = (
    "AssertionError", "AttributeError", "TypeError", "ValueError",
    "KeyError", "IndexError", "OSError", "FileNotFoundError",
    "RuntimeError", "ImportError", "ZeroDivisionError", "Exception",
)


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
    """Supprime les bannières répétitives (#, =, -) et sauts de ligne échappés."""
    cleaned: str = re.sub(r"[#=-]{6,}", "", text)
    cleaned = cleaned.replace("\\n", " | ")
    cleaned = re.sub(r"(?:\s*\|\s*){2,}", " | ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()
def extract_warnings_and_console_errors(raw_output: str) -> str:
    """Détecte et dédoublonne les avertissements Python (ResourceWarning, etc.) en console."""
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


def _parse_failure_block(blk: List[str], root_prefix: str) -> Optional[str]:
    """Formate un bloc FAIL/ERROR en une ligne dense avec fichier, assertion et exception."""
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
        first_loc = next(iter(project_locs))
        f_part, l_part = first_loc.rsplit(":", 1)
        if l_part.isdigit():
            snippet = _read_source_snippet(f_part, int(l_part))
    exc_msg: str = _clean_noise_banners(" ".join(exc_lines)) or "Échec sans détail"
    if len(exc_msg) > 460:
        exc_msg = exc_msg[:220] + " [...] " + exc_msg[-220:]
    code_hint: str = f" | Code: `{snippet}`" if snippet else ""
    return f"{header} | {loc_str}{code_hint} | {exc_msg}"


def compact_error_report(raw_output: str) -> str:
    """Extrait uniquement les blocs FAIL/ERROR structurés sans logs parasites."""
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
        formatted = _parse_failure_block(blk, root_prefix)
        if formatted and formatted not in seen_sigs:
            seen_sigs.add(formatted)
            compact_lines.append(formatted)

    if summary_footer:
        compact_lines.append(summary_footer[-1])
    return "\n".join(compact_lines).strip()
def _extract_str_arg(argv: List[str], flag: str) -> Optional[str]:
    """Récupère la valeur d'une option CLI (--report-file, --max-errors)."""
    if flag in argv:
        idx: int = argv.index(flag)
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return None


def main() -> int:
    """Affiche l'intégralité de l'exécution et exporte erreurs + anomalies console."""
    use_clip: bool = "--no-clipboard" not in sys.argv
    report_file: Optional[str] = _extract_str_arg(sys.argv, "--report-file")
    max_err_val: str = _extract_str_arg(sys.argv, "--max-errors") or "5"
    interactive_pause: bool = use_clip and report_file is None and sys.stdin is not None and sys.stdin.isatty()
    if use_clip:
        os.system("cls" if os.name == "nt" else "clear")

    runner_script: str = os.path.join(ROOT_DIR, "tests", "run_all_tests.py")
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    cmd: List[str] = [sys.executable, "-u", runner_script, "--max-errors", max_err_val]
    if "--fast" in sys.argv:
        cmd.append("--fast")
    proc = subprocess.Popen(
        cmd, cwd=ROOT_DIR, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
    )

    captured_lines: List[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        captured_lines.append(line)

    returncode: int = proc.wait()
    combined: str = "".join(captured_lines).strip()
    has_failure: bool = any(ln.strip().startswith(("FAIL:", "ERROR:", "FAILED")) for ln in combined.splitlines())
    console_issues: str = extract_warnings_and_console_errors(combined)
    timing_lines: List[str] = [
        ln.strip() for ln in combined.splitlines()
        if ln.strip().startswith(("TEMPS TESTS :", "1.", "2.", "3.", "4.", "5."))
    ]

    if returncode == 0 and not has_failure and not console_issues:
        summary_lines: List[str] = [
            ln.strip() for ln in combined.splitlines() if ln.strip().startswith(("Ran ", "OK", "TOTAL"))
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

    if use_clip and copy_to_clipboard(payload_out):
        ok_all: bool = returncode == 0 and not has_failure and not console_issues
        label: str = "Résumé copié." if ok_all else f"{len(payload_out)} car. copiés."
        print(f"\n[PRESSE-PAPIERS] {label}", flush=True)

    exit_code: int = 0 if (returncode == 0 and not has_failure and not console_issues) else (returncode or 1)
    if interactive_pause:
        try:
            input("\nAppuyez sur Entrée pour fermer cette fenêtre...")
        except EOFError:
            pass
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
