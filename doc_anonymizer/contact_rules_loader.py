# Commandes pip à exécuter : Aucune dépendance externe requise

from collections import defaultdict
import os
import re
from typing import Any, DefaultDict, Dict, List, Optional, Pattern, Set, Tuple
from common.core_utils import SharedCoreUtils
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class ContactRulesLoader:
    """
    Charge contacts.txt, contacts_emails_decouverts.txt, contacts_manuels.txt
    et contacts_indexes.txt, puis compile des regex optimisées (Trie) pour
    éliminer tous les noms de famille, variantes OCR et lieux.
    """

    ACCENT_MAP: Dict[str, str] = {
        "a": "[aàâä]", "e": "[eéèêë]", "i": "[iîï]",
        "o": "[oôö]", "u": "[uùûü]", "c": "[cç]", "y": "[yÿ]",
    }

    TITLE_PREFIXES: Tuple[str, ...] = (
        "M.", "M", "Monsieur", "Mme", "Madame", "Mlle", "Mademoiselle",
        "Dr", "Docteur", "Pr", "Professeur", "Me", "Maître", "Maitre",
        "Famille", "Consorts", "Epoux", "Époux",
    )

    PARTICLES: Tuple[str, ...] = (
        "de", "du", "des", "d", "le", "la", "les",
        "van", "von", "der", "den", "ten", "ter",
        "ben", "el", "al", "ait", "ou", "ould", "dos", "da", "di",
    )

    def __init__(self, config: PipelineConfig, manual_only: bool = False) -> None:
        """
        Initialise le chargeur de règles et les structures de recherche rapide.

        :param config: Instance de PipelineConfig.
        :param manual_only: Si True, charge uniquement contacts_manuels.txt.
        """
        self.config: PipelineConfig = config
        self.manual_only: bool = manual_only
        self.contacts_id: Dict[str, str] = {}
        self.combined_keyword_pattern: Optional[Pattern[str]] = None
        self.normalized_keyword_map: Dict[str, str] = {}
        self.combined_glued_pattern: Optional[Pattern[str]] = None
        self.normalized_glued_map: Dict[str, str] = {}
        self.combined_location_pattern: Optional[Pattern[str]] = None
        self.alias_words: Set[str] = set()
        self.full_targets: Set[str] = set()
        self.last_name_to_aliases: DefaultDict[str, Set[str]] = defaultdict(set)
        self.last_name_display: Dict[str, str] = {}

    def is_first_name(self, word: str) -> bool:
        """
        Vérifie si un mot figure dans le référentiel des prénoms.

        :param word: Mot brut à tester.
        :return: True si le mot est un prénom connu.
        """
        norm: str = DocumentTextUtils.normalize_word(word)
        if norm in self.config.known_first_names:
            return True
        if "-" in norm:
            parts: List[str] = [p for p in norm.split("-") if p]
            return bool(parts) and all(p in self.config.known_first_names for p in parts)
        return False

    @classmethod
    def _render_trie_body(cls, terms: List[str]) -> str:
        """
        Construit le corps d'une regex en arbre préfixe (Trie) sans frontières.

        :param terms: Liste de termes normalisés sans accents.
        :return: Chaîne de motif regex compilable.
        """
        trie: Dict[str, Any] = {}
        for term in sorted(set(terms), key=len, reverse=True):
            if not term:
                continue
            node: Dict[str, Any] = trie
            for ch in term:
                node = node.setdefault(ch, {})
            node[""] = True
        def _render_node(node: Dict[str, Any]) -> str:
            if "" in node and len(node) == 1:
                return ""
            alternatives: List[str] = []
            for ch in sorted(k for k in node.keys() if k != ""):
                char_pat: str = cls.ACCENT_MAP.get(ch, re.escape(ch))
                sub_pat: str = _render_node(node.get(ch, {}))
                alternatives.append(f"{char_pat}{sub_pat}")
            has_end: bool = "" in node
            joined: str = next(iter(alternatives)) if len(alternatives) == 1 else f"(?:{'|'.join(alternatives)})"
            return f"(?:{joined})?" if has_end else joined

        return _render_node(trie)

    @classmethod
    def _build_trie_regex(cls, terms: List[str], allow_suffix_letters: bool = False) -> Optional[Pattern[str]]:
        """
        Compile une expression régulière unique optimisée par arbre préfixe (Trie).

        :param terms: Liste de termes normalisés (minuscules, sans accents).
        :param allow_suffix_letters: Autorise une suite alphabétique collée.
        :return: Pattern compilé ou None si la liste est vide.
        """
        if not terms:
            return None
        body: str = cls._render_trie_body(terms)
        if not body:
            return None
        right_boundary: str = r"(?=[a-zàâäéèêëîïôöùûüç]|\b)" if allow_suffix_letters else r"(?!\w)"
        return re.compile(rf"(?<!\w){body}{right_boundary}", re.IGNORECASE)

    def lookup_keyword_alias(self, matched_text: str) -> str:
        """
        Retrouve l'alias associé à une correspondance standard trouvée par le Trie.

        :param matched_text: Segment exact capturé dans le document.
        :return: Alias de remplacement correspondant.
        """
        norm_match: str = DocumentTextUtils.strip_accents(matched_text).lower()
        return self.normalized_keyword_map.get(norm_match, matched_text)

    def lookup_glued_alias(self, matched_text: str) -> str:
        """
        Retrouve l'alias associé à une variante collée (PrénomNom / NomPrénom).

        :param matched_text: Segment exact capturé dans le document.
        :return: Alias de remplacement correspondant.
        """
        norm_match: str = DocumentTextUtils.strip_accents(matched_text).lower()
        return self.normalized_glued_map.get(norm_match, matched_text)

    @staticmethod
    def _split_camel_case_target(raw_name: str) -> str:
        """
        Sépare un nom collé en CamelCase ou majuscules (ex: 'AlexandraVIDAL' -> 'Alexandra VIDAL').

        :param raw_name: Chaîne brute candidate.
        :return: Chaîne découpée si applicable.
        """
        if " " in raw_name.strip():
            return raw_name.strip()
        split_camel: str = re.sub(
            r"([a-zéèêëàâäîïôöùûüç])([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]{2,})",
            r"\1 \2",
            raw_name.strip(),
        )
        return split_camel

    def _extract_first_and_last(self, tokens: List[str]) -> Optional[Tuple[str, str]]:
        """
        Identifie le prénom et le nom de famille pour des noms à 2 mots ou plus,
        en gérant les particules et les prénoms composés.

        :param tokens: Liste des mots composant le nom complet.
        :return: Tuple (prénom, nom_de_famille) ou None si indéterminé.
        """
        if len(tokens) == 2:
            tok1, tok2 = tokens
            f1: bool = self.is_first_name(tok1)
            f2: bool = self.is_first_name(tok2)
            if f1 and not f2:
                return tok1, tok2
            if f2 and not f1:
                return tok2, tok1
            if f1 and f2:
                return tok1, tok2
            return None

        if len(tokens) > 2:
            if re.search(r"\b(?:et|&)\b", " ".join(tokens), flags=re.IGNORECASE):
                return None
            first_tok: str = next(iter(tokens))
            last_tok: str = tokens[-1]
            if self.is_first_name(first_tok):
                return first_tok, " ".join(tokens[1:])
            if self.is_first_name(last_tok):
                return last_tok, " ".join(tokens[:-1])
        return None
    def _register_single_surname(self, last_tok: str, alias: str, keywords: Dict[str, str]) -> None:
        """
        Enregistre les règles de masquage pour un nom de famille isolé et ses variantes OCR.

        :param last_tok: Nom de famille brut (ex: 'Sobréro' ou 'De La Tour').
        :param alias: Alias cible (ex: 'Aurélie S.').
        :param keywords: Dictionnaire cumulatif terme -> alias.
        """
        clean_last: str = last_tok.strip()
        norm_last: str = DocumentTextUtils.normalize_word(clean_last)
        if (
            len(norm_last) < 3
            or norm_last in self.config.excluded_words
            or norm_last in self.config.masked_locations
        ):
            return

        self.last_name_to_aliases[norm_last].add(alias)
        self.last_name_display.setdefault(norm_last, clean_last)
        for prefix in self.TITLE_PREFIXES:
            keywords.setdefault(f"{prefix} {clean_last}", alias)

        parts: List[str] = [p for p in re.split(r"[\s'-]+", clean_last) if p]
        core_parts: List[str] = [
            p for p in parts if DocumentTextUtils.normalize_word(p) not in self.PARTICLES
        ]
        if not core_parts:
            return

        first_core: str = next(iter(core_parts))
        last_initial: str = f"{first_core.strip()[:1].upper()}."
        if len(norm_last) >= 4 and not self.is_first_name(clean_last):
            keywords.setdefault(clean_last, last_initial)

        for part in core_parts:
            norm_p: str = DocumentTextUtils.normalize_word(part)
            if (
                len(norm_p) >= 4
                and not self.is_first_name(part)
                and norm_p not in self.config.excluded_words
                and norm_p not in self.config.masked_locations
            ):
                p_init: str = f"{part.strip()[:1].upper()}."
                keywords.setdefault(part, p_init)
                for prefix in self.TITLE_PREFIXES:
                    keywords.setdefault(f"{prefix} {part}", alias)

                if len(norm_p) >= 6:
                    for idx in range(len(norm_p)):
                        for ch in "abcdefghijklmnopqrstuvwxyz":
                            cand: str = f"{norm_p[:idx]}{ch}{norm_p[idx + 1:]}"
                            if (
                                cand != norm_p
                                and cand not in self.config.excluded_words
                                and cand not in self.config.known_first_names
                                and cand not in self.config.masked_locations
                            ):
                                keywords.setdefault(cand, p_init)

    def _add_name_variants(
        self, full_name: str, alias: str, keywords: Dict[str, str], glued_keywords: Dict[str, str]
    ) -> None:
        """
        Ajoute Prénom Nom, Nom Prénom, Titre Nom, le Nom seul et les variantes collées.

        :param full_name: Nom complet de la personne.
        :param alias: Alias anonymisé cible.
        :param keywords: Dictionnaire cumulatif terme -> alias.
        :param glued_keywords: Dictionnaire cumulatif terme_collé -> alias.
        """
        cleaned_full: str = self._split_camel_case_target(full_name)
        keywords[cleaned_full] = alias
        keywords.setdefault(full_name, alias)
        self.full_targets.add(DocumentTextUtils.normalize_word(cleaned_full))

        tokens: List[str] = [t for t in cleaned_full.split() if t]
        if len(tokens) == 1:
            self._register_single_surname(next(iter(tokens)), alias, keywords)
            return

        extracted: Optional[Tuple[str, str]] = self._extract_first_and_last(tokens)
        if not extracted:
            return

        first_tok, last_tok = extracted
        inv: str = f"{last_tok} {first_tok}"
        keywords.setdefault(inv, alias)
        self.full_targets.add(DocumentTextUtils.normalize_word(inv))

        self._register_single_surname(last_tok, alias, keywords)

        norm_first: str = DocumentTextUtils.normalize_word(first_tok)
        compact_last: str = SharedCoreUtils.normalize_compact_text(last_tok)
        if len(norm_first) >= 3 and len(compact_last) >= 4:
            glued_keywords.setdefault(f"{first_tok}{compact_last}", alias)
            glued_keywords.setdefault(f"{compact_last}{first_tok}", alias)
    def _extract_surname_from_email_identifier(
        self, email: str, alias: str, keywords: Dict[str, str]
    ) -> None:
        """
        Déduit un nom de famille depuis une adresse 'prenom.nom@domaine' afin de
        masquer ce nom de famille même s'il est absent du libellé du contact.

        :param email: Adresse e-mail normalisée.
        :param alias: Alias cible associé à l'e-mail.
        :param keywords: Dictionnaire cumulatif terme -> alias.
        """
        if "@" not in email:
            return
        local_part, _ = email.split("@", 1)
        tokens: List[str] = [t for t in re.split(r"[\.\-_]+", local_part) if t]
        if len(tokens) != 2 or any(ch.isdigit() for ch in local_part):
            return
        t1, t2 = tokens
        if self.is_first_name(t1) and not self.is_first_name(t2) and len(t2) >= 4:
            self._register_single_surname(t2.capitalize(), alias, keywords)
        elif self.is_first_name(t2) and not self.is_first_name(t1) and len(t1) >= 4:
            self._register_single_surname(t1.capitalize(), alias, keywords)

    def _ensure_manual_contacts_file(self) -> None:
        """
        Crée le fichier contacts_manuels.txt avec un en-tête explicatif s'il est absent.
        """
        manual_path: str = self.config.manual_contacts_file
        if os.path.exists(manual_path):
            return
        header: str = (
            "# RÈGLES D'ANONYMISATION MANUELLES\n"
            "# Ce fichier n'est jamais écrasé par lancer_contacts.py.\n"
            "# Ajoutez ici les noms issus de audit_noms_residuels.txt :\n"
            "# Format : Prénom Nom = Alias\n\n"
        )
        SharedCoreUtils.atomic_write_text(manual_path, header)

    def _parse_rules_file(
        self, file_path: str, keywords: Dict[str, str], glued_keywords: Dict[str, str]
    ) -> Tuple[int, int]:
        """
        Lit et dédoublonne en mémoire un fichier de règles 'Cible = Alias'.

        :param file_path: Chemin vers le fichier de règles à charger.
        :param keywords: Dictionnaire cumulatif terme -> alias.
        :param glued_keywords: Dictionnaire cumulatif terme_collé -> alias.
        :return: Tuple (nombre_règles_uniques, nombre_doublons_ignorés).
        """
        if not os.path.exists(file_path):
            return 0, 0
        seen_targets: Set[str] = set()
        line_count: int = 0
        with open(file_path, "r", encoding="utf-8") as f_in:
            for raw in f_in:
                line: str = raw.strip()
                if not line or line.startswith("#"):
                    continue
                line_count += 1
                for sep in ("=", ";", ","):
                    if sep not in line:
                        continue
                    left, right = line.split(sep, 1)
                    target, alias, _ = DocumentTextUtils.resolve_contact_pair(left, right)
                    if target and alias:
                        norm_t: str = DocumentTextUtils.normalize_word(target)
                        seen_targets.add(norm_t)
                        self.full_targets.add(norm_t)
                        if DocumentTextUtils.is_contact_identifier(target):
                            norm_id: str = DocumentTextUtils.normalize_identifier(target)
                            self.contacts_id[norm_id] = alias
                            self._extract_surname_from_email_identifier(norm_id, alias, keywords)
                        else:
                            self._add_name_variants(target, alias, keywords, glued_keywords)
                        for w in re.split(r"[\s_'-]+", alias):
                            if w:
                                self.alias_words.add(DocumentTextUtils.normalize_word(w))
                    break
        return len(seen_targets), line_count - len(seen_targets)
    def _register_paired_entry(
        self, full_raw: str, alias_raw: str, keywords: Dict[str, str], glued_keywords: Dict[str, str]
    ) -> int:
        """
        Enregistre une correspondance nom complet -> alias nettoyée de toute parenthèse.

        :param full_raw: Nom complet brut issu de contacts_indexes.txt.
        :param alias_raw: Alias brut issu de contacts_anonymises.txt.
        :param keywords: Dictionnaire cumulatif terme -> alias.
        :param glued_keywords: Dictionnaire cumulatif terme_collé -> alias.
        :return: 1 si un nouveau nom complet a été ajouté, sinon 0.
        """
        clean_full: str = re.sub(r"\s*\([^)]*\)", "", full_raw).strip()
        clean_alias: str = re.sub(r"\s*\([^)]*\)", "", alias_raw).strip()
        if not clean_full or not clean_alias:
            return 0
        if DocumentTextUtils.normalize_word(clean_full) == DocumentTextUtils.normalize_word(clean_alias):
            return 0

        is_new: int = 1 if clean_full not in keywords else 0
        self._add_name_variants(clean_full, clean_alias, keywords, glued_keywords)
        for w in re.split(r"[\s_'-]+", clean_alias):
            if w:
                self.alias_words.add(DocumentTextUtils.normalize_word(w))
        return is_new

    def _load_paired_names(self, keywords: Dict[str, str], glued_keywords: Dict[str, str]) -> int:
        """
        Croise contacts_indexes.txt et contacts_anonymises.txt ligne par ligne
        pour éviter toute perte sur les coordonnées partagées.

        :param keywords: Dictionnaire cumulatif terme -> alias.
        :param glued_keywords: Dictionnaire cumulatif terme_collé -> alias.
        :return: Nombre de nouveaux noms complets ajoutés.
        """
        idx_path: str = self.config.indexed_contacts_file
        ano_path: str = self.config.anonymized_contacts_file
        if not (os.path.exists(idx_path) and os.path.exists(ano_path)):
            return 0

        idx_entries: List[Tuple[str, str]] = []
        with open(idx_path, "r", encoding="utf-8") as f_idx:
            for line in f_idx:
                s: str = line.strip()
                if s and not s.startswith("#") and "=" in s:
                    left, right = s.split("=", 1)
                    idx_entries.append((DocumentTextUtils.normalize_identifier(left), right.strip()))

        ano_entries: List[Tuple[str, str]] = []
        with open(ano_path, "r", encoding="utf-8") as f_ano:
            for line in f_ano:
                s = line.strip()
                if s and not s.startswith("#") and "=" in s:
                    left, right = s.split("=", 1)
                    ano_entries.append((DocumentTextUtils.normalize_identifier(left), right.strip()))

        added: int = 0
        if len(idx_entries) == len(ano_entries):
            for (coord_i, full_raw), (coord_a, alias_raw) in zip(idx_entries, ano_entries):
                if coord_i == coord_a:
                    added += self._register_paired_entry(full_raw, alias_raw, keywords, glued_keywords)
            return added

        coord_to_fulls: DefaultDict[str, List[str]] = defaultdict(list)
        for coord, full_raw in idx_entries:
            if full_raw not in coord_to_fulls[coord]:
                coord_to_fulls[coord].append(full_raw)

        for coord, alias_raw in ano_entries:
            for full_raw in coord_to_fulls.get(coord, []):
                added += self._register_paired_entry(full_raw, alias_raw, keywords, glued_keywords)
        return added
    def load_all(self) -> bool:
        """
        Charge les règles de contacts en lecture seule et compile les Tries uniques.

        :return: True si le chargement a réussi, False sinon.
        """
        self.contacts_id.clear()
        self.alias_words.clear()
        self.full_targets.clear()
        self.last_name_to_aliases.clear()
        self.last_name_display.clear()
        self._ensure_manual_contacts_file()
        for tok in re.split(r"[\s_'-]+", self.config.main_character_name):
            if tok:
                self.alias_words.add(DocumentTextUtils.normalize_word(tok))

        keywords: Dict[str, str] = {}
        glued_keywords: Dict[str, str] = {}
        if self.manual_only:
            print(f"1. Lecture EXCLUSIVE de '{self.config.manual_contacts_file}'...", flush=True)
            man_count, man_dup = self._parse_rules_file(self.config.manual_contacts_file, keywords, glued_keywords)
            auto_count = auto_dup = disc_count = paired_added = 0
        else:
            if not os.path.exists(self.config.contacts_file):
                print(f"Erreur : '{self.config.contacts_file}' introuvable.", flush=True)
                return False
            print("1. Lecture des règles de contacts (auto, découverts, manuels)...", flush=True)
            auto_count, auto_dup = self._parse_rules_file(self.config.contacts_file, keywords, glued_keywords)
            disc_count, _ = self._parse_rules_file(self.config.discovered_contacts_file, keywords, glued_keywords)
            man_count, man_dup = self._parse_rules_file(self.config.manual_contacts_file, keywords, glued_keywords)
            paired_added = self._load_paired_names(keywords, glued_keywords)

        self.normalized_keyword_map = {}
        for term in sorted(keywords.keys(), key=len, reverse=True):
            norm_k: str = DocumentTextUtils.strip_accents(term).lower()
            if norm_k:
                self.normalized_keyword_map.setdefault(norm_k, keywords[term])

        self.normalized_glued_map = {}
        for term in sorted(glued_keywords.keys(), key=len, reverse=True):
            norm_g: str = DocumentTextUtils.strip_accents(term).lower()
            if norm_g:
                self.normalized_glued_map.setdefault(norm_g, glued_keywords[term])

        self.combined_keyword_pattern = self._build_trie_regex(list(self.normalized_keyword_map.keys()))
        self.combined_glued_pattern = self._build_trie_regex(
            list(self.normalized_glued_map.keys()), allow_suffix_letters=True
        )
        norm_locs: List[str] = sorted(
            {DocumentTextUtils.strip_accents(loc).lower() for loc in self.config.masked_locations if len(loc.strip()) >= 3},
            key=len,
            reverse=True,
        )
        self.combined_location_pattern = self._build_trie_regex(norm_locs)
        print(
            f"   -> {auto_count} auto ({auto_dup} doublon(s)), {disc_count} découvert(s), "
            f"{man_count} manuel(s) ({man_dup} doublon(s)), {paired_added} nom(s) complet(s), "
            f"{len(self.normalized_keyword_map)} motif(s) standard(s) + {len(self.normalized_glued_map)} collé(s) en Trie.",
            flush=True,
        )
        return True
