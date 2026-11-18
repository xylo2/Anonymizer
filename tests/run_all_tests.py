# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import importlib.util
import os
import sys
import tempfile
import unittest

TESTS_DIR: str = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR: str = os.path.dirname(TESTS_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def _load_mbox_tester():
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
    Exécute l'ensemble des tests unitaires et le test d'intégration .mbox.
    """
    print("=== 1. EXÉCUTION DES TESTS UNITAIRES ===")
    loader: unittest.TestLoader = unittest.TestLoader()
    suite: unittest.TestSuite = loader.discover(
        start_dir=TESTS_DIR,
        pattern="test_*.py",
    )
    runner: unittest.TextTestRunner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)

    print("\n=== 2. EXÉCUTION DU TEST D'INTÉGRATION .MBOX ===")
    tester_cls = _load_mbox_tester()
    with tempfile.TemporaryDirectory(prefix="test_mbox_anon_") as tmp_dir:
        tester_cls(work_dir=tmp_dir).run_and_assert()


if __name__ == "__main__":
    main()
