# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

from typing import List, Tuple
from common.core_utils import SharedCoreUtils
from google_contacts_parser.config_manager import ContactsConfig


class ContactsOutputWriter:
    """
    Écrit de manière atomique les correspondances (coordonnée = prénom nom)
    dans le fichier texte de sortie.
    """

    def __init__(self, config: ContactsConfig) -> None:
        """
        Initialise le rédacteur avec la configuration du projet.

        :param config: Instance de ContactsConfig contenant le chemin et le séparateur.
        """
        self.config: ContactsConfig = config

    def write_entries(self, entries: List[Tuple[str, str]]) -> None:
        """
        Écrit chaque paire (coordonnée, nom) sur une ligne distincte du fichier cible
        via l'écriture atomique partagée.

        :param entries: Liste complète des tuples (coordonnée, prénom nom) à enregistrer.
        """
        lines: List[str] = [
            f"{contact_value}{self.config.separator}{full_name}\n"
            for contact_value, full_name in entries
        ]
        SharedCoreUtils.atomic_write_text(
            target_path=self.config.output_file,
            content="".join(lines),
            encoding="utf-8",
        )
