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
            "paths", "sources_dir", "input_documents"
        )
        self.transcriptions_dir: str = self._resolve_path(
            "paths", "transcriptions_dir", "extracted_texts"
        )
        self.results_dir: str = self._resolve_path(
            "paths", "results_dir", "anonymized_results"
        )
        self.contacts_file: str = self._resolve_path(
            "paths", "contacts_file", "output_contacts/contacts.txt"
        )
        self.indexed_contacts_file: str = self._resolve_path(
            "files", "output_file", "output_contacts/.intermediates/indexed_contacts.txt"
        )
        self.anonymized_contacts_file: str = self._resolve_path(
            "files", "anonymized_output_file", "output_contacts/.intermediates/anonymized_contacts.txt"
        )
        self.deduplicated_contacts_file: str = self._resolve_path(
            "files", "deduplicated_output_file", "output_contacts/.intermediates/deduplicated_contacts.txt"
        )
        self.surnames_contacts_file: str = self._resolve_path(
            "paths", "surnames_contacts_file", "output_contacts/.intermediates/contact_surnames.txt"
        )
        self.manual_contacts_file: str = self._resolve_path(
            "paths", "manual_contacts_file", "output_contacts/manual_contacts.txt"
        )
        self.discovered_contacts_file: str = self._resolve_path(
            "paths", "discovered_contacts_file", "output_contacts/discovered_email_contacts.txt"
        )
        self.discovered_chats_file: str = self._resolve_path(
            "paths", "discovered_chats_file", "output_contacts/discovered_chat_contacts.txt"
        )
        self.all_sms_numbers_file: str = self._resolve_path(
            "paths", "all_sms_numbers_file", "audits/all_sms_numbers.txt"
        )
        self.all_emails_file: str = self._resolve_path(
            "paths", "all_emails_file", "audits/all_found_emails.txt"
        )
        self.audit_report_file: str = self._resolve_path(
            "paths", "audit_report_file", "audits/residual_names_audit.txt"
        )
        self.audit_copy_file: str = self._resolve_path(
            "paths", "audit_copy_file", "audits/residual_names_copy.txt"
        )
        self.extraction_report_file: str = self._resolve_path(
            "paths", "extraction_report_file", "audits/extraction_report.txt"
        )

        self.first_names_file: str = self._resolve_path(
            "files", "first_names_file", "data/prenoms.txt"
        )
        self.locations_file: str = self._resolve_path(
            "files", "locations_file", "data/villes_masquees.txt"
        )
        self.surname_collisions_file: str = self._resolve_path(
            "files", "surname_collisions_file", "data/collisions_noms.txt"
        )
        self.excluded_words_file: str = self._resolve_path(
            "files", "excluded_words_file", "data/mots_exclus.txt"
        )

        self.state_file: str = os.path.join(
            self.results_dir, ".anonymization_state.json"
        )
        self.resume_state_file: str = self.state_file
        self.extraction_state_file: str = os.path.join(
            self.transcriptions_dir, ".extraction_state.txt"
        )
        self.extraction_tracking_file: str = self.extraction_state_file
        self.sms_tracking_file: str = os.path.join(
            self.transcriptions_dir, ".sms_state.txt"
        )
        self.email_tracking_file: str = os.path.join(
            self.transcriptions_dir, ".email_state.txt"
        )
        self.main_character_name: str = self._parser.get(
            "anonymization", "main_character_name", fallback="Personnage_Principal"
        ).strip()
        self.file_prefix: str = self._parser.get(
            "anonymization", "file_prefix", fallback="anonymized_"
        ).strip()
        self.max_batch_bytes: int = self._parser.getint(
            "anonymization", "max_batch_bytes", fallback=184320
        )
        self.max_batch_files: int = self._parser.getint(
            "anonymization", "max_batch_files", fallback=50
        )
        self.files_per_folder: int = max(
            1,
            self._parser.getint("anonymization", "files_per_folder", fallback=10),
        )
        self.min_audit_occurrences: int = max(
            1,
            self._parser.getint(
                "anonymization", "min_audit_occurrences", fallback=1
            ),
        )

        self.mask_ssn: bool = self._parser.getboolean(
            "anonymization", "mask_ssn", fallback=True
        )
        self.mask_addresses: bool = self._parser.getboolean(
            "anonymization", "mask_addresses", fallback=True
        )
        self.mask_urls: bool = self._parser.getboolean(
            "anonymization", "mask_urls", fallback=True
        )
        self.mask_financial_and_admin_ids: bool = self._parser.getboolean(
            "anonymization", "mask_financial_and_admin_ids", fallback=True
        )

        raw_birth_dates: str = self._parser.get(
            "anonymization", "masked_birth_dates", fallback=""
        )
        self.masked_birth_dates: List[str] = [
            d.strip() for d in raw_birth_dates.split(",") if d.strip()
        ]
        self.custom_birth_date_pattern: Optional[Pattern[str]] = (
            self._compile_custom_dates_pattern(self.masked_birth_dates)
        )

        self.enable_ocr: bool = self._parser.getboolean(
            "extraction", "enable_ocr", fallback=True
        )
        self.enable_audio: bool = self._parser.getboolean(
            "extraction", "enable_audio", fallback=True
        )
        self.ignore_google_chat_images: bool = self._parser.getboolean(
            "extraction", "ignore_google_chat_images", fallback=True
        )
        self.whisper_model: str = self._parser.get(
            "extraction", "whisper_model", fallback="base"
        ).strip()
        self.defer_heavy_files: bool = self._parser.getboolean(
            "extraction", "defer_heavy_files", fallback=True
        )
        self.heavy_file_threshold_mb: float = self._parser.getfloat(
            "extraction", "heavy_file_threshold_mb", fallback=25.0
        )
        self.extraction_workers: int = self._parser.getint(
            "extraction", "extraction_workers", fallback=0
        )

        raw_ignored: str = self._parser.get(
            "extraction",
            "ignored_dirs",
            fallback=(
                "extracted_texts, anonymized_results, output_contacts, audits, "
                "data, docs, venv, .venv, .git, __pycache__, common, tools, tests"
            ),
        )
        self.ignored_dirs: Set[str] = {
            d.strip() for d in raw_ignored.split(",") if d.strip()
        }

        self.secret_salt: str = self._load_or_create_salt()
        self.known_first_names: Set[str] = set()
        self.masked_locations: Set[str] = set()
        self.surname_collisions: Set[str] = set()
        self.excluded_words: Set[str] = set()
        self.domain_aliases: Dict[str, str] = {}
        self.load_external_lists()

    def load_external_lists(self) -> None:
        """Charge ou recharge les référentiels externes (prénoms, villes, exclusions)."""
        self.known_first_names = self._load_word_set(self.first_names_file)
        self.masked_locations = self._load_locations_set()
        self.surname_collisions = self._load_word_set(
            self.surname_collisions_file
        )
        self.excluded_words = self._load_word_set(self.excluded_words_file)
        self.domain_aliases = self._load_domain_aliases()

    def _resolve_path(self, section: str, key: str, default: str) -> str:
        """Résout un chemin relatif par rapport à config.ini."""
        raw_val: str = self._parser.get(section, key, fallback=default).strip()
        if os.path.isabs(raw_val):
            return os.path.normpath(raw_val)
        return os.path.normpath(os.path.join(self.base_dir, raw_val))

    def _load_or_create_salt(self) -> str:
        """Charge le sel cryptographique depuis config.ini ou .secret_salt."""
        ini_salt: str = self._parser.get(
            "anonymization", "secret_salt", fallback=""
        ).strip()
        if ini_salt and ini_salt != "REMPLACER_PAR_UNE_CHAINE_ALEATOIRE_UNIQUE":
            return ini_salt
        salt_file: str = os.path.join(self.base_dir, ".secret_salt")
        if os.path.exists(salt_file):
            with open(salt_file, "r", encoding="utf-8") as f:
                existing: str = f.read().strip()
                if existing:
                    return existing
        generated: str = secrets.token_hex(32)
        with open(salt_file, "w", encoding="utf-8") as f:
            f.write(generated)
        return generated

    @staticmethod
    def _load_word_set(file_path: str) -> Set[str]:
        """Charge un fichier dictionnaire en ensemble de mots normalisés."""
        words: Set[str] = set()
        if not file_path or not os.path.exists(file_path):
            return words
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                stripped: str = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                norm: str = DocumentTextUtils.normalize_word(stripped)
                if norm:
                    words.add(norm)
        return words

    def _load_locations_set(self) -> Set[str]:
        """Charge les communes masquées depuis data/villes_masquees.txt + extra_locations."""
        locs: Set[str] = self._load_word_set(self.locations_file)
        extra: str = self._parser.get(
            "anonymizer", "extra_locations", fallback=""
        )
        for item in extra.split(","):
            norm: str = DocumentTextUtils.normalize_word(item.strip())
            if norm:
                locs.add(norm)
        return locs

    def _load_domain_aliases(self) -> Dict[str, str]:
        """Charge la section [domain_aliases] en minuscules."""
        aliases: Dict[str, str] = {}
        if self._parser.has_section("domain_aliases"):
            for k, v in self._parser.items("domain_aliases"):
                clean_k: str = k.strip().lower()
                clean_v: str = v.strip()
                if clean_k and clean_v:
                    aliases[clean_k] = clean_v
        return aliases

    @staticmethod
    def _compile_custom_dates_pattern(
        dates_list: List[str],
    ) -> Optional[Pattern[str]]:
        """Compile un motif regex tolérant les formats JJ/MM/AAAA, AAAA-MM-JJ et AAAAMMJJ."""
        patterns: List[str] = []
        for raw_d in dates_list:
            m_fr = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", raw_d)
            m_iso = re.fullmatch(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", raw_d)
            if m_fr:
                dd, mm, yyyy = m_fr.group(1).zfill(2), m_fr.group(2).zfill(2), m_fr.group(3)
            elif m_iso:
                yyyy, mm, dd = m_iso.group(1), m_iso.group(2).zfill(2), m_iso.group(3).zfill(2)
            else:
                continue
            d_pat: str = str(int(dd)) if int(dd) >= 10 else f"0?{int(dd)}"
            m_pat: str = str(int(mm)) if int(mm) >= 10 else f"0?{int(mm)}"
            patterns.append(rf"{d_pat}[/\-.\s]{m_pat}[/\-.\s]{yyyy}")
            patterns.append(rf"{yyyy}[/\-.\s]{m_pat}[/\-.\s]{d_pat}")
            patterns.append(rf"{yyyy}{mm}{dd}")
        if not patterns:
            return None
        return re.compile(rf"(?<!\d)(?:{'|'.join(patterns)})(?!\d)")
    def load_external_lists(self) -> None:
        """Charge ou recharge les référentiels externes (prénoms, villes, exclusions)."""
        self.known_first_names = self._load_word_set(self.first_names_file)
        self.masked_locations = self._load_locations_set()
        self.surname_collisions = self._load_word_set(
            self.surname_collisions_file
        )
        self.excluded_words = self._load_word_set(self.excluded_words_file)
        self.domain_aliases = self._load_domain_aliases()

    def _resolve_path(self, section: str, key: str, default: str) -> str:
        """Résout un chemin relatif par rapport à config.ini."""
        raw_val: str = self._parser.get(section, key, fallback=default).strip()
        if os.path.isabs(raw_val):
            return os.path.normpath(raw_val)
        return os.path.normpath(os.path.join(self.base_dir, raw_val))

    def _load_or_create_salt(self) -> str:
        """Charge le sel cryptographique depuis config.ini ou .secret_salt."""
        ini_salt: str = self._parser.get(
            "anonymization", "secret_salt", fallback=""
        ).strip()
        if ini_salt and ini_salt != "REMPLACER_PAR_UNE_CHAINE_ALEATOIRE_UNIQUE":
            return ini_salt
        salt_file: str = os.path.join(self.base_dir, ".secret_salt")
        if os.path.exists(salt_file):
            with open(salt_file, "r", encoding="utf-8") as f:
                existing: str = f.read().strip()
                if existing:
                    return existing
        generated: str = secrets.token_hex(32)
        with open(salt_file, "w", encoding="utf-8") as f:
            f.write(generated)
        return generated

    @staticmethod
    def _load_word_set(file_path: str) -> Set[str]:
        """Charge un fichier dictionnaire en ensemble de mots normalisés."""
        words: Set[str] = set()
        if not file_path or not os.path.exists(file_path):
            return words
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                stripped: str = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                norm: str = DocumentTextUtils.normalize_word(stripped)
                if norm:
                    words.add(norm)
        return words

    def _load_locations_set(self) -> Set[str]:
        """Charge les communes masquées depuis data/villes_masquees.txt + extra_locations."""
        locs: Set[str] = self._load_word_set(self.locations_file)
        extra: str = self._parser.get(
            "anonymizer", "extra_locations", fallback=""
        )
        for item in extra.split(","):
            norm: str = DocumentTextUtils.normalize_word(item.strip())
            if norm:
                locs.add(norm)
        return locs

    def _load_domain_aliases(self) -> Dict[str, str]:
        """Charge la section [domain_aliases] en minuscules."""
        aliases: Dict[str, str] = {}
        if self._parser.has_section("domain_aliases"):
            for k, v in self._parser.items("domain_aliases"):
                clean_k: str = k.strip().lower()
                clean_v: str = v.strip()
                if clean_k and clean_v:
                    aliases[clean_k] = clean_v
        return aliases

    @staticmethod
    def _compile_custom_dates_pattern(
        dates_list: List[str],
    ) -> Optional[Pattern[str]]:
        """Compile un motif regex tolérant JJ/MM/AAAA, AAAA-MM-JJ, AAAAMMJJ et JJMMAAAA."""
        patterns: List[str] = []
        for raw_d in dates_list:
            m_fr = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", raw_d)
            m_iso = re.fullmatch(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", raw_d)
            if m_fr:
                dd, mm, yyyy = m_fr.group(1).zfill(2), m_fr.group(2).zfill(2), m_fr.group(3)
            elif m_iso:
                yyyy, mm, dd = m_iso.group(1), m_iso.group(2).zfill(2), m_iso.group(3).zfill(2)
            else:
                continue
            d_pat: str = str(int(dd)) if int(dd) >= 10 else f"0?{int(dd)}"
            m_pat: str = str(int(mm)) if int(mm) >= 10 else f"0?{int(mm)}"
            patterns.append(rf"{d_pat}[/\-.\s]{m_pat}[/\-.\s]{yyyy}")
            patterns.append(rf"{yyyy}[/\-.\s]{m_pat}[/\-.\s]{d_pat}")
            patterns.append(rf"{yyyy}{mm}{dd}")
            patterns.append(rf"{dd}{mm}{yyyy}")
        if not patterns:
            return None
        return re.compile(rf"(?<!\d)(?:{'|'.join(patterns)})(?!\d)")
