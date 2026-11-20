# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import configparser
import importlib
import os
import sys
from typing import List, Optional, Tuple
from doc_anonymizer.chat_prescanner import ChatContactPrescanner
from doc_anonymizer.contact_merger import ContactCatalogMerger

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def _load_contacts_backend():
    """Détecte et importe dynamiquement les modules config_manager et pipeline_runner des contacts."""
    candidates: List[str] = [
        "contacts",
        "contacts_pipeline",
        "contact_pipeline",
        "contacts_extractor",
        "contacts_manager",
    ]
    for entry in sorted(os.listdir(ROOT_DIR)):
        full_p: str = os.path.join(ROOT_DIR, entry)
        if (
            os.path.isdir(full_p)
            and entry != "doc_anonymizer"
            and os.path.isfile(os.path.join(full_p, "pipeline_runner.py"))
            and entry not in candidates
        ):
            candidates.insert(0, entry)

    for pkg_name in candidates:
        try:
            cfg_mod = importlib.import_module(f"{pkg_name}.config_manager")
            run_mod = importlib.import_module(f"{pkg_name}.pipeline_runner")
            cfg_cls = next(
                getattr(cfg_mod, attr)
                for attr in dir(cfg_mod)
                if attr.endswith("Config") and not attr.startswith("_")
            )
            run_cls = next(
                getattr(run_mod, attr)
                for attr in dir(run_mod)
                if attr.endswith("PipelineRunner") and not attr.startswith("_")
            )
            return cfg_cls, run_cls
        except (ModuleNotFoundError, StopIteration):
            continue
    raise ModuleNotFoundError("Impossible de localiser le package de traitement des contacts.")


def _resolve_sources_dir(ini_path: str) -> str:
    """Résout le dossier sources_dir depuis config.ini (par défaut input_documents)."""
    abs_ini: str = os.path.abspath(ini_path)
    base_dir: str = os.path.dirname(abs_ini)
    parser = configparser.ConfigParser()
    if os.path.isfile(abs_ini):
        parser.read(abs_ini, encoding="utf-8")
    rel_src: str = parser.get("paths", "sources_dir", fallback="input_documents").strip()
    return os.path.abspath(os.path.join(base_dir, rel_src))


def main(argv: Optional[List[str]] = None) -> int:
    """Point d'entrée CLI pour l'extraction, le pré-scan des chats et la fusion des contacts."""
    parser = argparse.ArgumentParser(
        description="Extraction, pré-scan et unification des contacts (CSV + chats + e-mails)."
    )
    parser.add_argument(
        "--config",
        default="config.ini",
        help="Chemin vers le fichier de configuration config.ini (défaut : config.ini).",
    )
    args, _ = parser.parse_known_args(argv)

    cfg_cls, run_cls = _load_contacts_backend()
    config = cfg_cls(args.config)
    runner = run_cls(config)
    ret_code: int = runner.run_all()

    if ret_code == 0:
        final_file: str = getattr(config, "final_contacts_file", "") or getattr(
            config, "contacts_file", ""
        )
        if final_file:
            out_dir: str = os.path.dirname(os.path.abspath(final_file))
            disc_chats: str = os.path.join(out_dir, "discovered_chat_contacts.txt")
            disc_emails: str = os.path.join(out_dir, "discovered_email_contacts.txt")
            sources_dir: str = _resolve_sources_dir(args.config)

            prescanner = ChatContactPrescanner(
                sources_dir=sources_dir,
                discovered_chats_file=disc_chats,
                discovered_emails_file=disc_emails,
                contacts_file=final_file,
                known_first_names=getattr(config, "known_first_names", set()),
            )
            pre_chats, pre_emails = prescanner.prescan_sources()
            if pre_chats > 0 or pre_emails > 0:
                print(
                    f"[PRÉ-SCAN DOCUMENTS] +{pre_chats} contact(s) de chat et "
                    f"+{pre_emails} adresse(s) e-mail détecté(s) dans '{sources_dir}'."
                )

            merger = ContactCatalogMerger(
                contacts_file=final_file,
                discovered_chats_file=disc_chats,
                discovered_emails_file=disc_emails,
                known_first_names=getattr(config, "known_first_names", set()),
            )
            added, total = merger.merge_all()
            if added > 0:
                print(
                    f"[FUSION CONTACTS] +{added} contact(s) issu(s) des chats/e-mails fusionné(s) "
                    f"dans '{final_file}' (total : {total})."
                )
    return ret_code


if __name__ == "__main__":
    sys.exit(main())
