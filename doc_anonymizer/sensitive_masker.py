# Commandes pip à exécuter : Aucune dépendance externe requise

import re
from typing import Any, Dict, List, Optional, Pattern
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_rules_loader import ContactRulesLoader
from doc_anonymizer.text_utils import DocumentTextUtils


class SensitiveTextMasker:
    """Moteur de masquage contextuel multi-passes."""

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
        "AIMER", "TROUVER", "CHERCHER", "ATTENDRE", "ENTENDRE",
        "REPONDRE", "RENDRE", "PERDRE", "VENDRE", "BATTRE", "SUIVRE",
        "LIRE", "ECRIRE", "DATE", "OBJET", "SUJET", "PIECE", "JOINTE",
        "PJ", "URGENT", "IMPORTANT", "NOTE", "NOTES", "AVIS", "RAPPORT",
        "BILAN", "COMPTE", "RENDU", "SYNTHESE", "RESUME", "CONCLUSION",
        "SUITE", "FIN", "DEBUT", "TOTAL", "HORS", "TAXE", "TTC", "TVA",
        "HT", "EURO", "EUROS", "LUNDI", "MARDI", "MERCREDI", "JEUDI",
        "VENDREDI", "SAMEDI", "DIMANCHE", "JANVIER", "FEVRIER", "MARS",
        "AVRIL", "MAI", "JUIN", "JUILLET", "AOUT", "SEPTEMBRE",
        "OCTOBRE", "NOVEMBRE", "DECEMBRE", "NORD", "SUD", "EST",
        "OUEST", "CENTRE", "FRANCE", "PARIS", "LYON", "MARSEILLE",
        "BORDEAUX", "LILLE", "NANTES", "TOULOUSE", "STRASBOURG",
        "RENNES", "CAEN", "ROUEN", "HAVRE", "TEL", "FAX", "GSM",
        "PORT", "MAIL", "EMAIL", "WEB", "SITE", "HTTP", "HTTPS", "WWW",
        "COM", "ORG", "NET", "FR", "EU", "PDF", "DOC", "DOCX", "XLS",
        "XLSX", "PPT", "PPTX", "TXT", "JPG", "JPEG", "PNG", "GIF",
        "MP3", "MP4", "WAV", "AVI", "ZIP", "RAR", "7Z", "TAR", "GZ",
        "ISO", "EXE", "DLL", "OK", "OUI", "NON", "SI", "BONJOUR",
        "BONSOIR", "SALUT", "MERCI", "CORDIALEMENT", "SINCEREMENT",
        "AMICALEMENT", "BISOUS", "RAS", "NC", "ND", "NR", "NA", "NB",
        "PS", "PPS", "REF", "NO", "NUM", "CODE", "ID", "IBAN", "BIC",
        "RIB", "NIR", "SS", "SECU", "CAF", "CPAM", "MSA", "ARS", "MDPH",
    })
    EXTRA_SAFE_UPPER = frozenset({
        "CHU", "CHR", "CMP", "CATTP", "HDJ", "IME", "IMPRO", "SESSAD",
        "CAMSP", "PMI", "ASE", "PJJ", "JAF", "TGI", "TJ", "AVOCAT",
        "JUGE", "GREFFIER", "HUISSIER", "NOTAIRE", "EXPERT", "MEDECIN",
        "DOCTEUR", "DR", "PR", "PROFESSEUR", "INFIRMIER", "INFIRMIERE",
        "IDE", "KINE", "ORTHO", "PSY", "PSYCHOLOGUE", "PSYCHIATRE",
        "PEDIATRE", "GENERALISTE", "SPECIALISTE", "MME", "MADAME",
        "MR", "MONSIEUR", "MLLE", "MADEMOISELLE", "FAMILLE", "PARENT",
        "PARENTS", "PERE", "MERE", "PAPA", "MAMAN", "FILS", "FILLE",
        "FRERE", "SOEUR", "ONCLE", "TANTE", "COUSIN", "COUSINE",
        "GRAND", "PETIT", "ENFANT", "ENFANTS", "BEBE", "ECOLE",
        "COLLEGE", "LYCEE", "CLASSE", "CP", "CE1", "CE2", "CM1", "CM2",
        "SIXIEME", "CINQUIEME", "QUATRIEME", "TROISIEME", "SECONDE",
        "PREMIERE", "TERMINALE", "BAC", "BREVET", "DIPLOME", "MAISON",
        "APPARTEMENT", "RUE", "AVENUE", "BOULEVARD", "PLACE", "IMPASSE",
        "CHEMIN", "ROUTE", "ALLEE", "SQUARE", "QUAI", "VILLE",
        "VILLAGE", "QUARTIER", "CANTON", "COMMUNE", "VOITURE", "TRAIN",
        "BUS", "METRO", "AVION", "VELO", "MATIN", "MIDI", "APRES",
        "SOIR", "NUIT", "JOUR", "SEMAINE", "MOIS", "AN", "ANNEE",
        "HEURE", "MINUTE", "SECONDE", "AUJOURDHUI", "HIER", "DEMAIN",
        "MAINTENANT", "TOUJOURS", "JAMAIS", "SOUVENT", "PARFOIS",
        "RAREMENT", "ENCORE", "DEJA", "TROP", "ASSEZ", "PEU",
        "BEAUCOUP", "MOINS", "AUTANT", "SOL", "MER", "TERRE", "CIEL",
        "EAU", "FEU", "AIR", "A", "M", "L", "S", "C", "N", "T", "D",
        "J", "Y",
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
        "rit", "pleure", "dort", "mange", "boit", "court", "marche",
        "joue", "chante", "travaille", "etudie", "apprend", "comprend",
        "explique", "montre", "ouvre", "ferme", "commence", "finit",
        "continue", "arrete", "change", "garde", "laisse", "porte",
        "appelle", "demande", "parle", "ecoute", "regarde", "sent",
        "touche", "achete", "paie", "gagne", "depense", "voyage",
        "visite", "arrive", "retourne", "revient", "manque",
        "telephoner", "telephone", "ecrire", "repondre", "lui", "leur",
        "le", "la", "les", "me", "te", "se", "nous", "vous", "en", "y",
        "ne", "pas", "plus", "bien", "mal", "trop", "tres", "aussi",
        "encore", "deja", "toujours", "jamais", "souvent", "parfois",
        "avec", "sans", "pour", "dans", "sur", "sous", "chez", "vers",
        "et", "ou", "mais", "donc", "car", "que", "qui", "quoi", "dont",
    })
    CASE_SENSITIVE_LOCATIONS = frozenset({
        "rots", "ifs", "boulon", "clin", "orge", "aire", "sens", "nice", "pau", "auch",
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
    })

    def __init__(
        self,
        config: PipelineConfig,
        rules: ContactRulesLoader,
        manual_only: bool = False,
        vault: Optional[Any] = None,
    ) -> None:
        self.config: PipelineConfig = config
        self.rules: ContactRulesLoader = rules
        self.manual_only: bool = manual_only
        self.vault: Optional[Any] = vault
        self.dynamic_tokens: Dict[str, str] = {}
        self.email_counter: int = 1
        self.phone_counter: int = 1
        self._active_stats: Optional[Dict[str, int]] = None

        self.regex_compiled: bool = False
        self.fast_replacer_regex: Optional[Pattern[str]] = None
        self.fast_replacer_map: Dict[str, str] = {}
        self.upper_surnames_regex: Optional[Pattern[str]] = None
        self.title_last_name_regex: Optional[Pattern[str]] = None
        self.title_first_last_regex: Optional[Pattern[str]] = None
        self.auto_first_double_upper_regex: Optional[Pattern[str]] = None
        self.auto_first_last_regex: Optional[Pattern[str]] = None
        self.auto_last_first_regex: Optional[Pattern[str]] = None
        self.initial_last_name_regex: Optional[Pattern[str]] = None
        self.locations_regex: Optional[Pattern[str]] = None

    def _bump_stat(self, key: str, count: int = 1) -> None:
        if self._active_stats is not None and count > 0:
            self._active_stats[key] = self._active_stats.get(key, 0) + count

    def _record_vault(self, token: str, original_val: str, category: str) -> None:
        if self.vault is not None and token and original_val:
            self.vault.record_mapping(token, original_val, category)

    def _mask_entity_value(
        self, original_val: str, static_tag: str, prefix: str, category: str
    ) -> str:
        clean_orig: str = original_val.strip()
        if self.vault is not None and getattr(self.config, "numbered_placeholders", False):
            return self.vault.get_or_create_numbered_token(prefix, clean_orig, category)
        self._record_vault(static_tag, clean_orig, category)
        return static_tag

    def _sub_regex_tracked(
        self, rx: Pattern[str], text: str, static_tag: str,
        prefix: str, category: str, stat_key: str,
    ) -> str:
        def _repl(m: re.Match) -> str:
            self._bump_stat(stat_key)
            return self._mask_entity_value(m.group(0), static_tag, prefix, category)

        return rx.sub(_repl, text)
    def sync_dynamic_counters(self) -> None:
        for token in self.dynamic_tokens.values():
            if token.startswith("EMAIL_"):
                try:
                    self.email_counter = max(
                        self.email_counter, int(token.split("_")[-1]) + 1
                    )
                except (ValueError, IndexError):
                    pass
            elif token.startswith("TEL_"):
                try:
                    self.phone_counter = max(
                        self.phone_counter, int(token.split("_")[-1]) + 1
                    )
                except (ValueError, IndexError):
                    pass

    def get_or_create_token(self, raw_val: str, prefix: str) -> str:
        if prefix == "TEL":
            norm: str = (
                DocumentTextUtils.normalize_any_phone(raw_val)
                or raw_val.strip().lower()
            )
        else:
            norm = (
                DocumentTextUtils.normalize_identifier(raw_val)
                or raw_val.strip().lower()
            )
        key: str = f"{prefix}:{norm}"
        if key in self.dynamic_tokens:
            tok_existing: str = self.dynamic_tokens[key]
            self._record_vault(tok_existing, raw_val.strip(), "Coordonnée")
            return tok_existing
        if prefix == "EMAIL":
            token: str = f"EMAIL_{self.email_counter:03d}"
            self.email_counter += 1
        else:
            token = f"TEL_{self.phone_counter:03d}"
            self.phone_counter += 1
        self.dynamic_tokens[key] = token
        self._record_vault(token, raw_val.strip(), "Coordonnée")
        return token

    @staticmethod
    def _normalize_fast_key(raw_text: str) -> str:
        norm: str = DocumentTextUtils.normalize_word(raw_text)
        return re.sub(r"[\s\-'\u2019_]+", " ", norm).strip()
    def compile_patterns(self) -> None:
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
            self.fast_replacer_map[self._normalize_fast_key(clean_t)] = alias
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
        if self.rules.auto_surnames:
            up_surs: List[str] = sorted(
                {s.upper() for s in self.rules.auto_surnames if len(s) >= 4},
                key=lambda s: (-len(s), s),
            )
            if up_surs:
                self.upper_surnames_regex = re.compile(
                    rf"(?<![A-Za-zÀ-ÿ0-9])(?:{'|'.join(re.escape(s) for s in up_surs)})(?![A-Za-zÀ-ÿ0-9])"
                )

        all_dates: List[str] = list(self.config.masked_birth_dates) + sorted(
            self.rules.extra_sensitive_dates
        )
        if all_dates:
            self.config.custom_birth_date_pattern = (
                PipelineConfig._compile_custom_dates_pattern(all_dates)
            )
        titles_pat: str = (
            r"(?:Dr\.?|Dra\.?|Docteur|Doctor|Doutor|Doutora|Pr\.?|Professeur|"
            r"Professor|Professora|Me\.?|Ma[îi]tre|Mme\.?|Madame|Mrs\.?|Ms\.?|"
            r"Miss|Mlle\.?|Mademoiselle|M\.|Mr\.?|Monsieur|Sr\.?|Sra\.?|Srta\.?|"
            r"Senhor|Senhora|Famille|Family|Fam[íi]lia)"
        )
        cap_w: str = (
            r"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇÃÕÁÍÓÚ]"
            r"[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇÃÕÁÍÓÚéèêëàâäîïôöùûüçãõáíóú'\-]+"
        )
        up_w: str = r"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇÃÕÁÍÓÚ]{2,25}"
        part_p: str = (
            r"(?:(?:[Dd]e|[Dd]u|[Dd]es|[Dd]o|[Dd]os|[Dd]as|[Ll]e|[Ll]a|"
            r"[Ll]es|[Vv]an|[Vv]on|[Dd]a|[Dd]i)[ \t]+){1,2}"
        )
        sur_p: str = rf"(?:{part_p})?{cap_w}"

        self.title_first_last_regex = re.compile(
            rf"\b({titles_pat})[ \t]+({cap_w}(?:[ \t]+{cap_w})?)[ \t]+({sur_p})\b"
        )
        self.title_last_name_regex = re.compile(
            rf"\b({titles_pat})[ \t]+({sur_p})\b"
        )
        self.auto_first_double_upper_regex = re.compile(
            rf"\b({cap_w})[ \t]+({up_w})[ \t]+({up_w})\b"
        )
        self.auto_first_last_regex = re.compile(
            rf"(?<![A-Za-zÀ-ÿ])(?:({cap_w}[ \t]+{cap_w})[ \t]+({cap_w})|({cap_w})[ \t]+({cap_w})|({cap_w})_({cap_w}))(?![A-Za-zÀ-ÿ])"
        )
        self.auto_last_first_regex = re.compile(
            rf"(?<![A-Za-zÀ-ÿ])({up_w}(?:[ \t]+(?:DE|DU|DES|LE|LA|LES|VAN|VON|DA|DI|"
            rf"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]{{2,25}}))*)[ \t_]+({cap_w})(?![A-Za-zÀ-ÿ])"
        )
        self.initial_last_name_regex = re.compile(
            rf"\b([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ])\.[ \t]+({up_w}|{cap_w})\b"
        )
        if self.config.masked_locations:
            loc_trie: str = DocumentTextUtils.build_ocr_tolerant_trie_regex(
                sorted(self.config.masked_locations)
            )
            if loc_trie:
                self.locations_regex = re.compile(
                    rf"(?<![A-Za-zÀ-ÿ0-9])(?:{loc_trie})(?![A-Za-zÀ-ÿ0-9])",
                    re.IGNORECASE,
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
            f_sub, s_sub = sub_tokens
            if (
                self._is_known_first_name(f_sub)
                and s_sub not in self.config.excluded_words
                and s_sub not in self.config.masked_locations
            ):
                return True
        if not self.config.known_first_names:
            return len(norm) >= 2 and norm not in self.config.masked_locations
        return False

    @staticmethod
    def _format_surname_initials(last_name: str) -> str:
        parts: List[str] = [p for p in re.split(r"[\s\-]+", last_name.strip()) if p]
        initials: List[str] = []
        for part in parts:
            m_ap = re.match(
                r"^([A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ])(['\u2019])([A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ])",
                part,
            )
            if m_ap:
                initials.append(
                    f"{m_ap.group(1).upper()}{m_ap.group(2)}{m_ap.group(3).upper()}."
                )
            else:
                initials.append(f"{part[:1].upper()}.")
        return " ".join(initials)

    def _replace_fast_target(self, match: re.Match) -> str:
        raw: str = match.group(0)
        for key in (
            DocumentTextUtils.normalize_word(raw),
            self._normalize_fast_key(raw),
        ):
            if key in self.fast_replacer_map:
                self._bump_stat("noms_masques")
                alias_v: str = self.fast_replacer_map[key]
                self._record_vault(alias_v, raw.strip(), "Identité / Règle")
                return alias_v
        return raw
    def _replace_title_first_last(self, match: re.Match) -> str:
        title, firsts, last = match.group(1), match.group(2), match.group(3)
        norm_last: str = DocumentTextUtils.normalize_word(next(reversed(last.split())))
        if (
            norm_last.upper() in self.SAFE_UPPER_WORDS
            or norm_last.upper() in self.EXTRA_SAFE_UPPER
            or norm_last in self.config.excluded_words
        ):
            return match.group(0)
        f_toks: List[str] = [t for t in re.split(r"[\s\-]+", firsts) if t]
        if f_toks and self._is_known_first_name(next(iter(f_toks))):
            self._bump_stat("noms_masques")
            l_init: str = self._format_surname_initials(last)
            if len(f_toks) >= 2 and " " in firsts:
                mid_ini: str = " ".join(f"{p[:1].upper()}." for p in f_toks[1:])
                repl: str = f"{title} {next(iter(f_toks))} {mid_ini} {l_init}"
            else:
                repl = f"{title} {firsts} {l_init}"
            self._record_vault(repl, match.group(0), "Identité détectée")
            return repl
        return match.group(0)

    def _replace_title_last_name(self, match: re.Match) -> str:
        title, last = match.group(1), match.group(2)
        core_l: str = next(reversed(last.split()))
        nl: str = DocumentTextUtils.normalize_word(core_l)
        if (
            nl.upper() in self.SAFE_UPPER_WORDS
            or nl.upper() in self.EXTRA_SAFE_UPPER
            or nl in self.config.excluded_words
            or nl in self.config.surname_collisions
            or nl in self.config.masked_locations
            or self._is_known_first_name(core_l)
        ):
            return match.group(0)
        self._bump_stat("noms_masques")
        repl: str = f"{title} {self._format_surname_initials(last)}"
        self._record_vault(repl, match.group(0), "Identité détectée")
        return repl

    def _replace_auto_first_double_upper(self, match: re.Match) -> str:
        first, l1, l2 = match.group(1), match.group(2), match.group(3)
        if not self._is_known_first_name(first):
            return match.group(0)
        for lp in (l1, l2):
            nlp: str = DocumentTextUtils.normalize_word(lp)
            if (
                nlp.upper() in self.SAFE_UPPER_WORDS
                or nlp.upper() in self.EXTRA_SAFE_UPPER
                or nlp in self.config.excluded_words
                or nlp in self.config.surname_collisions
                or nlp in self.config.masked_locations
                or self._is_known_first_name(lp)
            ):
                return match.group(0)
        self._bump_stat("noms_masques")
        repl: str = f"{first} {l1[:1].upper()}. {l2[:1].upper()}."
        self._record_vault(repl, match.group(0), "Identité détectée")
        return repl
    def _replace_auto_first_last(self, match: re.Match) -> str:
        firsts: str = match.group(1) or match.group(3) or match.group(5) or ""
        last: str = match.group(2) or match.group(4) or match.group(6) or ""
        sep: str = "_" if "_" in match.group(0) else " "
        core_l: str = next(reversed(last.split()))
        nl: str = DocumentTextUtils.normalize_word(core_l)
        if (
            nl.upper() in self.SAFE_UPPER_WORDS
            or nl.upper() in self.EXTRA_SAFE_UPPER
            or nl in self.config.excluded_words
            or nl in self.config.surname_collisions
            or nl in self.config.masked_locations
            or nl in self.VERBS_AND_PRONOUNS_FOLLOWING_FIRSTNAME
            or self._is_known_first_name(core_l)
        ):
            return match.group(0)
        l_init: str = self._format_surname_initials(last)
        if " " in firsts and len(firsts.split(" ")) == 2:
            p1, p2 = firsts.split(" ")
            np2: str = DocumentTextUtils.normalize_word(p2)
            if self._is_known_first_name(p2) or (
                self._is_known_first_name(p1) and np2 not in self.rules.auto_surnames and not p2.isupper()
            ):
                self._bump_stat("noms_masques")
                repl_p: str = f"{p1} {p2} {l_init}"
                self._record_vault(repl_p, match.group(0), "Identité détectée")
                return repl_p
        if self._is_known_first_name(firsts):
            self._bump_stat("noms_masques")
            repl: str = f"{firsts}{sep}{l_init}"
            self._record_vault(repl, match.group(0), "Identité détectée")
            return repl
        return match.group(0)

    def _replace_auto_last_first(self, match: re.Match) -> str:
        last_u, first = match.group(1), match.group(2)
        sep: str = "_" if "_" in match.group(0) else " "
        f_tok: str = next(iter(last_u.split()))
        nl: str = DocumentTextUtils.normalize_word(f_tok)
        first_t: str = next(iter(re.split(r"[\s\-]+", first)), first)
        if (
            last_u in self.SAFE_UPPER_WORDS or last_u in self.EXTRA_SAFE_UPPER
            or nl in self.config.excluded_words or nl in self.config.surname_collisions
            or nl in self.config.masked_locations or self._is_known_first_name(last_u)
        ):
            return match.group(0)
        if self._is_known_first_name(first_t):
            self._bump_stat("noms_masques")
            repl: str = f"{f_tok[:1].upper()}.{sep}{first}"
            self._record_vault(repl, match.group(0), "Identité détectée")
            return repl
        return match.group(0)
    def _replace_initial_last_name(self, match: re.Match) -> str:
        ini, last = match.group(1), match.group(2)
        nl: str = DocumentTextUtils.normalize_word(last)
        if (
            nl.upper() in self.SAFE_UPPER_WORDS
            or nl.upper() in self.EXTRA_SAFE_UPPER
            or nl in self.config.excluded_words
            or nl in self.config.surname_collisions
            or nl in self.config.masked_locations
            or nl in self.rules.COMMON_WORD_COLLISIONS
            or self._is_known_first_name(last)
        ):
            return match.group(0)
        self._bump_stat("noms_masques")
        repl: str = f"{ini}. {self._format_surname_initials(last)}"
        self._record_vault(repl, match.group(0), "Identité détectée")
        return repl

    def _replace_location_match(self, match: re.Match) -> str:
        raw: str = match.group(0)
        norm: str = DocumentTextUtils.normalize_word(raw)
        if norm in self.CASE_SENSITIVE_LOCATIONS and not raw[:1].isupper():
            return raw
        self._bump_stat("lieux_dates_masques")
        return self._mask_entity_value(raw, "[LIEU_MASQUE]", "LIEU", "Lieu")

    def _replace_upper_surname(self, match: re.Match) -> str:
        raw: str = match.group(0)
        alias_v: str = self.rules.auto_surnames.get(DocumentTextUtils.normalize_word(raw), f"{raw[:1].upper()}.")
        self._bump_stat("noms_masques")
        self._record_vault(alias_v, raw, "Nom de famille")
        return alias_v

    def _replace_email_with_alias(self, match: re.Match) -> str:
        rm: str = match.group(0)
        self._bump_stat("coordonnees_masquees")
        av: str = self.rules.email_to_alias.get(DocumentTextUtils.normalize_identifier(rm)) or self.get_or_create_token(rm, "EMAIL")
        self._record_vault(av, rm.strip(), "E-mail")
        return av

    def _replace_phone_with_alias(self, match: re.Match) -> str:
        rt: str = match.group(0)
        nt: str = DocumentTextUtils.normalize_any_phone(rt)
        self._bump_stat("coordonnees_masquees")
        av: str = self.rules.target_phones.get(nt) if (nt and nt in self.rules.target_phones) else self.get_or_create_token(rt, "TEL")
        self._record_vault(av, rt.strip(), "Téléphone")
        return av

    def anonymize_text(self, text: str, stats_collector: Optional[Dict[str, int]] = None) -> str:
        if not text:
            return text
        if not self.regex_compiled:
            self.compile_patterns()
        prev_stats, self._active_stats = self._active_stats, stats_collector
        try:
            res: str = DocumentTextUtils.repair_mojibake(text)
            if self.manual_only:
                return self.fast_replacer_regex.sub(self._replace_fast_target, res) if self.fast_replacer_regex else res
            if self.config.mask_financial_and_admin_ids:
                res = self._sub_regex_tracked(re.compile(r"\b[A-Z0-9]{10,}<{2,}[A-Z0-9<]{10,}\b"), res, "[MRZ_IDENTITE_MASQUEE]", "MRZ_IDENTITE", "Identifiant", "identifiants_masques")
            css_stash: List[str] = []
            res = re.sub(r'\b(?:style|class|width|height|cellpadding|cellspacing|border)\s*=\s*"[^"]*"', lambda m: css_stash.append(m.group(0)) or f"__CSS_ATTR_{len(css_stash) - 1}__", res, flags=re.IGNORECASE)
            res = re.sub(r"\b([0-2]\d:[0-5]\d)([A-Za-zÀ-ÿ])", r"\1 \2", res)
            res = re.sub(r"\b(SOCIETE|Societe|SOCIÉTÉ|Société|EAEA|IDFRA|DOCTEUR|Docteur|MADAME|Madame|MONSIEUR|Monsieur|MME|Mme|MR|Mr|DR|Dr|MLLE|Mlle|ENFANT|Enfant)_?([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç\-]{2,})", r"\1 \2", res)
            res = re.sub(r"\b(Dr\.?|Docteur|Pr\.?|Professeur|Mme\.?|Madame|M\.|Mr\.?|Monsieur|Mlle\.?|Mademoiselle)[ \t]*([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç]{2,})([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]{3,25})\b", r"\1 \2 \3", res)
            res = re.sub(r"\b(Rue|Avenue|Boulevard|Allée|Allee|Impasse|Place|Chemin|Route)(de|du|des|la|le|les)(de|du|des|la|le|les)([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç]{2,})\b", r"\1 \2 \3 \4", res)
            res = re.sub(r"([A-Za-zéèêëàâäîïôöùûüç]{2,})(par|avec|pour|de|du|des|le|la|les)([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç]{2,})", r"\1 \2 \3", res)
            if self.config.custom_birth_date_pattern:
                res = self._sub_regex_tracked(self.config.custom_birth_date_pattern, res, "[DATE_MASQUEE]", "DATE", "Date", "lieux_dates_masques")
            res, n_gd = DocumentTextUtils.REGEX_GLUED_PERSON_BIRTH_DATE.subn(r"\1[DATE_MASQUEE]", res)
            res, n_bd = DocumentTextUtils.REGEX_BIRTH_DATE.subn(r"\1[JOUR_MOIS_MASQUES]/\2", res)
            res, n_id_d = DocumentTextUtils.REGEX_ID_DOC_DATES.subn(r"\1[DATE_TITRE_MASQUEE]", res)
            self._bump_stat("lieux_dates_masques", n_gd + n_bd + n_id_d)
            if self.config.mask_financial_and_admin_ids:
                for rx, tag, pfx in ((DocumentTextUtils.REGEX_IBAN, "[IBAN_MASQUE]", "IBAN"), (DocumentTextUtils.REGEX_BIC, "[BIC_MASQUE]", "BIC"), (DocumentTextUtils.REGEX_FISCAL_ID, "[ID_FISCAL_MASQUE]", "ID_FISCAL"), (DocumentTextUtils.REGEX_FRANCE_TRAVAIL, "[ID_FT_MASQUE]", "ID_FT"), (DocumentTextUtils.REGEX_CAF_ALLOCATAIRE, "[ID_CAF_MASQUE]", "ID_CAF"), (DocumentTextUtils.REGEX_OFFICIAL_MEDICAL_ID, "[ID_CNI_PERMIS_MASQUE]", "ID_CNI_PERMIS"), (DocumentTextUtils.REGEX_ISOLATED_12_DIGITS, "[ID_CNI_PERMIS_MASQUE]", "ID_CNI_PERMIS"), (DocumentTextUtils.REGEX_BANK_TX_AND_CARDS, "[REF_BANCAIRE_TX_MASQUEE]", "REF_BANCAIRE_TX"), (DocumentTextUtils.REGEX_MEETING_IDS, "[ID_REUNION_MASQUE]", "ID_REUNION"), (DocumentTextUtils.REGEX_LICENSE_PLATE, "[PLAQUE_IMMAT_MASQUEE]", "PLAQUE_IMMAT"), (DocumentTextUtils.REGEX_ACCESS_CODES, "[CODE_ACCES_MASQUE]", "CODE_ACCES"), (DocumentTextUtils.REGEX_ADMIN_REFS, "[REF_ADMIN_MASQUEE]", "REF_ADMIN")):
                    res = self._sub_regex_tracked(rx, res, tag, pfx, "Identifiant", "identifiants_masques")
            if self.fast_replacer_regex:
                res = self.fast_replacer_regex.sub(self._replace_fast_target, res)
            if self.upper_surnames_regex:
                res = self.upper_surnames_regex.sub(self._replace_upper_surname, res)
            if self.config.mask_ssn:
                res = self._sub_regex_tracked(DocumentTextUtils.REGEX_SSN, res, "[NUM_SECU_MASQUE]", "NUM_SECU", "Identifiant", "identifiants_masques")
                res = self._sub_regex_tracked(DocumentTextUtils.REGEX_SSN_OCR_GLUED, res, "[NUM_SECU_MASQUE]", "NUM_SECU", "Identifiant", "identifiants_masques")
            if self.config.mask_addresses:
                res = self._sub_regex_tracked(DocumentTextUtils.REGEX_STREET_ADDRESS, res, "[ADRESSE_MASQUEE]", "ADRESSE", "Adresse", "lieux_dates_masques")
                res = self._sub_regex_tracked(DocumentTextUtils.REGEX_POSTAL_CITY, res, "[ADRESSE_MASQUEE]", "ADRESSE", "Adresse", "lieux_dates_masques")
                res = self._sub_regex_tracked(DocumentTextUtils.REGEX_FACILITIES_AND_ZONES, res, "[ETABLISSEMENT_LIEU_MASQUE]", "ETABLISSEMENT", "Établissement", "lieux_dates_masques")
            if self.locations_regex:
                res = self.locations_regex.sub(self._replace_location_match, res)
            for rx_obj, fn_obj in ((self.title_first_last_regex, self._replace_title_first_last), (self.auto_first_double_upper_regex, self._replace_auto_first_double_upper), (self.auto_last_first_regex, self._replace_auto_last_first), (self.auto_first_last_regex, self._replace_auto_first_last), (self.title_last_name_regex, self._replace_title_last_name), (self.initial_last_name_regex, self._replace_initial_last_name)):
                if rx_obj:
                    res = rx_obj.sub(fn_obj, res)
            if self.config.mask_urls:
                res = self._sub_regex_tracked(DocumentTextUtils.REGEX_URL, res, "[URL_MASQUEE]", "URL", "URL", "coordonnees_masquees")
            res = DocumentTextUtils.REGEX_EMAIL.sub(self._replace_email_with_alias, res)
            res = DocumentTextUtils.REGEX_PHONE.sub(self._replace_phone_with_alias, res)
            for idx, original_css in enumerate(css_stash):
                res = res.replace(f"__CSS_ATTR_{idx}__", original_css)
            return res
        finally:
            self._active_stats = prev_stats
