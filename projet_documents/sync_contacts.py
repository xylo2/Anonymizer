# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import os
import shutil
from typing import List, Set


def merge_and_sync_contacts(
    source_path: str,
    dest_path: str,
    preserve_manual_rules: bool = True,
) -> None:
    """
    Copie le fichier contacts.txt généré par google_contacts_parser vers le
    dossier doc_anonymizer en conservant les règles manuelles existantes.

    :param source_path: Chemin vers le fichier contacts.txt source.
    :param dest_path: Chemin de destination dans doc_anonymizer.
    :param preserve_manual_rules: Conserve les lignes non issues de l'export.
    """
    resolved_src: str = os.path.abspath(source_path)
    resolved_dst: str = os.path.abspath(dest_path)

    if not os.path.exists(resolved_src):
        raise FileNotFoundError(
            f"Fichier source introuvable : '{resolved_src}'"
        )

    if not preserve_manual_rules or not os.path.exists(resolved_dst):
        shutil.copy2(resolved_src, resolved_dst)
        print(
            f"[OK] '{resolved_src}' copié vers '{resolved_dst}'.",
            flush=True,
        )
        return

    with open(resolved_src, "r", encoding="utf-8") as f_src:
        src_lines: List[str] = [
            ln.rstrip("\r\n") for ln in f_src if ln.strip()
        ]

    src_keys: Set[str] = {
        ln.split("=", 1).strip().lower() for ln in src_lines if "=" in ln
    }

    manual_lines: List[str] = []
    with open(resolved_dst, "r", encoding="utf-8") as f_dst:
        for raw_ln in f_dst:
            clean_ln: str = raw_ln.strip()
            if not clean_ln or clean_ln.startswith("#") or "=" not in clean_ln:
                continue
            left_key: str = clean_ln.split("=", 1).strip().lower()
            if left_key not in src_keys:
                manual_lines.append(clean_ln)

    with open(resolved_dst, "w", encoding="utf-8", newline="\n") as f_out:
        for ln in src_lines:
            f_out.write(f"{ln}\n")
        if manual_lines:
            f_out.write("\n# --- RÈGLES MANUELLES CONSERVÉES ---\n")
            for m_ln in sorted(set(manual_lines)):
                f_out.write(f"{m_ln}\n")

    print(
        f"[OK] Synchronisation terminée : {len(src_lines)} contact(s) "
        f"importé(s), {len(set(manual_lines))} règle(s) manuelle(s) "
        "conservée(s).",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    """
    Analyse les arguments de ligne de commande pour la copie de contacts.txt.

    :return: Espace de noms contenant les chemins source et destination.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Synchronise contacts.txt entre les deux sous-projets."
    )
    parser.add_argument(
        "-s", "--source",
        default=os.path.join("..", "contacts.txt"),
        help="Chemin du contacts.txt généré (défaut : ../contacts.txt).",
    )
    parser.add_argument(
        "-d", "--dest",
        default="contacts.txt",
        help="Chemin de destination (défaut : ./contacts.txt).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Écrase totalement le fichier destination sans fusionner.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Point d'entrée principal du script de synchronisation.
    """
    args: argparse.Namespace = parse_args()
    merge_and_sync_contacts(
        source_path=args.source,
        dest_path=args.dest,
        preserve_manual_rules=not args.overwrite,
    )


if __name__ == "__main__":
    main()
