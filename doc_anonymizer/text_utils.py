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
        "a": "[aàâä@4]", "e": "[eéèêë3]", "i": "[iîï1l!|]",
        "l": "[l1iîï|]", "o": "[oôö0]", "u": "[uùûü]",
        "c": "[cç]", "n": "[nm]", "s": "[s5$]", "b": "[b8]",
        "g": "[g96]", "t": "[t7+]", "z": "[z2]",
    }

    ORG_GENERIC_WORDS: Set[str] = {
        "association", "societe", "entreprise", "cabinet", "groupe",
        "agence", "institut", "fondation", "syndicat", "federation",
        "comite", "conseil", "centre", "service", "direction", "departement",
        "region", "mairie", "prefecture", "tribunal", "cour", "ministere",
        "universite", "ecole", "college", "lycee", "creche", "hopital",
        "clinique", "laboratoire", "pharmacie", "banque", "assurance",
        "mutuelle", "caisse", "urssaf", "acoss", "cpam", "caf", "carsat",
        "france", "paris", "lyon", "marseille", "sarl", "sas",
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
        r"(?<![\d.])(?:"
        r"(?:\+33|0033)\s*[1-9](?:[\s.\-/,]*\d){8}"
        r"|0\s*[1-9](?:[\s.\-/,]*\d){8}"
        r"|(?:\+|00)(?!33\b)[1-9]\d{0,2}(?:[\s.\-()/,]*\d){6,12}"
        r")(?!(?:\s*\d))"
    )
    REGEX_SSN = re.compile(
        r"(?<![0-9])(?:1|2)\s*\d{2}\s*(?:0[1-9]|1[0-2]|[2-9]\d)\s*(?:\d{2}|2[AB])\s*\d{3}\s*\d{3}(?:\s*\d{2})?(?![0-9])",
        re.IGNORECASE,
    )
    REGEX_SSN_OCR_GLUED = re.compile(r"(?<![0-9])\d{12}(?:\d{2})?(?![0-9])")
    REGEX_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[\s\-]?[A-Z0-9]{4}){3,7}(?:[\s\-]?[A-Z0-9]{1,3})?\b")
    REGEX_BIC = re.compile(r"\b(?:BIC|SWIFT)\s*[:\-]?\s*[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b", re.IGNORECASE)
    REGEX_FISCAL_ID = re.compile(r"(?i)(?:num[ée]ro\s+fiscal|n[°o]\s*fiscal|identifiant\s+fiscal|spi)\s*[:\-]?\s*\d{13}\b")
    REGEX_FRANCE_TRAVAIL = re.compile(r"(?i)(?:identifiant|n[°o]|allocataire)\s*(?:p[ôo]le\s*emploi|france\s*travail)\s*[:\-]?\s*\d{7}[A-Z]\b")
    REGEX_CAF_ALLOCATAIRE = re.compile(r"(?i)(?:allocataire|n[°o]\s*caf|dossier\s*caf)\s*[:\-]?\s*\d{7,8}\b")
    REGEX_OFFICIAL_MEDICAL_ID = re.compile(
        r"(?i)(?:cni|carte\s*nationale|passeport|permis\s*de\s*conduire|titre(?:\s*de\s*s[ée]jour)?|rpps|adeli|finess)\s*[:\-n°o\s]*[A-Z0-9]{8,15}\b"
    )
    REGEX_ISOLATED_12_DIGITS = re.compile(r"(?<![0-9A-Za-z/.\-])\d{12}(?![0-9A-Za-z/.\-])")
    REGEX_BANK_TX_AND_CARDS = re.compile(
        r"(?i)(?:carte\s*(?:bancaire|cb|visa|mastercard)?|op[ée]ration|transaction|mandat\s*sepa|rum)\s*[:\-n°o\s]*(?:\*{4,}\d{4}|[A-Z0-9*]{6,24})\b"
    )
    REGEX_MEETING_IDS = re.compile(
        r"(?i)(?:(?:id\s*(?:de\s*)?r[ée]union|meeting\s*id|visio|zoom|teams)\s*[:\-]?\s*\d{3}[\s\-]?\d{3,4}[\s\-]?\d{3,4}|(?:code\s*secret|passcode)\s*[:\-]?\s*[A-Za-z0-9]{4,12})\b"
    )
    REGEX_LICENSE_PLATE = re.compile(r"\b(?:[A-Z]{2}[\s\-]?\d{3}[\s\-]?[A-Z]{2}|\d{1,4}[\s\-]?[A-Z]{2,3}[\s\-]?\d{2})\b")
    REGEX_ACCESS_CODES = re.compile(
        r"(?i)(?:code\s*(?:d['’]acc[èe]s|pin|digicode|porte|interphone|wifi)|digicode|mot\s*de\s*passe|mdp)\s*[:\-]?\s*[A-Za-z0-9*#+\-]{3,16}\b"
    )
    REGEX_ADMIN_REFS = re.compile(
        r"(?i)(?:r[ée]f[ée]rence|r[ée]f\.?|dossier|sinistre|contrat|police|adh[ée]rent|immatriculation|siret|siren|commande|affaire\s*rg)\s*[:\-n°o\s]*(?=[A-Z0-9\-/\s]*\d)[A-Z0-9\-/]{4,24}\b"
    )
    REGEX_URL = re.compile(r"https?://[^\s<>\"'\)\]]+|www\.[^\s<>\"'\)\]]+", re.IGNORECASE)
    REGEX_GLUED_PERSON_BIRTH_DATE = re.compile(
        r"(?i)((?:datedenaiss|ddn|n[ée]e?\s*le|naissance)\s*[:\-]?\s*)"
        r"(?:(?:0?[1-9]|[12]\d|3[01])(?:0?[1-9]|1[0-2])(?:19|20)\d{2}|(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0?[1-9]|[12]\d|3[01]))\b"
    )
    REGEX_BIRTH_DATE = re.compile(
        r"(?i)(n[ée]e?\s*le\s*|date\s*de\s*naissance\s*[:\-]?\s*|ddn\s*[:\-]?\s*|born\s+on\s+|date\s+of\s+birth\s*[:\-]?\s*|nascid[oa]\s+em\s+|data\s+de\s+nascimento\s*[:\-]?\s*)"
        r"(?:(?:0?[1-9]|[12]\d|3[01])[/.\-](?:0?[1-9]|1[0-2])[/.\-]|(?:0?[1-9]|[12]\d|3[01])(?:er)?\s+(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)\s+)"
        r"((?:19|20)\d{2})"
    )
    REGEX_ID_DOC_DATES = re.compile(
        r"(?i)((?:d[ée]livr[ée]e?\s+le|valable\s+jusqu['’]au|expir(?:e|ation)\s+le)\s*[:\-]?\s*)"
        r"(?:0?[1-9]|[12]\d|3[01])[/.\-](?:0?[1-9]|1[0-2])[/.\-](?:19|20)\d{2}\b"
    )
    REGEX_STREET_ADDRESS = re.compile(
        r"(?:"
        r"\b\d{1,4}(?:\s*(?:bis|ter|quater|[A-Za-z]))?\s*,?\s*"
        r"(?:[Rr]ue|[Rr]ua|[Aa]venue|[Aa]venida|[Aa][Vv]\.|[Bb]oulevard|[Bb][Dd]\.|[Aa]ll[ée]e|[Ii]mpasse|[Pp]lace|[Pp]ra[çc]a|[Pp][Ll]\.|"
        r"[Cc]hemin|[Rr]oute|[Rr][Tt][Ee]\.|[Ss]quare|[Qq]uai|[Pp]assage|[Cc]ours|[Vv]oie|[Ss]entier|[Ff]aubourg|"
        r"[Tt]ravessa|[Aa]lameda|[Ss]treet|[Ss][Tt]\.|[Rr]oad|[Rr][Dd]\.|[Ll]ane|[Ll][Nn]\.|[Dd]rive|[Dd][Rr]\.)"
        r"(?:\s+(?:de|du|des|do|dos|das|d['’]|da|la|le|les|l['’]|[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇÃÕÁÍÓÚ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇÃÕÁÍÓÚéèêëàâäîïôöùûüçãõáíóú'\-]+)){1,6}"
        r"|"
        r"(?<!\best\s)(?<!\bsont\s)(?<!\bétait\s)"
        r"\b(?:[Rr]ue|[Rr]ua|[Aa]venue|[Aa]venida|[Bb]oulevard|[Aa]ll[ée]e|[Ii]mpasse|[Cc]hemin|[Rr]oute|[Ff]aubourg|[Tt]ravessa|[Aa]lameda)"
        r"(?:\s*(?:de|du|des|do|dos|das|d['’]|da|la|le|les|l['’]|[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇÃÕÁÍÓÚ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇÃÕÁÍÓÚéèêëàâäîïôöùûüçãõáíóú'\-]+)){1,6}"
        r"|"
        r"\b(?:[Rr]ue|[Aa]venue|[Bb]oulevard|[Aa]ll[ée]e|[Ii]mpasse|[Cc]hemin|[Rr]oute)"
        r"(?:de|du|des|d['’]|da|la|le|les|l['’]){0,2}[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-]{2,}\b"
        r"|"
        r"\b\d{1,5}\s+[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,3}\s+(?:[Ss]treet|[Ss][Tt]\.|[Rr]oad|[Rr][Dd]\.|[Aa]venue|[Aa][Vv][Ee]\.|[Ll]ane|[Dd]rive)\b"
        r")"
    )
    REGEX_POSTAL_CITY = re.compile(
        r"\b(?:0[1-9]|[1-8]\d|9[0-5]|97[1-6])\d{3}\s+[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-]+(?:[\s\-][A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-]+){0,3}\b"
    )
    REGEX_FACILITIES_AND_ZONES = re.compile(
        r"\b(?:CHU|CHR|EHPAD|IME|SESSAD|CAMSP|CMP|CATTP|PMI|CAF|CPAM|MDPH|Gare|Clinique|H[ôo]pital)"
        r"(?:\s+(?:de|du|des|d['’]|la|le|les|l['’]|[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-]+)){1,5}\b"
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
        if not text or not any(marker in text for marker in ("Ã", "â€", "Å", "Â ")):
            return text
        res: str = text
        for broken, fixed in cls.MOJIBAKE_MAP.items():
            if broken in res:
                res = res.replace(broken, fixed)
        return res

    @staticmethod
    def clean_extracted_text(text: str) -> str:
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
        if not word:
            return ""
        nfkd: str = unicodedata.normalize("NFKD", word.strip().lower())
        ascii_only: str = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
        ascii_only = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", ascii_only)
        return re.sub(r"\s+", " ", ascii_only).strip()
    @classmethod
    def detect_period_in_text(cls, text: str) -> Optional[str]:
        """Détecte une période AAAA-MM en privilégiant les dates complètes."""
        if not text:
            return None
        sample: str = text[:4000]
        day_pat: str = r"(?:0?[1-9]|[12]\d|3[01])"
        day2_pat: str = r"(?:0[1-9]|[12]\d|3[01])"

        m_iso_full = re.search(
            rf"(?<!\d)(20[0-3]\d|19\d{{2}})[/\-_.](0[1-9]|1[0-2])[/\-_.]{day2_pat}(?!\d)",
            sample,
        )
        if m_iso_full:
            return f"{m_iso_full.group(1)}-{m_iso_full.group(2)}"

        m_fr_num = re.search(
            rf"(?<!\d){day_pat}[/.\-](0?[1-9]|1[0-2])[/.\-](20[0-3]\d|19\d{{2}})(?!\d)",
            sample,
        )
        if m_fr_num:
            return f"{m_fr_num.group(2)}-{int(m_fr_num.group(1)):02d}"

        norm_sample: str = cls.normalize_word(sample)
        m_month = re.search(
            r"\b(" + "|".join(cls.FRENCH_MONTHS.keys()) + r")\s+(20[0-3]\d|19\d{2})\b",
            norm_sample,
        )
        if m_month:
            month_num: Optional[str] = cls.FRENCH_MONTHS.get(m_month.group(1))
            if month_num:
                return f"{m_month.group(2)}-{month_num}"

        m_compact = re.search(
            rf"(?:^|[_\-.\s/\\:])(20[0-3]\d)(0[1-9]|1[0-2]){day2_pat}(?=$|[_\-.\sT/\\])",
            sample,
        )
        if m_compact:
            return f"{m_compact.group(1)}-{m_compact.group(2)}"

        m_iso_ym = re.search(
            r"(?<!\d)(20[0-3]\d|19\d{2})[/\-_.](0[1-9]|1[0-2])(?!\d)",
            sample,
        )
        if m_iso_ym:
            return f"{m_iso_ym.group(1)}-{m_iso_ym.group(2)}"
        return None

    @staticmethod
    def normalize_identifier(identifier: str) -> str:
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
        return SharedCoreUtils.normalize_fr_phone(raw_phone)

    @staticmethod
    def sanitize_filename_component(name: str, max_len: int = 80) -> str:
        cleaned: str = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name or "").strip(" .")
        return (cleaned[:max_len].strip(" .")) or "document"

    @staticmethod
    def sanitize_filename(name: str, max_len: int = 80) -> str:
        return DocumentTextUtils.sanitize_filename_component(name, max_len=max_len)

    @staticmethod
    def atomic_write_text(file_path: str, content: str) -> None:
        SharedCoreUtils.atomic_write_text(file_path, content)
    @classmethod
    def _char_to_ocr_regex(cls, ch: str) -> str:
        if ch in {" ", "-", "'", "\u2019", "_"}:
            return r"[\s\-'\u2019_]*"
        low: str = ch.lower()
        return cls.OCR_CHAR_CLASSES.get(low, re.escape(ch))

    @classmethod
    def build_ocr_tolerant_trie_regex(cls, words: List[str]) -> str:
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
            branches: List[str] = [f"{cls._char_to_ocr_regex(k)}{_render(node[k])}" for k in keys]
            body: str = next(iter(branches)) if len(branches) == 1 else f"(?:{'|'.join(branches)})"
            return f"(?:{body})?" if has_end else body

        return _render(trie)

    @staticmethod
    def period_from_timestamp(ts: float) -> str:
        try:
            dt = datetime.datetime.fromtimestamp(ts)
            if 1990 <= dt.year <= 2035:
                return f"{dt.year:04d}-{dt.month:02d}"
        except (OSError, OverflowError, ValueError):
            pass
        return "Date_Inconnue"

    @classmethod
    def resolve_file_period(cls, content: str, filename: str = "", file_path: str = "") -> str:
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
        if re.search(r"(?i)<!\s*(?:DOCTYPE|ENTITY)\b", xml_content or ""):
            raise ValueError("Déclaration DOCTYPE/ENTITY interdite dans le flux XML (XXE).")
        return ET.fromstring(xml_content)

    @classmethod
    def normalize_any_phone(cls, raw_phone: str) -> str:
        compact_fr: str = re.sub(r"[\s\u00a0\u202f.\-()/,]+", "", (raw_phone or "").lstrip("* ").strip())
        fr: str = cls._normalize_fr_phone(compact_fr)
        if fr:
            return fr
        if compact_fr.startswith("00") and len(compact_fr) > 6 and compact_fr[2:].isdigit():
            compact_fr = "+" + compact_fr[2:]
        if compact_fr.startswith("+") and 8 <= len(compact_fr) <= 16 and compact_fr[1:].isdigit():
            return compact_fr
        return ""

    @classmethod
    def split_sms_addresses(cls, raw_address: str) -> List[str]:
        if not raw_address:
            return []
        prepared: str = re.sub(r"(?<!^)(?=\+[1-9]\d{7,}|00[1-9]\d{7,})", "~", raw_address.strip())
        tokens: List[str] = [t.strip() for t in prepared.split("~") if t.strip()]
        result: List[str] = []
        for tok in tokens:
            norm: str = cls.normalize_any_phone(tok)
            val: str = norm if norm else tok
            if val and val not in result:
                result.append(val)
        return result

    @classmethod
    def is_contact_identifier(cls, value: str) -> bool:
        if not value:
            return False
        s: str = value.strip()
        if "@" in s and cls.REGEX_EMAIL.search(s):
            return True
        return bool(cls.normalize_any_phone(s))

    @classmethod
    def resolve_contact_pair(cls, left: str, right: str) -> Tuple[str, str, str]:
        l_clean, r_clean = left.strip(), right.strip()
        target, alias = (r_clean, l_clean) if (cls.is_contact_identifier(r_clean) and not cls.is_contact_identifier(l_clean)) else (l_clean, r_clean)
        norm_id: str = cls.normalize_identifier(target) if "@" in target else (cls.normalize_any_phone(target) or cls.normalize_word(target))
        return target, alias, norm_id

    @classmethod
    def mask_identifiers_in_filename(cls, filename: str, contact_map: Dict[str, str]) -> str:
        if not filename:
            return filename
        res: str = cls.REGEX_EMAIL.sub(lambda m: contact_map.get(cls.normalize_identifier(m.group(0)), "EMAIL_MASQUE"), filename)
        return cls.REGEX_PHONE.sub(lambda m: contact_map.get(cls.normalize_any_phone(m.group(0)), "TEL_MASQUE"), res)

    @classmethod
    def html_to_plain_text(cls, html_content: str) -> str:
        if not html_content:
            return ""
        import html as html_lib

        def _preserve_at(m: re.Match) -> str:
            attrs, inner = m.group(1) or "", m.group(2) or ""
            m_mail = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", attrs)
            return f"@{inner} ({m_mail.group(0)})" if m_mail else f"@{inner}"

        txt: str = re.sub(r"(?is)<at\b([^>]*)>(.*?)</at>", _preserve_at, html_content)
        txt = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", txt)
        txt = re.sub(r"(?i)<br\s*/?>", "\n", txt)
        txt = re.sub(r"(?i)</(?:p|div|li|tr|h[1-6])>", "\n", txt)
        txt = re.sub(r"<[^>]+>", " ", txt)
        return cls.clean_extracted_text(html_lib.unescape(txt))

    @staticmethod
    def format_webvtt_timestamp(raw_ts: str) -> str:
        clean: str = next(iter(re.split(r"[.,]", (raw_ts or "").strip())), "")
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
                speaker, msg = v_match.group(1).strip(), re.sub(r"<[^>]+>", "", v_match.group(2)).strip()
                lines.append(f"{f'[{current_ts}] ' if current_ts else ''}{speaker} : {msg}")
            else:
                clean_msg: str = re.sub(r"<[^>]+>", "", line).strip()
                if clean_msg:
                    lines.append(f"{f'[{current_ts}] ' if current_ts else ''}{clean_msg}")
        return "\n".join(lines)

    @classmethod
    def load_filter_contacts(cls, file_path: str) -> Tuple[Dict[str, str], Set[str]]:
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
