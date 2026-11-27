import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import io
import os
import re
import subprocess
import sys
import time
import unittest
from typing import Dict, List, Optional, Set, Tuple

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def _discover_test_modules(tests_dir: str, pattern: str = "test_*.py") -> List[str]:
    """Découvre tous les modules de tests dans tests_dir."""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=tests_dir, pattern=pattern, top_level_dir=ROOT_DIR)
    modules: List[str] = []
    seen: Set[str] = set()

    def _walk(node: unittest.TestSuite) -> None:
        for item in node:
            if isinstance(item, unittest.TestSuite):
                _walk(item)
            else:
                mod_name: str = item.__class__.__module__
                if mod_name not in seen:
                    seen.add(mod_name)
                    modules.append(mod_name)

    _walk(suite)
    return sorted(modules)


def _is_gui_test_module(mod_name: str) -> bool:
    """Indique si le module de test instancie une interface Tkinter."""
    rel_p: str = mod_name.replace(".", os.sep) + ".py"
    full_p: str = os.path.join(ROOT_DIR, rel_p)
    if "gui" in os.path.basename(full_p).lower():
        return True
    try:
        with open(full_p, "r", encoding="utf-8", errors="ignore") as f_in:
            head: str = f_in.read(4096)
        return bool(re.search(r"\b(tkinter|AnonymizerWizardApp|tk\.Tk)\b", head))
    except OSError:
        return False


def _detect_changed_files() -> Set[str]:
    """Détecte les fichiers Python modifiés via git status."""
    changed: Set[str] = set()
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT_DIR, capture_output=True, text=True, timeout=3, check=False,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if len(line) >= 4:
                    rel: str = line[3:].strip().strip('"')
                    if rel.endswith(".py"):
                        changed.add(os.path.normpath(rel))
    except Exception:
        pass
    return changed


def _prioritize_impacted_modules(
    all_modules: List[str], only_changed: bool = False
) -> List[str]:
    """Place en tête les modules de tests impactés par git status."""
    changed: Set[str] = _detect_changed_files()
    if not changed:
        return all_modules
    changed_mod_tokens: Set[str] = set()
    direct_tests: Set[str] = set()
    for rel_p in changed:
        stem: str = os.path.splitext(os.path.basename(rel_p))[0]
        changed_mod_tokens.add(stem)
        if rel_p.startswith("tests" + os.sep) and stem.startswith("test_"):
            direct_tests.add(f"tests.{stem}")
    impacted: List[str] = []
    remaining: List[str] = []
    for mod in all_modules:
        if mod in direct_tests:
            impacted.append(mod)
            continue
        full_p: str = os.path.join(ROOT_DIR, mod.replace(".", os.sep) + ".py")
        try:
            with open(full_p, "r", encoding="utf-8", errors="ignore") as f_in:
                src: str = f_in.read()
            if any(tok in src for tok in changed_mod_tokens):
                impacted.append(mod)
            else:
                remaining.append(mod)
        except OSError:
            impacted.append(mod)
    if only_changed:
        return impacted or all_modules
    return impacted + remaining
