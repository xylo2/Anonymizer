# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import os
import sys
from contacts_anonymizer.config_manager import ContactsConfig
from contacts_anonymizer.pipeline_runner import ContactsPipelineRunner
from doc_anonymizer.contact_merger import ContactCatalogMerger


def main() -> int:
    """Point d'entrée CLI pour l'extraction, l'anonymisation et la fusion des contacts."""
    parser = argparse.ArgumentParser(
        description="Extraction, anonymisation et unifications des contacts (CSV + chats + e-mails)."
    )
    parser.add_argument(
        "--config",
        default="config.ini",
        help="Chemin vers le fichier de configuration config.ini (défaut : config.ini).",
    )
    args = parser.parse_args()

    config = ContactsConfig(args.config)
    runner = ContactsPipelineRunner(config)
    ret_code: int = runner.run_all()

    if ret_code == 0:
        out_dir: str = os.path.dirname(os.path.abspath(config.final_contacts_file))
        disc_chats: str = os.path.join(out_dir, "discovered_chat_contacts.txt")
        disc_emails: str = os.path.join(out_dir, "discovered_email_contacts.txt")
        merger = ContactCatalogMerger(
            contacts_file=config.final_contacts_file,
            discovered_chats_file=disc_chats,
            discovered_emails_file=disc_emails,
            known_first_names=config.known_first_names,
        )
        added, total = merger.merge_all()
        if added > 0:
            print(
                f"[FUSION CONTACTS] +{added} contact(s) issu(s) des chats/e-mails fusionné(s) "
                f"dans '{config.final_contacts_file}' (total : {total})."
            )
    return ret_code


if __name__ == "__main__":
    sys.exit(main())
