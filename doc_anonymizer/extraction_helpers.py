import json
import os
import re
from typing import Dict, List, Optional, Set, Tuple
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_csv_importer import normalize_phone_identifier
from doc_anonymizer.text_utils import DocumentTextUtils


class ExtractionFilterLoader:
    """Charge les listes blanches de contacts/chats et normalise les numéros."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config: PipelineConfig = config

    @staticmethod
    def normalize_any_phone(raw_phone: str) -> str:
        """Normalise un numéro de téléphone FR ou international."""
        fr_norm: str = DocumentTextUtils._normalize_fr_phone(raw_phone)
        if fr_norm:
            return fr_norm
        generic: str = normalize_phone_identifier(raw_phone)
        if not generic or "@" in generic or any(ch.isalpha() for ch in generic):
            return ""
        digits_only: str = re.sub(r"\D", "", generic)
        return generic if len(digits_only) >= 4 else ""

    def load_filter_paths_list(self) -> List[str]:
        """Retourne la liste des fichiers de contacts utilisés pour le filtrage."""
        sel_file: str = getattr(
            self.config, "selected_extraction_contacts_file", ""
        )
        if sel_file and os.path.exists(sel_file):
            return [sel_file, self.config.manual_contacts_file]
        return [
            self.config.contacts_file,
            self.config.discovered_contacts_file,
            self.config.discovered_chats_file,
            self.config.manual_contacts_file,
        ]
    def load_allowed_chat_names(self) -> Optional[Set[str]]:
        """Retourne les noms autorisés depuis whitelist_contacts.json, ou None si absent."""
        contacts_dir: str = os.path.dirname(
            os.path.abspath(self.config.contacts_file)
        )
        wl_file: str = os.path.join(contacts_dir, "whitelist_contacts.json")
        if not os.path.isfile(wl_file):
            return None
        allowed_names: Set[str] = set()
        try:
            with open(wl_file, "r", encoding="utf-8") as f_wl:
                raw_list = json.load(f_wl)
            if isinstance(raw_list, list):
                for entry in raw_list:
                    val: str = str(entry).strip()
                    if not val or "@" in val or any(ch.isdigit() for ch in val):
                        continue
                    norm_n: str = DocumentTextUtils.normalize_word(val)
                    if len(norm_n) >= 2:
                        allowed_names.add(norm_n)
        except (OSError, json.JSONDecodeError):
            pass
        return allowed_names

    def load_allowed_chat_titles(self) -> Optional[Set[str]]:
        """Retourne les titres de conversations autorisés, ou None si absent."""
        contacts_dir: str = os.path.dirname(
            os.path.abspath(self.config.contacts_file)
        )
        wl_chat_file: str = os.path.join(contacts_dir, "whitelist_chats.json")
        if not os.path.isfile(wl_chat_file):
            return None
        allowed_titles: Set[str] = set()
        try:
            with open(wl_chat_file, "r", encoding="utf-8") as f_wc:
                raw_list = json.load(f_wc)
            if isinstance(raw_list, list):
                for entry in raw_list:
                    norm_t: str = DocumentTextUtils.normalize_word(str(entry))
                    if norm_t:
                        allowed_titles.add(norm_t)
        except (OSError, json.JSONDecodeError):
            pass
        return allowed_titles
    def is_chat_file_allowed_by_whitelist(
        self, file_path: str, allowed_titles: Optional[Set[str]]
    ) -> bool:
        """Vérifie si une conversation de chat est autorisée par whitelist_chats.json."""
        if allowed_titles is None:
            return True
        from doc_anonymizer.chat_filter_manager import ChatFilterManager

        meta = ChatFilterManager._inspect_chat_metadata(file_path)
        if not meta:
            return True
        norm_title: str = DocumentTextUtils.normalize_word(
            str(meta.get("title") or "")
        )
        return norm_title in allowed_titles

    def load_all_filter_contacts(self) -> Tuple[Dict[str, str], Set[str]]:
        """Charge tous les numéros et e-mails retenus pour le filtrage."""
        target_phones: Dict[str, str] = {}
        allowed_emails: Set[str] = set()
        for path in self.load_filter_paths_list():
            if not path or not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as f_in:
                for raw_line in f_in:
                    line: str = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    left_p, right_p = line.split("=", 1)
                    left, right = left_p.strip(), right_p.strip()
                    if not left or not right:
                        continue
                    if "@" in right and "@" not in left:
                        left, right = right, left
                    elif self.normalize_any_phone(right) and not self.normalize_any_phone(left):
                        left, right = right, left
                    if "@" in left:
                        norm_m: str = DocumentTextUtils.normalize_identifier(left)
                        if norm_m:
                            allowed_emails.add(norm_m)
                    else:
                        norm_p: str = self.normalize_any_phone(left)
                        if norm_p:
                            target_phones[norm_p] = right
        return target_phones, allowed_emails


class ExtractionReportWriter:
    """Consolide et écrit les rapports finaux (numéros SMS, e-mails, anomalies)."""

    IGNORED_SUFFIXES: Tuple[str, ...] = ("chat." + "google.com", "://" + "google.com")

    def __init__(self, config: PipelineConfig) -> None:
        self.config: PipelineConfig = config

    @classmethod
    def _merge_existing_lines(
        cls, file_path: str, phones_out: Set[str], emails_out: Set[str]
    ) -> None:
        """Fusionne les entrées déjà enregistrées dans un fichier de rapport."""
        if not file_path or not os.path.exists(file_path):
            return
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f_old:
            for ln in f_old:
                s: str = ln.strip()
                if not s or s.startswith("#"):
                    continue
                if "@" in s:
                    nm: str = DocumentTextUtils.normalize_identifier(s)
                    if nm and not nm.endswith(cls.IGNORED_SUFFIXES):
                        emails_out.add(nm)
                else:
                    np: str = ExtractionFilterLoader.normalize_any_phone(s)
                    if np:
                        phones_out.add(np)
    def finalize_reports(
        self,
        discovered_phones: Set[str],
        discovered_emails: Set[str],
        warnings: List[str],
    ) -> None:
        """Écrit les rapports finaux (numéros SMS, e-mails et anomalies)."""
        clean_phones: Set[str] = set()
        clean_emails: Set[str] = set()
        for raw_p in discovered_phones:
            if "@" in raw_p:
                nm = DocumentTextUtils.normalize_identifier(raw_p)
                if nm and not nm.endswith(self.IGNORED_SUFFIXES):
                    clean_emails.add(nm)
            else:
                np = ExtractionFilterLoader.normalize_any_phone(raw_p)
                if np:
                    clean_phones.add(np)
        for raw_e in discovered_emails:
            ne = DocumentTextUtils.normalize_identifier(raw_e)
            if ne and "@" in ne and not ne.endswith(self.IGNORED_SUFFIXES):
                clean_emails.add(ne)

        if self.config.all_sms_numbers_file:
            self._merge_existing_lines(
                self.config.all_sms_numbers_file, clean_phones, clean_emails
            )
            os.makedirs(
                os.path.dirname(os.path.abspath(self.config.all_sms_numbers_file)),
                exist_ok=True,
            )
            DocumentTextUtils.atomic_write_text(
                self.config.all_sms_numbers_file,
                "# NUMÉROS DÉTECTÉS\n"
                + "".join(f"{p}\n" for p in sorted(clean_phones)),
            )

        if self.config.all_emails_file:
            self._merge_existing_lines(
                self.config.all_emails_file, clean_phones, clean_emails
            )
            os.makedirs(
                os.path.dirname(os.path.abspath(self.config.all_emails_file)),
                exist_ok=True,
            )
            DocumentTextUtils.atomic_write_text(
                self.config.all_emails_file,
                "# E-MAILS DÉTECTÉS\n"
                + "".join(f"{e}\n" for e in sorted(clean_emails)),
            )

        if self.config.extraction_report_file:
            os.makedirs(
                os.path.dirname(os.path.abspath(self.config.extraction_report_file)),
                exist_ok=True,
            )
            body: str = "\n".join(warnings) if warnings else "Aucune anomalie détectée."
            DocumentTextUtils.atomic_write_text(
                self.config.extraction_report_file,
                f"# RAPPORT D'EXTRACTION\n{body}\n",
            )
