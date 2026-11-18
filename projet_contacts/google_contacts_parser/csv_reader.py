# Commandes pip à exécuter : Aucune dépendance externe requise

import csv
import os
import re
import unicodedata
from typing import Dict, List, Optional, Set, Tuple
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.text_utils import ContactTextUtils


class GoogleContactsReader:
    """
    Lit les exports CSV Google Contacts et Microsoft 365 / Outlook (FR/EN),
    fusionne les prénoms composés, corrige les inversions, détecte les
    enseignes ou contacts couples et déduit l'identité depuis l'e-mail.
    """

    COMMON_NICKNAMES: Dict[str, str] = {
        "nico": "Nicolas",
        "steph": "Stéphanie",
        "seb": "Sébastien",
        "alex": "Alexandre",
        "fred": "Frédéric",
        "greg": "Grégory",
        "chris": "Christophe",
        "flo": "Florence",
        "caro": "Caroline",
        "ben": "Benjamin",
        "guigui": "Guillaume",
        "math": "Mathieu",
        "tom": "Thomas",
        "sam": "Samuel",
        "max": "Maxime",
        "val": "Valérie",
        "nat": "Nathalie",
        "nath": "Nathalie",
        "pat": "Patrick",
        "phil": "Philippe",
        "dom": "Dominique",
        "jp": "Jean-Pierre",
        "jc": "Jean-Claude",
        "jl": "Jean-Luc",
        "jm": "Jean-Marc",
    }

    def __init__(self, config: ContactsConfig) -> None:
        """
        Initialise le lecteur avec les règles de formatage et charge la liste
        des prénoms fréquents.

        :param config: Instance de ContactsConfig contenant les paramètres.
        """
        self.config: ContactsConfig = config
        self.frequent_first_names: Set[str] = set()
        self.norm_to_display_first_name: Dict[str, str] = {}
        self._load_first_names()

    def _normalize_name_token(self, text: str) -> str:
        """
        Normalise un prénom ou nom (minuscules, sans accents ni espaces).

        :param text: Chaîne brute à normaliser.
        :return: Chaîne normalisée sans accents.
        """
        nfkd: str = unicodedata.normalize("NFKD", text.strip().lower())
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    def _sanitize_name_part(self, raw_part: str) -> str:
        """
        Nettoie un prénom ou un nom : retire les guillemets, ignore les
        e-mails bruts, supprime les crochets techniques et la ponctuation
        finale superflue.

        :param raw_part: Prénom ou nom brut extrait du CSV.
        :return: Chaîne nettoyée.
        """
        cleaned: str = raw_part.strip().strip('"').strip()
        if not cleaned:
            return ""
        if "@" in cleaned or ("\x3c" in cleaned and "\x3e" in cleaned):
            return ""
        cleaned = re.sub(r"\[[^\]]*\]", "", cleaned).strip().strip('"').strip()
        if not cleaned or not any(ch.isalnum() for ch in cleaned):
            return ""
        cleaned = re.sub(r"([^\w\s\)\.]+)$", "", cleaned).strip()
        cleaned = re.sub(r"\.{2,}$", ".", cleaned)
        cleaned = re.sub(r"\){2,}$", ")", cleaned)
        return cleaned
    def _load_first_names(self) -> None:
        """
        Charge et normalise la liste des prénoms fréquents depuis le fichier
        configuré, en mémorisant leur orthographe accentuée éventuelle.
        """
        if not os.path.exists(self.config.first_names_file):
            print(
                f"[AVERTISSEMENT] Fichier de prénoms introuvable : "
                f"'{self.config.first_names_file}'"
            )
            return

        with open(self.config.first_names_file, mode="r", encoding="utf-8") as f:
            for line in f:
                raw: str = line.strip()
                if not raw or raw.startswith("#"):
                    continue
                cleaned: str = self._normalize_name_token(raw)
                if cleaned:
                    self.frequent_first_names.add(cleaned)
                    if (
                        cleaned not in self.norm_to_display_first_name
                        or raw.lower() != cleaned
                    ):
                        self.norm_to_display_first_name[cleaned] = (
                            self._capitalize_word_segment(raw)
                        )

    def _capitalize_word_segment(self, raw_text: str) -> str:
        """
        Met en majuscule la première lettre de chaque segment séparé par
        espace, tiret ou point.

        :param raw_text: Segment brut.
        :return: Texte capitalisé proprement.
        """
        parts: List[str] = re.split(r"([\s\-\.]+)", raw_text.strip())
        return "".join(
            p.capitalize() if p and not re.match(r"^[\s\-\.]+$", p) else p
            for p in parts
        )

    def _resolve_first_name_display(self, token: str) -> Optional[str]:
        """
        Vérifie si un jeton est un prénom connu ou un diminutif courant et
        retourne sa forme affichable.

        :param token: Jeton brut extrait d'une adresse e-mail.
        :return: Prénom capitalisé si reconnu, sinon None.
        """
        norm: str = self._normalize_name_token(token)
        if norm in self.COMMON_NICKNAMES:
            return self.COMMON_NICKNAMES[norm]
        if norm in self.frequent_first_names:
            return self.norm_to_display_first_name.get(
                norm, self._capitalize_word_segment(token)
            )
        return None

    def _format_org_label(self, raw_org: str) -> str:
        """
        Capitalise la première lettre de l'enseigne ainsi que les prénoms
        qu'elle contient.

        :param raw_org: Libellé brut de l'enseigne.
        :return: Libellé formaté proprement.
        """
        words: List[str] = raw_org.strip().split()
        if not words:
            return ""
        formatted: List[str] = []
        for idx, word in enumerate(words):
            norm_w: str = self._normalize_name_token(word)
            if norm_w in self.norm_to_display_first_name:
                formatted.append(self.norm_to_display_first_name[norm_w])
            elif idx == 0:
                formatted.append(self._capitalize_word_segment(word))
            else:
                formatted.append(word)
        return " ".join(formatted)
    def _extract_identity_from_email(
        self, emails: List[str]
    ) -> Optional[Tuple[str, str]]:
        """
        Cherche une adresse nominative avec séparateur ou collée contenant
        un prénom fréquent ou diminutif connu.

        :param emails: Liste des adresses e-mail du contact.
        :return: Tuple (Prénom, Nom) capitalisé si trouvé, sinon None.
        """
        if not self.frequent_first_names and not self.COMMON_NICKNAMES:
            return None

        all_known_tokens: Set[str] = set(self.frequent_first_names) | set(
            self.COMMON_NICKNAMES.keys()
        )
        sorted_first_names: List[str] = sorted(
            all_known_tokens, key=len, reverse=True
        )

        for email in emails:
            canonical_email: str = ContactTextUtils.normalize_email_alias(email)
            if "@" not in canonical_email:
                continue
            local_part, _ = canonical_email.split("@", 1)
            local_part = local_part.strip()
            tokens: List[str] = [
                t for t in re.split(r"[\.\-_]+", local_part) if t
            ]

            if len(tokens) == 2:
                part1, part2 = tokens
                if not any(ch.isdigit() for ch in part1 + part2):
                    disp1: Optional[str] = self._resolve_first_name_display(
                        part1
                    )
                    disp2: Optional[str] = self._resolve_first_name_display(
                        part2
                    )
                    if disp1 and not disp2 and len(part2) >= 2:
                        return disp1, self._capitalize_word_segment(part2)
                    if disp2 and not disp1 and len(part1) >= 2:
                        return disp2, self._capitalize_word_segment(part1)

            elif len(tokens) == 1 and not any(
                ch.isdigit() for ch in local_part
            ):
                norm_local: str = self._normalize_name_token(local_part)
                if norm_local in all_known_tokens:
                    continue
                for fname in sorted_first_names:
                    if len(fname) < 4:
                        continue
                    if norm_local.endswith(fname) and (
                        len(norm_local) >= len(fname) + 3
                    ):
                        raw_last: str = local_part[
                            : len(local_part) - len(fname)
                        ]
                        disp: str = (
                            self._resolve_first_name_display(fname)
                            or self._capitalize_word_segment(fname)
                        )
                        return disp, self._capitalize_word_segment(raw_last)
                    if norm_local.startswith(fname) and (
                        len(norm_local) >= len(fname) + 3
                    ):
                        raw_last = local_part[len(fname) :]
                        disp = (
                            self._resolve_first_name_display(fname)
                            or self._capitalize_word_segment(fname)
                        )
                        return disp, self._capitalize_word_segment(raw_last)

        return None

    def _infer_last_name_from_emails(
        self, first_name: str, emails: List[str]
    ) -> str:
        """
        Déduit un nom de famille si un e-mail est au format
        'prenom.nom@domaine', 'surnom.nom@domaine' ou 'prenomnom@domaine'.

        :param first_name: Prénom ou surnom connu du contact.
        :param emails: Liste des adresses e-mail associées au contact.
        :return: Nom de famille déduit et capitalisé, ou chaîne vide.
        """
        norm_first: str = self._normalize_name_token(first_name)
        if not norm_first:
            return ""

        for email in emails:
            canonical_email: str = ContactTextUtils.normalize_email_alias(email)
            if "@" not in canonical_email:
                continue
            local_part, _ = canonical_email.split("@", 1)
            local_part = local_part.strip()

            if "." in local_part:
                prefix, candidate_last = local_part.split(".", 1)
                norm_prefix: str = self._normalize_name_token(prefix)
                is_exact_match: bool = norm_prefix == norm_first
                is_nickname_match: bool = (
                    len(norm_first) >= 3
                    and len(norm_prefix) >= 3
                    and norm_first[:3] == norm_prefix[:3]
                    and (
                        norm_prefix in self.frequent_first_names
                        or norm_first in self.frequent_first_names
                    )
                )
                if (is_exact_match or is_nickname_match) and (
                    len(candidate_last) >= 2
                ):
                    if not any(ch.isdigit() for ch in candidate_last):
                        return self._capitalize_word_segment(
                            candidate_last.replace(".", " ")
                        )
            else:
                norm_local: str = self._normalize_name_token(local_part)
                if (
                    norm_local.startswith(norm_first)
                    and len(norm_local) >= len(norm_first) + 2
                    and norm_local not in self.frequent_first_names
                ):
                    candidate_last = local_part[len(norm_first) :].lstrip("_-")
                    if len(candidate_last) >= 2 and not any(
                        ch.isdigit() for ch in candidate_last
                    ):
                        return self._capitalize_word_segment(candidate_last)
        return ""
    def _format_couple_from_paired_fields(
        self, c_first: str, c_last: str
    ) -> Optional[str]:
        """
        Détecte un couple saisi sous la forme 'Prénom1 - Prénom2' et
        'Nom1 - Nom2' et associe chaque prénom à son nom respectif.

        :param c_first: Champ prénom contenant potentiellement deux prénoms.
        :param c_last: Champ nom contenant potentiellement deux noms.
        :return: Libellé 'Prénom1 Nom1 et Prénom2 Nom2' si détecté, sinon None.
        """
        if not (c_first and c_last):
            return None

        first_match: Optional[re.Match[str]] = re.match(
            r"^(.+?)\s*(?:-|/|–|—|\bet\b|&)\s*(.+)$",
            c_first,
            flags=re.IGNORECASE,
        )
        last_match: Optional[re.Match[str]] = re.match(
            r"^(.+?)\s*(?:-|/|–|—|\bet\b|&)\s*(.+)$",
            c_last,
            flags=re.IGNORECASE,
        )
        if not (first_match and last_match):
            return None

        f1_raw: str = first_match.group(1).strip()
        f2_raw: str = first_match.group(2).strip()
        l1_raw: str = last_match.group(1).strip()
        l2_raw: str = last_match.group(2).strip()

        if (
            self._normalize_name_token(f1_raw) in self.frequent_first_names
            and self._normalize_name_token(f2_raw) in self.frequent_first_names
        ):
            f1: str = (
                self._capitalize_word_segment(f1_raw)
                if f1_raw.isupper()
                else f1_raw
            )
            f2: str = (
                self._capitalize_word_segment(f2_raw)
                if f2_raw.isupper()
                else f2_raw
            )
            l1: str = (
                self._capitalize_word_segment(l1_raw)
                if l1_raw.isupper()
                else l1_raw
            )
            l2: str = (
                self._capitalize_word_segment(l2_raw)
                if l2_raw.isupper()
                else l2_raw
            )
            return f"{f1} {l1} et {f2} {l2}"

        return None

    @staticmethod
    def _get_first_non_empty_field(
        row: Dict[str, str], candidates: Tuple[str, ...]
    ) -> str:
        """
        Retourne la première valeur non vide parmi une liste de colonnes
        candidates (insensible à la casse).

        :param row: Ligne CSV lue par DictReader.
        :param candidates: Noms de colonnes possibles (Google / Outlook).
        :return: Valeur nettoyée ou chaîne vide.
        """
        lower_map: Dict[str, str] = {
            k.strip().lower(): (v or "").strip()
            for k, v in row.items()
            if k
        }
        for cand in candidates:
            val: str = lower_map.get(cand.lower(), "")
            if val:
                return val
        return ""

    def _extract_full_name(
        self, row: Dict[str, str], row_emails: List[str]
    ) -> str:
        """
        Construit la chaîne 'Prénom Nom' depuis les colonnes Google ou
        Microsoft 365 / Outlook (FR/EN), gère les couples et déduit l'identité.

        :param row: Dictionnaire représentant une ligne du fichier CSV.
        :param row_emails: Adresses e-mail extraites pour cette ligne CSV.
        :return: Nom complet nettoyé et ordonné, ou chaîne vide.
        """
        raw_first: str = self._get_first_non_empty_field(
            row, ("First Name", "Given Name", "Prénom", "Prenom")
        )
        raw_middle: str = self._get_first_non_empty_field(
            row,
            ("Middle Name", "Additional Name", "Deuxième prénom", "Deuxieme prenom"),
        )
        raw_last: str = self._get_first_non_empty_field(
            row, ("Last Name", "Family Name", "Nom de famille", "Nom")
        )

        c_first: str = self._sanitize_name_part(raw_first)
        c_middle: str = self._sanitize_name_part(raw_middle)
        c_last: str = self._sanitize_name_part(raw_last)

        if not c_first and not c_middle and not c_last:
            raw_full: str = self._get_first_non_empty_field(
                row, ("Name", "Nom complet", "Display Name", "Nom affiché")
            )
            if not raw_full:
                email_only_id: Optional[Tuple[str, str]] = (
                    self._extract_identity_from_email(row_emails)
                )
                if email_only_id:
                    e_first, e_last = email_only_id
                    print(
                        f"[IDENTITÉ DÉDUITE MAIL] {row_emails} -> "
                        f"'{e_first} {e_last}'"
                    )
                    return f"{e_first} {e_last}"
                return ""
            if "\x3c" in raw_full or "@" in raw_full:
                return raw_full
            if " " in raw_full:
                part_first, part_last = raw_full.split(" ", 1)
                c_first = self._sanitize_name_part(part_first)
                c_last = self._sanitize_name_part(part_last)
            else:
                c_first = self._sanitize_name_part(raw_full)

        if c_middle and re.search(r"\b(?:et|&)\b", c_middle, flags=re.IGNORECASE):
            couple_parts: List[str] = [
                p for p in [c_first, c_middle, c_last] if p
            ]
            return " ".join(couple_parts)

        if not c_middle:
            paired_couple: Optional[str] = (
                self._format_couple_from_paired_fields(c_first, c_last)
            )
            if paired_couple:
                return paired_couple
        if c_first and not c_middle and not c_last and row_emails:
            inferred_single: str = self._infer_last_name_from_emails(
                c_first, row_emails
            )
            if inferred_single:
                print(
                    f"[NOM DÉDUIT] '{c_first}' + {row_emails} -> "
                    f"'{c_first} {inferred_single}'"
                )
                return f"{c_first} {inferred_single}"

        org_candidate: str = " ".join(
            p for p in [c_first, c_middle, c_last] if p
        )
        words_in_label: List[str] = org_candidate.split()
        if len(words_in_label) >= 1 and row_emails and self.frequent_first_names:
            first_label_word: str = next(iter(words_in_label), "")
            first_tok: str = self._normalize_name_token(
                next(iter(re.split(r"[\s\-]+", first_label_word)), "")
            )
            last_label_word: str = words_in_label[-1]
            last_tok: str = self._normalize_name_token(
                next(iter(re.split(r"[\s\-]+", last_label_word)), "")
            )

            if (
                first_tok not in self.frequent_first_names
                and last_tok not in self.frequent_first_names
            ):
                email_identity: Optional[Tuple[str, str]] = (
                    self._extract_identity_from_email(row_emails)
                )
                if email_identity:
                    e_first, e_last = email_identity
                    clean_org: str = self._format_org_label(org_candidate)
                    print(
                        f"[ENSEIGNE + MAIL] '{org_candidate}' + "
                        f"{row_emails} -> '{e_first} {e_last} ({clean_org})'"
                    )
                    return f"{e_first} {e_last} ({clean_org})"

        if c_first and c_middle and not c_last:
            norm_f: str = self._normalize_name_token(c_first)
            norm_m: str = self._normalize_name_token(c_middle)
            if (
                norm_m in self.frequent_first_names
                and norm_f not in self.frequent_first_names
            ):
                first_name: str = c_middle
                last_name: str = c_first
            else:
                sep: str = "-" if norm_f in self.frequent_first_names else " "
                first_name = f"{c_first}{sep}{c_middle}"
                last_name = ""
        elif c_first and c_middle:
            sep = (
                "-"
                if self._normalize_name_token(c_first)
                in self.frequent_first_names
                else " "
            )
            first_name = f"{c_first}{sep}{c_middle}"
            last_name = c_last
        else:
            first_name = c_first or c_middle
            last_name = c_last

        if first_name and not last_name and row_emails:
            inferred: str = self._infer_last_name_from_emails(
                first_name, row_emails
            )
            if inferred:
                last_name = inferred
                print(
                    f"[NOM DÉDUIT] '{first_name}' + {row_emails} -> "
                    f"'{first_name} {last_name}'"
                )

        if first_name and last_name and self.frequent_first_names:
            first_word: str = next(iter(re.split(r"[\s\-]+", first_name)), "")
            last_word: str = next(iter(re.split(r"[\s\-]+", last_name)), "")
            if (
                self._normalize_name_token(last_word)
                in self.frequent_first_names
                and self._normalize_name_token(first_word)
                not in self.frequent_first_names
            ):
                print(
                    f"[INVERSION] '{first_name} {last_name}' -> "
                    f"'{last_name} {first_name}'"
                )
                first_name, last_name = last_name, first_name

        if first_name.isupper():
            first_name = self._capitalize_word_segment(first_name)
        if last_name.isupper():
            last_name = self._capitalize_word_segment(last_name)

        return f"{first_name} {last_name}".strip()

    def _is_contact_column(self, col_name: str) -> Tuple[bool, bool]:
        """
        Détermine si une colonne CSV Google ou Outlook (FR/EN) contient un
        téléphone ou une adresse e-mail.

        :param col_name: Nom de l'en-tête de colonne CSV.
        :return: Tuple (est_téléphone, est_email).
        """
        lower_col: str = col_name.strip().lower()
        ignored_markers: Tuple[str, ...] = (
            "type",
            "label",
            "étiquette",
            "etiquette",
            "display name",
            "nom affiché",
            "nom affiche",
        )
        if any(marker in lower_col for marker in ignored_markers):
            return False, False

        is_phone: bool = any(
            k in lower_col
            for k in ("phone", "téléphone", "telephone", "tél.", "tel.")
        )
        is_email: bool = any(
            k in lower_col
            for k in (
                "e-mail",
                "email",
                "mail",
                "adresse de messagerie",
                "courriel",
            )
        )
        return is_phone, is_email

    def _normalize_value(
        self, raw_val: str, is_phone: bool, is_email: bool
    ) -> str:
        """
        Applique les règles de nettoyage définies dans config.ini sur une
        coordonnée (et supprime les suffixes '+alias' sur les e-mails).

        :param raw_val: Valeur brute extraite de la cellule CSV.
        :param is_phone: Indique s'il s'agit d'un numéro de téléphone.
        :param is_email: Indique s'il s'agit d'une adresse e-mail.
        :return: Coordonnée normalisée.
        """
        cleaned: str = raw_val.strip()
        if is_phone and self.config.clean_phone_spaces:
            cleaned = re.sub(r"[\s\-\.]", "", cleaned)
        if is_email:
            cleaned = ContactTextUtils.normalize_email_alias(cleaned)
            if self.config.lowercase_emails:
                cleaned = cleaned.lower()
        return cleaned

    @staticmethod
    def _detect_csv_delimiter(sample: str) -> str:
        """
        Détecte automatiquement si le CSV utilise ',' (Google / Outlook EN)
        ou ';' (Outlook FR).

        :param sample: Début du contenu du fichier CSV.
        :return: Caractère délimiteur détecté.
        """
        first_line: str = sample.splitlines()[0] if sample.splitlines() else ""
        if first_line.count(";") > first_line.count(","):
            return ";"
        return ","

    def parse_file(self, file_path: str) -> List[Tuple[str, str]]:
        """
        Parcourt un fichier CSV Google Contacts ou Microsoft 365 / Outlook
        et retourne la liste des paires (coordonnée, nom).

        :param file_path: Chemin vers le fichier CSV à analyser.
        :return: Liste de tuples (coordonnée, prénom nom).
        """
        if not os.path.exists(file_path):
            print(f"[AVERTISSEMENT] Fichier introuvable ignoré : '{file_path}'")
            return []

        results: List[Tuple[str, str]] = []
        with open(
            file_path, mode="r", encoding=self.config.encoding, newline=""
        ) as csv_file:
            sample: str = csv_file.read(4096)
            csv_file.seek(0)
            delimiter: str = self._detect_csv_delimiter(sample)
            reader: csv.DictReader = csv.DictReader(
                csv_file, delimiter=delimiter
            )
            if not reader.fieldnames:
                return []

            target_cols: List[Tuple[str, bool, bool]] = [
                (col, *self._is_contact_column(col))
                for col in reader.fieldnames
                if any(self._is_contact_column(col))
            ]

            for row in reader:
                row_values: List[Tuple[str, bool]] = []
                row_emails: List[str] = []
                for col_name, is_phone, is_email in target_cols:
                    cell_value: str = (row.get(col_name) or "").strip()
                    if not cell_value:
                        continue
                    for sub_val in cell_value.split(":::"):
                        normalized: str = self._normalize_value(
                            sub_val, is_phone, is_email
                        )
                        if normalized:
                            row_values.append((normalized, is_email))
                            if is_email:
                                row_emails.append(normalized)

                full_name: str = self._extract_full_name(row, row_emails)
                if full_name:
                    for val, _ in row_values:
                        results.append((val, full_name))

        print(
            f"[INFO] {len(results)} entrée(s) extraite(s) depuis "
            f"'{file_path}' (délimiteur '{delimiter}')."
        )
        return results
