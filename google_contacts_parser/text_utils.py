# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import re
from typing import List, Optional, Set, Tuple
from common.core_utils import SharedCoreUtils


class ContactTextUtils:
    """
    Fournit des utilitaires de normalisation, formatage et détection d'enseignes/sociétés
    pour le traitement des noms et coordonnées de contacts.
    """

    @staticmethod
    def normalize_email_alias(email: str) -> str:
        """
        Supprime l'extension d'alias '+...' dans la partie locale d'une adresse e-mail.

        :param email: Adresse e-mail brute à normaliser.
        :return: Adresse e-mail canonique sans suffixe '+'.
        """
        return SharedCoreUtils.normalize_email_alias(email, lowercase=False)

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Supprime les accents, espaces superflus et met en minuscules pour comparer deux chaînes.

        :param text: Texte brut à normaliser.
        :return: Chaîne normalisée en minuscules sans accents.
        """
        return SharedCoreUtils.normalize_compact_text(text)

    @classmethod
    def strip_provider_suffix(cls, name: str, ignored_domains: Set[str]) -> str:
        """
        Supprime un suffixe final de fournisseur de messagerie (ex: ' - Gmail', ' (Yahoo)')
        lorsqu'il correspond à l'un des domaines ignorés configurés.

        :param name: Libellé brut du contact.
        :param ignored_domains: Ensemble des fournisseurs de mail à ignorer (en minuscules).
        :return: Libellé nettoyé de toute mention finale de fournisseur.
        """
        cleaned: str = name.strip()
        if not cleaned or not ignored_domains:
            return cleaned

        sep_match: Optional[re.Match[str]] = re.match(r"^(.*?)\s*(?:-|/|–|—)\s*([^\s\-/]+)$", cleaned)
        if sep_match:
            prefix_part: str = sep_match.group(1).strip()
            suffix_token: str = sep_match.group(2).strip().lower()
            suffix_root: str = next(iter(suffix_token.split(".", 1)), "")
            if prefix_part and (suffix_token in ignored_domains or suffix_root in ignored_domains):
                return prefix_part

        paren_match: Optional[re.Match[str]] = re.match(r"^(.*?)\s*\(([^)]+)\)$", cleaned)
        if paren_match:
            prefix_part = paren_match.group(1).strip()
            paren_token: str = paren_match.group(2).strip().lower()
            paren_root: str = next(iter(paren_token.split(".", 1)), "")
            if prefix_part and (paren_token in ignored_domains or paren_root in ignored_domains):
                return prefix_part

        return cleaned

    @staticmethod
    def _abbreviate_geo_label(location_text: str) -> str:
        """
        Remplace un nom géographique par sa première lettre majuscule suivie d'un point.

        :param location_text: Nom du lieu géographique détecté.
        :return: Initiale majuscule suivie d'un point, ou chaîne vide.
        """
        for ch in location_text.strip():
            if ch.isalpha():
                return f"{ch.upper()}."
        return ""

    @classmethod
    def _abbreviate_hyphenated_word(cls, word: str, excluded_locations_norm: Set[str]) -> str:
        """
        Abrège tout sous-segment géographique à l'intérieur d'un mot composé avec tiret.

        :param word: Mot contenant éventuellement des tirets.
        :param excluded_locations_norm: Ensemble des lieux normalisés à abréger.
        :return: Mot transformé avec les segments géographiques abrégés.
        """
        if "-" not in word:
            return word
        parts: List[str] = word.split("-")
        replaced: bool = False
        new_parts: List[str] = []
        for part in parts:
            if part and cls.normalize_text(part) in excluded_locations_norm:
                abbr: str = cls._abbreviate_geo_label(part)
                new_parts.append(abbr if abbr else part)
                replaced = True
            else:
                new_parts.append(part)
        return "-".join(new_parts) if replaced else word
    @classmethod
    def abbreviate_locations_in_text(cls, text: str, excluded_locations_norm: Set[str]) -> str:
        """
        Remplace toute mention d'un lieu géographique configuré par son initiale.

        :param text: Libellé ou nom de domaine formaté à inspecter.
        :param excluded_locations_norm: Ensemble des lieux normalisés à abréger.
        :return: Texte avec les lieux remplacés par leur initiale suivie d'un point.
        """
        cleaned: str = text.strip()
        if not cleaned or not excluded_locations_norm:
            return cleaned

        paren_match: Optional[re.Match[str]] = re.match(r"^(.*?)\s*\(([^)]+)\)$", cleaned)
        if paren_match:
            prefix_part: str = paren_match.group(1).strip()
            inside_paren: str = paren_match.group(2).strip()
            if prefix_part and cls.normalize_text(inside_paren) in excluded_locations_norm:
                cleaned = f"{prefix_part} {cls._abbreviate_geo_label(inside_paren)}".strip()

        sep_match: Optional[re.Match[str]] = re.match(r"^(.*?)\s*(?:-|/|–|—|,)\s*(.+)$", cleaned)
        if sep_match:
            prefix_part = sep_match.group(1).strip()
            tail_part: str = sep_match.group(2).strip()
            if prefix_part and cls.normalize_text(tail_part) in excluded_locations_norm:
                cleaned = f"{prefix_part} {cls._abbreviate_geo_label(tail_part)}".strip()

        words: List[str] = cleaned.split()
        idx: int = 0
        output_tokens: List[str] = []
        while idx < len(words):
            matched: bool = False
            max_span: int = min(len(words) - idx, 4)
            for span in range(max_span, 0, -1):
                candidate: str = " ".join(words[idx : idx + span])
                if cls.normalize_text(candidate) in excluded_locations_norm:
                    abbr: str = cls._abbreviate_geo_label(candidate)
                    if abbr:
                        output_tokens.append(abbr)
                    idx += span
                    matched = True
                    break
            if not matched:
                output_tokens.append(cls._abbreviate_hyphenated_word(words[idx], excluded_locations_norm))
                idx += 1

        return " ".join(output_tokens)

    @staticmethod
    def format_first_name(first_name: str) -> str:
        """
        Convertit un prénom tout en majuscules en capitale initiale suivie de minuscules.

        :param first_name: Prénom brut à formater.
        :return: Prénom proprement capitalisé.
        """
        cleaned: str = first_name.strip().strip('"').strip()
        if not cleaned or not cleaned.isupper():
            return cleaned
        parts: List[str] = re.split(r"([\s\-]+)", cleaned)
        return "".join(p.capitalize() if p and not re.match(r"^[\s\-]+$", p) else p for p in parts)

    @staticmethod
    def extract_domain_root(email: str) -> str:
        """
        Extrait le nom de domaine sans extension.

        :param email: Adresse e-mail complète.
        :return: Nom de domaine principal en minuscules, ou chaîne vide si invalide.
        """
        if "@" not in email:
            return ""
        _, domain_part = email.rsplit("@", 1)
        domain_part = domain_part.strip().lower()
        if not domain_part:
            return ""
        labels: List[str] = [lbl for lbl in domain_part.split(".") if lbl]
        if not labels:
            return ""
        if len(labels) == 1:
            return next(iter(labels), "").strip()
        if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in {"co", "com", "org", "net", "gouv", "asso"}:
            return labels[-3].strip()
        return labels[-2].strip()

    @staticmethod
    def format_initials(last_name: str, extra_chars: int = 0) -> str:
        """
        Convertit un nom de famille en initiales suivies d'un point.

        :param last_name: Nom de famille complet.
        :param extra_chars: Nombre de lettres supplémentaires à afficher (limité à 1).
        :return: Initiales formatées.
        """
        tokens: List[str] = [t for t in re.split(r"[\s\-]+", last_name.strip()) if any(c.isalpha() for c in t)]
        if not tokens:
            return ""
        letters: List[str] = []
        total_tokens: int = len(tokens)
        clamped_extra: int = min(extra_chars, 1)
        for idx, token in enumerate(tokens):
            alpha_only: str = "".join(c for c in token if c.isalpha())
            if not alpha_only:
                continue
            if idx == total_tokens - 1 and clamped_extra > 0:
                letters.append(alpha_only[: 1 + clamped_extra].capitalize())
            else:
                letters.append(alpha_only[:1].upper())
        return ".".join(letters) + "." if letters else ""

    @classmethod
    def is_non_person_entity(
        cls,
        base_name: str,
        contact_val: str,
        entity_prefixes: Set[str],
        company_keywords: Set[str],
        frequent_first_names: Set[str],
    ) -> bool:
        """
        Détermine si le libellé est une enseigne, société ou pseudo plutôt qu'une personne.

        :param base_name: Nom complet nettoyé de toute parenthèse.
        :param contact_val: Coordonnée associée (e-mail ou téléphone).
        :param entity_prefixes: Ensemble des préfixes d'enseignes configurés.
        :param company_keywords: Ensemble des mots-clés de sociétés.
        :param frequent_first_names: Ensemble des prénoms connus normalisés.
        :return: True si le libellé ne doit pas être abrégé en initiale.
        """
        words: List[str] = [w for w in re.split(r"[\s'\-]+", base_name.strip()) if w]
        if not words:
            return False
        if any(ch.isdigit() for ch in base_name):
            return True
        if re.search(r"\b(?:et|&)\b", base_name, flags=re.IGNORECASE):
            return False

        norm_words: List[str] = [cls.normalize_text(w) for w in words if cls.normalize_text(w)]
        if not norm_words:
            return False

        first_norm: str = next(iter(norm_words))
        if first_norm in entity_prefixes:
            return True
        if any(nw in company_keywords for nw in norm_words):
            return True
        if len(norm_words) == 1 and first_norm not in frequent_first_names:
            return True
        if len(norm_words) >= 2 and not any(nw in frequent_first_names for nw in norm_words):
            return True
        return False

    @staticmethod
    def format_entity_label(base_name: str) -> str:
        """
        Capitalise proprement une enseigne ou société.

        :param base_name: Libellé brut de l'enseigne ou société.
        :return: Libellé proprement capitalisé.
        """
        cleaned: str = base_name.strip().strip('"').strip()
        if not cleaned:
            return ""
        if cleaned.isupper():
            parts: List[str] = re.split(r"([\s\-]+)", cleaned)
            return "".join(p.capitalize() if p and not re.match(r"^[\s\-]+$", p) else p for p in parts)
        return f"{cleaned[:1].upper()}{cleaned[1:]}"

    @staticmethod
    def clean_display_name(raw_name: str) -> Tuple[str, str, bool]:
        """
        Nettoie les formats spéciaux comme '"Service-Client" <mail@...>' et sépare
        les éventuelles annotations entre parenthèses en fin de nom.

        :param raw_name: Nom brut issu du fichier indexé.
        :return: Tuple (nom_nettoyé, suffixe_parenthèse_existant, est_nom_affichage_mail).
        """
        cleaned: str = raw_name.strip().strip('"').strip()
        rfc_match: Optional[re.Match[str]] = re.match(r'^"?([^"<]+?)"?\s*\x3c[^\x3e]+@[^\x3e]+\x3e$', cleaned)
        if rfc_match:
            display_label: str = rfc_match.group(1).strip().strip('"').strip()
            return display_label, "", True

        paren_match: Optional[re.Match[str]] = re.match(r"^(.*?)\s*(\([^)]+\))$", cleaned)
        if paren_match:
            base_name: str = paren_match.group(1).strip().strip('"').strip()
            existing_paren: str = paren_match.group(2).strip()
            return base_name, f" {existing_paren}", False

        return cleaned, "", False

    @staticmethod
    def sanitize_final_line(text: str) -> str:
        """
        Supprime les guillemets résiduels et séries de caractères spéciaux en fin de chaîne.

        :param text: Ligne formatée avant écriture.
        :return: Chaîne propre sans guillemet ni ponctuation multiple en fin de ligne.
        """
        cleaned: str = text.strip().lstrip('"').strip()
        cleaned = re.sub(r"([^\w\s\)\.]+)$", "", cleaned).strip()
        cleaned = re.sub(r"\.{2,}$", ".", cleaned)
        cleaned = re.sub(r"\){2,}$", ")", cleaned)
        return cleaned
