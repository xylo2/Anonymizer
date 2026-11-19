# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import os
import sys

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common.core_utils import SharedCoreUtils
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.pipeline_runner import ContactsPipelineRunner


class RootContactsLauncher:
    """
    Encapsule l'analyse des arguments et l'exécution du pipeline
    de contacts depuis la racine du dépôt.
    """

    def __init__(self) -> None:
        """
        Initialise le répertoire racine du projet.
        """
        self.root_dir: str = ROOT_DIR

    @staticmethod
    def parse_args() -> argparse.Namespace:
        """
        Analyse les arguments de ligne de commande pour le lanceur contacts.

        :return: Espace de noms contenant le chemin du fichier de configuration.
        """
        parser: argparse.ArgumentParser = argparse.ArgumentParser(
            description=(
                "Lance le pipeline d'extraction et d'anonymisation des contacts "
                "(google_contacts_parser) depuis la racine."
            )
        )
        parser.add_argument(
            "-c", "--config",
            default="config.ini",
            help="Chemin vers le fichier config.ini (défaut : config.ini).",
        )
        return parser.parse_args()

    def run(self) -> None:
        """
        Résout config.ini et exécute l'ensemble du pipeline de contacts.
        """
        args: argparse.Namespace = self.parse_args()
        config_path: str = SharedCoreUtils.resolve_config_path(args.config, self.root_dir)
        config: ContactsConfig = ContactsConfig(config_path=config_path)
        runner: ContactsPipelineRunner = ContactsPipelineRunner(config=config)
        runner.run_all()


def main() -> None:
    """
    Point d'entrée racine pour exécuter google_contacts_parser.
    """
    RootContactsLauncher().run()


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
