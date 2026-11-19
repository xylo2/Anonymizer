# Commandes pip à exécuter : pip install coverage

import argparse
import importlib.util
import io
import os
import sys
import tempfile
from typing import Any, List, Optional, Tuple
import unittest

TESTS_DIR: str = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR: str = os.path.dirname(TESTS_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def _start_coverage() -> Optional[Any]:
    """
    Démarre la mesure de couverture sur les packages métier si coverage est installé.

    :return: Instance de coverage.Coverage ou None si le module est absent.
    """
    try:
        import coverage  # type: ignore[import-not-found]
    except ImportError:
        print(
            "[INFO] Module 'coverage' non installé : exécution sans rapport "
            "(pip install coverage pour l'activer).\n",
            flush=True,
        )
        return None

    cov = coverage.Coverage(
        source=[
            os.path.join(ROOT_DIR, "common"),
            os.path.join(ROOT_DIR, "doc_anonymizer"),
            os.path.join(ROOT_DIR, "google_contacts_parser"),
            os.path.join(ROOT_DIR, "tools"),
        ],
        omit=["*/__init__.py", "*/tests/*", "*/.venv/*", "*/venv/*"],
    )
    cov.start()
    return cov


def _format_coverage_summary(cov: Any, show_missing: bool = False) -> None:
    """
    Affiche un tableau compact, trié et lisible des taux de couverture par module.

    :param cov: Instance active de coverage.Coverage.
    :param show_missing: Affiche le détail des lignes manquantes si True.
    """
    if show_missing:
        cov.report(show_missing=True, skip_empty=True)
        return

    buf: io.StringIO = io.StringIO()
    total_pct: float = cov.report(file=buf, show_missing=False, skip_empty=True)
    rows: List[Tuple[float, str, int, int]] = []

    for line in buf.getvalue().splitlines():
        parts: List[str] = line.split()
        if len(parts) < 4 or parts[0] in {"Name", "TOTAL"} or line.startswith("-"):
            continue
        pct_str: str = parts[-1].rstrip("%")
        try:
            pct: float = float(pct_str)
            stmts: int = int(parts[-3])
            miss: int = int(parts[-2])
        except ValueError:
            continue
        raw_path: str = " ".join(parts[:-3])
        rel_path: str = os.path.relpath(raw_path, ROOT_DIR).replace("\\", "/")
        rows.append((pct, rel_path, stmts, miss))

    rows.sort(key=lambda item: (item[0], item[1]))
    print(f"{'Module':<46} | {'Couv.':>6} | {'Statut':<7} | {'Lignes'}", flush=True)
    print("-" * 76, flush=True)
    for pct, rel_path, stmts, miss in rows:
        status: str = "OK" if pct >= 85.0 else ("MOYEN" if pct >= 70.0 else "BAS")
        covered: int = stmts - miss
        print(f"{rel_path:<46} | {pct:5.1f}% | {status:<7} | {covered}/{stmts}", flush=True)
    print("-" * 76, flush=True)
    print(f"{'COUVERTURE GLOBALE':<46} | {total_pct:5.1f}%", flush=True)
def _stop_and_report_coverage(cov: Optional[Any], show_missing: bool = False) -> None:
    """
    Arrête la mesure de couverture et affiche le rapport synthétique.

    :param cov: Instance active de coverage.Coverage ou None.
    :param show_missing: Affiche les numéros de lignes manquantes si True.
    """
    if cov is None:
        return
    cov.stop()
    cov.save()
    print("\n=== 3. RAPPORT DE COUVERTURE DE CODE ===", flush=True)
    _format_coverage_summary(cov, show_missing=show_missing)


def _load_mbox_tester() -> Any:
    """
    Charge dynamiquement MboxPipelineTester depuis tests/test_mbox_pipeline.py.

    :return: Classe MboxPipelineTester.
    """
    mbox_test_path: str = os.path.join(TESTS_DIR, "test_mbox_pipeline.py")
    if not os.path.exists(mbox_test_path):
        raise FileNotFoundError(
            f"Fichier introuvable : '{mbox_test_path}'. "
            "Vérifiez que test_mbox_pipeline.py est bien dans le dossier tests/."
        )
    spec = importlib.util.spec_from_file_location("local_test_mbox_pipeline", mbox_test_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossible de charger '{mbox_test_path}'.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MboxPipelineTester


def main() -> None:
    """
    Exécute l'ensemble des tests unitaires, le test d'intégration .mbox
    et affiche le taux de couverture de code.
    """
    parser = argparse.ArgumentParser(description="Lance tous les tests et la couverture.")
    parser.add_argument(
        "--show-missing",
        action="store_true",
        help="Affiche les numéros précis des lignes non couvertes.",
    )
    args = parser.parse_args()

    cov: Optional[Any] = _start_coverage()
    try:
        print("=== 1. EXÉCUTION DES TESTS UNITAIRES ===", flush=True)
        loader: unittest.TestLoader = unittest.TestLoader()
        suite: unittest.TestSuite = loader.discover(
            start_dir=TESTS_DIR,
            pattern="test_*.py",
        )
        runner: unittest.TextTestRunner = unittest.TextTestRunner(verbosity=1)
        result = runner.run(suite)
        if not result.wasSuccessful():
            sys.exit(1)

        print("\n=== 2. EXÉCUTION DU TEST D'INTÉGRATION .MBOX ===", flush=True)
        tester_cls = _load_mbox_tester()
        with tempfile.TemporaryDirectory(prefix="test_mbox_anon_") as tmp_dir:
            tester_cls(work_dir=tmp_dir).run_and_assert()
    finally:
        _stop_and_report_coverage(cov, show_missing=args.show_missing)


if __name__ == "__main__":
    main()
