# Commandes pip à exécuter : Aucune dépendance externe requise

import datetime
import html
import os
import re
import unicodedata
from typing import Dict, List, Optional, Pattern, Set, Tuple


class DocumentTextUtils:
    """
    Fournit des utilitaires statiques pour la normalisation des textes,
    des identifiants (téléphones/e-mails), le masquage des NIR, adresses,
    IBAN/BIC et numéros administratifs (CAF, France Travail, Impôts).
    """

    REGEX_PHONE: Pattern[str] = re.compile(
        r"(?:(?:\+|00)33|0)\s*[1-9](?:[\s.-]*\d{2}){4}"
    )
    REGEX_EMAIL: Pattern[str] = re.compile(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    )
    REGEX_SSN: Pattern[str] = re.compile(
        r"\b[\s.-]?\d{2}[\s.-]?(?:0[1-9]|1[0-2]|[2-9]\d)[\s.-]?"
        r"(?:\d{2}|2[abAB])[\s.-]?\d{3}[\s.-]?\d{3}(?:[\s.-]?\d{2})?\b"
    )
    REGEX_IBAN: Pattern[str] = re.compile(
        r"\b(?:FR|BE|CH|DE|ES|IT|LU|NL|PT|GB)\d{2}"
        r"(?:[\s.-]*[A-Z0-9]{4}){3,7}(?:[\s.-]*[A-Z0-9]{1,3})?\b",
        re.IGNORECASE,
    )
    REGEX_BIC: Pattern[str] = re.compile(
        r"\b(?:BIC|SWIFT)\s*[:\-]?\s*[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b"
    )
    REGEX_FISCAL_ID: Pattern[str] = re.compile(
        r"\b(?:n[°o]?\s*fiscal|num[ée]ro\s+fiscal|spi|r[ée]f[ée]rence\s+avis)"
        r"\s*[:\-]?\s*\d{2}[\s.-]?\d{2}[\s.-]?\d{3}[\s.-]?\d{3}[\s.-]?\d{3}\b",
        re.IGNORECASE,
    )
    REGEX_FRANCE_TRAVAIL: Pattern[str] = re.compile(
        r"\b(?:identifiant|n[°o]?\s*allocataire|p[ôo]le\s+emploi|"
        r"france\s+travail)\s*[:\-]?\s*\d{7}[A-Z]\b",
        re.IGNORECASE,
    )
    REGEX_CAF_ALLOCATAIRE: Pattern[str] = re.compile(
        r"\b(?:caf|msa|allocataire|n[°o]?\s*dossier|n[°o]?\s*allocataire)"
        r"\s*[:\-]?\s*\d{7,8}\b",
        re.IGNORECASE,
    )
    REGEX_POSTAL_CITY: Pattern[str] = re.compile(
        r"\b(?:0[1-9]|[1-8]\d|9[0-8])\d{3}\s+"
        r"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'-]+"
        r"(?:[\s-][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'-]+){0,3}\b"
    )
    REGEX_STREET_ADDRESS: Pattern[str] = re.compile(
        r"\b\d{1,4}(?:\s*(?:bis|ter|quater|[a-zA-Z]))?[\s,]+"
        r"(?:rue|avenue|av\.?|boulevard|bd\.?|place|pl\.?|allée|allee|"
        r"impasse|imp\.?|chemin|route|rte\.?|voie|quai|cours|square|"
        r"passage|résidence|residence|lotissement|lieu-dit|hameau)\b"
        r"[^\n,;\(\)]{2,65}",
        re.IGNORECASE,
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

    @staticmethod
    def strip_accents(text: str) -> str:
        """
        Retire les diacritiques et accents d'une chaîne Unicode.

        :param text: Texte source.
        :return: Texte sans accents.
        """
        return "".join(
            ch
            for ch in unicodedata.normalize("NFD", text)
            if unicodedata.category(ch) != "Mn"
        )

    @classmethod
    def normalize_word(cls, word: str) -> str:
        """
        Normalise un mot en minuscules sans accents ni espaces superflus.

        :param word: Mot brut.
        :return: Mot normalisé.
        """
        return cls.strip_accents(word).lower().strip()

    @staticmethod
    def normalize_identifier(value: str) -> str:
        """
        Uniformise un numéro de téléphone français (format 0XXXXXXXXX)
        ou une adresse e-mail.

        :param value: Identifiant brut extrait.
        :return: Identifiant normalisé.
        """
        val: str = value.strip().replace("mailto:", "").replace("MAILTO:", "")
        if "@" in val:
            return val.lower()
        num: str = re.sub(r"[\s.-]", "", val)
        if num.startswith("+33"):
            num = "0" + num[3:]
        elif num.startswith("0033"):
            num = "0" + num[4:]
        return num
    @classmethod
    def is_contact_identifier(cls, value: str) -> bool:
        """
        Vérifie si une chaîne correspond à un e-mail ou un téléphone.

        :param value: Chaîne brute à tester.
        :return: True s'il s'agit d'un e-mail ou d'un numéro valide.
        """
        cleaned: str = value.strip()
        if not cleaned:
            return False
        if "@" in cleaned:
            return True
        norm: str = cls.normalize_identifier(cleaned)
        return bool(re.match(r"^[\d+]{6,}$", norm))

    @classmethod
    def resolve_contact_pair(
        cls, left_part: str, right_part: str
    ) -> Tuple[str, str, bool]:
        """
        Détermine automatiquement quelle partie est la cible à masquer
        et quelle partie est l'alias, quel que soit le sens autour du '='.

        :param left_part: Partie gauche avant le séparateur.
        :param right_part: Partie droite après le séparateur.
        :return: Tuple (cible_a_masquer, alias, est_alias_a_gauche).
        """
        left_clean: str = left_part.strip()
        right_clean: str = right_part.strip()
        if cls.is_contact_identifier(
            right_clean
        ) and not cls.is_contact_identifier(left_clean):
            return right_clean, left_clean, True
        return left_clean, right_clean, False

    @classmethod
    def mask_identifiers_in_filename(
        cls,
        filename: str,
        phone_map: Dict[str, str],
        email_map: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Remplace tout numéro de téléphone, adresse e-mail, NIR ou IBAN
        présent dans un nom de fichier par son alias ou une balise masquée.

        :param filename: Nom du fichier d'origine.
        :param phone_map: Dictionnaire numéro normalisé -> alias.
        :param email_map: Dictionnaire optionnel e-mail normalisé -> alias.
        :return: Nom de fichier assaini.
        """
        def _replace_phone(match: re.Match[str]) -> str:
            norm_num: str = cls.normalize_identifier(match.group(0))
            return phone_map.get(norm_num, "NUMERO_MASQUE")

        def _replace_email(match: re.Match[str]) -> str:
            norm_mail: str = cls.normalize_identifier(match.group(0))
            if email_map and norm_mail in email_map:
                return email_map[norm_mail]
            return "EMAIL_MASQUE"

        masked: str = cls.REGEX_SSN.sub("NUM_SECU_MASQUE", filename)
        masked = cls.REGEX_IBAN.sub("IBAN_MASQUE", masked)
        masked = cls.REGEX_PHONE.sub(_replace_phone, masked)
        return cls.REGEX_EMAIL.sub(_replace_email, masked)

    @staticmethod
    def html_to_plain_text(raw_html: str) -> str:
        """
        Convertit un contenu HTML en texte brut structuré.

        :param raw_html: Chaîne HTML source.
        :return: Texte lisible nettoyé des balises.
        """
        txt: str = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", raw_html)
        txt = re.sub(r"(?i)<br\s*/?>", "\n", txt)
        txt = re.sub(r"(?i)</(p|div|tr|li|h[1-6])>", "\n", txt)
        txt = re.sub(r"<[^>]+>", " ", txt)
        txt = html.unescape(txt)
        lines: List[str] = [
            re.sub(r"[ \t]+", " ", line).strip() for line in txt.splitlines()
        ]
        return "\n".join(line for line in lines if line)

    @classmethod
    def detect_period_in_text(cls, text: str) -> Optional[str]:
        """
        Recherche les dates valides dans un texte ou nom de fichier et retourne
        la plus ancienne au format AAAA-MM.

        :param text: Contenu textuel ou nom de fichier à analyser.
        :return: Chaîne 'AAAA-MM' si trouvée, sinon None.
        """
        if not text:
            return None
        sample: str = cls.strip_accents(text[:15000]).lower()
        candidates: List[str] = []

        for m in re.finditer(
            r"(?<!\d)(199\d|20[0-3]\d)[-/. _]"
            r"(0[1-9]|1[0-2])[-/. _](0[1-9]|\d|3)(?!\d)",
            sample,
        ):
            candidates.append(f"{m.group(1)}-{m.group(2)}")

        for m in re.finditer(
            r"(?<!\d)(0[1-9]|\d|3)[-/. _]"
            r"(0[1-9]|1[0-2])[-/. _](199\d|20[0-3]\d)(?!\d)",
            sample,
        ):
            candidates.append(f"{m.group(3)}-{m.group(2)}")

        for m in re.finditer(
            r"(?<!\d)(199\d|20[0-3]\d)(0[1-9]|1[0-2])(0[1-9]|\d|3)(?!\d)",
            sample,
        ):
            candidates.append(f"{m.group(1)}-{m.group(2)}")

        months_pattern: str = "|".join(cls.FRENCH_MONTHS.keys())
        for m in re.finditer(
            rf"(?<!\d)\d{{1,2}}(?:er)?[\s_-]+({months_pattern})\.?"
            rf"[\s_-]+(199\d|20[0-3]\d)(?!\d)",
            sample,
        ):
            month_num: Optional[str] = cls.FRENCH_MONTHS.get(m.group(1))
            if month_num:
                candidates.append(f"{m.group(2)}-{month_num}")

        for m in re.finditer(
            rf"(?<![a-z])({months_pattern})\.?[\s_-]+(199\d|20[0-3]\d)(?!\d)",
            sample,
        ):
            month_num = cls.FRENCH_MONTHS.get(m.group(1))
            if month_num:
                candidates.append(f"{m.group(2)}-{month_num}")

        return min(candidates) if candidates else None

    @classmethod
    def resolve_file_period(
        cls, extracted_text: str, filename: str, file_path: str
    ) -> str:
        """
        Détermine la période AAAA-MM par priorité : nom de fichier d'abord,
        puis contenu extrait, puis date de modification disque.

        :param extracted_text: Texte extrait du document.
        :param filename: Nom du fichier.
        :param file_path: Chemin complet sur le disque.
        :return: Chaîne 'AAAA-MM' ou '0000-00'.
        """
        period_name: Optional[str] = cls.detect_period_in_text(filename)
        if period_name:
            return period_name
        period: Optional[str] = cls.detect_period_in_text(extracted_text)
        if period:
            return period
        try:
            timestamp: float = os.path.getmtime(file_path)
            return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m")
        except Exception:
            return "0000-00"

    @classmethod
    def load_filter_contacts(
        cls, contacts_path: str
    ) -> Tuple[Optional[Dict[str, str]], Optional[Set[str]]]:
        """
        Charge les numéros de téléphone et adresses e-mail indexés depuis
        contacts.txt, quel que soit le sens autour du signe '='.

        :param contacts_path: Chemin vers le fichier contacts.txt.
        :return: Tuple (dictionnaire_telephones, ensemble_emails) ou None.
        """
        phones: Dict[str, str] = {}
        emails: Set[str] = set()
        if not os.path.exists(contacts_path):
            print(f"Erreur : '{contacts_path}' introuvable.", flush=True)
            return None, None
        with open(contacts_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line: str = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                for sep in ("=", ";", ","):
                    if sep in line:
                        left_part, right_part = line.split(sep, 1)
                        target_val, alias_val, _ = cls.resolve_contact_pair(
                            left_part, right_part
                        )
                        if target_val and alias_val:
                            norm_id: str = cls.normalize_identifier(target_val)
                            if "@" in norm_id:
                                emails.add(norm_id)
                            elif re.match(r"^[\d+]+$", norm_id):
                                phones[norm_id] = alias_val
                        break
        return phones, emails
