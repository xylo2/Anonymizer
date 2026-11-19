# Commandes pip à exécuter : Aucune dépendance externe requise

from datetime import datetime
import html
import os
import re
import tempfile
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple
import unicodedata
import xml.etree.ElementTree as ET


class DocumentTextUtils:
    """
    Fournit les utilitaires de normalisation linguistique, de détection
    d'entités sensibles, d'extraction sécurisée (HTML/ICS/XML) et de
    construction d'arbres préfixes (Trie) tolérants aux erreurs OCR.
    """

    REGEX_EMAIL: Pattern[str] = re.compile(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    )
    REGEX_PHONE: Pattern[str] = re.compile(
        r"(?:\+33\s*(?:\(0\)\s*)?|0033\s*(?:\(0\)\s*)?|(?<![\d.])0(?![.,]\d))[1-9]"
        r"(?:[\s.\-]?\d{2}){4}(?![\d:])(?!\.\d)"
    )
    REGEX_SSN: Pattern[str] = re.compile(
        r"(?<!\d)(?:1|2)\s?\d{2}\s?(?:0[1-9]|1[0-2]|2[0-9]|[3-9]\d)\s?"
        r"(?:\d{2}|2[AB])\s?\d{3}\s?\d{3}(?:\s?\d{2})?(?!\d)",
        re.IGNORECASE,
    )
    REGEX_SSN_OCR_GLUED: Pattern[str] = re.compile(
        r"(?i)(?:(?<=Nmle)|(?<=NIR)|(?<=SS)|(?<![A-Z0-9]))"
        r"[1289H]?[0-9H]{2}[0-1][0-9H][0-9A-BH]{2}[0-9H]{6,8}(?![0-9])"
    )
    REGEX_IBAN: Pattern[str] = re.compile(
        r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b"
    )
    REGEX_BIC: Pattern[str] = re.compile(
        r"\b[A-Z]{4}FR[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b"
    )
    REGEX_FISCAL_ID: Pattern[str] = re.compile(
        r"(?i)\b(?:n[°o]?\s*fiscal|spi|revenu\s+fiscal)[^\d\n]{0,15}\d{13}\b"
    )
    REGEX_FRANCE_TRAVAIL: Pattern[str] = re.compile(
        r"(?i)\b(?:identifiant|p[ôo]le\s*emploi|france\s*travail)[^\w\n]{0,20}\d{7}[A-Z]\b"
    )
    REGEX_CAF_ALLOCATAIRE: Pattern[str] = re.compile(
        r"(?i)\b(?:allocataire|caf)[^\d\n]{0,15}\d{7,8}\b"
    )
    REGEX_OFFICIAL_MEDICAL_ID: Pattern[str] = re.compile(
        r"(?i)\b(?:"
        r"ipp\s*[:#-]?\s*\d{6,10}"
        r"|(?:n[°o]\s*(?:rpps|am|finess|sinistre|dossier|ordre|électeur|electeur)"
        r"|cartenationale\s*d'identiten[°o])\s*[:#-]?\s*[A-Z0-9]{7,15}"
        r"(?:\s+\d{2}\s+\d\s+[A-Z0-9]{2}\s+\d)?"
        r"|\d{9}\s+\d{2}\s+\d\s+[A-Z0-9]{2}\s+\d"
        r"|cni\s*[:#-]?\s*[A-Z0-9]{9,12}"
        r"|[A-Z]{2}\d[A-Z0-9]{6}"
        r"|\d{6}X{4,8}\d{4}"
        r")\b"
    )
    REGEX_ISOLATED_12_DIGITS: Pattern[str] = re.compile(
        r"(?<!\d)\d{12}(?!\d)"
    )
    REGEX_ID_DOC_DATES: Pattern[str] = re.compile(
        r"(?i)\b((?:d[ée]livr[ée]e?\s+le|valable\s+jusqu'au|expiration)\s*[:=\-]?\s*)"
        r"\d{1,2}[/\-.]\d{1,2}[/\-.](?:19|20)\d{2}\b"
    )
    REGEX_BANK_TX_AND_CARDS: Pattern[str] = re.compile(
        r"(?i)\b(?:"
        r"(?:carte\s*(?:bancaire|cb)?|cb|terminant\s+par|fin\s+de\s+carte)\s*[:#*\-xX\s]{0,12}\d{4}"
        r"|(?:autorisation|transaction|commande|suivi|colis|re[çc]u\s*fiscal)\s*(?:n[°o])?\s*[:#=\-]?\s*[A-Z0-9\-]{5,22}"
        r"|(?:don|versement)\s+(?:de\s+)?\d+(?:[.,]\d{1,2})?\s*(?:€|euros?)"
        r")\b"
    )
    REGEX_MEETING_IDS: Pattern[str] = re.compile(
        r"(?i)\b(?:id\s*(?:de\s*)?(?:la\s*)?r[ée]union|meeting\s*id|code\s*secret|passcode)"
        r"\s*[:#=\-]?\s*(?:\d[\d\s]{7,14}|[A-Za-z0-9]{4,12})\b"
    )
    REGEX_LICENSE_PLATE: Pattern[str] = re.compile(
        r"\b(?:[A-HJ-NP-TV-Z]{2}[\s\-]\d{3}[\s\-][A-HJ-NP-TV-Z]{2}"
        r"|\d{1,4}[\s\-][A-Z]{2,3}[\s\-](?:0[1-9]|[1-8]\d|9[0-5]|2[AB]|97[1-6]))\b"
    )
    REGEX_ACCESS_CODES: Pattern[str] = re.compile(
        r"(?i)\b(?:digicode|code\s*(?:d'acc[èe]s|immeuble|portail|retrait|colis|locker|"
        r"vous\s+permettant\s+d'acc[ée]der[^\n:]{0,35})|mot\s*de\s*passe|mdp)"
        r"\s*[:=\-]?\s*(?:\r?\n\s*)?[A-Za-z0-9#*+]{4,20}\b"
    )
    REGEX_ADMIN_REFS: Pattern[str] = re.compile(
        r"(?i)\b(?:dossier\s+sinistre|sinistre|dossier|affaire|rg|siret|siren|permis|cni)\s*"
        r"(?:n[°o]\s*[:=\-]?\s*|[:=\-]\s*|\s+)(?=[A-Z0-9/\-\s]*\d)[A-Z0-9/\-\s]{5,22}\b"
    )
    REGEX_BIRTH_DATE: Pattern[str] = re.compile(
        r"(?i)\b((?:n[ée](?:[\(（]e[\)）]|e)?(?:\s+le)?(?:/rang)?|date\s+de\s+naissance|naissance|ddn|"
        r"enfant|fils|fille|b[ée]b[ée]|nourrisson|patient|patiente)\s*(?:du|le)?\s*[:=\-]?\s*)"
        r"(?:\d{1,2}[/\-.]\d{1,2}[/\-.]|\d{1,2}\s+[a-zéû]+\s+|(?:0[1-9]|\d|3)(?:0[1-9]|1[0-2]|0s))((?:19|20)\d{2}|\d{2})\b"
    )
    REGEX_GLUED_PERSON_BIRTH_DATE: Pattern[str] = re.compile(
        r"((?:Aurélie\s+S\.|S\.,?\s*AURELIE|AURELIE)\s*)"
        r"(?:0[1-9]|\d|3)[/\-.](?:0[1-9]|1[0-2])[/\-.]((?:19|20)\d{2})\b",
        re.IGNORECASE,
    )
    REGEX_FACILITIES_AND_ZONES: Pattern[str] = re.compile(
        r"\b(?:CHU|Clinique|Polyclinique|H[ôo]pital|Centre\s+[Hh]ospitalier|"
        r"Maison\s+[Mm][ée]dicale|Maison\s+de\s+[Ss]ant[ée]|Institut|Espace|Foyer|"
        r"Centre\s+[Cc]ommercial|ZAC|ZI|Gare\s+de|Porte\s+de|Rives\s+de)\s*"
        r"(?:de\s+la\s+|des\s+|du\s+|de\s+|d'|l')?"
        r"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-]+"
        r"(?:[\s\-]+(?:de|du|des|la|le|les|l'|sur|en|[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-]+)){0,4}\b"
    )
    REGEX_URL: Pattern[str] = re.compile(
        r"(?:https?://|www\.)[^\s<>\"'\)\]]+", re.IGNORECASE
    )

    _STREET_TYPES_NO_NUM: str = (
        r"(?:rue|rve|avenue|av\.|boulevard|bd\.?|bld\.?|all[ée]e|all\.?|impasse|imp\.?|"
        r"chemin|chem\.?|route|rte\.?|quai|square|sq\.?|cours|passage|"
        r"sentier|faubourg|fbg\.?|r[ée]sidence|r[ée]s\.?|lotissement|hameau|"
        r"lieu-dit|lieudit|esplanade|terrasse|parvis|promenade|foss[ée]s|vente)"
    )
    _STREET_TYPES_WITH_NUM: str = rf"(?:{_STREET_TYPES_NO_NUM}|place|pl\.?|voie|cr\.?)"

    REGEX_STREET_ADDRESS: Pattern[str] = re.compile(
        rf"(?i)\b(?:\d{{1,4}}(?:\s*(?:bis|ter|quater))?\s*[,]?\s*{_STREET_TYPES_WITH_NUM}(?:\b|(?=[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]))"
        rf"|{_STREET_TYPES_NO_NUM}(?:\b|(?=[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ])))\s*"
        rf"(?:de\s*la\s*|des\s*|du\s*|de\s*|d'|l')?[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]"
        rf"[^\n,;()\[\]{{}}]{{2,45}}"
    )

    REGEX_POSTAL_CITY: Pattern[str] = re.compile(
        r"(?<!\d)\b(?:0[1-9]|[1-8]\d|9[0-8])\d{3}\s*"
        r"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-]+"
        r"(?:[\s\-]+(?:sur|sous|en|de|du|des|la|le|les|l'|st|ste|saint|sainte|cedex|"
        r"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-]+)){0,5}(?:\s*\d{1,2})?\b"
    )
    ORG_GENERIC_WORDS = frozenset({
        "france", "travail", "pole", "emploi", "caf", "cpam", "urssaf",
        "caisse", "primaire", "assurance", "maladie", "mutuelle", "banque",
        "postale", "credit", "agricole", "mutuel", "lyonnais", "societe",
        "generale", "bnp", "paribas", "epargne", "poste",
        "service", "services", "client", "clients", "contact", "contacts",
        "direction", "departement", "region", "mairie", "commune", "ville",
        "prefecture", "ministere", "academie", "rectorat", "ecole", "college",
        "lycee", "universite", "institut", "centre", "hopital", "clinique",
        "chu", "cabinet", "laboratoire", "pharmacie", "association", "groupe",
        "agence", "bureau", "atelier", "ateliers", "entreprise", "sarl",
        "sas", "eurl", "sa", "sci", "scp", "selarl", "syndicat", "comite",
        "conseil", "ordre", "tribunal", "cour", "justice", "police",
        "gendarmerie", "pompiers", "samu", "smur", "ars", "has", "ansm",
        "cnam", "carsat", "msa", "rsi", "cipav", "agirc", "arrco",
        "retraite", "prevoyance", "sante", "social", "sociale", "medico",
        "medical", "medicale", "paramedical", "infirmier", "infirmiere",
        "medecin", "docteur", "professeur", "chirurgien", "dentiste",
        "kinesitherapeute", "osteopathe", "psychologue", "psychiatre",
        "orthophoniste", "podologue", "sage", "femme", "aide", "soignant",
        "soignante", "auxiliaire", "puericulture", "creche", "halte",
        "garderie", "loisirs", "vacances", "animation", "culture", "sport",
        "musique", "danse", "theatre", "cinema", "bibliotheque", "mediatheque",
        "musee", "office", "tourisme", "syndicat", "initiative", "parc",
        "jardin", "foret", "nature", "environnement", "energie", "eau",
        "electricite", "gaz", "telephone", "internet", "mobile", "fibre",
        "orange", "sfr", "bouygues", "free", "edf", "engie", "veolia",
        "suez", "sncf", "ratp", "transilien", "ter", "tgv", "ouigo",
        "air", "bus", "tram", "metro", "velo", "auto", "moto", "garage",
        "controle", "technique", "dekra", "norisko", "securitest",
        "maif", "macif", "matmut", "gmf", "mma", "axa", "allianz",
        "generali", "groupama", "gan", "swiss", "life", "amazon", "cdiscount",
        "fnac", "darty", "boulanger", "ikea", "conforama", "but", "castorama",
        "leroy", "merlin", "bricorama", "bricomarche", "weldom", "point",
        "gedimat", "kiloutou", "loxam", "carrefour", "leclerc", "auchan",
        "intermarche", "super", "hyper", "monoprix", "franprix", "lidl",
        "aldi", "netto", "leader", "price", "picard", "biocoop", "naturalia",
        "vie", "grand", "frais", "decathlon", "intersport", "go",
        "courir", "foot", "locker", "kiabi", "gem", "gemo", "chaussea",
        "besson", "eram", "andre", "minelli", "san", "marina", "bata",
        "halle", "vetements", "chaussures", "vinted", "leboncoin", "rakuten",
        "ebay", "paypal", "paylib", "lydia", "sumup", "mondial", "relay",
        "colissimo", "chronopost", "dpd", "gls", "ups", "dhl", "fedex",
        "tnt", "relais", "colis", "pickup", "drive", "livraison", "commande",
        "facture", "devis", "avoir", "remboursement", "paiement", "virement",
        "prelevement", "cheque", "especes", "carte", "bancaire", "visa",
        "mastercard", "compte", "livret", "epargne", "pret", "impots",
        "tresor", "public", "finances", "publiques", "net", "entreprises",
        "infogreffe", "verif", "pappers", "kompass", "pages", "jaunes",
        "blanches", "google", "microsoft", "apple", "samsung", "android",
        "ios", "windows", "mac", "linux", "ubuntu", "debian", "java",
        "python", "javascript", "html", "css", "sql", "json", "xml",
        "rest", "api", "web", "site", "blog", "forum", "mail", "email",
        "courriel", "message", "sms", "mms", "appel", "visio", "teams",
        "zoom", "skype", "whatsapp", "telegram", "signal", "messenger",
        "facebook", "instagram", "twitter", "linkedin", "viadeo", "youtube",
        "tiktok", "snapchat", "pinterest", "reddit", "discord", "twitch",
        "spotify", "deezer", "netflix", "canal", "plus", "prime", "video",
        "disney", "molotov", "salto", "ocs", "bein", "rmc", "bfm", "lci",
        "cnews", "tf1", "m6", "arte", "w9", "tmc", "tfx", "nrj12",
    })
    MOJIBAKE_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
        ("\ufffd", "e"), ("ï¿½", "e"),
        ("Ã©", "é"), ("Ã¨", "è"), ("Ãª", "ê"), ("Ã«", "ë"),
        ("Ã ", "à"), ("Ã¢", "â"), ("Ã¤", "ä"),
        ("Ã®", "î"), ("Ã¯", "ï"),
        ("Ã´", "ô"), ("Ã¶", "ö"),
        ("Ã¹", "ù"), ("Ã»", "û"), ("Ã¼", "ü"),
        ("Ã§", "ç"),
        ("Ã‰", "É"), ("Ãˆ", "È"), ("ÃŠ", "Ê"), ("Ã‹", "Ë"),
        ("Ã€", "À"), ("Ã‚", "Â"), ("Ã„", "Ä"),
        ("ÃŽ", "Î"), ("Ã\x8f", "Ï"),
        ("Ã”", "Ô"), ("Ã–", "Ö"),
        ("Ã™", "Ù"), ("Ã›", "Û"), ("Ãœ", "Ü"),
        ("Ã‡", "Ç"),
        ("â€™", "'"), ("â€œ", '"'), ("â€\x9d", '"'),
        ("â€“", "-"), ("â€”", "-"), ("â€¦", "..."),
        ("Â ", " "), ("Â«", "«"), ("Â»", "»"),
    )

    FRENCH_MONTHS: Dict[str, str] = {
        "janvier": "01", "janv": "01", "jan": "01",
        "fevrier": "02", "février": "02", "fevr": "02", "févr": "02", "feb": "02",
        "mars": "03", "mar": "03",
        "avril": "04", "avr": "04", "apr": "04",
        "mai": "05", "may": "05",
        "juin": "06", "jun": "06",
        "juillet": "07", "juil": "07", "jul": "07",
        "aout": "08", "août": "08", "aug": "08",
        "septembre": "09", "sept": "09", "sep": "09",
        "octobre": "10", "oct": "10",
        "novembre": "11", "nov": "11",
        "decembre": "12", "décembre": "12", "dec": "12", "déc": "12",
    }

    @classmethod
    def repair_mojibake(cls, text: str) -> str:
        """Corrige les séquences UTF-8 mal décodées et les caractères de remplacement."""
        if (
            "Ã" not in text
            and "â€" not in text
            and "Â" not in text
            and "\ufffd" not in text
            and "ï¿½" not in text
        ):
            return text
        repaired: str = text
        for bad, good in cls.MOJIBAKE_REPLACEMENTS:
            if bad in repaired:
                repaired = repaired.replace(bad, good)
        return repaired

    @staticmethod
    def normalize_word(word: str) -> str:
        """Normalise un mot en minuscules sans accents ni ponctuation périphérique."""
        nfkd: str = unicodedata.normalize("NFKD", word.strip().lower())
        no_acc: str = "".join(c for c in nfkd if not unicodedata.combining(c))
        return re.sub(r"^[^\w]+|[^\w]+$", "", no_acc)

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Nettoie un nom de fichier pour Windows/Linux en conservant l'extension."""
        cleaned: str = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()
        return cleaned or "document_sans_nom"

    @staticmethod
    def atomic_write_text(target_path: str, content: str) -> None:
        """Écrit un fichier texte de façon atomique via fichier temporaire."""
        parent_dir: str = os.path.dirname(os.path.abspath(target_path))
        os.makedirs(parent_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=parent_dir, prefix=".tmp_anon_", suffix=".txt"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f_out:
                f_out.write(content)
            os.replace(tmp_path, target_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
    @staticmethod
    def _normalize_fr_phone(raw_val: str) -> str:
        """Normalise un numéro français au format canonique '0XXXXXXXXX'."""
        digits: str = re.sub(r"[\s.\-()]+", "", raw_val.strip())
        if digits.startswith("+33") and len(digits) == 12 and digits[3:].isdigit():
            return "0" + digits[3:]
        if digits.startswith("0033") and len(digits) == 13 and digits[4:].isdigit():
            return "0" + digits[4:]
        if digits.startswith("0") and len(digits) == 10 and digits.isdigit():
            return digits
        return ""

    @classmethod
    def normalize_identifier(cls, raw_val: str) -> str:
        """Normalise un e-mail (sans +alias) ou un numéro de téléphone français."""
        cleaned: str = raw_val.strip()
        if not cleaned:
            return ""
        if "@" in cleaned:
            return re.sub(r"\+[^@]+(?=@)", "", cleaned.lower()).strip()
        norm_phone: str = cls._normalize_fr_phone(cleaned)
        return norm_phone if norm_phone else cleaned.lower()

    @classmethod
    def load_filter_contacts(cls, file_path: str) -> Tuple[Dict[str, str], Set[str]]:
        """Charge les numéros de téléphone et adresses e-mail depuis un fichier de contacts."""
        target_phones: Dict[str, str] = {}
        allowed_emails: Set[str] = set()
        if not file_path or not os.path.exists(file_path):
            return target_phones, allowed_emails
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
                    norm_mail: str = cls.normalize_identifier(left)
                    if norm_mail:
                        allowed_emails.add(norm_mail)
                else:
                    norm_phone: str = cls._normalize_fr_phone(left)
                    if norm_phone:
                        target_phones[norm_phone] = right
        return target_phones, allowed_emails

    @classmethod
    def detect_period_in_text(cls, text: str) -> Optional[str]:
        """Détecte une période AAAA-MM dans un nom de fichier ou un texte."""
        if not text:
            return None
        m_iso = re.search(r"(?<!\d)(19\d{2}|20\d{2})[-_/.](0[1-9]|1[0-2])(?!\d)", text)
        if m_iso:
            return f"{m_iso.group(1)}-{m_iso.group(2)}"
        m_fr = re.search(r"(?<!\d)(?:0?[1-9]|\d|3)[/\-.](0[1-9]|1[0-2])[/\-.](19\d{2}|20\d{2})(?!\d)", text)
        if m_fr:
            return f"{m_fr.group(3)}-{m_fr.group(1)}"
        m_compact = re.search(r"(?<!\d)(19\d{2}|20\d{2})(0[1-9]|1[0-2])(?:0[1-9]|\d|3)(?!\d)", text)
        if m_compact:
            return f"{m_compact.group(1)}-{m_compact.group(2)}"
        m_word = re.search(
            r"(?i)(?<![A-Za-zÀ-ÿ])([a-zéû]{3,10})\.?\s+(19\d{2}|20\d{2})(?!\d)",
            text,
        )
        if m_word:
            month_num = cls.FRENCH_MONTHS.get(m_word.group(1).lower())
            if month_num:
                return f"{m_word.group(2)}-{month_num}"
        return None

    @classmethod
    def resolve_file_period(
        cls, extracted_text: str, file_name: str, file_path: str
    ) -> str:
        """Détermine la période AAAA-MM à partir du nom de fichier, du contenu ou du mtime."""
        detected: Optional[str] = cls.detect_period_in_text(file_name)
        if detected:
            return detected
        detected = cls.detect_period_in_text(extracted_text[:4000])
        if detected:
            return detected
        try:
            mtime: float = os.path.getmtime(file_path)
            return datetime.fromtimestamp(mtime).strftime("%Y-%m")
        except OSError:
            return "0000-00"
    @classmethod
    def split_sms_addresses(cls, raw_address: str) -> List[str]:
        """Découpe les adresses multiples d'un SMS/MMS et normalise les numéros FR."""
        if not raw_address:
            return []
        parts: List[str] = []
        for chunk in re.split(r"[~;,]+", raw_address):
            sub_chunks = re.split(r"(?<=\d)(?=(?:\+33|0033|0[1-9]\d{8}))", chunk.strip())
            for sc in sub_chunks:
                val = sc.strip()
                if not val:
                    continue
                norm_fr = cls._normalize_fr_phone(val)
                parts.append(norm_fr if norm_fr else val)
        return parts

    @staticmethod
    def format_epoch_ms(epoch_ms: str) -> str:
        """Convertit un timestamp Unix en millisecondes en date lisible."""
        try:
            ts_sec: float = float(epoch_ms) / 1000.0
            return datetime.fromtimestamp(ts_sec).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError, OSError):
            return str(epoch_ms)

    @classmethod
    def html_to_plain_text(cls, raw_html: str) -> str:
        """Supprime les balises script/style et convertit le HTML en texte propre."""
        if not raw_html:
            return ""
        cleaned: str = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", raw_html)
        cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
        cleaned = re.sub(r"(?i)</(?:p|div|li|tr|h[1-6])>", "\n", cleaned)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = html.unescape(cleaned)
        lines: List[str] = [re.sub(r"[ \t]+", " ", ln).strip() for ln in cleaned.splitlines()]
        return "\n".join(ln for ln in lines if ln)

    @classmethod
    def strip_html_tags(cls, raw_html: str) -> str:
        """Alias rétrocompatible vers html_to_plain_text."""
        return cls.html_to_plain_text(raw_html)

    @classmethod
    def extract_ics_text(cls, raw_ics: str) -> str:
        """Extrait et formate les événements VEVENT d'un fichier agenda ICS."""
        if not raw_ics:
            return ""
        unfolded: str = re.sub(r"\r?\n[ \t]", "", raw_ics)
        events: List[str] = []
        in_event: bool = False
        cur: Dict[str, str] = {}
        for line in unfolded.splitlines():
            stripped: str = line.strip()
            if stripped == "BEGIN:VEVENT":
                in_event = True
                cur = {}
            elif stripped == "END:VEVENT" and in_event:
                in_event = False
                block = [
                    f"DTSTART:{cur.get('DTSTART', '')}",
                    f"DTEND:{cur.get('DTEND', '')}",
                    f"SUMMARY:{cur.get('SUMMARY', '')}",
                    f"LOCATION:{cur.get('LOCATION', '')}",
                    f"DESCRIPTION:{cur.get('DESCRIPTION', '')}",
                ]
                events.append("\n".join(b for b in block if not b.endswith(":")))
            elif in_event and ":" in stripped:
                key_part, val_part = stripped.split(":", 1)
                base_key: str = key_part.split(";", 1).upper()
                if base_key in {"DTSTART", "DTEND", "SUMMARY", "LOCATION", "DESCRIPTION"}:
                    cur[base_key] = val_part.replace(r"\n", "\n").replace(r"\,", ",")
        return "\n---\n".join(events)

    @staticmethod
    def safe_parse_xml_fromstring(xml_content: str) -> ET.Element:
        """Parse une chaîne XML en bloquant toute déclaration DOCTYPE/ENTITY (XXE)."""
        if re.search(r"<!(?:DOCTYPE|ENTITY)\b", xml_content, re.IGNORECASE):
            raise ValueError("Déclaration DOCTYPE/ENTITY interdite (protection XXE).")
        return ET.fromstring(xml_content)

    @classmethod
    def resolve_contact_pair(
        cls, left_part: str, right_part: str
    ) -> Tuple[str, str, str]:
        """Résout une paire issue d'un fichier de contacts (cible = alias)."""
        left: str = left_part.strip()
        right: str = right_part.strip()
        if not left or not right:
            return "", "", ""
        if "@" in left:
            return left, right, cls.normalize_identifier(left)
        norm_phone: str = cls._normalize_fr_phone(left)
        if norm_phone:
            return left, right, norm_phone
        return left, right, ""

    @classmethod
    def is_contact_identifier(cls, value: str) -> bool:
        """Indique si une chaîne est une adresse e-mail ou un numéro de téléphone FR."""
        cleaned: str = value.strip()
        if not cleaned:
            return False
        if "@" in cleaned and bool(cls.REGEX_EMAIL.fullmatch(cleaned)):
            return True
        return bool(cls._normalize_fr_phone(cleaned))

    @classmethod
    def mask_identifiers_in_filename(
        cls, filename_stem: str, target_phones: Dict[str, str]
    ) -> str:
        """Masque les numéros et e-mails dans un nom de fichier pour la restauration."""
        masked: str = cls.REGEX_EMAIL.sub("EMAIL_MASQUE", filename_stem)
        for raw_phone, alias in target_phones.items():
            if raw_phone in masked:
                masked = masked.replace(raw_phone, alias)
        return cls.REGEX_PHONE.sub("NUMERO_MASQUE", masked)

    @staticmethod
    def _char_to_ocr_regex(ch: str) -> str:
        """Convertit un caractère en classe regex tolérante aux confusions OCR."""
        low: str = ch.lower()
        ocr_classes: Dict[str, str] = {
            "a": "[aàâä4]", "à": "[aàâä4]", "â": "[aàâä4]", "ä": "[aàâä4]",
            "b": "[b8]", "c": "[cç]", "ç": "[cç]",
            "e": "[eéèêë]", "é": "[eéèêë]", "è": "[eéèêë]", "ê": "[eéèêë]", "ë": "[eéèêë]",
            "g": "[g6]", "i": "[iîï1l]", "î": "[iîï1l]", "ï": "[iîï1l]",
            "l": "[li1]", "o": "[oôö0]", "ô": "[oôö0]", "ö": "[oôö0]",
            "s": "[s5]", "u": "[uùûü]", "ù": "[uùûü]", "û": "[uùûü]", "ü": "[uùûü]",
            "y": "[yÿ]", "ÿ": "[yÿ]",
            " ": r"[\s\-'\u2019]*", "-": r"[\s\-'\u2019]*",
            "'": r"[\s\-'\u2019]*", "\u2019": r"[\s\-'\u2019]*",
        }
        if low in ocr_classes:
            return ocr_classes[low]
        return re.escape(ch)

    @classmethod
    def _compile_trie_node(cls, node: Dict[str, Any]) -> str:
        """Sérialise récursivement un noeud d'arbre préfixe en motif regex."""
        is_end: bool = bool(node.pop("__end__", False))
        if not node:
            return ""
        branches: List[str] = []
        for ch in sorted(node.keys(), key=lambda c: (-len(node[c]), c)):
            sub: str = cls._compile_trie_node(node[ch])
            branches.append(f"{cls._char_to_ocr_regex(ch)}{sub}")
        joined: str = (
            next(iter(branches))
            if len(branches) == 1
            else f"(?:{'|'.join(branches)})"
        )
        if is_end:
            return f"(?:{joined})?"
        return joined

    @classmethod
    def build_ocr_tolerant_trie_regex(cls, words: List[str]) -> str:
        """Construit une expression régulière Trie compacte tolérante OCR."""
        trie: Dict[str, Any] = {}
        unique_sorted: List[str] = sorted(
            {w.strip() for w in words if w and w.strip()},
            key=lambda x: (-len(x), x),
        )
        for word in unique_sorted:
            curr: Dict[str, Any] = trie
            for ch in word:
                if ch not in curr:
                    curr[ch] = {}
                curr = curr[ch]
            curr["__end__"] = True
        return cls._compile_trie_node(trie)
