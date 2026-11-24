# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
from typing import Dict, List, Optional, Set, Tuple
from doc_anonymizer.text_utils import DocumentTextUtils


class ContactCatalogMerger:
    """
    Fusionne et dédoublonne dans output_contacts/contacts.txt :
    - les contacts principaux extraits des CSV (contacts.txt)
    - les participants découverts dans les chats (discovered_chat_contacts.txt)
    - les adresses/contacts découverts dans les e-mails (discovered_email_contacts.txt)
    avec résolution automatique des collisions d'alias (Prénom N. -> Prénom Nu. -> Prénom Nu-2).
    """

    def __init__(
        self,
        contacts_file: str,
        discovered_chats_file: str = "",
        discovered_emails_file: str = "",
        known_first_names: Optional[Set[str]] = None,
    ) -> None:
        self.contacts_file: str = contacts_file
        self.discovered_chats_file: str = discovered_chats_file
        self.discovered_emails_file: str = discovered_emails_file
        self.known_first_names: Set[str] = known_first_names or set()

    @staticmethod
    def _load_pairs(file_path: str) -> List[Tuple[str, str]]:
        """Lit un fichier 'Identifiant = Alias' en ignorant les commentaires et lignes vides."""
        pairs: List[Tuple[str, str]] = []
        if not file_path or not os.path.isfile(file_path):
            return pairs
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f_in:
                for raw_line in f_in:
                    line: str = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    left, right = line.split("=", 1)
                    target, alias, _ = DocumentTextUtils.resolve_contact_pair(left, right)
                    if target and alias:
                        pairs.append((target, alias))
        except OSError:
            pass
        return pairs

    def _build_unique_person_alias(
        self,
        raw_name: str,
        suggested_alias: str,
        used_aliases: Set[str],
    ) -> str:
        """
        Génère un alias 'Prénom N.' sans collision avec les alias déjà attribués
        (passe à 'Prénom Nu.' puis 'Prénom Nu-2' en cas d'homonyme).
        """
        tokens: List[str] = [t for t in re.split(r"[\s_]+", raw_name.strip()) if t]
        if len(tokens) < 2 or "@" in raw_name or any(ch.isdigit() for ch in raw_name):
            return suggested_alias

        first_tok: str = next(iter(tokens))
        last_tok: str = tokens[-1]
        norm_first: str = DocumentTextUtils.normalize_word(first_tok)
        if self.known_first_names and norm_first not in self.known_first_names:
            return suggested_alias

        clean_last: str = re.sub(r"[^A-Za-zÀ-ÿ]", "", last_tok)
        if not clean_last:
            return suggested_alias

        first_cap: str = first_tok[:1].upper() + first_tok[1:]
        cand1: str = f"{first_cap} {clean_last[:1].upper()}."
        if cand1 not in used_aliases:
            return cand1

        if len(clean_last) >= 2:
            cand2: str = f"{first_cap} {clean_last[:1].upper()}{clean_last[1:2].lower()}."
            if cand2 not in used_aliases:
                return cand2

        idx: int = 2
        base_stem: str = (
            f"{first_cap} {clean_last[:1].upper()}{clean_last[1:2].lower()}"
            if len(clean_last) >= 2
            else f"{first_cap} {clean_last[:1].upper()}"
        )
        while True:
            cand_n: str = f"{base_stem}-{idx}"
            if cand_n not in used_aliases:
                return cand_n
            idx += 1

    def merge_all(self) -> Tuple[int, int]:
        """
        Fusionne les contacts découverts dans contacts.txt et retourne
        (nombre_ajouts, nombre_total_unifie).
        """
        if not self.contacts_file:
            return 0, 0

        base_pairs: List[Tuple[str, str]] = self._load_pairs(self.contacts_file)
        merged_map: Dict[str, Tuple[str, str]] = {}
        used_aliases: Set[str] = set()

        for target, alias in base_pairs:
            norm_key: str = (
                DocumentTextUtils.normalize_identifier(target)
                if "@" in target
                else DocumentTextUtils.normalize_word(target)
            )
            if not norm_key:
                continue
            merged_map[norm_key] = (target, alias)
            used_aliases.add(alias)

        added_count: int = 0
        for extra_file in (self.discovered_chats_file, self.discovered_emails_file):
            for target, alias in self._load_pairs(extra_file):
                norm_key = (
                    DocumentTextUtils.normalize_identifier(target)
                    if "@" in target
                    else DocumentTextUtils.normalize_word(target)
                )
                if not norm_key or norm_key in merged_map:
                    continue
                final_alias: str = (
                    alias
                    if alias.startswith(("Contact_", "EMAIL_", "TEL_"))
                    else self._build_unique_person_alias(target, alias, used_aliases)
                )
                merged_map[norm_key] = (target, final_alias)
                used_aliases.add(final_alias)
                added_count += 1

        if added_count > 0:
            os.makedirs(os.path.dirname(self.contacts_file), exist_ok=True)
            sorted_entries: List[Tuple[str, str]] = sorted(
                merged_map.values(), key=lambda item: next(iter(item)).lower()
            )
            with open(self.contacts_file, "w", encoding="utf-8") as f_out:
                f_out.write("# CATALOGUE UNIFIÉ DES CONTACTS (CSV + CHATS + E-MAILS)\n")
                for tgt, als in sorted_entries:
                    f_out.write(f"{tgt} = {als}\n")

        return added_count, len(merged_map)
