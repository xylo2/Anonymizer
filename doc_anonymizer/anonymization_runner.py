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
from doc_anonymizer.text_utils import DocumentTextUtils


class DocumentAnonymizationRunner:
    """
    Moteur d'anonymisation de niveau 3+ avec découpage par lots (batch_XX),
    masquage contextuel multi-passes et audit continu.
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

    def __init__(self, config: PipelineConfig, manual_only: bool = False) -> None:
        """Initialise le moteur d'anonymisation."""
        self.config: PipelineConfig = config
        self.manual_only: bool = manual_only
        self.rules: ContactRulesLoader = ContactRulesLoader(config, manual_only=manual_only)
        self.audit: AuditAndStateManager = AuditAndStateManager(config, self.rules)

        self.dynamic_tokens: Dict[str, str] = {}
        self.email_counter: int = 1
        self.phone_counter: int = 1

        self.current_chunk: List[str] = []
        self.current_size: int = 0
        self.processed_in_session: int = 0

        self.regex_compiled: bool = False
        self.fast_replacer_regex: Optional[Pattern[str]] = None
        self.fast_replacer_map: Dict[str, str] = {}
        self.title_last_name_regex: Optional[Pattern[str]] = None
        self.title_first_last_regex: Optional[Pattern[str]] = None
        self.auto_first_last_regex: Optional[Pattern[str]] = None
        self.auto_last_first_regex: Optional[Pattern[str]] = None
        self.locations_regex: Optional[Pattern[str]] = None

    def initialize(self) -> bool:
        """Charge les règles, compile les expressions régulières et restaure l'état."""
        if not self.rules.load_all():
            return False
        self.audit.load()
        self._sync_dynamic_counters()
        self._compile_patterns()
        print(
            f"[INIT ANONYMIZER] État chargé : {len(self.audit.already_processed)} "
            f"fichier(s) déjà traité(s), prochain index de lot = {self.audit.file_idx}.",
            flush=True,
        )
        return True

    def _sync_dynamic_counters(self) -> None:
        """Synchronise les compteurs EMAIL_XXX et TEL_XXX avec l'état restauré."""
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
        """Retourne un jeton déterministe EMAIL_XXX ou TEL_XXX pour une coordonnée."""
        norm: str = DocumentTextUtils.normalize_identifier(raw_val) or raw_val.strip().lower()
        key: str = f"{prefix}:{norm}"
        if key in self.dynamic_tokens:
            return self.dynamic_tokens[key]

        digest: str = hashlib.sha256(
            f"{self.config.secret_salt}:{key}".encode("utf-8")
        ).hexdigest()[:6].upper()
        if prefix == "EMAIL":
            token: str = f"EMAIL_{self.email_counter:03d}"
            self.email_counter += 1
        else:
            token = f"TEL_{self.phone_counter:03d}"
            self.phone_counter += 1
        _ = digest
        self.dynamic_tokens[key] = token
        return token
    CASE_SENSITIVE_LOCATIONS = frozenset({
        "rots", "ifs", "boulon", "clin", "orge", "aire", "sens", "nice", "pau", "auch",
    })

    def _compile_patterns(self) -> None:
        """Compile les expressions régulières optimisées sans traverser les sauts de ligne."""
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
                rf"(?<![A-Za-zÀ-ÿ0-9_])(?:{'|'.join(patterns)})(?![A-Za-zÀ-ÿ0-9_])",
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
        cap_word: str = r"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-]{2,25}"
        self.title_first_last_regex = re.compile(
            rf"\b({titles_pat})[ \t]+({cap_word}(?:[ \t\-]{cap_word}){{0,2}})[ \t]+({cap_word})\b"
        )
        self.title_last_name_regex = re.compile(
            rf"\b({titles_pat})[ \t]*({cap_word})\b"
        )
        self.auto_first_last_regex = re.compile(
            rf"\b({cap_word}(?:[ \t\-]{cap_word})?)[ \t]+({cap_word})\b"
        )
        self.auto_last_first_regex = re.compile(
            rf"\b([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]{{3,25}})[ \t]+({cap_word})\b"
        )

        safe_locs: List[str] = sorted(
            loc
            for loc in self.config.masked_locations
            if len(loc) >= 3
            and loc not in self.rules.COMMON_WORD_COLLISIONS
            and loc not in self.config.excluded_words
        )
        if safe_locs:
            ci_locs: List[str] = [
                loc for loc in safe_locs if loc not in self.CASE_SENSITIVE_LOCATIONS
            ]
            cs_locs: List[str] = [
                loc for loc in safe_locs if loc in self.CASE_SENSITIVE_LOCATIONS
            ]
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
                    rf"(?<![A-Za-zÀ-ÿ0-9_])(?:{'|'.join(loc_branches)})(?![A-Za-zÀ-ÿ0-9_])"
                )
        self.regex_compiled = True

    def _replace_fast_target(self, match: re.Match) -> str:
        """Remplace une cible reconnue en ignorant les vrais toponymes composés."""
        matched_text: str = match.group(0)
        full_str: str = match.string
        start_idx: int = match.start()
        end_idx: int = match.end()

        prefix_ctx: str = full_str[max(0, start_idx - 10):start_idx]
        suffix_ctx: str = full_str[end_idx:min(len(full_str), end_idx + 15)]
        if re.search(r"(?i)\b(?:st|ste|saint|sainte)[\s\-]$", prefix_ctx):
            return matched_text
        if re.match(r"^(?i)-(?:de|du|des|sur|sous|en|la|le|les)\b", suffix_ctx):
            return matched_text
        if re.match(r"^\s+(?:sur|sous)\s+[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]", suffix_ctx):
            return matched_text

        norm: str = DocumentTextUtils.normalize_word(matched_text)
        alias: Optional[str] = self.fast_replacer_map.get(norm)
        if alias:
            return alias
        compact: str = re.sub(r"[\s\-'\u2019]+", "", norm)
        for k_norm, val_alias in self.fast_replacer_map.items():
            if re.sub(r"[\s\-'\u2019]+", "", k_norm) == compact:
                return val_alias
        return matched_text
    def _is_known_first_name(self, token: str) -> bool:
        """Vérifie si un jeton est un prénom connu (simple ou composé type Jean-Eudes)."""
        norm: str = DocumentTextUtils.normalize_word(token)
        if not norm or norm.upper() in self.SAFE_UPPER_WORDS or norm in self.config.excluded_words:
            return False
        if self.rules.is_first_name(token):
            return True
        if not self.config.known_first_names:
            return len(norm) >= 2 and norm not in self.config.masked_locations
        return False

    def _replace_title_first_last(self, match: re.Match) -> str:
        """Abrège 'Dr Jean Philippe Bernard' en 'Dr Jean Philippe B.'."""
        title: str = match.group(1)
        firsts: str = match.group(2)
        last: str = match.group(3)
        norm_last: str = DocumentTextUtils.normalize_word(last)
        if (
            norm_last.upper() in self.SAFE_UPPER_WORDS
            or norm_last in self.config.excluded_words
            or norm_last in self.config.masked_locations
            or norm_last in self.VERBS_AND_PRONOUNS_FOLLOWING_FIRSTNAME
        ):
            return match.group(0)
        first_tokens: List[str] = [t for t in re.split(r"[\s\-]+", firsts) if t]
        if first_tokens and self._is_known_first_name(next(iter(first_tokens))):
            return f"{title} {firsts} {last[:1].upper()}."
        return match.group(0)

    def _replace_title_last_name(self, match: re.Match) -> str:
        """Abrège 'Dr Lamotte' ou 'DrLAMOTTE' en 'Dr L.'."""
        title: str = match.group(1)
        last: str = match.group(2)
        norm_last: str = DocumentTextUtils.normalize_word(last)
        if (
            norm_last.upper() in self.SAFE_UPPER_WORDS
            or norm_last in self.config.excluded_words
            or norm_last in self.config.masked_locations
            or self._is_known_first_name(last)
        ):
            return match.group(0)
        return f"{title} {last[:1].upper()}."

    def _replace_auto_first_last(self, match: re.Match) -> str:
        """Abrège 'Charlotte Lemaitre' ou 'Jean-Eudes Lemoine'."""
        firsts: str = match.group(1)
        last: str = match.group(2)
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
                    return f"{t1} {t2} {last[:1].upper()}."

        if self._is_known_first_name(firsts):
            return f"{firsts} {last[:1].upper()}."
        return match.group(0)

    def _replace_auto_last_first(self, match: re.Match) -> str:
        """Abrège 'BERNARD Nadia' en 'B. Nadia'."""
        last_upper: str = match.group(1)
        first: str = match.group(2)
        norm_last: str = DocumentTextUtils.normalize_word(last_upper)
        if (
            last_upper in self.SAFE_UPPER_WORDS
            or norm_last in self.config.excluded_words
            or norm_last in self.config.surname_collisions
            or norm_last in self.config.masked_locations
            or self._is_known_first_name(last_upper)
        ):
            return match.group(0)
        if self._is_known_first_name(first):
            return f"{last_upper[:1].upper()}. {first}"
        return match.group(0)

    def _replace_email_with_alias(self, match: re.Match) -> str:
        """Remplace une adresse e-mail par son alias connu ou génère EMAIL_XXX."""
        raw_mail: str = match.group(0)
        norm_mail: str = DocumentTextUtils.normalize_identifier(raw_mail)
        if norm_mail in self.rules.email_to_alias:
            return self.rules.email_to_alias[norm_mail]
        return self._get_or_create_token(raw_mail, "EMAIL")

    def _replace_phone_with_alias(self, match: re.Match) -> str:
        """Remplace un numéro de téléphone par son alias connu ou génère TEL_XXX."""
        raw_tel: str = match.group(0)
        norm_tel: str = DocumentTextUtils._normalize_fr_phone(raw_tel)
        if norm_tel and norm_tel in self.rules.target_phones:
            return self.rules.target_phones[norm_tel]
        return self._get_or_create_token(raw_tel, "TEL")
    def anonymize_text(self, text: str) -> str:
        """Applique l'ensemble des passes d'anonymisation sur un texte."""
        if not text:
            return text
        if not self.regex_compiled:
            self._compile_patterns()

        res: str = DocumentTextUtils.repair_mojibake(text)

        if self.manual_only:
            if self.fast_replacer_regex:
                res = self.fast_replacer_regex.sub(self._replace_fast_target, res)
            return res

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

        res = re.sub(
            r"\b(MME|MR|DR|MLLE|ENFANT|Enfant)([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç]{2,})",
            r"\1 \2",
            res,
        )
        res = re.sub(
            r"([a-zéèêëàâäîïôöùûüç]{2,})(par|avec|pour|de|du|des|le|la|les)([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç]{2,})",
            r"\1 \2 \3",
            res,
        )

        if self.config.custom_birth_date_pattern:
            res = self.config.custom_birth_date_pattern.sub("[DATE_MASQUEE]", res)
        res = DocumentTextUtils.REGEX_GLUED_PERSON_BIRTH_DATE.sub(
            r"\1[DATE_MASQUEE]", res
        )
        res = DocumentTextUtils.REGEX_BIRTH_DATE.sub(
            r"\1[JOUR_MOIS_MASQUES]/\2", res
        )
        res = DocumentTextUtils.REGEX_ID_DOC_DATES.sub(
            r"\1[DATE_TITRE_MASQUEE]", res
        )

        if self.config.mask_ssn:
            res = DocumentTextUtils.REGEX_SSN.sub("[NUM_SECU_MASQUE]", res)
            res = DocumentTextUtils.REGEX_SSN_OCR_GLUED.sub("[NUM_SECU_MASQUE]", res)

        if self.config.mask_financial_and_admin_ids:
            res = DocumentTextUtils.REGEX_IBAN.sub("[IBAN_MASQUE]", res)
            res = DocumentTextUtils.REGEX_BIC.sub("[BIC_MASQUE]", res)
            res = DocumentTextUtils.REGEX_FISCAL_ID.sub("[ID_FISCAL_MASQUE]", res)
            res = DocumentTextUtils.REGEX_FRANCE_TRAVAIL.sub("[ID_FT_MASQUE]", res)
            res = DocumentTextUtils.REGEX_CAF_ALLOCATAIRE.sub("[ID_CAF_MASQUE]", res)
            res = DocumentTextUtils.REGEX_OFFICIAL_MEDICAL_ID.sub("[ID_CNI_PERMIS_MASQUE]", res)
            res = DocumentTextUtils.REGEX_ISOLATED_12_DIGITS.sub("[ID_CNI_PERMIS_MASQUE]", res)
            res = DocumentTextUtils.REGEX_BANK_TX_AND_CARDS.sub("[REF_BANCAIRE_TX_MASQUEE]", res)
            res = DocumentTextUtils.REGEX_MEETING_IDS.sub("[ID_REUNION_MASQUE]", res)
            res = DocumentTextUtils.REGEX_LICENSE_PLATE.sub("[PLAQUE_IMMAT_MASQUEE]", res)
            res = DocumentTextUtils.REGEX_ACCESS_CODES.sub("[CODE_ACCES_MASQUE]", res)
            res = DocumentTextUtils.REGEX_ADMIN_REFS.sub("[REF_ADMIN_MASQUEE]", res)
            res = re.sub(r"\b[A-Z0-9]{10,}<{2,}[A-Z0-9<]{10,}\b", "[MRZ_IDENTITE_MASQUEE]", res)

        if self.fast_replacer_regex:
            res = self.fast_replacer_regex.sub(self._replace_fast_target, res)

        if self.config.mask_addresses:
            res = DocumentTextUtils.REGEX_STREET_ADDRESS.sub("[ADRESSE_MASQUEE]", res)
            res = DocumentTextUtils.REGEX_POSTAL_CITY.sub("[ADRESSE_MASQUEE]", res)
            res = DocumentTextUtils.REGEX_FACILITIES_AND_ZONES.sub("[ETABLISSEMENT_LIEU_MASQUE]", res)

        if self.locations_regex:
            res = self.locations_regex.sub("[LIEU_MASQUE]", res)

        if self.title_first_last_regex:
            res = self.title_first_last_regex.sub(self._replace_title_first_last, res)
        if self.title_last_name_regex:
            res = self.title_last_name_regex.sub(self._replace_title_last_name, res)
        if self.auto_first_last_regex:
            res = self.auto_first_last_regex.sub(self._replace_auto_first_last, res)
        if self.auto_last_first_regex:
            res = self.auto_last_first_regex.sub(self._replace_auto_last_first, res)

        if self.config.mask_urls:
            res = DocumentTextUtils.REGEX_URL.sub("[URL_MASQUEE]", res)

        res = DocumentTextUtils.REGEX_EMAIL.sub(self._replace_email_with_alias, res)
        res = DocumentTextUtils.REGEX_PHONE.sub(self._replace_phone_with_alias, res)

        for idx, original_css in enumerate(css_stash):
            res = res.replace(f"__CSS_ATTR_{idx}__", original_css)

        return res
    def flush_batch(self) -> None:
        """Écrit le lot en cours sur disque dans batch_XX/, met à jour l'audit et l'état JSON."""
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

        count: int = self.audit.write_report()
        self.audit.save()
        print(
            f"    [+] LOT ÉCRIT : '{out_file}' (Audit : {count} nom(s))",
            flush=True,
        )
        self.audit.file_idx += 1
        self.current_chunk.clear()
        self.current_size = 0

    def _process_single_file(self, norm_path: str) -> bool:
        """Lit, anonymise, audite et met en tampon une transcription unique."""
        try:
            with open(norm_path, "r", encoding="utf-8", errors="ignore") as f_in:
                raw_text: str = f_in.read()
        except OSError as exc:
            print(f"[AVERTISSEMENT] Lecture impossible '{norm_path}' : {exc}", flush=True)
            return False

        anon_text: str = self.anonymize_text(raw_text)
        anon_header_path: str = self.anonymize_text(norm_path)
        if not self.manual_only:
            self.audit.scan_residual_names(anon_text, norm_path)

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
        self.current_size += block_bytes
        self.audit.already_processed.add(norm_path)
        self.processed_in_session += 1
        return True

    def anonymize_single_file(
        self, transcription_path: str, force_reprocess: bool = False
    ) -> bool:
        """Anonymise un fichier transcription à la volée."""
        norm_path: str = os.path.normpath(transcription_path)
        if not force_reprocess and norm_path in self.audit.already_processed:
            return False
        return self._process_single_file(norm_path)

    def finalize(self, start_time: float) -> None:
        """Vide le dernier tampon, génère les rapports d'audit et importe les règles sûres."""
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
        """Exécute l'anonymisation autonome sur l'ensemble de extracted_texts/."""
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
        """Réapplique uniquement manual_contacts.txt sur les lots existants."""
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
