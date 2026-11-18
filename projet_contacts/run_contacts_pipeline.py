# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import sys
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.pipeline_runner import ContactsPipelineRunner


def parse_args() -> argparse.Namespace:
    """
    Analyse les arguments de ligne de commande pour le pipeline de contacts.

    :return: Espace de noms contenant le chemin vers le fichier INI.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Exécute l'extraction, l'anonymisation et le dédoublonnage "
            "des exports Google Contacts et Microsoft 365."
        )
    )
    parser.add_argument(
        "-c", "--config",
        default="config.ini",
        help="Chemin vers le fichier config.ini (par défaut : config.ini).",
    )
    return parser.parse_args()


def main() -> None:
    """
    Point d'entrée principal du programme de contacts.
    """
    args: argparse.Namespace = parse_args()
    config: ContactsConfig = ContactsConfig(config_path=args.config)
    runner: ContactsPipelineRunner = ContactsPipelineRunner(config=config)
    runner.run_all()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(
            "\n[ARRÊT] Traitement des contacts interrompu par l'utilisateur "
            "(Ctrl+C). Aucun fichier final modifié.",
            flush=True,
        )
        sys.exit(130)
