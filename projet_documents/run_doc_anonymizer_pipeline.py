# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import sys
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner
from sync_contacts import merge_and_sync_contacts


def parse_args() -> argparse.Namespace:
    """
    Analyse les arguments de ligne de commande pour l'ordonnanceur doc_anonymizer.

    :return: Espace de noms contenant les options fournies.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Ordonnanceur exécutant l'extraction puis l'anonymisation "
            "au fil de l'eau sans mise en veille Windows/Linux."
        )
    )
    parser.add_argument(
        "-c", "--config",
        default="config.ini",
        help="Chemin vers le fichier config.ini (par défaut : config.ini).",
    )
    parser.add_argument(
        "--sync-contacts",
        default=None,
        help="Chemin du contacts.txt source à synchroniser avant traitement.",
    )
    parser.add_argument(
        "--overwrite-contacts",
        action="store_true",
        help="Écrase totalement contacts.txt lors de la synchronisation.",
    )
    parser.add_argument(
        "--allow-sleep",
        action="store_true",
        help="Autorise le système à se mettre en veille pendant l'exécution.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Point d'entrée principal de l'ordonnanceur doc_anonymizer.
    """
    args: argparse.Namespace = parse_args()
    config: PipelineConfig = PipelineConfig(config_path=args.config)

    if args.sync_contacts:
        print("=== SYNCHRONISATION DE CONTACTS.TXT ===", flush=True)
        merge_and_sync_contacts(
            source_path=args.sync_contacts,
            dest_path=config.contacts_file,
            preserve_manual_rules=not args.overwrite_contacts,
        )
        print("", flush=True)

    runner: DocAnonymizerPipelineRunner = DocAnonymizerPipelineRunner(
        config=config,
        prevent_sleep=not args.allow_sleep,
    )
    runner.run_all()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(
            "\n[ARRÊT] Pipeline interrompu proprement par l'utilisateur "
            "(Ctrl+C).",
            flush=True,
        )
        sys.exit(130)