def compact_error_report(raw_output: str) -> str:
    """Compacte une sortie unittest/trace en conservant erreurs, warnings et résumé."""
    lines: List[str] = raw_output.splitlines()
    out: List[str] = []
    seen_sigs: Set[str] = set()
    ran_line: str = ""
    status_line: str = ""
    i: int = 0
    while i < len(lines):
        ln: str = lines[i]
        m_hdr = re.match(r"^(FAIL|ERROR):\s+(.+)$", ln.strip())
        if m_hdr:
            kind, test_name = m_hdr.group(1), m_hdr.group(2).strip()
            block: List[str] = []
            i += 1
            while i < len(lines) and not re.match(r"^(={10,}|-{10,}|Ran \d+ test)", lines[i]):
                block.append(lines[i])
                i += 1
            loc = code = err_msg = ""
            for idx, b_ln in enumerate(block):
                m_f = re.search(r'File "([^"]+)", line (\d+)', b_ln)
                if m_f:
                    rel_p: str = m_f.group(1).replace("\\", "/")
                    for anchor in ("tests/", "doc_anonymizer/", "google_contacts_parser/", "common/", "tools/"):
                        if anchor in rel_p:
                            _, _, tail = rel_p.partition(anchor)
                            rel_p = anchor + tail
                            break
                    loc = f"{rel_p}:{m_f.group(2)}"
                    if idx + 1 < len(block):
                        code = block[idx + 1].strip()
            non_empty = [
                b.strip() for b in block
                if b.strip() and not b.strip().startswith(("Traceback", 'File "'))
            ]
            if non_empty:
                err_msg = non_empty[-1]
            sig: str = f"{kind}:{err_msg}"
            if sig in seen_sigs:
                out.append(f"[DOUBLON] {kind}: {test_name} -> {err_msg}")
            else:
                seen_sigs.add(sig)
                out.append(f"{kind}: {test_name} | LOC: {loc} | CODE: {code} | {err_msg}")
            continue
        if re.search(r"\b\w*Warning:", ln):
            w_clean: str = ln.strip()
            if w_clean not in seen_sigs:
                seen_sigs.add(w_clean)
                out.append(f"WARNING: {w_clean}")
        elif re.match(r"^Ran \d+ tests? in .+$", ln.strip()):
            ran_line = ln.strip()
        elif re.match(r"^(OK|FAILED).*$", ln.strip()):
            status_line = ln.strip()
        i += 1
    if ran_line:
        out.append(f"{ran_line} | {status_line}" if status_line else ran_line)
    return "\n".join(out)
def extract_coverage_section(raw_output: str) -> str:
    """Extrait la couverture au format COUVERTURE GLOBALE : XX.X%."""
    lines: List[str] = raw_output.splitlines()
    global_pcts: List[float] = []
    incomplete_rows: List[str] = []
    in_cov: bool = False
    for ln in lines:
        s: str = ln.strip()
        if "=== 3. COUVERTURE" in s:
            in_cov = True
            continue
        if s.startswith(("=== CHRONOMÉTRAGE", "TEMPS TESTS :")):
            in_cov = False
            continue
        m_glob = re.match(r"^COUVERTURE GLOBALE\s*[|:]\s*([0-9]+(?:\.[0-9]+)?)%", s)
        if m_glob:
            global_pcts.append(float(m_glob.group(1)))
            continue
        if in_cov and "|" in s and not s.startswith("Module"):
            parts: List[str] = [p.strip() for p in s.split("|")]
            pct_col: str = next(iter(parts[1:2]), "")
            if len(parts) >= 4 and pct_col != "100.0%":
                incomplete_rows.append(s)
    if not global_pcts:
        return ""
    out: List[str] = [f"COUVERTURE GLOBALE : {global_pcts[-1]:.1f}%"]
    if incomplete_rows:
        out.append("\nModules incomplets (< 100%) :")
        out.extend(incomplete_rows)
    return "\n".join(out).strip()


def _run_module_batch(modules: List[str]) -> Tuple[int, str]:
    """Exécute un lot de modules unittest avec affichage en temps réel."""
    loader = unittest.TestLoader()
    all_raw: List[str] = []
    total_run: int = 0
    for mod in modules:
        t_mod: float = time.perf_counter()
        suite = loader.loadTestsFromName(mod)
        stream = io.StringIO()
        runner = unittest.TextTestRunner(stream=stream, verbosity=2, buffer=True)
        res = runner.run(suite)
        out: str = stream.getvalue()
        all_raw.append(out)
        total_run += res.testsRun
        dt: float = time.perf_counter() - t_mod
        tag: str = "OK" if res.wasSuccessful() else "FAIL"
        print(f"  [{tag}] {mod} ({res.testsRun} test(s), {dt:.2f}s)", flush=True)
        if not res.wasSuccessful():
            for ln in out.splitlines():
                if " ... FAIL" in ln or " ... ERROR" in ln:
                    print(f"     -> {ln.strip()}", flush=True)
    return total_run, "\n".join(all_raw)


