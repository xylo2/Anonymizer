# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
from typing import Dict, List, Set
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class ContactRulesLoader:
    """
    Charge et fusionne les règles d'anonymisation depuis contacts.txt,
    discovered_email_contacts.txt, discovered_chat_contacts.txt et
    manual_contacts.txt, et déduit les noms de famille sûrs.
    """

    COMMON_WORD_COLLISIONS: Set[str] = {
        "la", "le", "les", "un", "une", "des", "du", "de", "au", "aux",
        "ce", "cet", "cette", "ces", "mon", "ton", "son", "ma", "ta", "sa",
        "mes", "tes", "ses", "notre", "votre", "leur", "nos", "vos", "leurs",
        "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
        "me", "te", "se", "lui", "y", "en", "qui", "que", "quoi", "dont", "ou",
        "et", "mais", "or", "ni", "car", "donc", "si", "ne", "pas", "plus",
        "tres", "bien", "mal", "peu", "trop", "tout", "tous", "toute", "toutes",
        "autre", "autres", "meme", "memes", "tel", "telle", "tels", "telles",
        "quel", "quelle", "quels", "quelles", "chaque", "aucun", "aucune",
        "certain", "certaine", "certains", "certaines", "plusieurs",
        "paris", "lyon", "marseille", "lille", "nantes", "bordeaux",
        "toulouse", "rennes", "nice", "strasbourg", "montpellier",
        "france", "europe",
        "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
        "janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
        "aout", "septembre", "octobre", "novembre", "decembre",
        "saint", "sainte", "saints", "rue", "avenue", "boulevard", "place",
        "route", "chemin", "impasse", "allee", "parc", "pont", "port", "gare",
        "mairie", "ecole", "college", "lycee", "hopital", "clinique", "centre",
        "service", "direction", "groupe", "societe", "entreprise", "cabinet",
        "agence", "association", "syndicat", "comite", "conseil", "region",
        "departement", "ville", "commune", "village", "quartier", "zone",
        "maison", "appartement", "etage", "porte", "bureau", "salle", "chambre",
        "cuisine", "jardin", "garage", "cave", "grenier", "toit", "mur",
        "eau", "gaz", "electricite", "chauffage", "internet", "telephone",
        "mail", "email", "message", "courrier", "lettre", "colis", "facture",
        "devis", "contrat", "dossier", "document", "fichier", "page", "note",
        "avis", "rapport", "bilan", "compte", "rendu", "proces", "verbal",
        "acte", "titre", "carte", "attestation", "certificat", "ordonnance",
        "feuille", "soins", "maladie", "sante", "travail", "arret", "conge",
    }
    EXTRA_WORD_COLLISIONS: Set[str] = {
        "vacances", "ferie", "jour", "nuit", "matin", "midi", "soir", "heure",
        "minute", "seconde", "semaine", "mois", "annee", "date", "periode",
        "debut", "fin", "suite", "retour", "envoi", "reception", "reponse",
        "demande", "accord", "refus", "urgent", "important", "info", "infos",
        "contact", "accueil", "secretariat", "client", "clients", "partenaire",
        "projet", "reunion", "point", "suivi", "action", "liste", "tableau",
        "prix", "tarif", "montant", "total", "somme", "euro", "euros", "payer",
        "reglement", "virement", "cheque", "banque", "assurance", "mutuelle",
        "caisse", "impot", "impots", "taxe", "taxes", "prime", "aide", "aides",
        "enfant", "enfants", "bebe", "fils", "fille", "pere", "mere", "parent",
        "parents", "famille", "frere", "soeur", "oncle", "tante", "cousin",
        "cousine", "grand", "petit", "jeune", "vieux", "nouveau", "ancien",
        "bon", "bonne", "bons", "bonnes", "mauvais", "mauvaise", "beau", "belle",
        "blanc", "blanche", "noir", "noire", "rouge", "bleu", "bleue", "vert",
        "verte", "jaune", "gris", "grise", "rose", "marron", "orange", "violet",
        "nord", "sud", "est", "ouest", "haut", "bas", "droite", "gauche",
        "merci", "bonjour", "bonsoir", "salut", "coucou", "bravo", "felicitations",
        "desole", "desolee", "excuse", "pardon", "oui", "non", "peut", "etre",
        "avoir", "faire", "aller", "venir", "voir", "savoir", "pouvoir", "vouloir",
        "devoir", "falloir", "prendre", "donner", "mettre", "passer", "rester",
        "tenir", "porter", "parler", "aimer", "trouver", "chercher", "attendre",
        "repondre", "ecrire", "lire", "comprendre", "connaitre", "croire",
        "penser", "sentir", "vivre", "partir", "sortir", "entrer", "monter",
        "descendre", "tomber", "ouvrir", "fermer", "commencer", "finir",
        "continuer", "changer", "garder", "laisser", "montrer", "demander",
        "essayer", "utiliser", "aider", "jouer", "manger", "boire", "dormir",
        "courir", "marcher", "conduire", "voyager", "acheter", "vendre",
        "choisir", "decider", "expliquer", "proposer", "accepter", "refuser",
        "oublier", "rappeler", "verifier", "controler", "valider", "signer",
        "annuler", "modifier", "supprimer", "ajouter", "creer", "produire",
        "envoyer", "recevoir", "partager", "publier", "afficher", "cacher",
        "masquer", "proteger", "sauvegarder", "restaurer", "copier", "coller",
        "couper", "imprimer", "scanner", "telecharger", "installer",
        "configurer", "tester", "corriger", "resoudre", "ameliorer", "optimiser",
        "fiers", "fier", "fiere", "fieres",
    }
    def __init__(self, config: PipelineConfig, manual_only: bool = False) -> None:
        self.config: PipelineConfig = config
        self.manual_only: bool = manual_only
        self.email_to_alias: Dict[str, str] = {}
        self.target_phones: Dict[str, str] = {}
        self.keyword_to_alias: Dict[str, str] = {}
        self.manual_keywords: Set[str] = set()
        self.extra_sensitive_dates: Set[str] = set()
        self.auto_surnames: Dict[str, str] = {}
        self.auto_first_names: Set[str] = set()
        self.last_name_to_aliases: Dict[str, Set[str]] = {}
        self.last_name_display: Dict[str, str] = {}
        self.learned_first_names: Set[str] = set()
        self.full_targets: Set[str] = set()
        self.alias_words: Set[str] = {"contact", "mail", "tel", "sms", "chat", "pseudo", "email"}

    def is_first_name(self, token: str) -> bool:
        norm: str = DocumentTextUtils.normalize_word(token)
        if not norm:
            return False
        if norm in self.config.known_first_names or norm in self.learned_first_names:
            return True
        if "-" in norm:
            parts: List[str] = [p for p in norm.split("-") if p]
            return bool(parts) and all(
                p in self.config.known_first_names or p in self.learned_first_names
                for p in parts
            )
        return False

    @staticmethod
    def is_one_edit_away(word_a: str, word_b: str) -> bool:
        a: str = DocumentTextUtils.normalize_word(word_a)
        b: str = DocumentTextUtils.normalize_word(word_b)
        if not a or not b or abs(len(a) - len(b)) > 1:
            return False
        if a == b:
            return True
        if len(a) == len(b):
            return sum(1 for ca, cb in zip(a, b) if ca != cb) == 1
        shorter, longer = (a, b) if len(a) < len(b) else (b, a)
        i = j = diffs = 0
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
    def _is_safe_auto_surname(self, norm_word: str) -> bool:
        if not norm_word or len(norm_word) < 4:
            return False
        if norm_word in self.COMMON_WORD_COLLISIONS or norm_word in self.EXTRA_WORD_COLLISIONS:
            return False
        if norm_word in self.config.known_first_names or norm_word in self.config.excluded_words:
            return False
        if norm_word in self.config.surname_collisions or norm_word in self.config.masked_locations:
            return False
        return True

    def _register_alias_tokens(self, alias: str) -> None:
        for tok in re.split(r"[^A-Za-zÀ-ÿ0-9]+", alias or ""):
            nw: str = DocumentTextUtils.normalize_word(tok)
            if len(nw) >= 2:
                self.alias_words.add(nw)

    def _register_auto_surname_from_pair(self, target: str, alias: str) -> None:
        if "@" in target:
            local_part, _ = target.split("@", 1)
            parts: List[str] = [p for p in re.split(r"[._\-]+", local_part.lower()) if p.isalpha()]
            alias_clean: str = re.sub(r"\([^)]*\)", "", alias).strip()
            alias_tokens: List[str] = [t for t in alias_clean.split() if t]
            if len(parts) >= 2 and len(alias_tokens) >= 2:
                first_tok: str = DocumentTextUtils.normalize_word(next(iter(parts)))
                last_tok: str = DocumentTextUtils.normalize_word(parts[-1])
                alias_last_init: str = DocumentTextUtils.normalize_word(alias_tokens[-1])
                if (
                    first_tok in self.config.known_first_names
                    and len(alias_last_init) == 1
                    and last_tok.startswith(alias_last_init)
                    and self._is_safe_auto_surname(last_tok)
                ):
                    self.auto_first_names.add(first_tok)
                    self.learned_first_names.add(first_tok)
                    self.auto_surnames.setdefault(last_tok, f"{last_tok[:1].upper()}.")
                    self.last_name_to_aliases.setdefault(last_tok, set()).add(alias)
                    self.last_name_display.setdefault(last_tok, parts[-1].capitalize())
            return

        words: List[str] = [w for w in re.split(r"[\s\-]+", target.strip()) if w]
        if len(words) < 2:
            return
        w_first: str = DocumentTextUtils.normalize_word(next(iter(words)))
        w_last: str = DocumentTextUtils.normalize_word(words[-1])
        if w_first in self.config.known_first_names and self._is_safe_auto_surname(w_last):
            self.auto_first_names.add(w_first)
            self.learned_first_names.add(w_first)
            self.auto_surnames.setdefault(w_last, f"{w_last[:1].upper()}.")
            self.last_name_to_aliases.setdefault(w_last, set()).add(alias)
            self.last_name_display.setdefault(w_last, words[-1].capitalize())
        elif w_last in self.config.known_first_names and self._is_safe_auto_surname(w_first):
            self.auto_first_names.add(w_last)
            self.learned_first_names.add(w_last)
            self.auto_surnames.setdefault(w_first, f"{w_first[:1].upper()}.")
            self.last_name_to_aliases.setdefault(w_first, set()).add(alias)
            self.last_name_display.setdefault(w_first, next(iter(words)).capitalize())
    def _build_glued_ocr_compounds(self) -> None:
        if not self.auto_surnames:
            return
        firsts = set(self.auto_first_names) | {
            fn for fn in self.config.known_first_names
            if len(fn) >= 4 and fn not in self.COMMON_WORD_COLLISIONS and fn not in self.EXTRA_WORD_COLLISIONS
        }
        for norm_sur, sur_alias in self.auto_surnames.items():
            if len(norm_sur) < 4:
                continue
            for fn in firsts:
                if len(fn) >= 4:
                    cap = fn.capitalize()
                    self.keyword_to_alias.setdefault(f"{fn}{norm_sur}", f"{cap} {sur_alias}")
                    self.keyword_to_alias.setdefault(f"{norm_sur}{fn}", f"{sur_alias} {cap}")

    def _load_file_rules(
        self, file_path: str, is_manual: bool = False,
        extract_auto_surnames: bool = False, override_existing: bool = False,
    ) -> None:
        if not file_path or not os.path.exists(file_path):
            return
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f_in:
                for raw_line in f_in:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    target, alias, _ = DocumentTextUtils.resolve_contact_pair(*line.split("=", 1))
                    if not target or not alias:
                        continue
                    self._register_alias_tokens(alias)
                    if alias == "[DATE_MASQUEE]":
                        self.extra_sensitive_dates.add(target)
                        continue
                    if "@" in target:
                        nm = DocumentTextUtils.normalize_identifier(target)
                        if nm and (is_manual or override_existing or nm not in self.email_to_alias):
                            self.email_to_alias[nm] = alias
                        if nm:
                            self.full_targets.add(nm)
                        if extract_auto_surnames:
                            self._register_auto_surname_from_pair(target, alias)
                        continue
                    nt = DocumentTextUtils.normalize_any_phone(target)
                    if nt:
                        self.full_targets.add(nt)
                        if is_manual or override_existing or nt not in self.target_phones:
                            self.target_phones[nt] = alias
                        continue
                    nkw = DocumentTextUtils.normalize_word(target)
                    if len(nkw) <= 2:
                        continue
                    self.full_targets.add(nkw)
                    if not is_manual and (nkw in self.COMMON_WORD_COLLISIONS or nkw in self.EXTRA_WORD_COLLISIONS):
                        continue
                    if is_manual or override_existing or nkw not in self.keyword_to_alias:
                        self.keyword_to_alias[nkw] = alias
                    if is_manual:
                        self.manual_keywords.add(nkw)
                    if extract_auto_surnames:
                        self._register_auto_surname_from_pair(target, alias)
        except OSError:
            pass

    def load_all(self) -> bool:
        for d in (self.email_to_alias, self.target_phones, self.keyword_to_alias, self.manual_keywords, self.extra_sensitive_dates, self.auto_surnames, self.auto_first_names, self.last_name_to_aliases, self.last_name_display, self.learned_first_names, self.full_targets):
            d.clear()
        self.alias_words = {"contact", "mail", "tel", "sms", "chat", "pseudo", "email"}
        if self.manual_only:
            self._load_file_rules(self.config.manual_contacts_file, is_manual=True)
            return True
        self._load_file_rules(self.config.contacts_file, is_manual=False, extract_auto_surnames=True)
        c_dir = os.path.dirname(self.config.contacts_file) if self.config.contacts_file else ""
        r_dir = getattr(self.config, "root_dir", "") or ""
        cands = [v for k, v in vars(self.config).items() if isinstance(v, str) and "discovered" in k.lower()] + [
            os.path.join(b, fn) for b in (c_dir, os.path.join(r_dir, "output_contacts") if r_dir else "")
            if b for fn in ("discovered_email_contacts.txt", "discovered_chat_contacts.txt")
        ]
        for p in dict.fromkeys(cands):
            if p and os.path.exists(p):
                self._load_file_rules(p, is_manual=False, override_existing=True)
        self._load_file_rules(self.config.manual_contacts_file, is_manual=True)
        self._build_glued_ocr_compounds()
        return True
