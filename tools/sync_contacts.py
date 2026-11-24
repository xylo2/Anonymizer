# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import os
import shutil
import sys
from typing import Optional

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common.core_utils import SharedCoreUtils


class ContactsSynchronizer:
    """
    Gère l'initialisation atomique de output_contacts/manual_contacts.txt et la copie
    sécurisée du référentiel output_contacts/contacts.txt.
    """

    @classmethod
    def ensure_manual_contacts_file(cls, manual_path: str) -> None:
        """
        Crée le fichier manual_contacts.txt avec son en-tête de façon atomique
        s'il n'existe pas encore.

        :param manual_path: Chemin vers le fichier des règles manuelles.
        """
        resolved_manual: str = os.path.abspath(manual_path)
        if os.path.exists(resolved_manual):
            return
        header: str = (
            "# RÈGLES D'ANONYMISATION MANUELLES\n"
            "# Ce fichier n'est jamais écrasé par run_contacts.py.\n"
            "# Ajoutez ici les noms issus de audits/residual_names_audit.txt :\n"
            "# Format : Prénom Nom = Alias\n\n"
        )
        SharedCoreUtils.atomic_write_text(resolved_manual, header)
        print(f"[OK] Fichier manuel initialisé : '{resolved_manual}'.", flush=True)

    @classmethod
    def merge_and_sync(
        cls,
        source_path: str,
        dest_path: str,
        preserve_manual_rules: bool = True,
        manual_path: Optional[str] = None,
    ) -> None:
        """
        Copie le fichier contacts.txt généré automatiquement vers la destination
        en vérifiant qu'il n'est pas vide et en gardant les règles manuelles isolées.

        :param source_path: Chemin vers le fichier contacts.txt source.
        :param dest_path: Chemin de destination de contacts.txt.
        :param preserve_manual_rules: Préserve le fichier manual_contacts.txt dédié.
        :param manual_path: Chemin optionnel vers manual_contacts.txt.
        """
        resolved_src: str = os.path.abspath(source_path)
        resolved_dst: str = os.path.abspath(dest_path)

        if not os.path.exists(resolved_src):
            raise FileNotFoundError(f"Fichier source introuvable : '{resolved_src}'")
        if os.path.getsize(resolved_src) == 0:
            raise ValueError(
                f"Le fichier source '{resolved_src}' est vide : copie annulée."
            )

        dst_dir: str = os.path.dirname(resolved_dst)
        if dst_dir:
            os.makedirs(dst_dir, exist_ok=True)

        if resolved_src != resolved_dst:
            shutil.copy2(resolved_src, resolved_dst)
            print(f"[OK] '{resolved_src}' copié vers '{resolved_dst}'.", flush=True)
        else:
            print(f"[INFO] Source et destination identiques ('{resolved_dst}').", flush=True)

        target_manual: str = (
            manual_path
            if manual_path
            else os.path.join(os.path.dirname(resolved_dst), "manual_contacts.txt")
        )
        if preserve_manual_rules:
            cls.ensure_manual_contacts_file(target_manual)


def parse_args() -> argparse.Namespace:
    """
    Analyse les arguments de ligne de commande pour la copie de contacts.txt.

    :return: Espace de noms contenant les chemins source et destination.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Synchronise contacts.txt et prépare manual_contacts.txt."
    )
    parser.add_argument(
        "-s", "--source",
        default=os.path.join(ROOT_DIR, "output_contacts", "contacts.txt"),
        help="Chemin du contacts.txt généré (défaut : output_contacts/contacts.txt).",
    )
    parser.add_argument(
        "-d", "--dest",
        default=os.path.join(ROOT_DIR, "output_contacts", "contacts.txt"),
        help="Chemin de destination (défaut : output_contacts/contacts.txt).",
    )
    parser.add_argument(
        "-m", "--manual",
        default=None,
        help="Chemin vers manual_contacts.txt (défaut : même dossier que dest).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Ignore l'initialisation du fichier manuel lors de la copie.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Point d'entrée principal du script de synchronisation.
    """
    args: argparse.Namespace = parse_args()
    ContactsSynchronizer.merge_and_sync(
        source_path=args.source,
        dest_path=args.dest,
        preserve_manual_rules=not args.overwrite,
        manual_path=args.manual,
    )


if __name__ == "__main__":
    main()
