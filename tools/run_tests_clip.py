# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Utilisateur_A

import argparse
import io
import json
import os
import re
import sys
import time
import unittest
import warnings
from typing import Any, List, Optional, Set, Tuple

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
sys.modules.setdefault("tools.run_tests_clip", sys.modules[__name__])


def _extract_test_id(label: str) -> str:
    """Extrait 'pkg.mod.Class.method' depuis 'method (pkg.mod.Class)'."""
    match = re.match(r"^([^\s(]+)\s*\(([^)]+)\)", label.strip())
    return f"{match.group(2).strip()}.{match.group(1).strip()}" if match else label.strip()


def _parse_failed(raw_cli: str) -> List[str]:
    """Parse la liste des tests KO depuis --failed-tests ou l'environnement."""
    raw: str = (raw_cli or os.environ.get("WATCH_CLIPBOARD_FAILED_TESTS", "")).strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [_extract_test_id(str(x)) for x in data if str(x).strip()]
        except json.JSONDecodeError:
            pass
    return [_extract_test_id(p) for p in raw.split("|") if p.strip()]


def compact_error_report(raw_output: str) -> str:
    """Compacte une sortie unittest en conservant erreurs et warnings."""
    out: List[str] = []
    warns: List[str] = []
    seen: Set[str] = set()
    ran_ln = st_ln = ""
    lines = raw_output.splitlines()
    i = 0
    while i < len(lines):
        cur = lines[i].strip()
        m_hdr = re.match(r"^(FAIL|ERROR):\s+(.+)$", cur)
        if m_hdr:
            kind, tname = m_hdr.group(1), m_hdr.group(2).strip()
            blk: List[str] = []
            i += 1
            while i < len(lines) and not re.match(r"^(={10,}|-{10,}|Ran \d+ test)", lines[i]):
                blk.append(lines[i].strip())
                i += 1
            msg = next((b for b in reversed(blk) if b and not b.startswith(("Traceback", 'File "'))), "")
            sig = f"{kind}:{msg}"
            out.append(f"[DOUBLON] {kind}: {tname} -> {msg}" if sig in seen else f"{kind}: {tname} | {msg}")
            seen.add(sig)
            continue
        if re.search(r"\b\w*Warning:", cur) and cur not in seen:
            seen.add(cur)
            warns.append(f"WARNING: {cur}")
        elif re.match(r"^Ran \d+ tests? in .+$", cur):
            ran_ln = cur
        elif re.match(r"^(OK|FAILED).*$", cur):
            st_ln = cur
        i += 1
    if warns:
        out.extend(["WARNINGS DÉTECTÉS :", *warns])
    if ran_ln:
        out.append(f"{ran_ln} | {st_ln}" if st_ln else ran_ln)
    return "\n".join(out)


def extract_coverage_section(raw_output: str) -> str:
    """Extrait la ligne COUVERTURE GLOBALE depuis une sortie brute."""
    m = re.search(r"COUVERTURE GLOBALE\s*[|:]\s*([0-9]+(?:\.[0-9]+)?)%", raw_output)
    return f"COUVERTURE GLOBALE : {float(m.group(1)):.1f}%" if m else ""


def main(argv: Optional[List[str]] = None) -> int:
    """Exécute les tests séquentiellement et quitte immédiatement après le bilan."""
    warnings.simplefilter("default")
    p = argparse.ArgumentParser()
    p.add_argument("--pattern", default="test_*.py")
    p.add_argument("--module", default="")
    p.add_argument("--failed-tests", default="")
    p.add_argument("--report-file", default="")
    p.add_argument("--coverage-file", default="")
    args, _ = p.parse_known_args(argv)
    t0 = time.perf_counter()
    failed = _parse_failed(args.failed_tests)
    tdir = os.path.join(ROOT_DIR, "tests")
    mods = sorted(f"tests.{f[:-3]}" for f in os.listdir(tdir) if f.startswith("test_") and f.endswith(".py"))
    targets = failed or ([args.module] if args.module else mods)
    print(f"=== Démarrage de {len(targets)} cible(s) ===", flush=True)
    cov: Any = None
    if args.coverage_file and not failed:
        try:
            import coverage  # type: ignore[import-not-found]
            cov = coverage.Coverage(source=[os.path.join(ROOT_DIR, d) for d in ("common", "doc_anonymizer", "google_contacts_parser", "tools")], omit=["*/__init__.py", "*/tests/*"])
            cov.start()
        except ImportError:
            cov = None
    total = 0
    chunks: List[str] = []
    for tgt in targets:
        tm = time.perf_counter()
        stream = io.StringIO()
        with warnings.catch_warnings(record=True) as cw:
            warnings.simplefilter("default")
            res = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.TestLoader().loadTestsFromName(tgt))
        out_s = stream.getvalue() + "".join(f"\n{w.filename}:{w.lineno}: {w.category.__name__}: {w.message}" for w in cw)
        total += res.testsRun
        chunks.append(out_s)
        print(f"  [{'OK' if res.wasSuccessful() and not cw else 'FAIL'}] {tgt} ({res.testsRun} test(s), {time.perf_counter() - tm:.2f}s)", flush=True)
    if cov is not None:
        cov.stop()
        cov.save()
    comp = compact_error_report("\n".join(chunks))
    err = any(ln.startswith(("FAIL:", "ERROR:", "WARNINGS DÉTECTÉS")) for ln in comp.splitlines())
    clean = [ln for ln in comp.splitlines() if not re.match(r"^(Ran \d+ tests? in .+|OK.*|FAILED.*)$", ln)]
    clean.append(f"Ran {total} tests in {time.perf_counter() - t0:.3f}s | {'FAILED' if err else 'OK'}")
    rep = "\n".join(clean)
    print(f"\n=== Bilan ===\n{rep}", flush=True)
    if args.report_file:
        os.makedirs(os.path.dirname(os.path.abspath(args.report_file)), exist_ok=True)
        open(args.report_file, "w", encoding="utf-8").write(rep + "\n")
    if cov is not None and not err:
        buf = io.StringIO()
        pct = cov.report(file=buf, skip_empty=True)
        os.makedirs(os.path.dirname(os.path.abspath(args.coverage_file)), exist_ok=True)
        open(args.coverage_file, "w", encoding="utf-8").write(f"COUVERTURE GLOBALE : {pct:.1f}% (0/0 lignes) ({total} tests unitaires)\n")
    sys.stdout.flush()
    sys.stderr.flush()
    if argv is None:
        os._exit(1 if err else 0)
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
