# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import sys

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from gui_anonymizer import main


if __name__ == "__main__":
    sys.exit(main(["--gui-errors", *sys.argv[1:]]))
