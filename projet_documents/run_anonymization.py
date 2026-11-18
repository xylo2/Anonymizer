# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig


def parse_args() -> argparse.Namespace:
    """
    Analyse les arguments de ligne de commande pour l'anonymisation des transcriptions.

    :return: Espace de noms contenant les options fournies.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Anonymise les transcriptions en appliquant les règles de contacts.txt."
    )
    parser.add_argument(
        "-c", "--config",
        default="config.ini",
        help="Chemin vers le fichier config.ini (par défaut : config.ini).",
    )
    return parser.parse_args()


def main() -> None:
    """
    Point d'entrée principal coordonnant l'étape 2 d'anonymisation et d'audit.
    """
    args: argparse.Namespace = parse_args()
    config: PipelineConfig = PipelineConfig(config_path=args.config)
    runner: DocumentAnonymizationRunner = DocumentAnonymizationRunner(config=config)
    runner.run()


if __name__ == "__main__":
    main()
