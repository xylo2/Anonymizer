# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
from typing import Dict, List, Pattern, Set, Tuple
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class ContactRulesLoader:
    """
    Prépare contacts.txt, déduit les noms complets associés aux alias et
    compile les motifs de remplacement pour l'anonymisation.
    """

    ACCENT_MAP: Dict[str, str] = {
        "a": "[aàâä]", "e": "[eéèêë]", "i": "[iîï]",
        "o": "[oôö]", "u": "[uùûü]", "c": "[cç]", "y": "[yÿ]",
    }

    TITLE_PREFIXES: Tuple[str, ...] = (
        "M.", "M", "Monsieur", "Mme", "Madame", "Mlle",
        "Dr", "Docteur", "Pr", "Professeur", "Me", "Maître",
    )

    def __init__(self, config: PipelineConfig) -> None:
        self.config: PipelineConfig = config
        self.contacts_id: Dict[str, str] = {}
        self.compiled_rules: List[Tuple[Pattern[str], str]] = []
        self.location_rules: List[Pattern[str]] = []
        self.alias_words: Set[str] = set()
        self.full_targets: Set[str] = set()

    def is_first_name(self, word: str) -> bool:
        """Vérifie si un mot figure dans le référentiel des prénoms."""
        norm: str = DocumentTextUtils.normalize_word(word)
        if norm in self.config.known_first_names:
            return True
        if "-" in norm:
            parts: List[str] = [p for p in norm.split("-") if p]
            return bool(parts) and all(
                p in self.config.known_first_names for p in parts
            )
        return False

    @classmethod
    def build_regex(
        cls, term: str, whole_word: bool = True
    ) -> Pattern[str]:
        """Compile une regex insensible à la casse et aux accents."""
        stripped: str = DocumentTextUtils.strip_accents(term).lower()
        pat: str = "".join(
            cls.ACCENT_MAP.get(c, re.escape(c)) for c in stripped
        )
        if whole_word:
            pat = rf"(?<!\w){pat}(?!\w)"
        return re.compile(pat, re.IGNORECASE)

    def _add_name_variants(
        self, full_name: str, alias: str, keywords: Dict[str, str]
    ) -> None:
        """Ajoute Prénom Nom, Nom Prénom et Titre Nom au dictionnaire."""
        keywords[full_name] = alias
        self.full_targets.add(DocumentTextUtils.normalize_word(full_name))
        tokens: List[str] = full_name.split()
        if len(tokens) != 2:
            return
        first_is_fn: bool = self.is_first_name(tokens[0])
        second_is_fn: bool = self.is_first_name(tokens[1])
        if not (first_is_fn or second_is_fn):
            return

        inv: str = f"{tokens[1]} {tokens[0]}"
        keywords.setdefault(inv, alias)
        self.full_targets.add(DocumentTextUtils.normalize_word(inv))

        last_tok: str = tokens[1] if first_is_fn else tokens[0]
        norm_last: str = DocumentTextUtils.normalize_word(last_tok)
        if (
            len(norm_last) >= 3
            and not self.is_first_name(last_tok)
            and norm_last not in self.config.excluded_words
            and norm_last not in self.config.masked_locations
        ):
            for prefix in self.TITLE_PREFIXES:
                keywords.setdefault(f"{prefix} {last_tok}", alias)

    def _load_paired_names(self, keywords: Dict[str, str]) -> int:
        """Croise contacts_indexes.txt et contacts_anonymises.txt."""
        idx_path: str = self.config.indexed_contacts_file
        ano_path: str = self.config.anonymized_contacts_file
        if not (os.path.exists(idx_path) and os.path.exists(ano_path)):
            return 0

        coord_to_full: Dict[str, str] = {}
        with open(idx_path, "r", encoding="utf-8") as f_idx:
            for line in f_idx:
                s: str = line.strip()
                if s and not s.startswith("#") and "=" in s:
                    left, right = s.split("=", 1)
                    coord_to_full[
                        DocumentTextUtils.normalize_identifier(left)
                    ] = right.strip()

        added: int = 0
        with open(ano_path, "r", encoding="utf-8") as f_ano:
            for line in f_ano:
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                left, right = s.split("=", 1)
                coord: str = DocumentTextUtils.normalize_identifier(left)
                full_raw: str = coord_to_full.get(coord, "")
                if not full_raw:
                    continue
                clean_full: str = re.sub(r"\s*\([^)]*\)", "", full_raw).strip()
                clean_alias: str = re.sub(r"\s*\([^)]*\)", "", right).strip()
                if (
                    clean_full
                    and clean_alias
                    and DocumentTextUtils.normalize_word(clean_full)
                    != DocumentTextUtils.normalize_word(clean_alias)
                ):
                    if clean_full not in keywords:
                        added += 1
                    self._add_name_variants(clean_full, clean_alias, keywords)
                    for w in re.split(r"[\s_'-]+", clean_alias):
                        if w:
                            self.alias_words.add(
                                DocumentTextUtils.normalize_word(w)
                            )
        return added

    def load_all(self) -> bool:
        """Nettoie contacts.txt et compile toutes les règles."""
        contacts_path: str = self.config.contacts_file
        if not os.path.exists(contacts_path):
            print(f"Erreur : '{contacts_path}' introuvable.", flush=True)
            return False

        print(f"1. Lecture et tri de '{contacts_path}'...", flush=True)
        for tok in re.split(r"[\s_'-]+", self.config.main_character_name):
            if tok:
                self.alias_words.add(DocumentTextUtils.normalize_word(tok))

        comments: List[str] = []
        unique_lines: Dict[str, Tuple[str, str]] = {}
        keywords: Dict[str, str] = {}
        line_count: int = 0

        with open(contacts_path, "r", encoding="utf-8") as f:
            for raw in f:
                line: str = raw.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    if line not in comments:
                        comments.append(line)
                    continue
                line_count += 1
                for sep in ("=", ";", ","):
                    if sep not in line:
                        continue
                    left, right = line.split(sep, 1)
                    target, alias, alias_left = (
                        DocumentTextUtils.resolve_contact_pair(left, right)
                    )
                    if target and alias:
                        norm_t: str = DocumentTextUtils.normalize_word(target)
                        unique_lines[norm_t] = (
                            (alias, target) if alias_left else (target, alias)
                        )
                        self.full_targets.add(norm_t)
                        if DocumentTextUtils.is_contact_identifier(target):
                            self.contacts_id[
                                DocumentTextUtils.normalize_identifier(target)
                            ] = alias
                        else:
                            self._add_name_variants(target, alias, keywords)
                        for w in re.split(r"[\s_'-]+", alias):
                            if w:
                                self.alias_words.add(
                                    DocumentTextUtils.normalize_word(w)
                                )
                    break

        sorted_entries: List[Tuple[str, str]] = sorted(
            unique_lines.values(),
            key=lambda item: (
                DocumentTextUtils.normalize_word(item[0]),
                item[0].lower(),
                item[1].lower(),
            ),
        )
        with open(contacts_path, "w", encoding="utf-8") as f_out:
            for com in comments:
                f_out.write(f"{com}\n")
            if comments:
                f_out.write("\n")
            for left_col, right_col in sorted_entries:
                f_out.write(f"{left_col} = {right_col}\n")

        paired_added: int = self._load_paired_names(keywords)
        removed: int = line_count - len(sorted_entries)
        print(
            f"   -> {len(sorted_entries)} règle(s) unique(s)"
            f" ({removed} doublon(s)), {paired_added} nom(s) complet(s).",
            flush=True,
        )

        self.compiled_rules = [
            (self.build_regex(term), keywords[term])
            for term in sorted(keywords.keys(), key=len, reverse=True)
        ]
        sorted_locs: List[str] = sorted(
            (loc for loc in self.config.masked_locations if len(loc) >= 3),
            key=len,
            reverse=True,
        )
        self.location_rules = [
            self.build_regex(loc, whole_word=True) for loc in sorted_locs
        ]
        return True
