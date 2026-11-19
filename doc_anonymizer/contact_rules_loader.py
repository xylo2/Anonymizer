# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
from typing import Dict, List, Optional, Pattern, Set, Tuple
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class ContactRulesLoader:
    """
    Charge les règles d'anonymisation depuis contacts.txt, contacts_manuels.txt
    et les référentiels lexicaux (prénoms, communes, collisions), puis compile
    les automates regex tolérants aux erreurs OCR.
    """

    COMMON_WORD_COLLISIONS = frozenset({
        "fois", "bois", "fiers", "fiere", "fier", "tiers", "mis", "mise",
        "cree", "creer", "cousin", "cousine", "barriere", "garage", "garcon",
        "garcons", "courant", "cerisier", "commande", "commandes", "colis",
        "rue", "route", "place", "maison", "chambre", "bureau", "salon",
        "jardin", "cuisine", "voiture", "velo", "train", "bus", "ecole",
        "travail", "vacances", "conge", "conges", "mere", "pere", "maman",
        "papa", "frere", "soeur", "enfant", "enfants", "bebe", "fils", "fille",
        "grand", "grande", "petit", "petite", "rouge", "bleu", "vert", "noir",
        "blanc", "gris", "jaune", "rose", "orange", "marron", "violet",
        "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
        "janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
        "aout", "septembre", "octobre", "novembre", "decembre",
        "france", "paris", "nord", "sud", "est", "ouest", "centre",
        "merci", "bonjour", "bonsoir", "salut", "coucou", "bisous", "bises",
        "cordialement", "madame", "monsieur", "docteur", "professeur",
        "maitre", "famille", "pharmacie", "clinique", "hopital", "cabinet",
        "saint", "sainte", "mont", "val", "port", "pont", "lac", "mer",
        "foret", "parc", "champ", "champs", "pre", "pres",
        "autre", "autres", "meme", "memes", "tout", "tous", "toute", "toutes",
        "rien", "peu", "beaucoup", "trop", "tres", "bien", "mal", "bon",
        "bonne", "nouveau", "nouvelle", "ancien", "ancienne", "jeune", "vieux",
        "vieille", "premier", "premiere", "dernier", "derniere", "prochain",
        "prochaine", "seul", "seule", "libre", "plein", "pleine", "vide",
        "clair", "claire", "sombre", "chaud", "chaude", "froid", "froide",
        "fort", "forte", "doux", "douce", "dur", "dure", "simple", "double",
        "page", "pages", "titre", "date", "heure", "heures", "jour", "jours",
        "mois", "annee", "annees", "semaine", "semaines", "matin", "midi",
        "soir", "nuit", "temps", "moment", "coup", "coups", "tour",
        "tours", "fin", "debut", "suite", "reste", "part", "partie", "cote",
        "cotes", "fond", "haut", "bas", "droite", "gauche", "face", "milieu",
        "point", "points", "ligne", "lignes", "zone", "zones", "secteur",
        "service", "services", "dossier", "dossiers", "compte", "comptes",
        "carte", "cartes", "cheque", "cheques", "virement", "paiement",
        "facture", "factures", "devis", "prix", "montant", "total", "somme",
        "euro", "euros", "centime", "centimes", "franc", "francs",
    })

    def __init__(
        self, config: PipelineConfig, manual_only: bool = False
    ) -> None:
        """
        Initialise le chargeur de règles d'anonymisation.

        :param config: Configuration globale du pipeline.
        :param manual_only: Si True, ne charge que contacts_manuels.txt.
        """
        self.config: PipelineConfig = config
        self.manual_only: bool = manual_only
        self.keyword_to_alias: Dict[str, str] = {}
        self.norm_keyword_to_alias: Dict[str, str] = {}
        self.case_sensitive_keywords: Dict[str, str] = {}
        self.glued_to_alias: Dict[str, str] = {}
        self.norm_glued_to_alias: Dict[str, str] = {}
        self.full_targets: Set[str] = set()
        self.alias_words: Set[str] = set()
        self.protected_surnames: Set[str] = set()
        self.last_name_to_aliases: Dict[str, Set[str]] = {}
        self.last_name_display: Dict[str, str] = {}
        self.contacts_id: Dict[str, str] = {}
        self.contact_emails: Set[str] = set()
        self.contact_phones: Dict[str, str] = {}
        self._normalized_first_names: Set[str] = set()

        self.combined_keyword_pattern: Optional[Pattern[str]] = None
        self.combined_case_sensitive_pattern: Optional[Pattern[str]] = None
        self.combined_glued_pattern: Optional[Pattern[str]] = None
        self.combined_location_pattern: Optional[Pattern[str]] = None
    @staticmethod
    def is_one_edit_away(word_a: str, word_b: str) -> bool:
        """
        Vérifie si deux chaînes normalisées sont à une distance d'édition <= 1
        (substitution, insertion ou suppression d'un caractère).

        :param word_a: Première chaîne normalisée.
        :param word_b: Seconde chaîne normalisée.
        :return: True si la distance est <= 1.
        """
        a: str = DocumentTextUtils.normalize_word(word_a)
        b: str = DocumentTextUtils.normalize_word(word_b)
        if a == b:
            return True
        if abs(len(a) - len(b)) > 1 or min(len(a), len(b)) < 4:
            return False
        if len(a) == len(b):
            return sum(1 for ca, cb in zip(a, b) if ca != cb) == 1
        shorter, longer = (a, b) if len(a) < len(b) else (b, a)
        i: int = 0
        j: int = 0
        diffs: int = 0
        while i < len(shorter) and j < len(longer):
            if shorter[i] != longer[j]:
                diffs += 1
                if diffs > 1:
                    return False
                j += 1
            else:
                i += 1
                j += 1
        return True

    def is_first_name(self, token: str) -> bool:
        """
        Indique si un jeton correspond à un prénom connu (simple ou composé).

        :param token: Jeton candidat.
        :return: True si reconnu comme prénom.
        """
        if not self._normalized_first_names and self.config.known_first_names:
            self._normalized_first_names = set(self.config.known_first_names)
        norm: str = DocumentTextUtils.normalize_word(token)
        if not norm or len(norm) < 2:
            return False
        if norm in self._normalized_first_names:
            return True
        if "-" in norm or " " in norm:
            parts: List[str] = [
                p for p in re.split(r"[\s\-]+", norm) if len(p) >= 2
            ]
            if len(parts) >= 2 and all(
                p in self._normalized_first_names for p in parts
            ):
                return True
            if norm.startswith(("jean ", "jean-")) and len(parts) >= 2:
                return True
        return False

    def _is_person_rule_for_surname_index(
        self, keyword: str, alias: str
    ) -> bool:
        """
        Détermine si une règle correspond à une personne physique.

        :param keyword: Libellé source.
        :param alias: Alias cible.
        :return: True si personne physique.
        """
        words: List[str] = [w for w in keyword.split() if len(w) >= 2]
        if len(words) < 2:
            return False
        if re.search(r"\b[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]\.", alias):
            return True
        return any(self.is_first_name(w) for w in words)

    def _is_blocked_single_word(self, norm_kw: str, is_manual: bool) -> bool:
        """
        Vérifie si un mot-clé isolé est un mot courant protégé contre le masquage.

        :param norm_kw: Mot-clé normalisé.
        :param is_manual: True si issu de contacts_manuels.txt.
        :return: True si le mot-clé isolé doit être ignoré.
        """
        if not norm_kw or len(norm_kw) < 2:
            return True
        if norm_kw in self.config.excluded_words:
            return True
        if norm_kw in self.COMMON_WORD_COLLISIONS:
            return True
        if not is_manual and norm_kw in self.config.surname_collisions:
            return True
        if not is_manual and norm_kw in DocumentTextUtils.ORG_GENERIC_WORDS:
            return True
        return False
    def _register_rule(
        self,
        keyword: str,
        alias: str,
        norm_id: str = "",
        is_manual: bool = False,
    ) -> None:
        """
        Enregistre une règle mot-clé -> alias et génère ses variantes OCR collées.

        :param keyword: Texte à rechercher.
        :param alias: Texte de remplacement.
        :param norm_id: Identifiant normalisé (e-mail ou téléphone) éventuel.
        :param is_manual: True si issu de contacts_manuels.txt.
        """
        kw: str = keyword.strip()
        al: str = alias.strip()
        if not kw or not al:
            return

        if norm_id:
            self.contacts_id[norm_id] = al
            if "@" in norm_id:
                self.contact_emails.add(norm_id)
            elif norm_id.isdigit():
                self.contact_phones[norm_id] = al
            return

        norm_kw: str = DocumentTextUtils.normalize_word(kw)
        words: List[str] = [w for w in kw.split() if w]
        if len(words) == 1 and self._is_blocked_single_word(norm_kw, is_manual):
            return

        for a_tok in al.split():
            norm_a: str = DocumentTextUtils.normalize_word(a_tok)
            if len(norm_a) >= 3:
                self.alias_words.add(norm_a)

        self.keyword_to_alias[kw] = al
        self.norm_keyword_to_alias[norm_kw] = al
        self.full_targets.add(norm_kw)

        if len(words) >= 2:
            glued_compact: str = "".join(words)
            if len(glued_compact) >= 6:
                self.glued_to_alias[glued_compact] = al
                self.norm_glued_to_alias[
                    DocumentTextUtils.normalize_word(glued_compact)
                ] = al
            reversed_kw: str = f"{words[-1]} {' '.join(words[:-1])}"
            norm_rev: str = DocumentTextUtils.normalize_word(reversed_kw)
            if len(words[-1]) >= 3 and norm_rev not in self.norm_keyword_to_alias:
                self.keyword_to_alias[reversed_kw] = al
                self.norm_keyword_to_alias[norm_rev] = al
                self.full_targets.add(norm_rev)

        self._extract_surname_protection(kw, al, is_manual=is_manual)

    def _extract_surname_protection(
        self, kw: str, al: str, is_manual: bool = False
    ) -> None:
        """Indexe le nom de famille d'une personne physique pour la détection contextuelle."""
        if not is_manual and not self._is_person_rule_for_surname_index(kw, al):
            return
        parts: List[str] = [p for p in kw.split() if len(p) >= 2]
        if len(parts) < 2:
            return
        first_part: str = parts[0]
        candidate_last: str = parts[-1]
        if self.is_first_name(candidate_last) and not self.is_first_name(first_part):
            candidate_last = first_part
        norm_last: str = DocumentTextUtils.normalize_word(candidate_last)
        if (
            len(norm_last) >= 3
            and norm_last not in self.COMMON_WORD_COLLISIONS
            and norm_last not in self.config.excluded_words
            and norm_last not in self.config.surname_collisions
        ):
            self.protected_surnames.add(norm_last)
            self.last_name_to_aliases.setdefault(norm_last, set()).add(al)
            if norm_last not in self.last_name_display:
                self.last_name_display[norm_last] = candidate_last.capitalize()
    def _load_indexed_and_anonymized_pairs(self) -> None:
        """Croise contacts_indexes.txt et contacts_anonymises.txt pour enregistrer les noms complets."""
        idx_p: str = self.config.indexed_contacts_file
        anon_p: str = self.config.anonymized_contacts_file
        if not os.path.exists(idx_p) or not os.path.exists(anon_p):
            return
        with open(idx_p, "r", encoding="utf-8", errors="ignore") as f_idx, open(
            anon_p, "r", encoding="utf-8", errors="ignore"
        ) as f_anon:
            idx_lines: List[str] = [
                ln.strip() for ln in f_idx if ln.strip() and "=" in ln
            ]
            anon_lines: List[str] = [
                ln.strip() for ln in f_anon if ln.strip() and "=" in ln
            ]
        if len(idx_lines) != len(anon_lines):
            return
        for raw_i, raw_a in zip(idx_lines, anon_lines):
            _, full_name = raw_i.split("=", 1)
            _, alias_name = raw_a.split("=", 1)
            fn: str = full_name.strip()
            an: str = alias_name.strip()
            if fn and an and fn != an:
                self._register_rule(fn, an, is_manual=False)

    def _load_file_rules(
        self, file_path: str, is_manual: bool = False
    ) -> None:
        """Charge les paires clé = valeur depuis un fichier de règles."""
        if not file_path or not os.path.exists(file_path):
            return
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line: str = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                left_p, right_p = line.split("=", 1)
                left: str = left_p.strip()
                right: str = right_p.strip()
                if not left or not right:
                    continue

                if DocumentTextUtils.is_contact_identifier(left):
                    target, alias, norm_id = (
                        DocumentTextUtils.resolve_contact_pair(left, right)
                    )
                    self._register_rule(
                        target, alias, norm_id=norm_id, is_manual=is_manual
                    )
                elif DocumentTextUtils.is_contact_identifier(right):
                    target, alias, norm_id = (
                        DocumentTextUtils.resolve_contact_pair(right, left)
                    )
                    self._register_rule(
                        target, alias, norm_id=norm_id, is_manual=is_manual
                    )
                else:
                    self._register_rule(left, right, is_manual=is_manual)

    def lookup_keyword_alias(self, matched_text: str) -> str:
        """Retourne l'alias correspondant à une correspondance regex de mot-clé."""
        if matched_text in self.keyword_to_alias:
            return self.keyword_to_alias[matched_text]
        norm: str = DocumentTextUtils.normalize_word(matched_text)
        return self.norm_keyword_to_alias.get(norm, matched_text)

    def lookup_glued_alias(self, matched_text: str) -> str:
        """Retourne l'alias correspondant à une variante OCR collée sans espaces."""
        if matched_text in self.glued_to_alias:
            return self.glued_to_alias[matched_text]
        norm: str = DocumentTextUtils.normalize_word(matched_text)
        return self.norm_glued_to_alias.get(norm, matched_text)
    def _compile_patterns(self) -> None:
        """Compile les expressions régulières Trie pour mots-clés, formes collées et communes."""
        if self.case_sensitive_keywords:
            cs_sorted: List[str] = sorted(
                self.case_sensitive_keywords.keys(),
                key=lambda x: (-len(x), x),
            )
            self.combined_case_sensitive_pattern = re.compile(
                r"(?<![A-Za-zÀ-ÿ0-9])(?:"
                + "|".join(re.escape(k) for k in cs_sorted)
                + r")(?![A-Za-zÀ-ÿ0-9])"
            )

        if self.keyword_to_alias:
            kw_list: List[str] = list(self.keyword_to_alias.keys())
            trie_rx: str = DocumentTextUtils.build_ocr_tolerant_trie_regex(
                kw_list
            )
            if trie_rx:
                self.combined_keyword_pattern = re.compile(
                    r"(?i)(?<![A-Za-zÀ-ÿ0-9])(?:"
                    + trie_rx
                    + r")(?![A-Za-zÀ-ÿ0-9])"
                )

        if self.glued_to_alias:
            glued_list: List[str] = list(self.glued_to_alias.keys())
            glued_trie: str = DocumentTextUtils.build_ocr_tolerant_trie_regex(
                glued_list
            )
            if glued_trie:
                self.combined_glued_pattern = re.compile(
                    r"(?i)(?<![A-Za-zÀ-ÿ0-9])(?:"
                    + glued_trie
                    + r")(?![A-Za-zÀ-ÿ0-9])"
                )

        safe_locations: List[str] = [
            loc
            for loc in self.config.masked_locations
            if len(loc) >= 4
            and loc not in self.COMMON_WORD_COLLISIONS
            and loc not in self.config.excluded_words
        ]
        if safe_locations and len(safe_locations) <= 2500:
            loc_trie: str = DocumentTextUtils.build_ocr_tolerant_trie_regex(
                safe_locations
            )
            if loc_trie:
                self.combined_location_pattern = re.compile(
                    r"(?i)(?<![A-Za-zÀ-ÿ0-9])(?:"
                    + loc_trie
                    + r")(?![A-Za-zÀ-ÿ0-9])"
                )

    def load_all(self) -> bool:
        """
        Charge l'ensemble des règles et dictionnaires configurés.

        :return: True si le chargement a réussi.
        """
        self.keyword_to_alias.clear()
        self.norm_keyword_to_alias.clear()
        self.case_sensitive_keywords.clear()
        self.glued_to_alias.clear()
        self.norm_glued_to_alias.clear()
        self.full_targets.clear()
        self.alias_words.clear()
        self.protected_surnames.clear()
        self.last_name_to_aliases.clear()
        self.last_name_display.clear()
        self.contacts_id.clear()
        self.contact_emails.clear()
        self.contact_phones.clear()
        self._normalized_first_names = set(self.config.known_first_names)

        if not self.manual_only:
            self._load_indexed_and_anonymized_pairs()
            self._load_file_rules(self.config.contacts_file, is_manual=False)
            self._load_file_rules(
                self.config.discovered_contacts_file, is_manual=False
            )
            if os.path.exists(self.config.surnames_contacts_file):
                with open(
                    self.config.surnames_contacts_file,
                    "r",
                    encoding="utf-8",
                    errors="ignore",
                ) as f_sur:
                    for raw_line in f_sur:
                        norm_s: str = DocumentTextUtils.normalize_word(raw_line)
                        if (
                            len(norm_s) >= 3
                            and norm_s not in self.COMMON_WORD_COLLISIONS
                            and norm_s not in self.config.excluded_words
                            and norm_s not in self.config.surname_collisions
                        ):
                            self.protected_surnames.add(norm_s)

        self._load_file_rules(self.config.manual_contacts_file, is_manual=True)
        self._compile_patterns()
        return True
