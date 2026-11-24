# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import os
from typing import List, Tuple
from common.core_utils import SharedCoreUtils
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.text_utils import ContactTextUtils


class ContactsInverter:
    """
    Lit le fichier dédoublonné, inverse la partie gauche et la partie droite du séparateur
    et trie les lignes obtenues par ordre alphabétique sur la nouvelle partie gauche.
    """

    def __init__(self, config: ContactsConfig) -> None:
        """
        Initialise l'inverseur avec la configuration du projet.

        :param config: Instance de ContactsConfig contenant les chemins et séparateurs.
        """
        self.config: ContactsConfig = config

    @staticmethod
    def _sort_key(pair: Tuple[str, str]) -> Tuple[str, str, str]:
        """
        Calcule la clé de tri alphabétique basée sur la nouvelle partie gauche (libellé)
        puis sur la partie droite (coordonnée).

        :param pair: Tuple (nouvelle_gauche, nouvelle_droite).
        :return: Tuple normalisé pour un tri alphabétique insensible aux accents et à la casse.
        """
        new_left, new_right = pair
        norm_left: str = ContactTextUtils.normalize_text(new_left)
        return (norm_left, new_left.lower(), new_right.lower())

    def process(self) -> int:
        """
        Inverse chaque ligne du fichier dédoublonné (droite = gauche), trie par la nouvelle
        partie gauche et écrit le résultat de manière atomique dans contacts.txt.

        :return: Nombre de lignes écrites dans le fichier inversé.
        """
        input_path: str = self.config.deduplicated_output_file
        output_path: str = self.config.inverted_output_file

        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Le fichier dédoublonné '{input_path}' est introuvable.")

        inverted_pairs: List[Tuple[str, str]] = []
        with open(input_path, mode="r", encoding="utf-8") as in_file:
            for raw_line in in_file:
                line: str = raw_line.rstrip("\r\n")
                if not line or self.config.separator not in line:
                    continue
                old_left, old_right = line.split(self.config.separator, 1)
                clean_left: str = old_right.strip()
                clean_right: str = old_left.strip()
                if clean_left and clean_right:
                    inverted_pairs.append((clean_left, clean_right))

        inverted_pairs.sort(key=self._sort_key)

        formatted_lines: List[str] = [
            f"{new_left}{self.config.separator}{new_right}\n"
            for new_left, new_right in inverted_pairs
        ]
        SharedCoreUtils.atomic_write_text(
            target_path=output_path,
            content="".join(formatted_lines),
            encoding="utf-8",
        )

        return len(inverted_pairs)
