# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import os
import sys


def parse_args() -> argparse.Namespace:
    """
    Analyse les arguments de ligne de commande pour le lanceur racine.

    :return: Espace de noms contenant les options d'exécution.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Lance le pipeline d'extraction et d'anonymisation de documents "
            "(projet_documents) depuis la racine."
        )
    )
    parser.add_argument(
        "-c", "--config",
        default="config.ini",
        help="Chemin vers le fichier config.ini (défaut : config.ini).",
    )
    parser.add_argument(
        "--sync-contacts",
        default=None,
        help="Chemin d'un contacts.txt externe à fusionner avant traitement.",
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
    Point d'entrée racine pour exécuter doc_anonymizer.
    """
    root_dir: str = os.path.dirname(os.path.abspath(__file__))
    project_dir: str = os.path.join(root_dir, "projet_documents")

    if not os.path.isdir(project_dir):
        raise FileNotFoundError(
            f"Sous-dossier introuvable : '{project_dir}'. "
            "Vérifiez l'arborescence de votre espace de travail."
        )

    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

    from doc_anonymizer.config_manager import PipelineConfig
    from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner
    from sync_contacts import merge_and_sync_contacts

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

    config: PipelineConfig = PipelineConfig(config_path=config_path)

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
