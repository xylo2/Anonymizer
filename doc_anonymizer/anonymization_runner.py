# Commandes pip à exécuter : Aucune dépendance externe requise

import hashlib
import os
import re
import time
from typing import Dict, List, Optional, Pattern, Set, Tuple
from doc_anonymizer.audit_state_manager import AuditAndStateManager
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_rules_loader import ContactRulesLoader
from doc_anonymizer.manual_contacts_importer import AuditManualContactsImporter
from doc_anonymizer.source_mapping_manager import SourceMappingManager
from doc_anonymizer.text_utils import DocumentTextUtils


class DocumentAnonymizationRunner:
    """
    Moteur d'anonymisation de niveau 3+ avec découpage par lots (batch_XX),
    masquage contextuel multi-passes, compteur de statistiques et audit continu.
    """

    SAFE_UPPER_WORDS = frozenset({
        "LE", "LA", "LES", "UN", "UNE", "DES", "DU", "AU", "AUX",
        "DE", "DANS", "SUR", "SOUS", "PAR", "POUR", "AVEC", "SANS",
        "CHEZ", "VERS", "ENTRE", "EST", "SONT", "ET", "OU", "MAIS",
        "DONC", "OR", "NI", "CAR", "QUE", "QUI", "QUOI", "DONT",
        "CE", "CET", "CETTE", "CES", "MON", "TON", "SON", "NOTRE",
        "VOTRE", "LEUR", "JE", "TU", "IL", "ELLE", "NOUS", "VOUS",
        "ILS", "ELLES", "ON", "NE", "PAS", "PLUS", "TRES", "BIEN",
        "MAL", "TOUT", "TOUS", "TOUTE", "TOUTES", "AUCUN", "CHAQUE",
        "AUTRE", "MEME", "TEL", "QUEL", "QUELLE", "VOIR", "FAIRE",
        "DIRE", "ALLER", "AVOIR", "ETRE", "POUVOIR", "VOULOIR",
        "DEVOIR", "SAVOIR", "FALLOIR", "VALOIR", "PRENDRE", "DONNER",
        "METTRE", "PASSER", "RESTER", "TENIR", "VENIR", "PARTIR",
        "SORTIR", "ENTRER", "MONTER", "DESCENDRE", "TOMBER", "VIVRE",
        "MOURIR", "NAITRE", "CONNAITRE", "PARAITRE", "CROIRE", "PENSER",
        "AIMER", "TROUVER", "CHERCHER", "ATTENDRE", "ENTENDRE", "REPONDRE",
        "RENDRE", "PERDRE", "VENDRE", "BATTRE", "SUIVRE", "LIRE", "ECRIRE",
        "RIRE", "SOURIRE", "PLEURER", "DORMIR", "MANGER", "BOIRE", "COURIR",
        "MARCHER", "JOUER", "CHANTER", "DANSER", "TRAVAILLER", "ETUDIER",
        "APPRENDRE", "COMPRENDRE", "EXPLIQUER", "MONTRER", "OUVRIR", "FERMER",
        "COMMENCER", "FINIR", "CONTINUER", "ARRETER", "CHANGER", "GARDER",
        "LAISSER", "PORTER", "APPELER", "DEMANDER", "PARLER", "ECOUTER",
        "REGARDER", "SENTIR", "TOUCHER", "GOUTER", "ACHETER", "PAYER",
        "COUTER", "GAGNER", "DEPENSER", "ECONOMISER", "PRETER", "EMPRUNTER",
        "LOUER", "VOYAGER", "VISITER", "ARRIVER", "RETOURNER", "REVENIR",
        "DATE", "OBJET", "SUJET", "PIECE", "JOINTE", "PJ", "URGENT",
        "IMPORTANT", "NOTE", "NOTES", "AVIS", "RAPPORT", "BILAN", "COMPTE",
        "RENDU", "SYNTHESE", "RESUME", "CONCLUSION", "SUITE", "FIN",
        "DEBUT", "TOTAL", "SOUS", "HORS", "TAXE", "TTC", "TVA", "HT",
        "EURO", "EUROS", "FRANC", "FRANCS", "CENTIME", "CENTIMES",
        "LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI", "SAMEDI", "DIMANCHE",
        "JANVIER", "FEVRIER", "MARS", "AVRIL", "MAI", "JUIN", "JUILLET",
        "AOUT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DECEMBRE",
        "NORD", "SUD", "EST", "OUEST", "CENTRE", "FRANCE", "PARIS",
        "LYON", "MARSEILLE", "BORDEAUX", "LILLE", "NANTES", "TOULOUSE",
        "STRASBOURG", "RENNES", "CAEN", "ROUEN", "LE", "HAVRE",
        "TEL", "FAX", "GSM", "PORT", "MAIL", "EMAIL", "WEB", "SITE",
        "HTTP", "HTTPS", "WWW", "COM", "ORG", "NET", "FR", "EU",
        "PDF", "DOC", "DOCX", "XLS", "XLSX", "PPT", "PPTX", "TXT",
        "JPG", "JPEG", "PNG", "GIF", "MP3", "MP4", "WAV", "AVI",
        "ZIP", "RAR", "7Z", "TAR", "GZ", "ISO", "EXE", "DLL",
        "OK", "OUI", "NON", "SI", "BONJOUR", "BONSOIR", "SALUT",
        "MERCI", "CORDIALEMENT", "SINCEREMENT", "AMICALEMENT", "BISOUS",
        "A+", "RAS", "NC", "ND", "NR", "NA", "NB", "PS", "PPS",
        "REF", "NO", "NUM", "CODE", "ID", "IBAN", "BIC", "RIB",
        "NIR", "SS", "SECU", "CAF", "CPAM", "MSA", "ARS", "MDPH",
        "CHU", "CHR", "CMP", "CATTP", "HDJ", "IME", "IMPRO", "SESSAD",
        "CAMSP", "PMI", "ASE", "PJJ", "JAF", "JE", "TGI", "TJ",
        "AVOCAT", "JUGE", "GREFFIER", "HUISSIER", "NOTAIRE", "EXPERT",
        "MEDECIN", "DOCTEUR", "DR", "PR", "PROFESSEUR", "INFIRMIER",
        "INFIRMIERE", "IDE", "KINE", "ORTHO", "PSY", "PSYCHOLOGUE",
        "PSYCHIATRE", "PEDIATRE", "GENERALISTE", "SPECIALISTE",
        "MME", "MADAME", "MR", "MONSIEUR", "MLLE", "MADEMOISELLE",
        "FAMILLE", "PARENT", "PARENTS", "PERE", "MERE", "PAPA", "MAMAN",
        "FILS", "FILLE", "FRERE", "SOEUR", "ONCLE", "TANTE", "COUSIN",
        "COUSINE", "GRAND", "PETIT", "ENFANT", "ENFANTS", "BEBE",
        "ECOLE", "COLLEGE", "LYCEE", "CLASSE", "CP", "CE1", "CE2",
        "CM1", "CM2", "SIXIEME", "CINQUIEME", "QUATRIEME", "TROISIEME",
        "SECONDE", "PREMIERE", "TERMINALE", "BAC", "BREVET", "DIPLOME",
        "MAISON", "APPARTEMENT", "RUE", "AVENUE", "BOULEVARD", "PLACE",
        "IMPASSE", "CHEMIN", "ROUTE", "ALLEE", "SQUARE", "QUAI",
        "VILLE", "VILLAGE", "QUARTIER", "CANTON", "COMMUNE",
        "VOITURE", "TRAIN", "BUS", "METRO", "AVION", "VELO",
        "MATIN", "MIDI", "APRES", "SOIR", "NUIT", "JOUR", "SEMAINE",
        "MOIS", "AN", "ANNEE", "HEURE", "MINUTE", "SECONDE",
        "AUJOURDHUI", "HIER", "DEMAIN", "MAINTENANT", "TOUJOURS",
        "JAMAIS", "SOUVENT", "PARFOIS", "RAREMENT", "ENCORE", "DEJA",
        "TROP", "ASSEZ", "PEU", "BEAUCOUP", "MOINS", "AUTANT",
        "SOL", "MER", "TERRE", "CIEL", "EAU", "FEU", "AIR",
        "A", "M", "L", "S", "C", "N", "T", "D", "J", "Y",
    })
    VERBS_AND_PRONOUNS_FOLLOWING_FIRSTNAME = frozenset({
        "a", "as", "ai", "ont", "avait", "avaient", "aura", "auront",
        "est", "es", "suis", "sont", "etait", "etaient", "sera", "seront",
        "fait", "font", "faisait", "fera", "va", "vas", "vont", "allait",
        "ira", "peut", "peuvent", "pouvait", "veut", "veulent", "voulait",
        "doit", "doivent", "devait", "sait", "savent", "savait", "dit",
        "disent", "disait", "prend", "prennent", "prenait", "donne",
        "donnent", "donnait", "met", "mettent", "mettait", "passe",
        "passent", "passait", "reste", "restent", "restait", "tient",
        "vient", "viennent", "venait", "part", "partent", "partait",
        "sort", "entre", "monte", "descend", "tombe", "vit", "connait",
        "parait", "croit", "pense", "aime", "trouve", "cherche", "attend",
        "entend", "repond", "rend", "perd", "vend", "suit", "lit", "ecrit",
        "rit", "pleure", "dort", "mange", "boit", "court", "marche", "joue",
        "chante", "travaille", "etudie", "apprend", "comprend", "explique",
        "montre", "ouvre", "ferme", "commence", "finit", "continue",
        "arrete", "change", "garde", "laisse", "porte", "appelle", "demande",
        "parle", "ecoute", "regarde", "sent", "touche", "achete", "paie",
        "gagne", "depense", "voyage", "visite", "arrive", "retourne",
        "revient", "manque", "telephoner", "telephone", "ecrire", "repondre",
        "lui", "leur", "le", "la", "les", "me", "te", "se", "nous", "vous",
        "en", "y", "ne", "pas", "plus", "bien", "mal", "trop", "tres",
        "aussi", "encore", "deja", "toujours", "jamais", "souvent", "parfois",
        "avec", "sans", "pour", "dans", "sur", "sous", "chez", "vers",
        "et", "ou", "mais", "donc", "car", "que", "qui", "quoi", "dont",
    })

    CASE_SENSITIVE_LOCATIONS = frozenset({
        "rots", "ifs", "boulon", "clin", "orge", "aire", "sens", "nice", "pau", "auch",
    })

    def __init__(self, config: PipelineConfig, manual_only: bool = False) -> None:
        self.config: PipelineConfig = config
        self.manual_only: bool = manual_only
        self.rules: ContactRulesLoader = ContactRulesLoader(config, manual_only=manual_only)
        self.audit: AuditAndStateManager = AuditAndStateManager(config, self.rules)
        self.source_mapper: SourceMappingManager = SourceMappingManager(config)

        self.dynamic_tokens: Dict[str, str] = {}
        self.email_counter: int = 1
        self.phone_counter: int = 1

        self.current_chunk: List[str] = []
        self.current_chunk_keys: List[str] = []
        self.current_size: int = 0
        self.processed_in_session: int = 0
        self._active_stats: Optional[Dict[str, int]] = None

        self.regex_compiled: bool = False
        self.fast_replacer_regex: Optional[Pattern[str]] = None
        self.fast_replacer_map: Dict[str, str] = {}
        self.title_last_name_regex: Optional[Pattern[str]] = None
        self.title_first_last_regex: Optional[Pattern[str]] = None
        self.auto_first_last_regex: Optional[Pattern[str]] = None
        self.auto_last_first_regex: Optional[Pattern[str]] = None
        self.locations_regex: Optional[Pattern[str]] = None

    def set_skipped_zips(self, skipped_zips: List[str]) -> None:
        """Enregistre la liste des archives ZIP ignorées pour le tableau de bord."""
        self.audit.stats["zip_ignores"] = list(skipped_zips)

    def _bump_stat(self, key: str, count: int = 1) -> None:
        """Incrémente un compteur de statistique d'anonymisation si actif."""
        if self._active_stats is not None and count > 0:
            self._active_stats[key] = self._active_stats.get(key, 0) + count

    def initialize(self) -> bool:
        if not self.rules.load_all():
            return False
        self.audit.load()
        self.source_mapper.load()
        self._sync_dynamic_counters()
        self._compile_patterns()
        print(
            f"[INIT ANONYMIZER] État chargé : {len(self.audit.already_processed)} "
            f"fichier(s) déjà traité(s), prochain index de lot = {self.audit.file_idx}.",
            flush=True,
        )
        return True
    def _sync_dynamic_counters(self) -> None:
        for token in self.dynamic_tokens.values():
            if token.startswith("EMAIL_"):
                try:
                    self.email_counter = max(self.email_counter, int(token.split("_")[-1]) + 1)
                except (ValueError, IndexError):
                    pass
            elif token.startswith("TEL_"):
                try:
                    self.phone_counter = max(self.phone_counter, int(token.split("_")[-1]) + 1)
                except (ValueError, IndexError):
                    pass

    def _get_or_create_token(self, raw_val: str, prefix: str) -> str:
        norm: str = DocumentTextUtils.normalize_identifier(raw_val) or raw_val.strip().lower()
        key: str = f"{prefix}:{norm}"
        if key in self.dynamic_tokens:
            return self.dynamic_tokens[key]
        if prefix == "EMAIL":
            token: str = f"EMAIL_{self.email_counter:03d}"
            self.email_counter += 1
        else:
            token = f"TEL_{self.phone_counter:03d}"
            self.phone_counter += 1
        self.dynamic_tokens[key] = token
        return token

    def _compile_patterns(self) -> None:
        self.fast_replacer_map = {}
        raw_targets: List[str] = []
        for target, alias in self.rules.keyword_to_alias.items():
            clean_t: str = target.strip()
            if not clean_t or not alias:
                continue
            norm_t: str = DocumentTextUtils.normalize_word(clean_t)
            if len(norm_t) <= 2 or norm_t.upper() in self.SAFE_UPPER_WORDS:
                continue
            self.fast_replacer_map[norm_t] = alias
            raw_targets.append(clean_t)

        if raw_targets:
            sorted_targets: List[str] = sorted(
                set(raw_targets), key=lambda s: (-len(s), s.lower())
            )
            patterns: List[str] = [
                "".join(DocumentTextUtils._char_to_ocr_regex(ch) for ch in t)
                for t in sorted_targets
            ]
            self.fast_replacer_regex = re.compile(
                rf"(?<![A-Za-zÀ-ÿ0-9])(?:{'|'.join(patterns)})(?![A-Za-zÀ-ÿ0-9])",
                re.IGNORECASE,
            )

        all_dates: List[str] = list(self.config.masked_birth_dates) + sorted(
            self.rules.extra_sensitive_dates
        )
        if all_dates:
            self.config.custom_birth_date_pattern = (
                PipelineConfig._compile_custom_dates_pattern(all_dates)
            )

        titles_pat: str = (
            r"(?:Dr\.?|Docteur|Pr\.?|Professeur|Me\.?|Ma[îi]tre|Mme\.?|Madame|"
            r"Mlle\.?|Mademoiselle|M\.|Mr\.?|Monsieur|Famille)"
        )
        cap_word: str = r"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-]+"
        upper_word: str = r"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]+"
        part_upper: str = rf"(?:DE|DU|DES|LE|LA|LES|{upper_word})"
        upper_surname: str = rf"{upper_word}(?:[\s\-]{part_upper})?(?:[\s\-]{part_upper})?"
        self.title_first_last_regex = re.compile(
            rf"(?<![A-Za-zÀ-ÿ0-9])({titles_pat})[ \t]+({cap_word}[ \t\-]{cap_word}|{cap_word})[ \t]+({cap_word})(?![A-Za-zÀ-ÿ0-9])"
        )
        self.title_last_name_regex = re.compile(
            rf"(?<![A-Za-zÀ-ÿ0-9])({titles_pat})[ \t]*({cap_word})(?![A-Za-zÀ-ÿ0-9])"
        )
        self.auto_first_double_upper_regex = re.compile(
            rf"(?<![A-Za-zÀ-ÿ0-9])({cap_word})[ \t]+({upper_word})[ \t]+({upper_word})(?![A-Za-zÀ-ÿ0-9])"
        )
        self.auto_first_last_regex = re.compile(
            rf"(?<![A-Za-zÀ-ÿ0-9])(?:({cap_word}[ \t]+{cap_word})[ \t]+({cap_word})|({cap_word})[ \t_]+({cap_word}))(?![A-Za-zÀ-ÿ0-9])(?![ \t]+[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]\.)"
        )
        self.auto_last_first_regex = re.compile(
            rf"(?<![A-Za-zÀ-ÿ0-9])({upper_surname})[ \t_]+({cap_word}(?:[\-]{cap_word})?)(?![A-Za-zÀ-ÿ0-9])"
        )
        self.initial_last_name_regex = re.compile(
            rf"(?<![A-Za-zÀ-ÿ0-9])([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ])\.[ \t]*({cap_word})(?![A-Za-zÀ-ÿ0-9])"
        )
        extra_cs_locs: Set[str] = set(self.CASE_SENSITIVE_LOCATIONS) | {
            "fiers", "fier", "fiere", "fieres", "vers", "car", "bon", "fort",
            "clair", "claire", "grand", "petit", "haut", "bas", "saint", "sainte",
            "mont", "val", "pont", "port", "bois", "champ", "champs", "cour",
            "cours", "tour", "tours", "forge", "forges", "roche", "roches",
            "pierre", "pierres", "croix", "eglise", "chapelle", "moulin",
            "chateau", "parc", "lac", "mer", "ile", "iles", "cap", "baie",
            "plage", "dune", "dunes", "lande", "landes", "plaine", "vallee",
            "col", "pic", "puy", "roc", "saut", "pas", "garde", "bastide",
            "maison", "maisons", "grange", "granges", "ferme", "fermes",
            "clos", "pre", "pres", "prat", "mas", "fresnes", "aulnay", "ormes",
            "tilleuls", "chenes", "pins", "sapins", "saules", "peupliers",
            "bouleaux", "noyers", "pommiers", "cerisiers", "vignes", "roses", "lilas",
        }
        safe_locs: List[str] = sorted(
            loc
            for loc in self.config.masked_locations
            if len(loc) >= 3 and loc not in self.config.excluded_words
        )
        if safe_locs:
            ci_locs: List[str] = [loc for loc in safe_locs if loc not in extra_cs_locs]
            cs_locs: List[str] = [loc for loc in safe_locs if loc in extra_cs_locs]
            loc_branches: List[str] = []
            if ci_locs:
                ci_trie: str = DocumentTextUtils.build_ocr_tolerant_trie_regex(ci_locs)
                if ci_trie:
                    loc_branches.append(f"(?i:{ci_trie})")
            for cs_word in cs_locs:
                cap_form: str = re.escape(cs_word.capitalize())
                up_form: str = re.escape(cs_word.upper())
                loc_branches.append(f"(?:{cap_form}|{up_form})")
            if loc_branches:
                self.locations_regex = re.compile(
                    rf"(?<![A-Za-zÀ-ÿ0-9])(?:{'|'.join(loc_branches)})(?![A-Za-zÀ-ÿ0-9])"
                )
        self.regex_compiled = True

    def _is_known_first_name(self, token: str) -> bool:
        norm: str = DocumentTextUtils.normalize_word(token)
        if not norm:
            return False
        if self.rules.is_first_name(token):
            return True
        if "-" in norm:
            hyphen_parts: List[str] = [p for p in norm.split("-") if p]
            if len(hyphen_parts) >= 2 and self.rules.is_first_name(next(iter(hyphen_parts))):
                return True
        sub_tokens: List[str] = [p for p in re.split(r"[\s_]+", norm) if p]
        if len(sub_tokens) == 2:
            first_sub: str = next(iter(sub_tokens))
            second_sub: str = sub_tokens[-1]
            if (
                self._is_known_first_name(first_sub)
                and second_sub not in self.config.excluded_words
                and second_sub not in self.config.masked_locations
            ):
                return True
        if not self.config.known_first_names:
            return len(norm) >= 2 and norm not in self.config.masked_locations
        return False

    def _replace_fast_target(self, match: re.Match) -> str:
        raw: str = match.group(0)
        norm: str = DocumentTextUtils.normalize_word(raw)
        if norm in self.fast_replacer_map:
            self._bump_stat("noms_masques")
            return self.fast_replacer_map[norm]
        return raw

    def _replace_title_first_last(self, match: re.Match) -> str:
        title: str = match.group(1)
        firsts: str = match.group(2)
        last: str = match.group(3)
        norm_last: str = DocumentTextUtils.normalize_word(last)
        if norm_last.upper() in self.SAFE_UPPER_WORDS or norm_last in self.config.excluded_words:
            return match.group(0)
        first_tokens: List[str] = [t for t in re.split(r"[\s\-]+", firsts) if t]
        if first_tokens and self._is_known_first_name(next(iter(first_tokens))):
            self._bump_stat("noms_masques")
            if len(first_tokens) >= 2 and " " in firsts:
                first_kept: str = next(iter(first_tokens))
                mid_initials: str = " ".join(f"{p[:1].upper()}." for p in first_tokens[1:])
                return f"{title} {first_kept} {mid_initials} {last[:1].upper()}."
            return f"{title} {firsts} {last[:1].upper()}."
        return match.group(0)

    def _replace_title_last_name(self, match: re.Match) -> str:
        title: str = match.group(1)
        last: str = match.group(2)
        norm_last: str = DocumentTextUtils.normalize_word(last)
        if (
            norm_last.upper() in self.SAFE_UPPER_WORDS
            or norm_last in self.config.excluded_words
            or norm_last in self.config.surname_collisions
            or norm_last in self.config.masked_locations
            or self._is_known_first_name(last)
        ):
            return match.group(0)
        self._bump_stat("noms_masques")
        return f"{title} {last[:1].upper()}."
    def _replace_auto_first_double_upper(self, match: re.Match) -> str:
        first: str = match.group(1)
        last1: str = match.group(2)
        last2: str = match.group(3)
        if not self._is_known_first_name(first):
            return match.group(0)
        for lp in (last1, last2):
            norm_lp: str = DocumentTextUtils.normalize_word(lp)
            if (
                norm_lp.upper() in self.SAFE_UPPER_WORDS
                or norm_lp in self.config.excluded_words
                or norm_lp in self.config.surname_collisions
                or norm_lp in self.config.masked_locations
                or self._is_known_first_name(lp)
            ):
                return match.group(0)
        self._bump_stat("noms_masques")
        return f"{first} {last1[:1].upper()}. {last2[:1].upper()}."

    def _replace_auto_first_last(self, match: re.Match) -> str:
        firsts: str = match.group(1) or match.group(3) or ""
        last: str = match.group(2) or match.group(4) or ""
        sep: str = "_" if "_" in match.group(0) else " "
        norm_last: str = DocumentTextUtils.normalize_word(last)
        if (
            norm_last.upper() in self.SAFE_UPPER_WORDS
            or norm_last in self.config.excluded_words
            or norm_last in self.config.surname_collisions
            or norm_last in self.config.masked_locations
            or norm_last in self.VERBS_AND_PRONOUNS_FOLLOWING_FIRSTNAME
            or self._is_known_first_name(last)
        ):
            return match.group(0)
        if " " in firsts:
            parts: List[str] = [p for p in firsts.split(" ") if p]
            if len(parts) == 2:
                t1, t2 = parts
                if not self._is_known_first_name(t1) and self._is_known_first_name(t2):
                    self._bump_stat("noms_masques")
                    return f"{t1} {t2} {last[:1].upper()}."
        if self._is_known_first_name(firsts):
            self._bump_stat("noms_masques")
            return f"{firsts}{sep}{last[:1].upper()}."
        return match.group(0)

    def _replace_auto_last_first(self, match: re.Match) -> str:
        last_upper: str = match.group(1)
        first: str = match.group(2)
        sep: str = "_" if "_" in match.group(0) else " "
        norm_last: str = DocumentTextUtils.normalize_word(last_upper)
        first_token: str = next(iter(re.split(r"[\s\-]+", first)), first)
        if (
            last_upper in self.SAFE_UPPER_WORDS
            or norm_last in self.config.excluded_words
            or norm_last in self.config.surname_collisions
            or norm_last in self.config.masked_locations
            or self._is_known_first_name(last_upper)
        ):
            return match.group(0)
        if self._is_known_first_name(first_token):
            self._bump_stat("noms_masques")
            return f"{last_upper[:1].upper()}.{sep}{first}"
        return match.group(0)

    def _replace_initial_last_name(self, match: re.Match) -> str:
        initial: str = match.group(1)
        last: str = match.group(2)
        norm_last: str = DocumentTextUtils.normalize_word(last)
        if (
            norm_last.upper() in self.SAFE_UPPER_WORDS
            or norm_last in self.config.excluded_words
            or norm_last in self.config.surname_collisions
            or norm_last in self.config.masked_locations
            or norm_last in self.rules.COMMON_WORD_COLLISIONS
            or self._is_known_first_name(last)
        ):
            return match.group(0)
        self._bump_stat("noms_masques")
        return f"{initial}. {last[:1].upper()}."

    def _replace_email_with_alias(self, match: re.Match) -> str:
        raw_mail: str = match.group(0)
        norm_mail: str = DocumentTextUtils.normalize_identifier(raw_mail)
        self._bump_stat("coordonnees_masquees")
        if norm_mail in self.rules.email_to_alias:
            return self.rules.email_to_alias[norm_mail]
        return self._get_or_create_token(raw_mail, "EMAIL")

    def _replace_phone_with_alias(self, match: re.Match) -> str:
        raw_tel: str = match.group(0)
        cleaned_tel: str = re.sub(r"[\s.\-/,]+", "", raw_tel)
        norm_tel: str = DocumentTextUtils._normalize_fr_phone(cleaned_tel)
        self._bump_stat("coordonnees_masquees")
        if norm_tel and norm_tel in self.rules.target_phones:
            return self.rules.target_phones[norm_tel]
        return self._get_or_create_token(raw_tel, "TEL")
    def anonymize_text(
        self, text: str, stats_collector: Optional[Dict[str, int]] = None
    ) -> str:
        """Applique l'ensemble des passes d'anonymisation et alimente les compteurs."""
        if not text:
            return text
        if not self.regex_compiled:
            self._compile_patterns()

        prev_stats = self._active_stats
        self._active_stats = stats_collector
        try:
            res: str = DocumentTextUtils.repair_mojibake(text)
            if self.manual_only:
                if self.fast_replacer_regex:
                    res = self.fast_replacer_regex.sub(self._replace_fast_target, res)
                return res

            if self.config.mask_financial_and_admin_ids:
                res, n_mrz = re.subn(r"\b[A-Z0-9]{10,}<{2,}[A-Z0-9<]{10,}\b", "[MRZ_IDENTITE_MASQUEE]", res)
                self._bump_stat("identifiants_masques", n_mrz)

            css_stash: List[str] = []

            def _stash_css(m_css: re.Match) -> str:
                idx: int = len(css_stash)
                css_stash.append(m_css.group(0))
                return f"__CSS_ATTR_{idx}__"

            res = re.sub(
                r'\b(?:style|class|width|height|cellpadding|cellspacing|border)\s*=\s*"[^"]*"',
                _stash_css,
                res,
                flags=re.IGNORECASE,
            )
            res = re.sub(r"\b([0-2]\d:[0-5]\d)([A-Za-zÀ-ÿ])", r"\1 \2", res)
            res = re.sub(
                r"\b(SOCIETE|Societe|SOCIÉTÉ|Société|EAEA|IDFRA|DOCTEUR|Docteur|MADAME|Madame|MONSIEUR|Monsieur|MME|Mme|MR|Mr|DR|Dr|MLLE|Mlle|ENFANT|Enfant)"
                r"(?!EYFUS\b)_?([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç\-]{2,})",
                r"\1 \2",
                res,
            )
            res = re.sub(
                r"\b((?:Dr\.?|Docteur|Pr\.?|Professeur|Mme\.?|Madame|M\.|Mr\.?|Monsieur|Mlle\.?|Mademoiselle)"
                r"[ \t]+[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç]{2,})"
                r"([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]{3,25})\b",
                r"\1 \2",
                res,
            )
            res = re.sub(
                r"([a-zéèêëàâäîïôöùûüç]{2,})(par|avec|pour|de|du|des|le|la|les)([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç]{2,})",
                r"\1 \2 \3",
                res,
            )

            if self.config.custom_birth_date_pattern:
                res, n_cd = self.config.custom_birth_date_pattern.subn("[DATE_MASQUEE]", res)
                self._bump_stat("lieux_dates_masques", n_cd)
            res, n_gd = DocumentTextUtils.REGEX_GLUED_PERSON_BIRTH_DATE.subn(r"\1[DATE_MASQUEE]", res)
            res, n_bd = DocumentTextUtils.REGEX_BIRTH_DATE.subn(r"\1[JOUR_MOIS_MASQUES]/\2", res)
            res, n_id_d = DocumentTextUtils.REGEX_ID_DOC_DATES.subn(r"\1[DATE_TITRE_MASQUEE]", res)
            self._bump_stat("lieux_dates_masques", n_gd + n_bd + n_id_d)

            if self.config.mask_financial_and_admin_ids:
                for rx, tag in (
                    (DocumentTextUtils.REGEX_IBAN, "[IBAN_MASQUE]"),
                    (DocumentTextUtils.REGEX_BIC, "[BIC_MASQUE]"),
                    (DocumentTextUtils.REGEX_FISCAL_ID, "[ID_FISCAL_MASQUE]"),
                    (DocumentTextUtils.REGEX_FRANCE_TRAVAIL, "[ID_FT_MASQUE]"),
                    (DocumentTextUtils.REGEX_CAF_ALLOCATAIRE, "[ID_CAF_MASQUE]"),
                    (DocumentTextUtils.REGEX_OFFICIAL_MEDICAL_ID, "[ID_CNI_PERMIS_MASQUE]"),
                    (DocumentTextUtils.REGEX_ISOLATED_12_DIGITS, "[ID_CNI_PERMIS_MASQUE]"),
                    (DocumentTextUtils.REGEX_BANK_TX_AND_CARDS, "[REF_BANCAIRE_TX_MASQUEE]"),
                    (DocumentTextUtils.REGEX_MEETING_IDS, "[ID_REUNION_MASQUE]"),
                    (DocumentTextUtils.REGEX_LICENSE_PLATE, "[PLAQUE_IMMAT_MASQUEE]"),
                    (DocumentTextUtils.REGEX_ACCESS_CODES, "[CODE_ACCES_MASQUE]"),
                    (DocumentTextUtils.REGEX_ADMIN_REFS, "[REF_ADMIN_MASQUEE]"),
                ):
                    res, n_hit = rx.subn(tag, res)
                    self._bump_stat("identifiants_masques", n_hit)
            if self.fast_replacer_regex:
                res = self.fast_replacer_regex.sub(self._replace_fast_target, res)

            if self.config.mask_ssn:
                res, n_s1 = DocumentTextUtils.REGEX_SSN.subn("[NUM_SECU_MASQUE]", res)
                res, n_s2 = DocumentTextUtils.REGEX_SSN_OCR_GLUED.subn("[NUM_SECU_MASQUE]", res)
                self._bump_stat("identifiants_masques", n_s1 + n_s2)
            if self.config.mask_addresses:
                res, n_a1 = DocumentTextUtils.REGEX_STREET_ADDRESS.subn("[ADRESSE_MASQUEE]", res)
                res, n_a2 = DocumentTextUtils.REGEX_POSTAL_CITY.subn("[ADRESSE_MASQUEE]", res)
                res, n_a3 = DocumentTextUtils.REGEX_FACILITIES_AND_ZONES.subn("[ETABLISSEMENT_LIEU_MASQUE]", res)
                self._bump_stat("lieux_dates_masques", n_a1 + n_a2 + n_a3)
            if self.locations_regex:
                res, n_loc = self.locations_regex.subn("[LIEU_MASQUE]", res)
                self._bump_stat("lieux_dates_masques", n_loc)
            if self.title_first_last_regex:
                res = self.title_first_last_regex.sub(self._replace_title_first_last, res)
            if self.title_last_name_regex:
                res = self.title_last_name_regex.sub(self._replace_title_last_name, res)
            if getattr(self, "auto_first_double_upper_regex", None):
                res = self.auto_first_double_upper_regex.sub(self._replace_auto_first_double_upper, res)
            if self.auto_first_last_regex:
                res = self.auto_first_last_regex.sub(self._replace_auto_first_last, res)
            if self.auto_last_first_regex:
                res = self.auto_last_first_regex.sub(self._replace_auto_last_first, res)
            if getattr(self, "initial_last_name_regex", None):
                res = self.initial_last_name_regex.sub(self._replace_initial_last_name, res)
            if self.config.mask_urls:
                res, n_url = DocumentTextUtils.REGEX_URL.subn("[URL_MASQUEE]", res)
                self._bump_stat("coordonnees_masquees", n_url)

            res = DocumentTextUtils.REGEX_EMAIL.sub(self._replace_email_with_alias, res)
            res = DocumentTextUtils.REGEX_PHONE.sub(self._replace_phone_with_alias, res)

            for idx, original_css in enumerate(css_stash):
                res = res.replace(f"__CSS_ATTR_{idx}__", original_css)
            return res
        finally:
            self._active_stats = prev_stats

    def flush_batch(self) -> None:
        if not self.current_chunk:
            return
        folder_num: int = ((self.audit.file_idx - 1) // self.config.files_per_folder) + 1
        batch_folder: str = os.path.join(self.config.results_dir, f"batch_{folder_num:02d}")
        os.makedirs(batch_folder, exist_ok=True)
        out_file: str = os.path.join(
            batch_folder, f"{self.config.file_prefix}part_{self.audit.file_idx:03d}.txt"
        )
        merged_content: str = "".join(self.current_chunk)
        DocumentTextUtils.atomic_write_text(out_file, merged_content)

        self.source_mapper.update_batch_for_keys(self.current_chunk_keys, out_file)
        self.source_mapper.save()

        count: int = self.audit.write_report()
        self.audit.save()
        print(f"    [+] LOT ÉCRIT : '{out_file}' (Audit : {count} nom(s))", flush=True)
        self.audit.file_idx += 1
        self.current_chunk.clear()
        self.current_chunk_keys.clear()
        self.current_size = 0

    def _process_single_file(self, norm_path: str) -> bool:
        try:
            with open(norm_path, "r", encoding="utf-8", errors="ignore") as f_in:
                raw_text: str = f_in.read()
        except OSError as exc:
            print(f"[AVERTISSEMENT] Lecture impossible '{norm_path}' : {exc}", flush=True)
            return False

        file_stats: Dict[str, int] = {}
        anon_text: str = self.anonymize_text(raw_text, stats_collector=file_stats)
        anon_header_path: str = self.anonymize_text(norm_path)
        self.source_mapper.register_entry(
            anonymized_path=anon_header_path,
            extracted_path=norm_path,
            raw_text=raw_text,
        )
        if not self.manual_only:
            self.audit.scan_residual_names(anon_text, norm_path)

        ds = self.audit.stats
        ds["documents_traites"] = int(ds.get("documents_traites", 0)) + 1
        for k in ("noms_masques", "coordonnees_masquees", "identifiants_masques", "lieux_dates_masques"):
            ds[k] = int(ds.get(k, 0)) + file_stats.get(k, 0)

        header: str = (
            f"\n{'#' * 72}\n"
            f"# SOURCE TRANSCRIPTION : {anon_header_path}\n"
            f"{'#' * 72}\n"
        )
        block: str = f"{header}{anon_text}\n"
        block_bytes: int = len(block.encode("utf-8"))

        if self.current_chunk and (
            self.current_size + block_bytes > self.config.max_batch_bytes
            or len(self.current_chunk) >= self.config.max_batch_files
        ):
            self.flush_batch()

        self.current_chunk.append(block)
        self.current_chunk_keys.append(anon_header_path)
        self.current_size += block_bytes
        self.audit.already_processed.add(norm_path)
        self.processed_in_session += 1
        return True

    def anonymize_single_file(
        self, transcription_path: str, force_reprocess: bool = False
    ) -> bool:
        norm_path: str = os.path.normpath(transcription_path)
        if not force_reprocess and norm_path in self.audit.already_processed:
            return False
        return self._process_single_file(norm_path)

    def finalize(self, start_time: float) -> None:
        self.flush_batch()
        count: int = self.audit.write_report()
        self.audit.save()

        if not self.manual_only:
            importer = AuditManualContactsImporter(
                self.config, self.rules, min_occurrences=3
            )
            imported: int = importer.import_high_confidence_from_audit()
            if imported > 0:
                print(
                    f"[AUTO-IMPORT] {imported} règle(s) haute confiance ajoutée(s) "
                    f"dans '{self.config.manual_contacts_file}'.",
                    flush=True,
                )

        elapsed: float = time.time() - start_time
        total_lots: int = max(0, self.audit.file_idx - 1)
        print(
            f"\n[100.0%] Terminé ({self.processed_in_session} fichier(s) anonymisé(s) en {elapsed:.1f}s).\n"
            f" * Lots totaux  : {total_lots} dans '{self.config.results_dir}/batch_XX/'\n"
            f" * Audit détail : {count} nom(s) dans '{self.config.audit_report_file}'\n"
            f" * Audit copier : {count} nom(s) dans '{self.config.audit_copy_file}'",
            flush=True,
        )

    def run(self) -> None:
        t0: float = time.time()
        if not self.initialize():
            return
        os.makedirs(self.config.results_dir, exist_ok=True)
        for root_p, _, files in os.walk(self.config.transcriptions_dir):
            for fname in sorted(files):
                if (
                    fname in {"rapport_extraction.txt", "extraction_report.txt"}
                    or fname.startswith(".")
                    or not fname.lower().endswith(".txt")
                ):
                    continue
                self.anonymize_single_file(os.path.join(root_p, fname))
        self.finalize(t0)

    def run_on_existing_results(self) -> None:
        t0: float = time.time()
        if not self.initialize():
            return
        updated_files: int = 0
        for root_p, _, files in os.walk(self.config.results_dir):
            for fname in sorted(files):
                if not fname.endswith(".txt"):
                    continue
                full_p: str = os.path.join(root_p, fname)
                with open(full_p, "r", encoding="utf-8", errors="ignore") as f_in:
                    content: str = f_in.read()
                new_content: str = self.anonymize_text(content)
                if new_content != content:
                    DocumentTextUtils.atomic_write_text(full_p, new_content)
                    updated_files += 1
        print(
            f"[MANUAL-ONLY] {updated_files} lot(s) mis à jour en {time.time() - t0:.1f}s.",
            flush=True,
        )