def _run_gui_module_isolated(mod: str, timeout_s: float = 25.0) -> Tuple[int, str]:
    """Exécute un module de test Tkinter en streaming temps réel."""
    cmd: List[str] = [sys.executable, "-u", "-m", "unittest", "-v", mod]
    t_mod: float = time.perf_counter()
    lines_out: List[str] = []
    try:
        proc = subprocess.Popen(
            cmd, cwd=ROOT_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        assert proc.stdout is not None
        for raw_ln in proc.stdout:
            lines_out.append(raw_ln)
            s: str = raw_ln.strip()
            if " ... " in s:
                print(f"     {s}", flush=True)
        proc.wait(timeout=timeout_s)
        out: str = "".join(lines_out)
        m_ran = re.search(r"Ran (\d+) test", out)
        cnt: int = int(m_ran.group(1)) if m_ran else 1
        dt: float = time.perf_counter() - t_mod
        tag: str = "OK" if proc.returncode == 0 else "FAIL"
        print(f"  [{tag}] {mod} ({cnt} test(s), {dt:.2f}s)", flush=True)
        return cnt, out
    except subprocess.TimeoutExpired:
        proc.kill()
        return 1, f"ERROR: {mod}\nTimeoutExpired: module GUI bloqué (> {timeout_s}s)\nRan 1 test in {timeout_s}s\nFAILED (errors=1)\n"


def main(argv: Optional[List[str]] = None) -> int:
    """Point d'entrée du lanceur de tests avec suivi temps réel."""
    parser = argparse.ArgumentParser(description="Exécuteur de tests AnonVault.")
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--module", default="")
    parser.add_argument("--single-process", action="store_true")
    parser.add_argument("--fast", "--changed", dest="fast", action="store_true", default=True)
    parser.add_argument("--only-changed", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--no-clipboard", action="store_true")
    parser.add_argument("--report-file", default="")
    parser.add_argument("--coverage-file", default="")
    args, _ = parser.parse_known_args(argv)

    t0: float = time.perf_counter()
    modules: List[str] = [args.module] if args.module else _discover_test_modules(os.path.join(ROOT_DIR, "tests"), args.pattern)
    if not args.module and not args.full:
        modules = _prioritize_impacted_modules(modules, only_changed=args.only_changed)

    print(f"=== Démarrage de {len(modules)} module(s) de tests ===", flush=True)
    total_run: int = 0
    raw_chunks: List[str] = []
    if args.single_process or len(modules) <= 1:
        total_run, out_s = _run_module_batch(modules)
        raw_chunks.append(out_s)
    else:
        non_gui = [m for m in modules if not _is_gui_test_module(m)]
        gui_mods = [m for m in modules if _is_gui_test_module(m)]
        max_w = args.workers if args.workers > 0 else min(4, max(2, (os.cpu_count() or 2) // 2))
        if non_gui:
            chunks = [non_gui[i::max_w] for i in range(min(max_w, len(non_gui)))]
            with ProcessPoolExecutor(max_workers=len(chunks)) as pool:
                for fut in as_completed([pool.submit(_run_module_batch, ch) for ch in chunks]):
                    cnt, out_s = fut.result()
                    total_run += cnt
                    raw_chunks.append(out_s)
        for g_mod in gui_mods:
            print(f"[GUI] {g_mod}...", flush=True)
            cnt_g, out_g = _run_gui_module_isolated(g_mod)
            total_run += cnt_g
            raw_chunks.append(out_g)

    elapsed: float = time.perf_counter() - t0
    combined_raw: str = "\n".join(raw_chunks)
    compacted: str = compact_error_report(combined_raw)
    has_err: bool = any(ln.startswith(("FAIL:", "ERROR:")) for ln in compacted.splitlines())
    clean_lines: List[str] = [
        ln for ln in compacted.splitlines()
        if not re.match(r"^(Ran \d+ tests? in .+|OK.*|FAILED.*)$", ln)
    ]
    status: str = "FAILED" if has_err else "OK"
    clean_lines.append(f"Ran {total_run} tests in {elapsed:.3f}s | {status}")
    report: str = "\n".join(clean_lines)
    print(f"\n=== Bilan ===\n{report}", flush=True)
    if args.report_file:
        os.makedirs(os.path.dirname(os.path.abspath(args.report_file)), exist_ok=True)
        with open(args.report_file, "w", encoding="utf-8") as f_rep:
            f_rep.write(report + "\n")
    if args.coverage_file:
        cov_txt: str = extract_coverage_section(combined_raw)
        os.makedirs(os.path.dirname(os.path.abspath(args.coverage_file)), exist_ok=True)
        with open(args.coverage_file, "w", encoding="utf-8") as f_cov:
            f_cov.write(cov_txt + ("\n" if cov_txt else ""))
    return 1 if has_err else 0


if __name__ == "__main__":
    raise SystemExit(main())
