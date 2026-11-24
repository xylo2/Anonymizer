# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import os
import signal
import sys
import time
from typing import Any, List, Optional

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common.core_utils import SharedCoreUtils
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner
from doc_anonymizer.power_manager import SystemSleepInhibitor
import run_contacts


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extraction multi-formats et anonymisation locale de documents."
    )
    parser.add_argument("-c", "--config", default=PipelineConfig.DEFAULT_CONFIG_PATH)
    parser.add_argument("--sync-contacts", default="")
    parser.add_argument("--overwrite-contacts", action="store_true")
    parser.add_argument("--allow-sleep", action="store_true")
    parser.add_argument("--complete-manual", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--manual-only", action="store_true")
    parser.add_argument("--anonymize-only", "--anon-only", action="store_true")
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("--reset-results", action="store_true")
    parser.add_argument("--with-contacts", action="store_true")
    parser.add_argument("--copy-unmasked", default="")
    parser.add_argument("--unmasked-dir", default="transcriptions_non_anonymisees")
    return parser.parse_args(argv)


def _install_sigint_handler() -> None:
    sigint_count: List[int] = [0]

    def _on_sigint(signum: int, frame: Any) -> None:
        sigint_count.append(1)
        if len(sigint_count) >= 3:
            print("\n[ARRÊT FORCÉ] Second Ctrl+C détecté : fermeture immédiate.", flush=True)
            os._exit(130)
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _on_sigint)
def main(argv: Optional[List[str]] = None) -> int:
    _install_sigint_handler()
    args = parse_args(argv)
    if args.with_contacts:
        ret_c: int = run_contacts.main(["-c", args.config])
        if ret_c != 0:
            return ret_c

    config = PipelineConfig(args.config)
    if args.copy_unmasked:
        from tools.copy_unmasked_transcriptions import UnmaskedTranscriptionCopier

        copier = UnmaskedTranscriptionCopier(config=config, output_dir=args.unmasked_dir)
        targets = copier.extract_targets_from_list_file(args.copy_unmasked)
        _, missing = copier.copy_from_targets(targets)
        return 0 if missing == 0 else 1

    if args.sync_contacts:
        from tools.sync_contacts import ContactsSynchronizer

        ContactsSynchronizer.merge_and_sync(
            source_path=args.sync_contacts,
            dest_path=config.contacts_file,
            preserve_manual_rules=not args.overwrite_contacts,
            manual_path=config.manual_contacts_file,
        )

    if args.complete_manual:
        from tools.complete_manual_contacts import ManualContactsAutoCompleter

        ManualContactsAutoCompleter(config, dry_run=args.dry_run).process()
        if args.dry_run:
            return 0

    t_start: float = time.time()
    try:
        if args.manual_only:
            with SystemSleepInhibitor(enabled=not args.allow_sleep):
                DocumentAnonymizationRunner(config, manual_only=True).run_on_existing_results()
        elif args.extract_only:
            DocAnonymizerPipelineRunner(config, prevent_sleep=not args.allow_sleep).run_extract_only(force_ocr_and_audio=True)
        elif args.anonymize_only:
            DocAnonymizerPipelineRunner(config, prevent_sleep=not args.allow_sleep).run_anonymize_only(reset_results=args.reset_results)
        else:
            DocAnonymizerPipelineRunner(config, prevent_sleep=not args.allow_sleep).run_all()
    except KeyboardInterrupt:
        print("\n[ARRÊT] Traitement interrompu proprement par l'utilisateur (Ctrl+C).", flush=True)
        return 130

    elapsed: str = SharedCoreUtils.format_duration(time.time() - t_start)
    print(f"[FIN] Pipeline documentaire terminé en {elapsed}.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
