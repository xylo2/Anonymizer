# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestCleanupDuplicateDir(unittest.TestCase):
    """Nettoie les éventuels fichiers ou dossiers obsolètes du projet."""

    def test_remove_nested_duplicate_folder_and_obsolete_vault_if_present(self) -> None:
        nested_dup: str = os.path.join(ROOT_DIR, "médical")
        if os.path.isdir(nested_dup):
            shutil.rmtree(nested_dup, ignore_errors=True)
        self.assertFalse(os.path.exists(nested_dup))

        obsolete_vault: str = os.path.join(ROOT_DIR, "doc_anonymizer", "reversibility_vault.py")
        if os.path.isfile(obsolete_vault):
            os.remove(obsolete_vault)
        self.assertFalse(os.path.exists(obsolete_vault))


if __name__ == "__main__":
    unittest.main()
