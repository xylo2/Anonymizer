# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
from typing import Dict, List, Set, Tuple
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class ContactRulesLoader:
    """
    Charge et fusionne les règles de remplacement issues de :
    - contacts.txt (index principal généré depuis Google Contacts),
    - discovered_email_contacts.txt (e-mails découverts automatiquement),
    - discovered_chat_contacts.txt (expéditeurs/participants des chats),
    - manual_contacts.txt (exceptions manuelles prioritaires).
    """

    COMMON_WORD_COLLISIONS = frozenset({
        "fiers", "fier", "bois", "foi", "fois", "voie", "voix", "champ",
        "champs", "pont", "ponts", "port", "ports", "mont", "monts", "val",
        "vaux", "lac", "lacs", "mer", "mers", "ile", "iles", "parc", "parcs",
        "rue", "rues", "place", "places", "cour", "cours", "tour", "tours",
        "bourg", "ville", "village", "camp", "camps", "roche", "roches",
        "pierre", "pierres", "sable", "sables", "terre", "terres", "eau",
        "eaux", "fontaine", "source", "sources", "moulin", "moulins",
        "chapelle", "eglise", "abbaye", "chateau", "maison", "maisons",
        "grange", "granges", "ferme", "fermes", "pre", "pres", "lande",
        "landes", "haie", "haies", "fosse", "fosses", "croix", "saint",
        "sainte", "saints", "saintes", "grand", "grande", "grands", "grandes",
        "petit", "petite", "petits", "petites", "haut", "haute", "hauts",
        "hautes", "bas", "basse", "basses", "neuf", "neuve",
        "vieux", "vieille", "blanc", "blanche", "noir", "noire", "rouge",
        "vert", "verte", "bleu", "bleue", "clair", "claire", "beau", "belle",
        "bon", "bonne", "franc", "franche", "libre", "long", "longue",
        "large", "fort", "forte", "doux", "douce", "chaud", "chaude",
        "froid", "froide", "sec", "seche", "humide", "plein", "pleine",
        "vide", "seul", "seule", "autre", "autres", "meme", "memes",
        "tout", "tous", "toute", "toutes", "rien", "personne", "quelque",
        "chaque", "aucun", "aucune", "certain", "certaine", "plusieurs",
        "divers", "diverse", "pareil", "pareille", "tel", "telle",
        "avril", "mai", "juin", "juillet", "aout", "mars", "lundi", "mardi",
        "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
        "car", "or", "ni", "donc", "mais", "ou", "et", "si", "que", "qui",
        "quoi", "dont", "quand", "comment", "pourquoi", "combien",
        "merci", "bonjour", "bonsoir", "salut", "pardon", "desole",
    })

    def __init__(self, config: PipelineConfig, manual_only: bool = False) -> None:
        """Initialise le chargeur de règles de contacts."""
        self.config: PipelineConfig = config
        self.manual_only: bool = manual_only
        self.keyword_to_alias: Dict[str, str] = {}
        self.manual_rules: Dict[str, str] = {}
        self.auto_name_rules: Dict[str, str] = {}
        self.reverse_contact_rules: Dict[str, str] = {}
        self.target_phones: Dict[str, str] = {}
        self.allowed_emails: Set[str] = set()
        self.email_to_alias: Dict[str, str] = {}
        self.known_surnames: Set[str] = set()
        self.last_name_to_aliases: Dict[str, Set[str]] = {}
        self.last_name_display: Dict[str, str] = {}
        self.alias_words: Set[str] = set()
        self.full_targets: Set[str] = set()

    def _ensure_manual_contacts_file(self) -> None:
        """Crée un fichier manual_contacts.txt vide avec en-tête s'il n'existe pas."""
        manual_path: str = self.config.manual_contacts_file
        if not manual_path or os.path.exists(manual_path):
            return
        parent: str = os.path.dirname(os.path.abspath(manual_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        DocumentTextUtils.atomic_write_text(
            manual_path,
            "# RÈGLES D'ANONYMISATION MANUELLES (EXCEPTIONS & VARIANTES OCR LOURDES)\n"
            "# Format : Mot ou Nom complet = Alias\n\n",
        )

    def _index_alias_metadata(self, keyword: str, alias: str) -> None:
        """Indexe les noms de famille et jetons d'alias pour l'audit phonétique et le filtrage."""
        for token in re.findall(r"[A-Za-zÀ-ÿ0-9_-]{2,}", alias):
            norm_tok: str = DocumentTextUtils.normalize_word(token)
            if norm_tok:
                self.alias_words.add(norm_tok)

        if keyword.strip():
            norm_kw: str = DocumentTextUtils.normalize_word(keyword)
            if norm_kw:
                self.full_targets.add(norm_kw)

        kw_parts: List[str] = [p for p in keyword.strip().split(" ") if p]
        if len(kw_parts) >= 2:
            raw_last: str = kw_parts[-1]
            norm_last: str = DocumentTextUtils.normalize_word(raw_last)
            if len(norm_last) >= 3:
                self.known_surnames.add(norm_last)
                self.last_name_to_aliases.setdefault(norm_last, set()).add(alias)
                self.last_name_display.setdefault(norm_last, raw_last)

    def _register_rule(self, keyword: str, alias: str, is_manual: bool = False) -> None:
        """Enregistre une règle de remplacement en filtrant les collisions courantes."""
        kw: str = keyword.strip()
        al: str = alias.strip()
        if not kw or not al or kw == al:
            return
        norm: str = DocumentTextUtils.normalize_word(kw)
        if not norm:
            return
        if not is_manual and norm in self.COMMON_WORD_COLLISIONS:
            return
        self.keyword_to_alias[kw] = al
        self._index_alias_metadata(kw, al)
        if is_manual:
            self.manual_rules[kw] = al
        else:
            self.auto_name_rules[kw] = al

    def _load_file_rules(self, file_path: str, is_manual: bool = False) -> None:
        """Lit un fichier clé = valeur et alimente les tables de correspondance."""
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

                if "@" in left:
                    norm_mail: str = DocumentTextUtils.normalize_identifier(left)
                    if norm_mail:
                        self.allowed_emails.add(norm_mail)
                        self.email_to_alias[norm_mail] = right
                        self.reverse_contact_rules[left] = right
                        self._index_alias_metadata("", right)
                    continue

                norm_phone: str = DocumentTextUtils._normalize_fr_phone(left)
                if norm_phone:
                    self.target_phones[norm_phone] = right
                    self.reverse_contact_rules[left] = right
                    self._index_alias_metadata("", right)
                    continue

                self._register_rule(left, right, is_manual=is_manual)
    def load_all(self) -> bool:
        """
        Charge l'ensemble des fichiers de contacts (auto, e-mails découverts,
        chats découverts et manuels).

        :return: True si le chargement a réussi, False si contacts.txt est introuvable.
        """
        if self.manual_only:
            self._ensure_manual_contacts_file()
            self._load_file_rules(self.config.manual_contacts_file, is_manual=True)
            return True

        if not os.path.exists(self.config.contacts_file):
            print(
                f"ERREUR : Fichier de contacts introuvable : '{self.config.contacts_file}'.\n"
                "Exécutez d'abord 'python run_contacts.py'.",
                flush=True,
            )
            return False

        self._ensure_manual_contacts_file()
        self._load_file_rules(self.config.contacts_file, is_manual=False)
        self._load_file_rules(self.config.discovered_contacts_file, is_manual=False)
        self._load_file_rules(self.config.discovered_chats_file, is_manual=False)
        self._load_file_rules(self.config.manual_contacts_file, is_manual=True)
        return True

    def get_ordered_rules(self) -> List[Tuple[str, str]]:
        """Retourne les règles triées par longueur décroissante de la cible."""
        return sorted(
            self.keyword_to_alias.items(),
            key=lambda item: (-len(item[0]), item[0].lower()),
        )

    def is_first_name(self, token: str) -> bool:
        """Vérifie si un mot ou prénom composé figure dans le référentiel des prénoms."""
        norm: str = DocumentTextUtils.normalize_word(token)
        if not norm:
            return False
        if norm in self.config.known_first_names:
            return True
        parts: List[str] = [p for p in re.split(r"[\s\-]+", norm) if p]
        if len(parts) >= 2:
            if parts[0] in {"jean", "marie", "pierre", "anne", "paul", "louis"}:
                return True
            return all(p in self.config.known_first_names for p in parts)
        return False

    @staticmethod
    def is_one_edit_away(word_a: str, word_b: str) -> bool:
        """Indique si deux mots diffèrent d'au plus une opération d'édition (Levenshtein <= 1)."""
        a: str = DocumentTextUtils.normalize_word(word_a)
        b: str = DocumentTextUtils.normalize_word(word_b)
        if a == b:
            return True
        len_a: int = len(a)
        len_b: int = len(b)
        if abs(len_a - len_b) > 1 or min(len_a, len_b) < 4:
            return False
        if len_a == len_b:
            diffs: int = sum(1 for c1, c2 in zip(a, b) if c1 != c2)
            return diffs <= 1
        shorter, longer = (a, b) if len_a < len_b else (b, a)
        i: int = 0
        j: int = 0
        found_diff: bool = False
        while i < len(shorter) and j < len(longer):
            if shorter[i] != longer[j]:
                if found_diff:
                    return False
                found_diff = True
                j += 1
            else:
                i += 1
                j += 1
        return True
