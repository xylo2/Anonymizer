# Commandes pip à exécuter : Aucune dépendance externe requise

import datetime
import html
import os
import re
from typing import Dict, FrozenSet, List, Optional, Pattern, Set, Tuple
from common.core_utils import SharedCoreUtils


class DocumentTextUtils:
    """
    Regroupe les expressions régulières de données sensibles, les outils
    de normalisation de texte et la construction d'arbres préfixes (Trie)
    tolérants aux variantes typographiques, OCR et encodages corrompus.
    """

    REGEX_SSN: Pattern[str] = re.compile(
        r"(?<![0-9])\s*\d\s*\d{2}\s*(?:0[1-9]|1[0-2]|[2-9]\d)\s*"
        r"(?:0[1-9]|[1-8]\d|9[0-5]|2[ABab]|9\d)\s*"
        r"\d{3}\s*\d{3}(?:\s*\d{2})?(?![0-9])"
    )
    REGEX_IBAN: Pattern[str] = re.compile(
        r"\b[A-Z]{2}[0-9]{2}(?:[\s\-]?[A-Z0-9]{4}){3,7}(?:[\s\-]?[A-Z0-9]{1,3})?\b"
    )
    REGEX_BIC: Pattern[str] = re.compile(
        r"\b(?:BIC|SWIFT)\s*[:\-]?\s*[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b",
        re.IGNORECASE,
    )
    REGEX_FISCAL_ID: Pattern[str] = re.compile(
        r"\b(?:num[eé]ro\s+fiscal|n°\s*fiscal|spi)\s*[:\-]?\s*[0-9]{2}\s*[0-9]{2}\s*[0-9]{3}\s*[0-9]{3}\s*[0-9]{3}\b",
        re.IGNORECASE,
    )
    REGEX_FRANCE_TRAVAIL: Pattern[str] = re.compile(
        r"\b(?:identifiant|n°\s*allocataire|allocataire|p[oô]le\s*emploi|france\s*travail)\s*[:\-]?\s*[0-9]{7}[A-Z]\b",
        re.IGNORECASE,
    )
    REGEX_CAF_ALLOCATAIRE: Pattern[str] = re.compile(
        r"\b(?:allocataire|n°\s*caf|dossier\s*caf)\s*[:\-]?\s*[0-9]{7,8}\b",
        re.IGNORECASE,
    )
    REGEX_EMAIL: Pattern[str] = re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    )
    REGEX_PHONE: Pattern[str] = re.compile(
        r"(?:(?:\+|00)\s*33[\s.\-\u00a0()]*0?|0)[1-9](?:[\s.\-\u00a0()]*\d{2}){4}\b"
    )
    REGEX_URL: Pattern[str] = re.compile(
        r"(?:https?://|www\.)[^\s\x3c\x3e\"'\]\)]+",
        re.IGNORECASE,
    )
    REGEX_STREET_ADDRESS: Pattern[str] = re.compile(
        r"\b(?:"
        r"\d{1,4}(?:\s*(?:bis|ter|quater|[a-z]))?[\s,]+(?:rue|avenue|av\.?|boulevard|bd\.?|all[eé]e|impasse|imp\.?|place|pl\.?|chemin|route|rte\.?|voie|passage|square|quai|cours|faubourg|lieu[\s\-]dit|lotissement)\s+(?:de\s+la\s+|des\s+|du\s+|de\s+|d'|l')?[A-Za-zÀ-ÿ0-9'\- ]{2,40}"
        r"|(?:rue|avenue|av\.?|boulevard|bd\.?|all[eé]e|impasse|imp\.?|place|pl\.?|chemin|route|rte\.?|square|quai|cours|faubourg|lieu[\s\-]dit|lotissement)\s+(?:de\s+la\s+|des\s+|du\s+|de\s+|d'|l')?[A-ZÀ-Ÿ][A-Za-zÀ-ÿ0-9'\- ]{2,35}"
        r")\b"
    )
    REGEX_POSTAL_CITY: Pattern[str] = re.compile(
        r"\b(?:0[1-9]|[1-8]\d|9[0-5]|9\d)\d{3}\s+[A-ZÀ-Ÿ][A-Za-zÀ-ÿ'\- ]{2,35}\b"
    )
    MOJIBAKE_SEQ: str = r"(?:ï¿½|\ufffd)"
    ACCENT_GROUPS: Dict[str, str] = {
        "a": rf"(?:[aàâä@4]|{MOJIBAKE_SEQ})",
        "e": rf"(?:[eéèêë]|{MOJIBAKE_SEQ})",
        "i": rf"(?:[iîï1l]|{MOJIBAKE_SEQ})",
        "o": rf"(?:[oôö0]|{MOJIBAKE_SEQ})",
        "u": rf"(?:[uùûü]|{MOJIBAKE_SEQ})",
        "c": rf"(?:[cç]|{MOJIBAKE_SEQ})",
        "n": "[nñ]",
        "y": "[yÿ]",
        "s": "[s5]",
        "b": "[b8]",
        "g": "[g6]",
    }

    ORG_GENERIC_WORDS: FrozenSet[str] = frozenset({
        "cabinet", "mairie", "association", "laboratoire", "pharmacie",
        "clinique", "hopital", "centre", "direction", "service",
        "secretariat", "accueil", "presse", "agence", "atelier",
        "restaurant", "hotel", "garage", "ecole", "college", "lycee",
        "universite", "tribunal", "prefecture", "banque", "assurance",
    })
    MONTH_NAMES_TO_NUM: Dict[str, str] = {
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

    @staticmethod
    def repair_mojibake(text: str) -> str:
        """Corrige les séquences UTF-8 décodées en Latin-1/CP1252."""
        if "Ã" not in text and "Â" not in text:
            return text
        for enc in ("cp1252", "latin-1"):
            try:
                fixed: str = text.encode(enc).decode("utf-8")
                return fixed
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        return (
            text.replace("Ã©", "é").replace("Ã¨", "è").replace("Ãª", "ê")
            .replace("Ã ", "à").replace("Ã¢", "â").replace("Ã´", "ô")
            .replace("Ã®", "î").replace("Ã¯", "ï").replace("Ã»", "û")
            .replace("Ã§", "ç").replace("Ã‰", "É").replace("Ãˆ", "È")
        )

    @classmethod
    def normalize_word(cls, text: str) -> str:
        """Normalise un mot après réparation des problèmes d'encodage."""
        repaired: str = cls.repair_mojibake(text)
        cleaned: str = repaired.replace("ï¿½", "e").replace("\ufffd", "e")
        return SharedCoreUtils.normalize_token(cleaned)

    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        """Normalise un numéro de téléphone ou une adresse e-mail."""
        return SharedCoreUtils.normalize_identifier(value, lowercase_email=True)

    @staticmethod
    def is_contact_identifier(value: str) -> bool:
        """Indique si la chaîne correspond à un e-mail ou un téléphone."""
        v: str = value.strip()
        if "@" in v:
            return True
        digits: str = re.sub(r"[\s.\-\u00a0()+]", "", v)
        return len(digits) >= 7 and digits.isdigit()
    @classmethod
    def split_sms_addresses(cls, raw_addr: str) -> List[str]:
        """Découpe et normalise les destinataires multiples d'un SMS/MMS."""
        if not raw_addr:
            return []
        prepared: str = re.sub(r"(?<=\d)(?=\+33|0033)", "~", raw_addr)
        result: List[str] = []
        for part in re.split(r"[~,;\s]+", prepared):
            cleaned: str = part.strip()
            if not cleaned or cleaned.lower().endswith("://google.com"):
                continue
            norm: str = cls.normalize_identifier(cleaned)
            if norm and norm not in result:
                result.append(norm)
        return result

    @classmethod
    def resolve_contact_pair(
        cls, left_part: str, right_part: str
    ) -> Tuple[str, str, str]:
        """Identifie (cible, alias, identifiant_normalisé) quelle que soit l'orientation."""
        left: str = left_part.strip()
        right: str = right_part.strip()
        if not left or not right:
            return "", "", ""
        if cls.is_contact_identifier(left) and not cls.is_contact_identifier(right):
            return left, right, cls.normalize_identifier(left)
        if cls.is_contact_identifier(right) and not cls.is_contact_identifier(left):
            return right, left, cls.normalize_identifier(right)
        return left, right, ""

    @classmethod
    def _char_to_ocr_atom(cls, ch: str) -> str:
        """Convertit un caractère en atome regex tolérant aux variantes OCR sans explosion."""
        low: str = SharedCoreUtils.strip_accents(ch).lower()
        if low in (" ", "-", "'", "\u2019"):
            return r"[\s\-'\u2019]?"
        if low in cls.ACCENT_GROUPS:
            return cls.ACCENT_GROUPS[low]
        return re.escape(ch)

    @classmethod
    def _trie_node_to_regex(cls, node: dict) -> str:
        """Sérialise récursivement un noeud d'arbre préfixe en expression régulière."""
        is_end: bool = "__END__" in node
        branches: List[str] = []
        for atom in sorted(k for k in node.keys() if k != "__END__"):
            sub: str = cls._trie_node_to_regex(node[atom])
            branches.append(f"{atom}{sub}")

        if not branches:
            return ""
        if len(branches) == 1:
            (body,) = branches
        else:
            body = f"(?:{'|'.join(branches)})"
        return f"(?:{body})?" if is_end else body

    @classmethod
    def build_trie_regex(cls, words: List[str]) -> str:
        """Construit une regex factorisée par arbre préfixe (Trie)."""
        return cls.build_ocr_tolerant_trie_regex(words)

    @classmethod
    def build_ocr_tolerant_trie_regex(cls, words: List[str]) -> str:
        """Construit une regex Trie tolérante aux confusions OCR et accents."""
        root: dict = {}
        unique_sorted: List[str] = sorted(
            {w.strip() for w in words if w and w.strip()},
            key=lambda s: (-len(s), s.lower()),
        )
        for word in unique_sorted:
            curr: dict = root
            for ch in word:
                atom: str = cls._char_to_ocr_atom(ch)
                curr = curr.setdefault(atom, {})
            curr["__END__"] = True
        return cls._trie_node_to_regex(root)
    @staticmethod
    def html_to_plain_text(raw_html: str) -> str:
        """Convertit du code HTML en texte brut lisible."""
        cleaned: str = re.sub(
            r"\x3c(script|style)[^\x3e]*\x3e.*?\x3c/\1\x3e", " ", raw_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned = re.sub(r"\x3cbr\s*/?\x3e", "\n", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\x3c/(p|div|li|tr|h[1-6])\x3e", "\n", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\x3c[^\x3e]+\x3e", " ", cleaned)
        cleaned = html.unescape(cleaned)
        cleaned = re.sub(r"[ \t\r\f\v]+", " ", cleaned)
        cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
        return cleaned.strip()

    @classmethod
    def detect_period_in_text(cls, text: str) -> Optional[str]:
        """Extrait une période AAAA-MM depuis une date ISO, française ou textuelle."""
        iso_m = re.search(
            r"(?<![0-9])(19[0-9]{2}|20[0-9]{2})[-_/\.](0[1-9]|1[0-2])(?:[-_/\.][0-9]{2})?(?![0-9])",
            text,
        )
        if iso_m:
            return f"{iso_m.group(1)}-{iso_m.group(2)}"
        fr_m = re.search(
            r"(?<![0-9])\d{1,2}[/\-\.](0[1-9]|1[0-2])[/\-\.](19[0-9]{2}|20[0-9]{2})(?![0-9])",
            text,
        )
        if fr_m:
            return f"{fr_m.group(2)}-{fr_m.group(1)}"
        txt_norm: str = cls.normalize_word(text)
        word_m = re.search(
            r"(?<![0-9])\d{1,2}\s+([a-z]{3,9})\.?\s+(19[0-9]{2}|20[0-9]{2})(?![0-9])",
            txt_norm,
        )
        if word_m and word_m.group(1) in cls.MONTH_NAMES_TO_NUM:
            return f"{word_m.group(2)}-{cls.MONTH_NAMES_TO_NUM[word_m.group(1)]}"
        return None

    @classmethod
    def resolve_file_period(
        cls, extracted_text: str, file_name: str, file_path: str
    ) -> str:
        """Détermine la période AAAA-MM d'un document depuis son nom, son contenu ou sa date."""
        for candidate in (file_name, extracted_text[:3000]):
            period: Optional[str] = cls.detect_period_in_text(candidate)
            if period:
                return period
        try:
            mtime: float = os.path.getmtime(file_path)
            return datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m")
        except OSError:
            return "0000-00"

    @staticmethod
    def atomic_write_text(
        target_path: str, content: str, encoding: str = "utf-8"
    ) -> None:
        """Écrit un fichier texte de façon atomique."""
        SharedCoreUtils.atomic_write_text(target_path, content, encoding=encoding)

    @classmethod
    def load_filter_contacts(
        cls, contacts_path: str
    ) -> Tuple[Optional[Dict[str, str]], Optional[Set[str]]]:
        """Charge les téléphones et adresses e-mail autorisés depuis un fichier de contacts."""
        if not os.path.exists(contacts_path):
            print(f"[ERREUR] Fichier introuvable : '{contacts_path}'", flush=True)
            return None, None
        phones: Dict[str, str] = {}
        emails: Set[str] = set()
        with open(contacts_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line: str = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                for sep in ("=", ";", ","):
                    if sep in line:
                        left_p, right_p = line.split(sep, 1)
                        target, alias, norm_id = cls.resolve_contact_pair(left_p, right_p)
                        if target and alias and norm_id:
                            if "@" in norm_id:
                                emails.add(norm_id)
                            else:
                                phones[norm_id] = alias
                        break
        return phones, emails
