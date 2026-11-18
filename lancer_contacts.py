# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import os
import sys


def parse_args() -> argparse.Namespace:
    """
    Analyse les arguments de ligne de commande pour le lanceur racine.

    :return: Espace de noms contenant le chemin du fichier de configuration.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Lance le pipeline d'extraction et d'anonymisation des contacts "
            "(projet_contacts) depuis la racine."
        )
    )
    parser.add_argument(
        "-c", "--config",
        default="config.ini",
        help="Chemin vers le fichier config.ini (défaut : config.ini).",
    )
    return parser.parse_args()


def main() -> None:
    """
    Point d'entrée racine pour exécuter google_contacts_parser.
    """
    root_dir: str = os.path.dirname(os.path.abspath(__file__))
    project_dir: str = os.path.join(root_dir, "projet_contacts")

    if not os.path.isdir(project_dir):
        raise FileNotFoundError(
            f"Sous-dossier introuvable : '{project_dir}'. "
            "Vérifiez l'arborescence de votre espace de travail."
        )

    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

    from google_contacts_parser.config_manager import ContactsConfig
    from google_contacts_parser.pipeline_runner import ContactsPipelineRunner

    args: argparse.Namespace = parse_args()
    config_path: str = (
        args.config
        if os.path.isabs(args.config)
        else os.path.join(root_dir, args.config)
    )

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Fichier de configuration introuvable : '{config_path}'"
        )

    config: ContactsConfig = ContactsConfig(config_path=config_path)
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
