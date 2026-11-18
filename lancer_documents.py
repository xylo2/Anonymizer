# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import os
import sys

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common.core_utils import SharedCoreUtils
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner
from tools.completer_contacts_manuels import ManualContactsAutoCompleter
from tools.sync_contacts import ContactsSynchronizer


class RootDocumentsLauncher:
    """
    Encapsule l'analyse des arguments et l'exécution du pipeline
    de documents depuis la racine du dépôt.
    """

    def __init__(self) -> None:
        """
        Initialise le répertoire racine du projet.
        """
        self.root_dir: str = ROOT_DIR

    @staticmethod
    def parse_args() -> argparse.Namespace:
        """
        Analyse les arguments de ligne de commande pour le lanceur documents.

        :return: Espace de noms contenant les options d'exécution.
        """
        parser: argparse.ArgumentParser = argparse.ArgumentParser(
            description=(
                "Lance le pipeline d'extraction et d'anonymisation de documents "
                "(doc_anonymizer) depuis la racine."
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
        parser.add_argument(
            "--complete-manual",
            action="store_true",
            help="Complète automatiquement les lignes vides 'Prénom Nom = ' dans contacts_manuels.txt.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Prévisualise les complétions de contacts_manuels.txt sans écrire sur le disque.",
        )
        parser.add_argument(
            "--manual-only",
            action="store_true",
            help="Applique uniquement contacts_manuels.txt sur resultats_anonymisation.",
        )
        return parser.parse_args()

    def run(self) -> None:
        """
        Exécute les synchronisations éventuelles puis l'étape demandée.
        """
        args: argparse.Namespace = self.parse_args()
        config_path: str = SharedCoreUtils.resolve_config_path(args.config, self.root_dir)
        config: PipelineConfig = PipelineConfig(config_path=config_path)

        if args.sync_contacts:
            print("=== SYNCHRONISATION DE CONTACTS.TXT ===", flush=True)
            ContactsSynchronizer.merge_and_sync(
                source_path=args.sync_contacts,
                dest_path=config.contacts_file,
                preserve_manual_rules=not args.overwrite_contacts,
            )
            print("", flush=True)

        if args.complete_manual:
            completer: ManualContactsAutoCompleter = ManualContactsAutoCompleter(
                config=config, dry_run=args.dry_run
            )
            completer.process()
            if not args.manual_only:
                return
            if args.dry_run:
                print(
                    "\n[INFO] Mode --dry-run actif : passe --manual-only "
                    "ignorée tant que les règles ne sont pas enregistrées.",
                    flush=True,
                )
                return
            print("", flush=True)

        if args.manual_only:
            manual_runner: DocumentAnonymizationRunner = DocumentAnonymizationRunner(
                config=config, manual_only=True
            )
            manual_runner.run_on_existing_results()
            return

        runner: DocAnonymizerPipelineRunner = DocAnonymizerPipelineRunner(
            config=config,
            prevent_sleep=not args.allow_sleep,
        )
        runner.run_all()


def main() -> None:
    """
    Point d'entrée racine pour exécuter doc_anonymizer.
    """
    RootDocumentsLauncher().run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(
            "\n[ARRÊT] Pipeline interrompu proprement par l'utilisateur "
            "(Ctrl+C). Fermeture immédiate.",
            flush=True,
        )
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(130)
