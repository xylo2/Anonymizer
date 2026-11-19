# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import os
import sys
import time
from typing import List, Optional

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common.core_utils import SharedCoreUtils
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Analyse les arguments passés en ligne de commande.

    :param argv: Liste d'arguments optionnelle.
    :return: Espace de noms des options analysées.
    """
    parser = argparse.ArgumentParser(
        description="Extraction multi-formats et anonymisation locale de documents."
    )
    parser.add_argument(
        "-c",
        "--config",
        default=PipelineConfig.DEFAULT_CONFIG_PATH,
        help="Chemin vers le fichier de configuration INI (défaut : config.ini).",
    )
    parser.add_argument(
        "--sync-contacts",
        default="",
        help="Chemin d'un fichier contacts.txt externe à fusionner avant exécution.",
    )
    parser.add_argument(
        "--overwrite-contacts",
        action="store_true",
        help="Réinitialise la protection des règles lors de la synchronisation.",
    )
    parser.add_argument(
        "--allow-sleep",
        action="store_true",
        help="Autorise la mise en veille du système pendant le traitement.",
    )
    parser.add_argument(
        "--complete-manual",
        action="store_true",
        help="Complète automatiquement les lignes 'Prénom Nom = ' dans contacts_manuels.txt.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prévisualise les complétions de contacts_manuels.txt sans écriture.",
    )
    parser.add_argument(
        "--manual-only",
        action="store_true",
        help="Réapplique uniquement contacts_manuels.txt sur les lots existants.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """
    Point d'entrée principal du pipeline documentaire.

    :param argv: Arguments CLI optionnels.
    :return: Code de retour système (0 si succès).
    """
    args = parse_args(argv)
    config = PipelineConfig(args.config)

    if args.sync_contacts:
        from tools.sync_contacts import ContactsSynchronizer

        ContactsSynchronizer.merge_and_sync(
            source_path=args.sync_contacts,
            dest_path=config.contacts_file,
            preserve_manual_rules=not args.overwrite_contacts,
            manual_path=config.manual_contacts_file,
        )

    if args.complete_manual:
        from tools.completer_contacts_manuels import (
            ManualContactsAutoCompleter,
        )

        ManualContactsAutoCompleter(config, dry_run=args.dry_run).process()
        if args.dry_run:
            return 0

    t_start: float = time.time()
    SharedCoreUtils.prevent_sleep(not args.allow_sleep)
    try:
        if args.manual_only:
            anon_runner = DocumentAnonymizationRunner(config, manual_only=True)
            anon_runner.run_on_existing_results()
        else:
            pipeline = DocAnonymizerPipelineRunner(config)
            pipeline.run_all()
    finally:
        SharedCoreUtils.prevent_sleep(False)

    elapsed: str = SharedCoreUtils.format_duration(time.time() - t_start)
    print(f"[FIN] Pipeline documentaire terminé en {elapsed}.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
