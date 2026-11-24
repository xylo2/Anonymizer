# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import os
import quopri
import re
from typing import Dict, List, Tuple
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.csv_reader import GoogleContactsReader


class VCardContactsReader:
    """
    Lit les fichiers vCard (.vcf 2.1 / 3.0 / 4.0) exportés depuis Apple / iCloud,
    Android ou Thunderbird et convertit chaque fiche en lignes normalisées
    compatibles avec GoogleContactsReader.
    """

    def __init__(self, config: ContactsConfig) -> None:
        self.config: ContactsConfig = config
        self._csv_helper: GoogleContactsReader = GoogleContactsReader(config=config)

    @staticmethod
    def _unfold_vcard_lines(raw_text: str) -> List[str]:
        """Déplie les lignes continuées (RFC 6350 : saut de ligne suivi d'un espace ou tabulation)."""
        normalized: str = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        unfolded: str = re.sub(r"\n[ \t]", "", normalized)
        return [ln.strip() for ln in unfolded.split("\n") if ln.strip()]

    @staticmethod
    def _decode_vcard_value(params_str: str, raw_val: str) -> str:
        """Décode une valeur vCard (QUOTED-PRINTABLE et échappements \\, \\; \\n)."""
        val: str = raw_val
        upper_params: str = params_str.upper()
        if "QUOTED-PRINTABLE" in upper_params:
            charset_m = re.search(r"CHARSET=([A-Za-z0-9_\-]+)", upper_params)
            charset: str = charset_m.group(1) if charset_m else "utf-8"
            try:
                val = quopri.decodestring(val.encode("ascii", errors="ignore")).decode(
                    charset, errors="ignore"
                )
            except Exception:
                pass
        val = val.replace("\\n", " ").replace("\\N", " ")
        val = val.replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")
        return val.strip()

    @staticmethod
    def _split_unescaped_semicolons(text: str) -> List[str]:
        """Découpe un champ N (Nom;Prénom;DeuxièmePrénom;Préfixe;Suffixe) sur ';' non échappés."""
        parts: List[str] = re.split(r"(?<!\\);", text)
        return [p.replace("\\;", ";").replace("\\,", ",").strip() for p in parts]

    def parse_file_rows(self, file_path: str) -> List[Dict[str, str]]:
        """Retourne les fiches d'un fichier .vcf sous forme de dictionnaires compatibles CSV."""
        if not os.path.exists(file_path):
            return []
        with open(file_path, mode="r", encoding="utf-8", errors="ignore") as f_vcf:
            raw_content: str = f_vcf.read()

        lines: List[str] = self._unfold_vcard_lines(raw_content)
        rows: List[Dict[str, str]] = []
        in_card: bool = False
        first_name: str = ""
        middle_name: str = ""
        last_name: str = ""
        full_name: str = ""
        org_name: str = ""
        emails: List[str] = []
        phones: List[str] = []

        for line in lines:
            upper_line: str = line.upper()
            if upper_line == "BEGIN:VCARD":
                in_card = True
                first_name = middle_name = last_name = full_name = org_name = ""
                emails = []
                phones = []
                continue
            if upper_line == "END:VCARD":
                if in_card and (emails or phones):
                    effective_full: str = full_name or org_name
                    rows.append({
                        "First Name": first_name,
                        "Middle Name": middle_name,
                        "Last Name": last_name,
                        "Name": effective_full if not (first_name or last_name) else "",
                        "E-mail 1 - Value": ":::".join(emails),
                        "Phone 1 - Value": ":::".join(phones),
                    })
                in_card = False
                continue
            if not in_card or ":" not in line:
                continue

            prop_head, raw_val = line.split(":", 1)
            prop_parts: List[str] = prop_head.split(";")
            prop_name: str = prop_parts[0].split(".")[-1].upper().strip()
            params_str: str = ";".join(prop_parts[1:])
            decoded_val: str = self._decode_vcard_value(params_str, raw_val)
            if not decoded_val:
                continue

            if prop_name == "N":
                n_parts: List[str] = self._split_unescaped_semicolons(raw_val)
                last_name = self._decode_vcard_value(params_str, n_parts[0]) if len(n_parts) > 0 else ""
                first_name = self._decode_vcard_value(params_str, n_parts[1]) if len(n_parts) > 1 else ""
                middle_name = self._decode_vcard_value(params_str, n_parts[2]) if len(n_parts) > 2 else ""
            elif prop_name == "FN":
                full_name = decoded_val
            elif prop_name == "ORG" and not org_name:
                org_name = decoded_val.replace(";", " ").strip()
            elif prop_name == "EMAIL":
                emails.append(decoded_val)
            elif prop_name == "TEL":
                phones.append(decoded_val)

        return rows

    def parse_file(self, file_path: str) -> List[Tuple[str, str]]:
        """Extrait toutes les paires (coordonnée, identité) depuis un fichier .vcf."""
        rows: List[Dict[str, str]] = self.parse_file_rows(file_path)
        results: List[Tuple[str, str]] = []
        for row in rows:
            row_values: List[str] = []
            row_emails: List[str] = []
            for raw_mail in (row.get("E-mail 1 - Value") or "").split(":::"):
                norm_m: str = self._csv_helper._normalize_value(raw_mail, is_phone=False, is_email=True)
                if norm_m:
                    row_values.append(norm_m)
                    row_emails.append(norm_m)
            for raw_tel in (row.get("Phone 1 - Value") or "").split(":::"):
                norm_t: str = self._csv_helper._normalize_value(raw_tel, is_phone=True, is_email=False)
                if norm_t:
                    row_values.append(norm_t)

            identity: str = self._csv_helper._extract_full_name(row, row_emails)
            if identity:
                for val in row_values:
                    results.append((val, identity))

        print(f"[INFO] {len(results)} entrée(s) extraite(s) depuis '{file_path}' (vCard .vcf).")
        return results
