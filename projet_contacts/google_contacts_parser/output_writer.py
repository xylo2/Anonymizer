# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import os
from typing import List, Tuple
from google_contacts_parser.config_manager import ContactsConfig


class ContactsOutputWriter:
    """
    Écrit les correspondances (coordonnée = prénom nom) dans le fichier texte de sortie.
    """

    def __init__(self, config: ContactsConfig) -> None:
        """
        Initialise le rédacteur avec la configuration du projet.

        :param config: Instance de ContactsConfig contenant le chemin et l'encodage de sortie.
        """
        self.config: ContactsConfig = config

    def write_entries(self, entries: List[Tuple[str, str]]) -> None:
        """
        Écrit chaque paire (coordonnée, nom) sur une ligne distincte du fichier cible.

        :param entries: Liste complète des tuples (coordonnée, prénom nom) à enregistrer.
        """
        output_dir: str = os.path.dirname(self.config.output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(self.config.output_file, mode="w", encoding="utf-8", newline="\n") as out_file:
            for contact_value, full_name in entries:
                out_file.write(f"{contact_value}{self.config.separator}{full_name}\n")
