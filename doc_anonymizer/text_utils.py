# Commandes pip à exécuter : Aucune dépendance externe requise

import datetime
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Set, Tuple
from common.core_utils import SharedCoreUtils


class DocumentTextUtils:
    """
    Utilitaires de normalisation linguistique, tolérance OCR et détection
    d'entités sensibles pour le pipeline documentaire.
    """

    MOJIBAKE_MAP: Dict[str, str] = {
        "Ã©": "é", "Ã¨": "è", "Ãª": "ê", "Ã«": "ë",
        "Ã ": "à", "Ã¢": "â", "Ã¤": "ä",
        "Ã®": "î", "Ã¯": "ï",
        "Ã´": "ô", "Ã¶": "ö",
        "Ã¹": "ù", "Ã»": "û", "Ã¼": "ü",
        "Ã§": "ç", "Ã‰": "É", "Ãˆ": "È", "ÃŠ": "Ê",
        "Ã€": "À", "Ã‡": "Ç", "â€™": "'", "â€œ": '"',
        "â€\x9d": '"', "â€“": "-", "â€”": "-", "Â ": " ",
        "Å“": "œ", "Å’": "Œ",
    }

    OCR_CHAR_CLASSES: Dict[str, str] = {
        "a": "[aàâä@4]",
        "e": "[eéèêë3]",
        "i": "[iîï1l!|]",
        "l": "[l1iîï|]",
        "o": "[oôö0]",
        "u": "[uùûü]",
        "c": "[cç]",
        "n": "[nm]",
        "s": "[s5$]",
        "b": "[b8]",
        "g": "[g96]",
        "t": "[t7+]",
        "z": "[z2]",
    }

    ORG_GENERIC_WORDS: Set[str] = {
        "association", "societe", "entreprise", "cabinet", "groupe",
        "agence", "institut", "fondation", "syndicat", "federation",
        "comite", "conseil", "centre", "service", "direction", "departement",
        "region", "mairie", "prefecture", "tribunal", "cour", "ministere",
        "universite", "ecole", "college", "lycee", "creche", "hopital",
        "clinique", "laboratoire", "pharmacie", "banque", "assurance",
        "mutuelle", "caisse", "urssaf", "acoss", "cpam", "caf", "carsat",
        "france", "paris", "caen", "normandie", "calvados", "sarl", "sas",
        "sa", "eurl", "sci", "selarl", "scp", "scm", "gie", "gip",
        "accueil", "contact", "secretariat", "administration", "support",
        "client", "clients", "presse", "communication", "marketing",
        "commercial", "recrutement", "rh", "drh", "cse", "comptabilite",
        "facturation", "commande", "livraison", "atelier", "boutique",
        "magasin", "restaurant", "brasserie", "boulangerie", "menuiserie",
        "isolation", "toiture", "batiment", "immobilier", "tourisme",
        "cuisine", "recettes", "blog", "bio", "marketplace", "amazon",
    }

    REGEX_EMAIL = re.compile(
        r"(?<!\d:)(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    )
    REGEX_PHONE = re.compile(
        r"(?<!\d)(?:"
        r"(?:\+33|0033)\s*[1-9](?:[\s.\-/,]*\d){8}"
        r"|0\s*[1-9](?:[\s.\-/,]*\d){8}"
        r")(?!(?:\s*\d))"
    )
    REGEX_SSN = re.compile(
        r"(?<![0-9])(?:1|2)\s*\d{2}\s*(?:0[1-9]|1[0-2]|[2-9]\d)\s*(?:\d{2}|2[AB])\s*\d{3}\s*\d{3}(?:\s*\d{2})?(?![0-9])",
        re.IGNORECASE,
    )
    REGEX_SSN_OCR_GLUED = re.compile(
        r"(?<![0-9])\d{12}(?:\d{2})?(?![0-9])"
    )
    REGEX_IBAN = re.compile(
        r"\b[A-Z]{2}\d{2}(?:[\s\-]?[A-Z0-9]{4}){3,7}(?:[\s\-]?[A-Z0-9]{1,3})?\b"
    )
    REGEX_BIC = re.compile(
        r"\b(?:BIC|SWIFT)\s*[:\-]?\s*[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b",
        re.IGNORECASE,
    )
    REGEX_FISCAL_ID = re.compile(
        r"(?i)(?:num[ée]ro\s+fiscal|n[°o]\s*fiscal|identifiant\s+fiscal|spi)\s*[:\-]?\s*\d{13}\b"
    )
    REGEX_FRANCE_TRAVAIL = re.compile(
        r"(?i)(?:identifiant|n[°o]|allocataire)\s*(?:p[ôo]le\s*emploi|france\s*travail)\s*[:\-]?\s*\d{7}[A-Z]\b"
    )
    REGEX_CAF_ALLOCATAIRE = re.compile(
        r"(?i)(?:allocataire|n[°o]\s*caf|dossier\s*caf)\s*[:\-]?\s*\d{7,8}\b"
    )
    REGEX_OFFICIAL_MEDICAL_ID = re.compile(
        r"(?i)(?:cni|carte\s*nationale|passeport|permis\s*de\s*conduire|titre(?:\s*de\s*s[ée]jour)?|rpps|adeli|finess)\s*[:\-n°o\s]*[A-Z0-9]{8,15}\b"
    )
    REGEX_ISOLATED_12_DIGITS = re.compile(
        r"(?<![0-9A-Za-z/.\-])\d{12}(?![0-9A-Za-z/.\-])"
    )
    REGEX_BANK_TX_AND_CARDS = re.compile(
        r"(?i)(?:carte\s*(?:bancaire|cb|visa|mastercard)?|op[ée]ration|transaction|mandat\s*sepa|rum)\s*[:\-n°o\s]*(?:\*{4,}\d{4}|[A-Z0-9*]{6,24})\b"
    )
    REGEX_MEETING_IDS = re.compile(
        r"(?i)(?:(?:id\s*(?:de\s*)?r[ée]union|meeting\s*id|visio|zoom|teams)\s*[:\-]?\s*\d{3}[\s\-]?\d{3,4}[\s\-]?\d{3,4}|(?:code\s*secret|passcode)\s*[:\-]?\s*[A-Za-z0-9]{4,12})\b"
    )
    REGEX_LICENSE_PLATE = re.compile(
        r"\b[A-Z]{2}[\s\-]?\d{3}[\s\-]?[A-Z]{2}\b"
    )
    REGEX_ACCESS_CODES = re.compile(
        r"(?i)(?:code\s*(?:d['’]acc[èe]s|pin|digicode|porte|interphone|wifi)|digicode|mot\s*de\s*passe|mdp)\s*[:\-]?\s*[A-Za-z0-9*#+\-]{3,16}\b"
    )
    REGEX_ADMIN_REFS = re.compile(
        r"(?i)(?:r[ée]f[ée]rence|r[ée]f\.?|dossier|sinistre|contrat|police|adh[ée]rent|immatriculation|siret|siren)\s*[:\-n°o\s]*[A-Z0-9\-/]{5,24}\b"
    )
    REGEX_URL = re.compile(
        r"https?://[^\s<>\"'\)\]]+|www\.[^\s<>\"'\)\]]+",
        re.IGNORECASE,
    )
    REGEX_BIRTH_DATE = re.compile(
        r"(?i)(n[ée]e?\s*le\s*|date\s*de\s*naissance\s*[:\-]?\s*|ddn\s*[:\-]?\s*)"
        r"(?:0?[1-9]|1\d|2\d|3)[/.\-](?:0?[1-9]|1[0-2])[/.\-]((?:19|20)\d{2})"
    )
    REGEX_GLUED_PERSON_BIRTH_DATE = re.compile(
        r"([A-Za-zÀ-ÿ]{3,})(?:0[1-9]|1\d|2\d|3)[./\-]?(?:0[1-9]|1[0-2])[./\-]?(?:19\d{2}|20[0-2]\d)(?![0-9])"
    )
    REGEX_ID_DOC_DATES = re.compile(
        r"(?i)((?:d[ée]livr[ée]e?|valable\s*jusqu['’]au|date\s*d['’]expiration|expiration|exp\.?)\s*(?:le\s*)?[:\-]?\s*)"
        r"(?:0?[1-9]|1\d|2\d|3)[/.\-](?:0?[1-9]|1[0-2])[/.\-](?:19|20)\d{2}"
    )
    REGEX_STREET_ADDRESS = re.compile(
        r"(?:\b\d{1,4}(?:\s*(?:bis|ter|quater))?[\s,]+|\b)"
        r"(?:[Rr]ue|[Aa]venue|[Aa]v\.?|[Bb]oulevard|[Bb]d\.?|[Ii]mpasse|[Aa]ll[ée]e|[Cc]hemin|[Rr]oute|[Pp]lace|[Ss]quare|[Qq]uai|[Pp]assage|[Rr][ée]sidence|[Ll]otissement|[Ll]ieu[\s\-]dit)"
        r"\s+(?:(?:de|du|des|la|le|les)\s+|d['’]|l['’])*[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][^\r\n,.;]{2,50}"
    )
    REGEX_POSTAL_CITY = re.compile(
        r"\b(?:0[1-9]|[1-8]\d|9[0-5]|97[1-6])\d{3}\s+[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-\s]{2,35}\b"
    )
    REGEX_FACILITIES_AND_ZONES = re.compile(
        r"(?i)\b(?:cr[èe]che|halte[\s\-]garderie|groupe\s*scolaire|[ée]cole\s*(?:maternelle|primaire|[ée]l[ée]mentaire)?|coll[èe]ge|lyc[ée]e|universit[ée]|facult[ée]|clinique|chu\b|chr\b|h[ôo]pital|centre\s*(?:hospitalier|m[ée]dical|m[ée]dico[\-\s]?psychologique|de\s*soins)|cmp\b|cmpp\b|ime\b|sessad\b|camsp\b|mdph\b|caf\b|cpam\b|urssaf\b|p[ôo]le\s*(?:de\s*)?(?:sant[ée]|m[ée]dical)|institut|maternit[ée]|ehpad|foyer|mairie|pr[ée]fecture|cabinet\s*(?:m[ée]dical|dentaire)|maison\s*(?:de\s*sant[ée]|de\s*retraite|m[ée]dicale)|zone\s*(?:industrielle|artisanale|commerciale)|za\b|zi\b|zac\b)\s+(?:de\s+|du\s+|des\s+|d['’]|l['’]|la\s+|le\s+|les\s+)?[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç0-9'\-\s]{2,40}"
    )
    FRENCH_MONTHS: Dict[str, str] = {
        "janvier": "01", "janv": "01", "jan": "01",
        "fevrier": "02", "fevr": "02", "feb": "02",
        "mars": "03", "mar": "03",
        "avril": "04", "avr": "04", "apr": "04",
        "mai": "05", "may": "05",
        "juin": "06", "jun": "06",
        "juillet": "07", "juil": "07", "jul": "07",
        "aout": "08", "aug": "08",
        "septembre": "09", "sept": "09", "sep": "09",
        "octobre": "10", "oct": "10",
        "novembre": "11", "nov": "11",
        "decembre": "12", "dec": "12",
    }

    @classmethod
    def repair_mojibake(cls, text: str) -> str:
        """Corrige les séquences UTF-8 mal décodées en Latin-1/CP1252."""
        if not text or not any(marker in text for marker in ("Ã", "â€", "Å", "Â ")):
            return text
        res: str = text
        for broken, fixed in cls.MOJIBAKE_MAP.items():
            if broken in res:
                res = res.replace(broken, fixed)
        return res

    @staticmethod
    def clean_extracted_text(text: str) -> str:
        """Nettoie les caractères de contrôle, espaces insécables et lignes vides multiples."""
        if not text:
            return ""
        cleaned: str = DocumentTextUtils.repair_mojibake(text)
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = cleaned.replace("\u00a0", " ").replace("\u202f", " ").replace("\ufeff", "")
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cleaned)
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
        return cleaned.strip()

    @staticmethod
    def normalize_word(word: str) -> str:
        """Normalise un mot en minuscules ASCII sans accents ni ponctuation périphérique."""
        if not word:
            return ""
        nfkd: str = unicodedata.normalize("NFKD", word.strip().lower())
        ascii_only: str = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
        ascii_only = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", ascii_only)
        return re.sub(r"\s+", " ", ascii_only).strip()

    @staticmethod
    def normalize_identifier(identifier: str) -> str:
        """Normalise une adresse e-mail ou un identifiant technique."""
        if not identifier:
            return ""
        cleaned: str = identifier.strip().lower()
        if "@" in cleaned:
            local_part, domain = cleaned.split("@", 1)
            if "+" in local_part:
                local_part = local_part.split("+", 1)[0]
            return f"{local_part}@{domain.strip()}"
        return cleaned

    @staticmethod
    def _normalize_fr_phone(raw_phone: str) -> str:
        """Normalise un numéro français au format 0XXXXXXXXX."""
        return SharedCoreUtils.normalize_fr_phone(raw_phone)

    @staticmethod
    def sanitize_filename_component(name: str, max_len: int = 80) -> str:
        """Assainit un composant de nom de fichier pour Windows/Linux."""
        cleaned: str = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name or "").strip(" .")
        return (cleaned[:max_len].strip(" .")) or "document"

    @staticmethod
    def sanitize_filename(name: str, max_len: int = 80) -> str:
        """Alias rétrocompatible de sanitize_filename_component."""
        return DocumentTextUtils.sanitize_filename_component(name, max_len=max_len)

    @staticmethod
    def atomic_write_text(file_path: str, content: str) -> None:
        """Écrit un fichier texte de façon atomique."""
        SharedCoreUtils.atomic_write_text(file_path, content)

    @classmethod
    def _char_to_ocr_regex(cls, ch: str) -> str:
        """Convertit un caractère en motif regex tolérant aux confusions OCR."""
        if ch in {" ", "-", "'", "\u2019", "_"}:
            return r"[\s\-'\u2019_]*"
        low: str = ch.lower()
        if low in cls.OCR_CHAR_CLASSES:
            return cls.OCR_CHAR_CLASSES[low]
        return re.escape(ch)

    @classmethod
    def build_ocr_tolerant_trie_regex(cls, words: List[str]) -> str:
        """Construit une expression régulière compacte sous forme d'arbre préfixe tolérant à l'OCR."""
        trie: Dict[str, Dict] = {}
        for w in words:
            norm: str = cls.normalize_word(w)
            if not norm:
                continue
            node: Dict = trie
            for ch in norm:
                node = node.setdefault(ch, {})
            node["__END__"] = True

        def _render(node: Dict) -> str:
            has_end: bool = "__END__" in node
            keys: List[str] = sorted(k for k in node if k != "__END__")
            if not keys:
                return ""
            branches: List[str] = []
            for k in keys:
                ch_pat: str = cls._char_to_ocr_regex(k)
                sub: str = _render(node[k])
                branches.append(f"{ch_pat}{sub}")
            body: str = branches[0] if len(branches) == 1 else f"(?:{'|'.join(branches)})"
            return f"(?:{body})?" if has_end else body

        return _render(trie)
    @classmethod
    def detect_period_in_text(cls, text: str) -> Optional[str]:
        """Détecte une période AAAA-MM dans un nom de fichier ou un contenu textuel."""
        if not text:
            return None
        sample: str = text[:4000]

        m_iso = re.search(
            r"(?<!\d)((?:19|20)\d{2})[/\-_.](0[1-9]|1[0-2])(?:[/\-_.](?:0[1-9]|1\d|2\d|3))?(?!\d)",
            sample,
        )
        if m_iso:
            return f"{m_iso.group(1)}-{m_iso.group(2)}"

        m_compact = re.search(
            r"(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])(?:0[1-9]|1\d|2\d|3)(?!\d)",
            sample,
        )
        if m_compact:
            return f"{m_compact.group(1)}-{m_compact.group(2)}"

        m_fr_num = re.search(
            r"(?<!\d)(?:0?[1-9]|1\d|2\d|3)[/.\-](0?[1-9]|1[0-2])[/.\-]((?:19|20)\d{2})(?!\d)",
            sample,
        )
        if m_fr_num:
            return f"{m_fr_num.group(2)}-{int(m_fr_num.group(1)):02d}"

        norm_sample: str = cls.normalize_word(sample)
        m_month = re.search(
            r"\b(" + "|".join(cls.FRENCH_MONTHS.keys()) + r")\s+((?:19|20)\d{2})\b",
            norm_sample,
        )
        if m_month:
            month_num: Optional[str] = cls.FRENCH_MONTHS.get(m_month.group(1))
            if month_num:
                return f"{m_month.group(2)}-{month_num}"
        return None

    @staticmethod
    def period_from_timestamp(ts: float) -> str:
        """Convertit un timestamp Unix en chaîne AAAA-MM."""
        try:
            dt = datetime.datetime.fromtimestamp(ts)
            if 1990 <= dt.year <= 2035:
                return f"{dt.year:04d}-{dt.month:02d}"
        except (OSError, OverflowError, ValueError):
            pass
        return "Date_Inconnue"

    @classmethod
    def resolve_file_period(
        cls, content: str, filename: str = "", file_path: str = ""
    ) -> str:
        """Détermine la période AAAA-MM depuis le nom, le chemin, le contenu ou le mtime."""
        for candidate in (filename, file_path, content):
            period: Optional[str] = cls.detect_period_in_text(candidate)
            if period:
                return period
        if file_path and os.path.exists(file_path):
            try:
                return cls.period_from_timestamp(os.path.getmtime(file_path))
            except OSError:
                pass
        return "Date_Inconnue"

    @staticmethod
    def safe_parse_xml_fromstring(xml_content: str) -> ET.Element:
        """Parse un flux XML en rejetant toute déclaration DOCTYPE/ENTITY (protection XXE)."""
        if re.search(r"(?i)<!\s*(?:DOCTYPE|ENTITY)\b", xml_content or ""):
            raise ValueError("Déclaration DOCTYPE/ENTITY interdite dans le flux XML (XXE).")
        return ET.fromstring(xml_content)

    @classmethod
    def split_sms_addresses(cls, raw_address: str) -> List[str]:
        """Découpe une chaîne d'adresses SMS/MMS multi-destinataires (~ ou +33) et normalise chaque numéro."""
        if not raw_address:
            return []
        prepared: str = re.sub(r"(?<!^)(?=\+33|0033)", "~", raw_address.strip())
        tokens: List[str] = [t.strip() for t in prepared.split("~") if t.strip()]
        result: List[str] = []
        for tok in tokens:
            norm: str = cls._normalize_fr_phone(tok)
            val: str = norm if norm else tok
            if val and val not in result:
                result.append(val)
        return result

    @classmethod
    def is_contact_identifier(cls, value: str) -> bool:
        """Indique si une chaîne est un identifiant technique (e-mail ou téléphone)."""
        if not value:
            return False
        s: str = value.strip()
        if "@" in s and cls.REGEX_EMAIL.search(s):
            return True
        digits: str = cls._normalize_fr_phone(s)
        return len(digits) == 10 and digits.startswith("0")

    @classmethod
    def resolve_contact_pair(cls, left: str, right: str) -> Tuple[str, str, str]:
        """Résout une paire clé=valeur en (Identifiant_Brut, Alias, Identifiant_Normalisé)."""
        l_clean: str = left.strip()
        r_clean: str = right.strip()
        if cls.is_contact_identifier(r_clean) and not cls.is_contact_identifier(l_clean):
            target, alias = r_clean, l_clean
        else:
            target, alias = l_clean, r_clean

        if "@" in target:
            norm_id: str = cls.normalize_identifier(target)
        else:
            digits: str = cls._normalize_fr_phone(target)
            norm_id = digits if digits else cls.normalize_word(target)
        return target, alias, norm_id

    @classmethod
    def mask_identifiers_in_filename(
        cls, filename: str, contact_map: Dict[str, str]
    ) -> str:
        """Remplace les e-mails et téléphones présents dans un nom de fichier."""
        if not filename:
            return filename

        def _repl_mail(m: re.Match) -> str:
            raw_m: str = m.group(0)
            norm_m: str = cls.normalize_identifier(raw_m)
            return contact_map.get(norm_m, "EMAIL_MASQUE")

        def _repl_tel(m: re.Match) -> str:
            raw_t: str = m.group(0)
            norm_t: str = cls._normalize_fr_phone(raw_t)
            return contact_map.get(norm_t, "TEL_MASQUE")

        res: str = cls.REGEX_EMAIL.sub(_repl_mail, filename)
        res = cls.REGEX_PHONE.sub(_repl_tel, res)
        return res

    @classmethod
    def html_to_plain_text(cls, html_content: str) -> str:
        """Convertit un fragment HTML en texte brut tout en conservant les mentions Teams."""
        if not html_content:
            return ""
        import html as html_lib

        def _preserve_at(m: re.Match) -> str:
            attrs: str = m.group(1) or ""
            inner: str = m.group(2) or ""
            m_mail = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", attrs)
            if m_mail:
                return f"@{inner} ({m_mail.group(0)})"
            return f"@{inner}"

        txt: str = re.sub(r"(?is)<at\b([^>]*)>(.*?)</at>", _preserve_at, html_content)
        txt = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", txt)
        txt = re.sub(r"(?i)<br\s*/?>", "\n", txt)
        txt = re.sub(r"(?i)</(?:p|div|li|tr|h[1-6])>", "\n", txt)
        txt = re.sub(r"<[^>]+>", " ", txt)
        txt = html_lib.unescape(txt)
        return cls.clean_extracted_text(txt)

    @staticmethod
    def format_webvtt_timestamp(raw_ts: str) -> str:
        """Formate un horodatage WebVTT (HH:MM:SS.mmm -> HH:MM:SS)."""
        clean: str = re.split(r"[.,]", (raw_ts or "").strip())[0]
        parts: List[str] = clean.split(":")
        if len(parts) == 2:
            mm, ss = parts
            return f"00:{mm.zfill(2)}:{ss.zfill(2)}"
        if len(parts) == 3:
            hh, mm, ss = parts
            return f"{hh.zfill(2)}:{mm.zfill(2)}:{ss.zfill(2)}"
        return clean

    @classmethod
    def parse_teams_vtt_content(cls, content: str) -> str:
        """Convertit une transcription Microsoft Teams .vtt en dialogue lisible."""
        if not content:
            return ""
        lines: List[str] = []
        current_ts: str = ""
        for raw_line in content.splitlines():
            line: str = raw_line.strip()
            if not line or line == "WEBVTT" or line.isdigit():
                continue
            if "-->" in line:
                start_raw, _ = line.split("-->", 1)
                current_ts = cls.format_webvtt_timestamp(start_raw.strip())
                continue
            v_match = re.match(r"^<v\s+([^>]+)>(.*?)(?:</v>)?$", line)
            if v_match:
                speaker: str = v_match.group(1).strip()
                msg: str = re.sub(r"<[^>]+>", "", v_match.group(2)).strip()
                prefix: str = f"[{current_ts}] " if current_ts else ""
                lines.append(f"{prefix}{speaker} : {msg}")
            else:
                clean_msg: str = re.sub(r"<[^>]+>", "", line).strip()
                if clean_msg:
                    prefix = f"[{current_ts}] " if current_ts else ""
                    lines.append(f"{prefix}{clean_msg}")
        return "\n".join(lines)

    @classmethod
    def load_filter_contacts(cls, file_path: str) -> Tuple[Dict[str, str], Set[str]]:
        """Charge un fichier de règles 'Identifiant = Alias'."""
        mapping: Dict[str, str] = {}
        aliases: Set[str] = set()
        if not file_path:
            return mapping, aliases
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f_in:
                for raw_line in f_in:
                    line: str = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    left, right = line.split("=", 1)
                    key_raw, val_alias, norm_id = cls.resolve_contact_pair(left, right)
                    if not key_raw or not val_alias:
                        continue
                    aliases.add(val_alias)
                    if norm_id:
                        mapping[norm_id] = val_alias
        except OSError:
            pass
        return mapping, aliases
