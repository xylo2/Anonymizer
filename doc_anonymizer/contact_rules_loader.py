# Commandes pip à exécuter : Aucune dépendance externe requise

from collections import defaultdict
import os
import re
from typing import DefaultDict, Dict, List, Optional, Pattern, Set
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class ContactRulesLoader:
    """
    Charge et unifie les règles d'anonymisation depuis les index CSV,
    les e-mails découverts, les noms de famille extraits et contacts_manuels.txt,
    puis compile les expressions régulières optimisées (Trie OCR).
    """

    COMMON_WORD_COLLISIONS = frozenset({
        "ami", "amis", "ange", "aube", "autre", "autres", "avec", "avis",
        "bac", "bain", "banc", "bas", "beau", "belle", "bien", "blanc",
        "bleu", "bois", "bon", "bonne", "bord", "bout", "brun", "bus",
        "camp", "car", "carte", "cas", "cave", "champ", "chat", "chaud",
        "chef", "cher", "ciel", "clair", "clef", "clos", "code", "coin",
        "col", "compte", "coq", "corps", "cote", "coup", "cour", "cours",
        "croix", "cuisine", "dame", "date", "debut", "dent", "deux",
        "dieu", "don", "doux", "droit", "eau", "ecole", "effet", "enfant",
        "envie", "etat", "ete", "face", "faim", "fait", "femme", "fer",
        "fete", "feu", "fil", "fille", "fils", "fin", "fleur", "foi",
        "fois", "fond", "font", "force", "foret", "fort", "frais", "franc",
        "froid", "front", "fruit", "gare", "gens", "glace", "grand", "gris",
        "gros", "haut", "heure", "hiver", "homme", "idee", "image", "jeu",
        "joie", "jour", "juge", "juste", "lac", "lait", "large", "laver",
        "libre", "lien", "lieu", "ligne", "lire", "lit", "livre", "loi",
        "long", "loup", "lune", "main", "maire", "maison", "mal", "maman",
        "marcher", "mari", "matin", "mer", "mere", "midi", "miel", "mille",
        "mine", "mode", "mois", "monde", "mont", "mort", "mot", "mur",
        "neige", "neuf", "nez", "noir", "nom", "nord", "note", "nuit",
        "oeil", "oeuvre", "oiseau", "ombre", "oncle", "or", "ordre", "ouest",
        "page", "pain", "paix", "papa", "parc", "parent", "part", "parti",
        "pas", "passe", "payer", "pays", "peau", "peine", "pere", "petit",
        "peur", "pied", "pierre", "place", "plan", "plein", "pluie", "plus",
        "poids", "point", "pont", "port", "porte", "poste", "pot", "pour",
        "pres", "pret", "prix", "proche", "projet", "propre", "puis",
        "quai", "quart", "raison", "rang", "recit", "regle", "reine",
        "repas", "reste", "reve", "rien", "rire", "rive", "robe", "roche",
        "roi", "role", "rond", "rose", "rouge", "route", "rue", "sable",
        "sac", "sage", "saint", "salle", "sang", "sans", "sante", "saut",
        "savoir", "scene", "sec", "sel", "sens", "sept", "seul", "siecle",
        "signe", "simple", "site", "soeur", "soin", "soir", "sol", "soleil",
        "somme", "son", "sort", "sou", "soupe", "source", "sous", "sud",
        "suite", "sujet", "sur", "table", "tache", "taille", "temps",
        "terre", "tete", "tiers", "titre", "toile", "toit", "ton", "tour",
        "tout", "train", "trait", "travail", "triste", "trop", "trou",
        "type", "usage", "val", "valeur", "vent", "verre", "vers", "vert",
        "vie", "vieux", "ville", "vin", "visage", "vite", "voie", "voix",
        "vol", "vue", "zone",
    })

    NON_PERSON_ALIAS_MARKERS = (
        "contact_", "service", "direction", "mairie", "cabinet", "agence",
        "association", "assurance", "banque", "mutuelle", "clinique",
        "hopital", "hôpital", "centre", "laboratoire", "pharmacie",
        "societe", "société", "entreprise", "ecole", "école", "college",
        "collège", "lycee", "lycée", "universite", "université", "caf",
        "cpam", "urssaf", "impots", "impôts", "tresor", "trésor",
        "prefecture", "préfecture", "ministere", "ministère", "tribunal",
        "police", "gendarmerie", "pompiers", "amazon", "leboncoin",
        "vinted", "paypal", "orange", "sfr", "free", "bouygues", "edf",
        "engie", "sncf", "ratp", "google", "microsoft", "apple", "eni",
        "acoss", "pole emploi", "pôle emploi", "france travail",
    )

    def __init__(
        self, config: PipelineConfig, manual_only: bool = False
    ) -> None:
        """Initialise les structures d'indexation des contacts."""
        self.config: PipelineConfig = config
        self.manual_only: bool = manual_only
        self.contacts_id: Dict[str, str] = {}
        self.keyword_to_alias: Dict[str, str] = {}
        self.case_sensitive_keywords: Dict[str, str] = {}
        self.glued_to_alias: Dict[str, str] = {}
        self.alias_words: Set[str] = set()
        self.protected_surnames: Set[str] = set()
        self.surname_to_alias: Dict[str, str] = {}
        self.last_name_to_aliases: DefaultDict[str, Set[str]] = defaultdict(set)
        self.last_name_display: Dict[str, str] = {}
        self.full_targets: Set[str] = set()
        self._normalized_first_names: Set[str] = set()

        self.combined_case_sensitive_pattern: Optional[Pattern[str]] = None
        self.combined_keyword_pattern: Optional[Pattern[str]] = None
        self.combined_glued_pattern: Optional[Pattern[str]] = None
        self.combined_location_pattern: Optional[Pattern[str]] = None

    @staticmethod
    def normalize_ocr_key(text: str) -> str:
        """Normalise une chaîne en absorbant les confusions fréquentes d'OCR."""
        norm: str = DocumentTextUtils.normalize_word(text)
        norm = (
            norm.replace("0", "o")
            .replace("1", "i")
            .replace("5", "s")
            .replace("8", "b")
        )
        return re.sub(r"[^a-z]", "", norm)

    @staticmethod
    def is_one_edit_away(word1: str, word2: str) -> bool:
        """Vérifie si deux mots normalisés ont au plus 1 faute de frappe/OCR."""
        if word1 == word2:
            return True
        l1, l2 = len(word1), len(word2)
        if abs(l1 - l2) > 1 or min(l1, l2) < 6:
            return False
        if l1 == l2:
            return sum(c1 != c2 for c1, c2 in zip(word1, word2)) == 1
        short_w, long_w = (word1, word2) if l1 < l2 else (word2, word1)
        i = j = diffs = 0
        while i < len(short_w) and j < len(long_w):
            if short_w[i] != long_w[j]:
                diffs += 1
                if diffs > 1:
                    return False
                j += 1
            else:
                i += 1
                j += 1
        return True
    def is_first_name(self, token: str) -> bool:
        """Vérifie si un jeton est un prénom connu (simple, composé ou commençant par Jean)."""
        norm: str = re.sub(r"\s+", " ", DocumentTextUtils.normalize_word(token))
        if not self._normalized_first_names and self.config.known_first_names:
            self._normalized_first_names = {
                DocumentTextUtils.normalize_word(fn)
                for fn in self.config.known_first_names
            }
        if norm in self._normalized_first_names:
            return True
        if norm.startswith(("jean ", "jean-")):
            split_parts: List[str] = re.split(r"[\s\-]+", norm, maxsplit=1)
            second_part: str = split_parts[-1] if len(split_parts) == 2 else ""
            if (
                re.fullmatch(r"[a-z]{2,}", second_part)
                and second_part not in {"de", "du", "des", "le", "la", "les", "en", "et"}
            ):
                return True
        if "-" in norm:
            parts: List[str] = [p for p in norm.split("-") if p]
            return bool(parts) and all(
                p in self._normalized_first_names for p in parts
            )
        return False

    def _is_person_rule_for_surname_index(self, kw: str, al: str) -> bool:
        """Vérifie qu'une règle représente une personne physique avant d'indexer son nom."""
        low_al: str = al.strip().lower()
        if any(marker in low_al for marker in self.NON_PERSON_ALIAS_MARKERS):
            return False
        if low_al.startswith("-") or "=" in kw or "=" in al:
            return False
        clean_kw: str = re.sub(r"\s*\([^)]*\)\s*", "", kw).strip()
        words: List[str] = [
            w for w in re.split(r"[\s\-'\u2019]+", clean_kw) if len(w) >= 2
        ]
        if len(words) < 2:
            return False
        return any(self.is_first_name(w) for w in words)

    def _register_rule(
        self,
        raw_keyword: str,
        raw_alias: str,
        norm_id: str = "",
        is_manual: bool = False,
    ) -> None:
        """Enregistre une règle (cible -> alias) en bloquant toute règle inversée."""
        kw: str = raw_keyword.strip()
        al: str = raw_alias.strip()
        if len(kw) < 2 or not al or "=" in kw or "=" in al:
            return
        if "@" in al or DocumentTextUtils.REGEX_PHONE.fullmatch(al):
            return

        for w in re.findall(r"[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'-]+", al):
            nw: str = DocumentTextUtils.normalize_word(w)
            if len(nw) >= 2:
                self.alias_words.add(nw)

        if norm_id:
            if norm_id not in self.contacts_id or is_manual:
                self.contacts_id[norm_id] = al
            return

        kw_words: List[str] = [
            w for w in re.split(r"[\s\-'\u2019]+", kw) if w
        ]
        if len(kw_words) == 1:
            single_norm: str = DocumentTextUtils.normalize_word(
                next(iter(kw_words), "")
            )
            if single_norm in self.config.surname_collisions:
                return
            if not is_manual and self.is_first_name(single_norm):
                return
            if is_manual and len(kw) <= 5 and any(ch.isupper() for ch in kw):
                self.case_sensitive_keywords[kw] = al
                self.full_targets.add(single_norm)
                return

        norm_kw: str = kw.lower()
        if norm_kw not in self.keyword_to_alias or is_manual:
            self.keyword_to_alias[norm_kw] = al
        self.full_targets.add(DocumentTextUtils.normalize_word(kw))

        words: List[str] = [w for w in kw.split() if len(w) >= 2]
        if len(words) >= 2:
            glued_key: str = self.normalize_ocr_key(kw)
            if len(glued_key) >= 7:
                self.glued_to_alias[glued_key] = al
                rev_key: str = self.normalize_ocr_key(" ".join(reversed(words)))
                if len(rev_key) >= 7:
                    self.glued_to_alias[rev_key] = al

        self._extract_surname_protection(kw, al, is_manual=is_manual)

    def _extract_surname_protection(
        self, kw: str, al: str, is_manual: bool = False
    ) -> None:
        """Protège uniquement les vrais noms de famille sans collision lexicale."""
        if not is_manual and not self._is_person_rule_for_surname_index(kw, al):
            return
        clean_kw: str = re.sub(r"\s*\([^)]*\)\s*", "", kw).strip()
        words: List[str] = [
            w for w in re.split(r"[\s\-'\u2019]+", clean_kw) if len(w) >= 2
        ]
        if not words:
            return
        clean_al: str = re.sub(r"\s*\([^)]*\)\s*", "", al).strip()
        first_is_fn: bool = len(words) >= 2 and self.is_first_name(next(iter(words)))
        for idx, word in enumerate(words):
            norm_w: str = DocumentTextUtils.normalize_word(word)
            is_last_pos: bool = len(words) >= 2 and idx == len(words) - 1
            is_surname_role: bool = (
                (is_last_pos and first_is_fn)
                or (not self.is_first_name(word) and (is_last_pos or is_manual))
            )
            if (
                len(norm_w) >= 4
                and is_surname_role
                and norm_w not in self.config.surname_collisions
                and norm_w not in self.config.excluded_words
                and norm_w not in self.config.masked_locations
                and norm_w not in DocumentTextUtils.ORG_GENERIC_WORDS
            ):
                self.protected_surnames.add(norm_w)
                if clean_al:
                    self.last_name_to_aliases[norm_w].add(clean_al)
                if norm_w not in self.last_name_display:
                    self.last_name_display[norm_w] = word.capitalize()
                short_alias: str = (
                    clean_al if is_manual and len(words) == 1 else f"{word[:1].upper()}."
                )
                if norm_w not in self.surname_to_alias or is_manual:
                    self.surname_to_alias[norm_w] = short_alias
    def _load_indexed_and_anonymized_pairs(self) -> None:
        """Relie les noms complets de contacts_indexes.txt aux alias de contacts_anonymises.txt."""
        idx_p: str = self.config.indexed_contacts_file
        ano_p: str = self.config.anonymized_contacts_file
        if not (os.path.exists(idx_p) and os.path.exists(ano_p)):
            return
        id_names: DefaultDict[str, List[str]] = defaultdict(list)
        with open(idx_p, "r", encoding="utf-8") as f_idx:
            for ln in f_idx:
                if "=" in ln and not ln.strip().startswith("#"):
                    l_p, r_p = ln.split("=", 1)
                    t, fn, nid = DocumentTextUtils.resolve_contact_pair(l_p, r_p)
                    if t and fn and nid:
                        id_names[nid].append(fn)
        id_aliases: DefaultDict[str, List[str]] = defaultdict(list)
        with open(ano_p, "r", encoding="utf-8") as f_ano:
            for ln in f_ano:
                if "=" in ln and not ln.strip().startswith("#"):
                    l_p, r_p = ln.split("=", 1)
                    t, al, nid = DocumentTextUtils.resolve_contact_pair(l_p, r_p)
                    if t and al and nid:
                        id_aliases[nid].append(al)
        for nid, fns in id_names.items():
            als: List[str] = id_aliases.get(nid, [])
            if len(fns) == len(als):
                for fn, al in zip(fns, als):
                    self._register_rule(fn, al, is_manual=False)
            elif len(als) == 1:
                single_al: str = next(iter(als))
                for fn in fns:
                    self._register_rule(fn, single_al, is_manual=False)

    def _load_file_rules(self, file_path: str, is_manual: bool = False) -> int:
        """Charge un fichier de règles cible = alias en ignorant les lignes corrompues."""
        if not os.path.exists(file_path):
            return 0
        loaded: int = 0
        with open(file_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line: str = raw_line.strip()
                if not line or line.startswith("#") or line.count("=") > 1:
                    continue
                for sep in ("=", ";", ","):
                    if sep in line:
                        left_p, right_p = line.split(sep, 1)
                        target, alias, norm_id = DocumentTextUtils.resolve_contact_pair(left_p, right_p)
                        if target and alias:
                            self._register_rule(target, alias, norm_id=norm_id, is_manual=is_manual)
                            loaded += 1
                        break
        return loaded

    def _register_protected_surnames(self) -> None:
        """Enregistre les noms de famille protégés pour les remplacer par leur initiale."""
        for surname, short_alias in self.surname_to_alias.items():
            if surname not in self.keyword_to_alias:
                self.keyword_to_alias[surname] = short_alias
                self.keyword_to_alias[surname.capitalize()] = short_alias
                self.keyword_to_alias[surname.upper()] = short_alias

    def _expand_saint_locations(self) -> Set[str]:
        """Génère les variantes Saint/Sainte/St/Ste pour les lieux personnalisés."""
        expanded: Set[str] = set()
        for loc in self.config.masked_locations:
            norm_loc: str = DocumentTextUtils.normalize_word(loc)
            if len(norm_loc) < 3 or norm_loc in self.COMMON_WORD_COLLISIONS:
                continue
            forms: Set[str] = {loc, loc.replace("-", " "), loc.replace(" ", "-")}
            for form in list(forms):
                if re.search(r"\bsainte\b", form):
                    forms.add(re.sub(r"\bsainte\b", "ste", form))
                    forms.add(re.sub(r"\bsainte\b", "st", form))
                if re.search(r"\bsaint\b", form):
                    forms.add(re.sub(r"\bsaint\b", "st", form))
            expanded.update(forms)
        return expanded

    def _compile_patterns(self) -> None:
        """Compile les expressions régulières Trie sans explosion mémoire."""
        if self.case_sensitive_keywords:
            cs_sorted: List[str] = sorted(self.case_sensitive_keywords.keys(), key=len, reverse=True)
            cs_alt: str = "|".join(re.escape(k) for k in cs_sorted)
            self.combined_case_sensitive_pattern = re.compile(rf"(?<![A-Za-zÀ-ÿ])(?:{cs_alt})(?![A-Za-zÀ-ÿ])")
        if self.keyword_to_alias:
            kw_regex: str = DocumentTextUtils.build_ocr_tolerant_trie_regex(list(self.keyword_to_alias.keys()))
            self.combined_keyword_pattern = re.compile(rf"(?<![A-Za-zÀ-ÿ]){kw_regex}(?![A-Za-zÀ-ÿ])", re.IGNORECASE)

        all_locs: Set[str] = self._expand_saint_locations()
        if len(all_locs) <= 15000:
            glued_map: Dict[str, str] = dict(self.glued_to_alias)
            for loc in all_locs:
                compact_loc: str = self.normalize_ocr_key(loc)
                if len(compact_loc) >= 10 and compact_loc not in glued_map:
                    glued_map[compact_loc] = "[LIEU_MASQUE]"
            self.glued_to_alias = glued_map
            valid_locs: List[str] = [loc for loc in all_locs if len(loc) >= 3]
            if valid_locs:
                loc_regex: str = DocumentTextUtils.build_ocr_tolerant_trie_regex(valid_locs)
                self.combined_location_pattern = re.compile(
                    rf"(?<![A-Za-zÀ-ÿ0-9]){loc_regex}(?![A-Za-zÀ-ÿ0-9])", re.IGNORECASE
                )

        if self.glued_to_alias:
            glued_alt: str = DocumentTextUtils.build_ocr_tolerant_trie_regex(list(self.glued_to_alias.keys()))
            self.combined_glued_pattern = re.compile(glued_alt, re.IGNORECASE)

    def lookup_keyword_alias(self, matched_text: str) -> str:
        """Retourne l'alias correspondant à un mot-clé, sa variante OCR ou à 1 lettre près."""
        low: str = matched_text.lower()
        if low in self.keyword_to_alias:
            return self.keyword_to_alias[low]
        norm_ocr: str = self.normalize_ocr_key(matched_text)
        for k, v in self.keyword_to_alias.items():
            if self.normalize_ocr_key(k) == norm_ocr:
                return v
        norm_word: str = DocumentTextUtils.normalize_word(matched_text)
        if len(norm_word) >= 6:
            for surname, short_alias in self.surname_to_alias.items():
                if self.is_one_edit_away(norm_word, surname):
                    return short_alias
        return matched_text

    def lookup_glued_alias(self, matched_text: str) -> str:
        """Retourne l'alias correspondant à un identifiant collé sans espaces."""
        compact: str = self.normalize_ocr_key(matched_text)
        if compact in self.glued_to_alias:
            return self.glued_to_alias[compact]
        for k, v in self.glued_to_alias.items():
            if self.normalize_ocr_key(k) == compact:
                return v
        return matched_text

    def load_all(self) -> bool:
        """Charge toutes les sources de règles et compile les expressions régulières."""
        if not self.manual_only and not os.path.exists(self.config.contacts_file):
            return False
        self._load_file_rules(self.config.contacts_file, is_manual=False)
        self._load_indexed_and_anonymized_pairs()
        self._load_file_rules(self.config.indexed_contacts_file, is_manual=False)
        self._load_file_rules(self.config.anonymized_contacts_file, is_manual=False)
        self._load_file_rules(self.config.discovered_contacts_file, is_manual=False)
        self._load_file_rules(self.config.surnames_contacts_file, is_manual=True)
        self._load_file_rules(self.config.manual_contacts_file, is_manual=True)
        self._register_protected_surnames()
        self._compile_patterns()
        return bool(
            self.contacts_id
            or self.keyword_to_alias
            or self.case_sensitive_keywords
            or self.glued_to_alias
            or self.combined_location_pattern
        )
