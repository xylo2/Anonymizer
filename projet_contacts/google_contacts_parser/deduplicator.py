# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import os
import re
from typing import Dict, List, Tuple
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.text_utils import ContactTextUtils


class ContactsDeduplicator:
    """
    Lit systématiquement le fichier anonymisé, normalise les alias '+...' des adresses e-mail,
    supprime les doublons exacts ou équivalents et fusionne les valeurs distinctes partageant
    une même clé tout en préservant l'ordre d'apparition d'origine.
    """

    def __init__(self, config: ContactsConfig) -> None:
        """
        Initialise le dédoublonneur avec la configuration du projet.

        :param config: Instance de ContactsConfig contenant les chemins et séparateurs.
        """
        self.config: ContactsConfig = config

    def _split_merged_values(self, raw_right: str) -> List[str]:
        """
        Découpe la partie droite si elle contient déjà des valeurs fusionnées.

        :param raw_right: Partie droite de la ligne après le séparateur principal.
        :return: Liste des libellés individuels nettoyés.
        """
        sep_token: str = self.config.merge_separator.strip()
        if sep_token and sep_token in raw_right:
            return [part.strip() for part in raw_right.split(sep_token) if part.strip()]
        cleaned: str = raw_right.strip()
        return [cleaned] if cleaned else []

    def _normalize_key(self, raw_key: str) -> str:
        """
        Normalise la clé de gauche (supprime l'alias '+...' s'il s'agit d'une adresse e-mail).

        :param raw_key: Coordonnée brute située à gauche du séparateur.
        :return: Clé canonique normalisée.
        """
        cleaned: str = raw_key.strip()
        if "@" in cleaned:
            cleaned = ContactTextUtils.normalize_email_alias(cleaned)
            if self.config.lowercase_emails:
                cleaned = cleaned.lower()
        return cleaned

    def _compute_value_signature(self, label: str) -> Tuple[str, ...]:
        """
        Calcule une signature canonique triée des prénoms et initiales d'un libellé
        afin de détecter deux variantes d'une même personne ou d'un même couple.

        :param label: Libellé anonymisé complet (avec éventuel suffixe entre parenthèses).
        :return: Tuple trié des jetons normalisés représentant l'identité.
        """
        base_part, _, _ = ContactTextUtils.clean_display_name(label)
        raw_tokens: List[str] = [t for t in re.split(r"[\s\.\-&]+", base_part) if t]
        meaningful: List[str] = []
        for tok in raw_tokens:
            norm_tok: str = ContactTextUtils.normalize_text(tok)
            if norm_tok and norm_tok not in {"et"}:
                meaningful.append(norm_tok)
        if not meaningful:
            return (ContactTextUtils.normalize_text(label),)
        return tuple(sorted(meaningful))
    def _is_better_variant(self, candidate: str, existing: str) -> bool:
        """
        Détermine si un libellé candidat est plus lisible qu'un libellé équivalent déjà retenu
        (privilégie la forme explicite avec 'et'/'&' plutôt qu'une fusion par tiret).

        :param candidate: Nouveau libellé équivalent rencontré.
        :param existing: Libellé déjà mémorisé pour la même signature.
        :return: True si le candidat doit remplacer l'existant.
        """
        cand_has_conj: bool = bool(re.search(r"\b(?:et|&)\b", candidate, flags=re.IGNORECASE))
        exist_has_conj: bool = bool(re.search(r"\b(?:et|&)\b", existing, flags=re.IGNORECASE))
        if cand_has_conj and not exist_has_conj:
            return True
        return False

    def process(self) -> Tuple[int, int, int]:
        """
        Lit le fichier anonymisé, dédoublonne les lignes exactes ou équivalentes,
        fusionne les clés communes distinctes et écrit le résultat sans modifier l'ordre.

        :return: Tuple (lignes_lues, lignes_écrites, clés_fusionnées).
        """
        input_path: str = self.config.anonymized_output_file
        output_path: str = self.config.deduplicated_output_file

        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Le fichier anonymisé '{input_path}' est introuvable.")

        grouped_entries: Dict[str, List[str]] = {}
        grouped_signatures: Dict[str, Dict[Tuple[str, ...], int]] = {}
        raw_line_count: int = 0

        with open(input_path, mode="r", encoding="utf-8") as in_file:
            for raw_line in in_file:
                line: str = raw_line.rstrip("\r\n")
                if not line or self.config.separator not in line:
                    continue
                raw_line_count += 1
                left_key, raw_right = line.split(self.config.separator, 1)
                clean_key: str = self._normalize_key(left_key)
                values: List[str] = self._split_merged_values(raw_right)

                if clean_key not in grouped_entries:
                    grouped_entries[clean_key] = []
                    grouped_signatures[clean_key] = {}

                for val in values:
                    sig: Tuple[str, ...] = self._compute_value_signature(val)
                    sig_map: Dict[Tuple[str, ...], int] = grouped_signatures[clean_key]
                    if sig not in sig_map:
                        sig_map[sig] = len(grouped_entries[clean_key])
                        grouped_entries[clean_key].append(val)
                    else:
                        existing_idx: int = sig_map[sig]
                        if self._is_better_variant(val, grouped_entries[clean_key][existing_idx]):
                            grouped_entries[clean_key][existing_idx] = val

        merged_keys_count: int = sum(1 for vals in grouped_entries.values() if len(vals) > 1)
        output_dir: str = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, mode="w", encoding="utf-8", newline="\n") as out_file:
            for key, values in grouped_entries.items():
                merged_right: str = self.config.merge_separator.join(values)
                out_file.write(f"{key}{self.config.separator}{merged_right}\n")

        return raw_line_count, len(grouped_entries), merged_keys_count
