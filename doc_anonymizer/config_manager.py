# Commandes pip à exécuter : Aucune dépendance externe requise

import configparser
import os
import re
import secrets
from typing import Dict, List, Optional, Pattern, Set
from doc_anonymizer.text_utils import DocumentTextUtils


class PipelineConfig:
    """
    Centralise les paramètres du pipeline d'extraction et d'anonymisation
    lus depuis un fichier INI partagé.
    """

    DEFAULT_CONFIG_PATH: str = "config.ini"

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH) -> None:
        """
        Initialise et charge la configuration depuis le fichier INI.

        :param config_path: Chemin vers le fichier de configuration INI.
        """
        self.config_path: str = os.path.abspath(config_path)
        self.base_dir: str = os.path.dirname(self.config_path) or os.getcwd()
        self._parser: configparser.ConfigParser = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            self._parser.read(self.config_path, encoding="utf-8")

        self.root_dir: str = self._resolve_path("paths", "root_dir", ".")
        self.sources_dir: str = self._resolve_path(
            "paths", "sources_dir", "fichiers sources"
        )
        self.transcriptions_dir: str = self._resolve_path(
            "paths", "transcriptions_dir", "transcriptions"
        )
        self.results_dir: str = self._resolve_path(
            "paths", "results_dir", "resultats_anonymisation"
        )
        self.contacts_file: str = self._resolve_path(
            "paths", "contacts_file", "contacts.txt"
        )
        self.indexed_contacts_file: str = self._resolve_path(
            "files", "output_file", "contacts_indexes.txt"
        )
        self.anonymized_contacts_file: str = self._resolve_path(
            "files", "anonymized_output_file", "contacts_anonymises.txt"
        )
        self.deduplicated_contacts_file: str = self._resolve_path(
            "files", "deduplicated_output_file", "contacts_dedoublonnes.txt"
        )
        self.surnames_contacts_file: str = self._resolve_path(
            "paths", "surnames_contacts_file", "noms_famille_contacts.txt"
        )
        self.manual_contacts_file: str = self._resolve_path(
            "paths", "manual_contacts_file", "contacts_manuels.txt"
        )
        self.discovered_contacts_file: str = self._resolve_path(
            "paths", "discovered_contacts_file", "contacts_emails_decouverts.txt"
        )
        self.all_sms_numbers_file: str = self._resolve_path(
            "paths", "all_sms_numbers_file", "tous_numeros_sms.txt"
        )
        self.all_emails_file: str = self._resolve_path(
            "paths", "all_emails_file", "tous_emails_trouves.txt"
        )
        self.audit_report_file: str = self._resolve_path(
            "paths", "audit_report_file", "audit_noms_residuels.txt"
        )
        self.audit_copy_file: str = self._resolve_path(
            "paths", "audit_copy_file", "audit_noms_residuels_copier.txt"
        )

        self.first_names_file: str = self._resolve_path(
            "files", "first_names_file", "prenoms.txt"
        )
        self.locations_file: str = self._resolve_path(
            "files", "locations_file", "villes_masquees.txt"
        )
        self.surname_collisions_file: str = self._resolve_path(
            "files", "surname_collisions_file", "collisions_noms.txt"
        )
        self.excluded_words_file: str = self._resolve_path(
            "files", "excluded_words_file", "mots_exclus.txt"
        )

        self.state_file: str = os.path.join(
            self.results_dir, ".etat_anonymisation.json"
        )
        self.resume_state_file: str = self.state_file
        self.extraction_state_file: str = os.path.join(
            self.transcriptions_dir, ".etat_extraction.json"
        )
        self.extraction_tracking_file: str = self.extraction_state_file
        self.sms_tracking_file: str = os.path.join(
            self.transcriptions_dir, ".etat_sms.txt"
        )
        self.email_tracking_file: str = os.path.join(
            self.transcriptions_dir, ".etat_emails.txt"
        )

        self.enable_ocr: bool = self._get_bool("extraction", "enable_ocr", True)
        self.enable_audio: bool = self._get_bool(
            "extraction", "enable_audio", True
        )
        self.whisper_model: str = self._get_str(
            "extraction", "whisper_model", "base"
        )
        self.defer_heavy_files: bool = self._get_bool(
            "extraction", "defer_heavy_files", True
        )
        self.heavy_file_threshold_mb: float = self._get_float(
            "extraction", "heavy_file_threshold_mb", 25.0
        )
        self.extraction_workers: int = self._get_int(
            "extraction", "extraction_workers", 0
        )
        self.ignored_dirs: Set[str] = self._get_csv_set(
            "extraction",
            "ignored_dirs",
            "transcriptions, resultats_anonymisation, venv, .venv, .git, "
            "__pycache__, common, tools, tests",
        )

        self.main_character_name: str = self._get_str(
            "anonymization", "main_character_name", "Personnage_Principal"
        )
        self.secret_salt: str = self._get_str(
            "anonymization", "secret_salt", ""
        ) or secrets.token_hex(16)
        self.file_prefix: str = self._get_str(
            "anonymization", "file_prefix", "anonymise_"
        )
        self.max_batch_bytes: int = self._get_int(
            "anonymization", "max_batch_bytes", 184320
        )
        self.max_batch_files: int = self._get_int(
            "anonymization", "max_batch_files", 50
        )
        self.files_per_folder: int = self._get_int(
            "anonymization", "files_per_folder", 10
        )
        self.min_audit_occurrences: int = self._get_int(
            "anonymization", "min_audit_occurrences", 1
        )
        self.mask_ssn: bool = self._get_bool("anonymization", "mask_ssn", True)
        self.mask_addresses: bool = self._get_bool(
            "anonymization", "mask_addresses", True
        )
        self.mask_urls: bool = self._get_bool(
            "anonymization", "mask_urls", True
        )
        self.mask_financial_and_admin_ids: bool = self._get_bool(
            "anonymization", "mask_financial_and_admin_ids", True
        )
        self.masked_birth_dates: List[str] = self._get_csv_list(
            "anonymization", "masked_birth_dates", ""
        )
        self.custom_birth_date_pattern: Optional[Pattern[str]] = (
            self._compile_custom_dates_pattern(self.masked_birth_dates)
        )
        self.ignored_domains: Set[str] = self._get_csv_set(
            "anonymizer",
            "ignored_domains",
            "gmail, googlemail, yahoo, hotmail, outlook, live, msn, orange, "
            "wanadoo, free, sfr, laposte, icloud, aol, protonmail, proton",
        )
        self.domain_aliases: Dict[str, str] = {}
        if self._parser.has_section("domain_aliases"):
            for k, v in self._parser.items("domain_aliases"):
                if k.strip() and v.strip():
                    self.domain_aliases[k.strip().lower()] = v.strip()

        self.known_first_names: Set[str] = set()
        self.masked_locations: Set[str] = set()
        self.surname_collisions: Set[str] = set()
        self.excluded_words: Set[str] = set()
        self.load_external_lists()

    def load_external_lists(self) -> None:
        """Charge ou recharge les dictionnaires externes (prénoms, lieux, collisions, mots exclus)."""
        self.known_first_names = self._load_word_set(self.first_names_file)
        self.masked_locations = self._load_word_set(self.locations_file)
        for extra_loc in self._get_csv_set("anonymizer", "extra_locations", ""):
            norm_loc: str = DocumentTextUtils.normalize_word(extra_loc)
            if norm_loc:
                self.masked_locations.add(norm_loc)
        self.surname_collisions = self._load_word_set(
            self.surname_collisions_file
        )
        self.excluded_words = self._load_word_set(self.excluded_words_file)

    def _resolve_path(self, section: str, key: str, default: str) -> str:
        """Résout un chemin relatif par rapport au dossier du fichier INI."""
        raw_val: str = self._get_str(section, key, default)
        if os.path.isabs(raw_val):
            return os.path.normpath(raw_val)
        return os.path.normpath(os.path.join(self.base_dir, raw_val))

    def _get_str(self, section: str, key: str, default: str) -> str:
        """Lit une chaîne de caractères depuis la configuration."""
        if self._parser.has_option(section, key):
            val: str = self._parser.get(section, key).strip()
            if val:
                return val
        return default

    def _get_int(self, section: str, key: str, default: int) -> int:
        """Lit un entier depuis la configuration."""
        if self._parser.has_option(section, key):
            try:
                return self._parser.getint(section, key)
            except ValueError:
                return default
        return default

    def _get_float(self, section: str, key: str, default: float) -> float:
        """Lit un flottant depuis la configuration."""
        if self._parser.has_option(section, key):
            try:
                return self._parser.getfloat(section, key)
            except ValueError:
                return default
        return default

    def _get_bool(self, section: str, key: str, default: bool) -> bool:
        """Lit un booléen depuis la configuration."""
        if self._parser.has_option(section, key):
            try:
                return self._parser.getboolean(section, key)
            except ValueError:
                return default
        return default

    def _get_csv_set(self, section: str, key: str, default: str) -> Set[str]:
        """Lit une liste séparée par des virgules et retourne un ensemble en minuscules."""
        raw: str = self._get_str(section, key, default)
        return {item.strip().lower() for item in raw.split(",") if item.strip()}

    def _get_csv_list(self, section: str, key: str, default: str) -> List[str]:
        """Lit une liste ordonnée séparée par des virgules."""
        raw: str = self._get_str(section, key, default)
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _compile_custom_dates_pattern(
        raw_dates: List[str],
    ) -> Optional[Pattern[str]]:
        """Compile un motif multi-formats pour chaque date déclarée dans config.ini."""
        month_names: Dict[str, str] = {
            "01": r"janvier|janv\.?|jan\.?",
            "02": r"f[ée]vrier|f[ée]vr\.?|feb\.?",
            "03": r"mars|mar\.?",
            "04": r"avril|avr\.?|apr\.?",
            "05": r"mai|may",
            "06": r"juin|jun\.?",
            "07": r"juillet|juil\.?|jul\.?",
            "08": r"ao[ûu]t|aug\.?",
            "09": r"septembre|sept\.?|sep\.?",
            "10": r"octobre|oct\.?",
            "11": r"novembre|nov\.?",
            "12": r"d[ée]cembre|d[ée]c\.?|dec\.?",
        }
        branches: List[str] = []
        for raw in raw_dates:
            day_s, month_s, year_s = "", "", ""
            m_fr = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.]((?:19|20)\d{2})", raw)
            m_iso = re.fullmatch(r"((?:19|20)\d{2})[/\-.](\d{1,2})[/\-.](\d{1,2})", raw)
            if m_fr:
                day_s, month_s, year_s = m_fr.group(1).zfill(2), m_fr.group(2).zfill(2), m_fr.group(3)
            elif m_iso:
                year_s, month_s, day_s = m_iso.group(1), m_iso.group(2).zfill(2), m_iso.group(3).zfill(2)
            else:
                continue

            d_ocr: str = day_s.replace("0", "[0Oo]").replace("5", "[5Ss]")
            if day_s.startswith("0"):
                d_ocr = f"(?:[0Oo]?{day_s.replace('5', '[5Ss]')})"
            m_ocr: str = month_s.replace("0", "[0Oo]").replace("5", "[5Ss]")
            if month_s.startswith("0"):
                m_ocr = f"(?:[0Oo]?{month_s.replace('5', '[5Ss]')})"
            y2: str = year_s[2:]
            m_word: str = month_names.get(month_s, month_s)

            branches.append(rf"(?<!\d){d_ocr}\s*[/\-.]\s*{m_ocr}\s*[/\-.]\s*(?:{year_s}|{y2})(?!\d)")
            branches.append(rf"(?<!\d){year_s}\s*[/\-.]\s*{m_ocr}\s*[/\-.]\s*{d_ocr}(?!\d)")
            branches.append(rf"(?<!\d){year_s}{month_s}{day_s}(?!\d)")
            branches.append(rf"(?<!\d){day_s}{month_s}{year_s}(?!\d)")
            branches.append(rf"(?i)(?<!\d){d_ocr}\s+(?:{m_word})\s+{year_s}(?!\d)")

        if not branches:
            return None
        return re.compile("|".join(branches))

    @staticmethod
    def _load_word_set(file_path: str) -> Set[str]:
        """Charge un fichier dictionnaire ligne par ligne en un ensemble normalisé."""
        words: Set[str] = set()
        if not os.path.exists(file_path):
            return words
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line: str = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                norm: str = DocumentTextUtils.normalize_word(line)
                if norm:
                    words.add(norm)
        return words
