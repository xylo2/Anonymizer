# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.extraction_runner import DocumentExtractionRunner


def parse_args() -> argparse.Namespace:
    """
    Analyse les arguments de ligne de commande pour l'extraction de documents.

    :return: Espace de noms contenant les options fournies.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Extrait et transcrit les documents et communications vers le dossier transcriptions."
    )
    parser.add_argument(
        "-c", "--config",
        default="config.ini",
        help="Chemin vers le fichier config.ini (par défaut : config.ini).",
    )
    return parser.parse_args()


def main() -> None:
    """
    Point d'entrée principal coordonnant l'étape 1 d'extraction multi-formats.
    """
    args: argparse.Namespace = parse_args()
    config: PipelineConfig = PipelineConfig(config_path=args.config)
    runner: DocumentExtractionRunner = DocumentExtractionRunner(config=config)
    runner.run()


if __name__ == "__main__":
    main()
