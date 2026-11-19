# Commandes pip à exécuter : Aucune dépendance externe requise

import configparser
import os
import secrets
from typing import FrozenSet, Set
from common.core_utils import SharedCoreUtils
from google_contacts_parser.geo_data import FrenchGeoCatalog


class PipelineConfig:
    """
    Charge et expose de manière typée les paramètres techniques d'extraction
    et d'anonymisation depuis le fichier config.ini unifié, en partageant
    prenoms.txt, villes_masquees.txt, mots_exclus.txt et les index de contacts.
    """

    DEFAULT_PLACEHOLDER_SALT: str = "cle_secrete_a_modifier_987"

    COMMON_WORD_LOCATIONS: FrozenSet[str] = frozenset({
        "reunion", "la reunion", "centre", "nord", "sud", "est", "ouest",
        "cher", "orne", "somme", "lot", "tarn", "var", "eure", "ain", "aude",
        "manche", "marne", "meuse", "nievre", "oise", "rhone", "sarthe",
        "savoie", "seine", "vendee", "vienne", "vosges", "yonne",
        "orange", "nice", "pau", "sens", "ales", "gap", "dax", "foix",
        "auch", "lozere", "creuse", "cantal", "landes", "jura", "doubs",
    })

    def __init__(self, config_path: str = "config.ini") -> None:
        """Initialise les valeurs par défaut puis charge le fichier INI."""
        self.config_path: str = os.path.abspath(config_path)
        self._base_dir: str = os.path.dirname(self.config_path)
        self._parser: configparser.ConfigParser = configparser.ConfigParser()

        self.root_dir: str = self._base_dir
        self.first_names_file: str = os.path.join(self._base_dir, "prenoms.txt")
        self.locations_file: str = os.path.join(self._base_dir, "villes_masquees.txt")
        self.excluded_words_file: str = os.path.join(self._base_dir, "mots_exclus.txt")
        self.contacts_file: str = os.path.join(self._base_dir, "contacts.txt")
        self.manual_contacts_file: str = os.path.join(self._base_dir, "contacts_manuels.txt")
        self.discovered_contacts_file: str = os.path.join(self._base_dir, "contacts_emails_decouverts.txt")
        self.indexed_contacts_file: str = os.path.join(self._base_dir, "contacts_indexes.txt")
        self.anonymized_contacts_file: str = os.path.join(self._base_dir, "contacts_anonymises.txt")
        self.all_sms_numbers_file: str = os.path.join(self._base_dir, "tous_numeros_sms.txt")
        self.all_emails_file: str = os.path.join(self._base_dir, "tous_emails_trouves.txt")
        self.sources_dir: str = os.path.join(self._base_dir, "fichiers sources")
        self.transcriptions_dir: str = os.path.join(self._base_dir, "transcriptions")
        self.results_dir: str = os.path.join(self._base_dir, "resultats_anonymisation")
        self.audit_report_file: str = os.path.join(self._base_dir, "audit_noms_residuels.txt")
        self.audit_copy_file: str = os.path.join(self._base_dir, "audit_noms_residuels_copier.txt")
        self.enable_ocr: bool = True
        self.enable_audio: bool = True
        self.whisper_model: str = "base"
        self.defer_heavy_files: bool = True
        self.heavy_file_threshold_mb: float = 25.0
        self.extraction_workers: int = 0
        self.ignored_dirs: Set[str] = {
            "transcriptions", "resultats_anonymisation",
            "venv", ".venv", ".git", "__pycache__", "common", "tools", "tests",
        }
        self.main_character_name: str = "Personnage_Principal"
        self.file_prefix: str = "anonymise_"
        self.secret_salt: str = self.DEFAULT_PLACEHOLDER_SALT
        self.max_batch_bytes: int = 180 * 1024
        self.max_batch_files: int = 50
        self.files_per_folder: int = 10
        self.min_audit_occurrences: int = 1
        self.mask_ssn: bool = True
        self.mask_addresses: bool = True
        self.mask_urls: bool = True
        self.mask_financial_and_admin_ids: bool = True
        self.masked_locations: Set[str] = set()
        self.known_first_names: Set[str] = set()
        self.excluded_words: Set[str] = set()

        self._load_french_geo_catalog()
        self._load()
        self.load_external_lists()
        self._ensure_strong_secret_salt()

        self.sms_tracking_file: str = os.path.join(self.transcriptions_dir, ".sms_numeros_traites.txt")
        self.extraction_tracking_file: str = os.path.join(self.transcriptions_dir, ".fichiers_extraits.txt")
        self.resume_state_file: str = os.path.join(self.results_dir, ".etat_anonymisation.json")

    def load_external_lists(self) -> None:
        """Charge ou recharge les listes externes (villes, mots exclus, prénoms)."""
        self.masked_locations.update(
            SharedCoreUtils.load_locations_set(self.locations_file)
        )
        self.excluded_words.update(
            SharedCoreUtils.load_words_set(self.excluded_words_file)
        )
        self._expand_location_variants()
        self.known_first_names.update(
            SharedCoreUtils.load_first_names_set(self.first_names_file)
        )

    def _load_french_geo_catalog(self) -> None:
        """Charge les départements, régions et grandes villes depuis FrenchGeoCatalog."""
        for attr_name in dir(FrenchGeoCatalog):
            if attr_name.startswith("_"):
                continue
            val = getattr(FrenchGeoCatalog, attr_name)
            if isinstance(val, (set, list, tuple)):
                for item in val:
                    if isinstance(item, str) and len(item.strip()) >= 3:
                        norm_loc: str = SharedCoreUtils.normalize_token(item)
                        if norm_loc not in self.COMMON_WORD_LOCATIONS:
                            self.masked_locations.add(norm_loc)

    def _expand_location_variants(self) -> None:
        """Ajoute les variantes avec espaces à la place des tirets pour les villes composées."""
        expanded: Set[str] = set()
        for loc in self.masked_locations:
            if "-" in loc:
                expanded.add(loc.replace("-", " "))
        self.masked_locations.update(expanded)

    def _ensure_strong_secret_salt(self) -> None:
        """Génère et persiste un sel cryptographique aléatoire de 256 bits dans .secret_salt."""
        if self.secret_salt and self.secret_salt != self.DEFAULT_PLACEHOLDER_SALT:
            return
        salt_file: str = os.path.join(self._base_dir, ".secret_salt")
        if os.path.exists(salt_file):
            try:
                with open(salt_file, "r", encoding="utf-8") as f_s:
                    stored: str = f_s.read().strip()
                if len(stored) >= 32:
                    self.secret_salt = stored
                    return
            except OSError:
                pass
        generated: str = secrets.token_hex(32)
        self.secret_salt = generated
        try:
            SharedCoreUtils.atomic_write_text(salt_file, f"{generated}\n")
        except OSError:
            pass
    def _resolve_path(self, raw_path: str) -> str:
        """Résout un chemin relativement au dossier contenant config.ini."""
        cleaned: str = raw_path.strip()
        if os.path.isabs(cleaned):
            return os.path.normpath(cleaned)
        return os.path.normpath(os.path.join(self._base_dir, cleaned))

    @staticmethod
    def _parse_csv_set(raw_value: str) -> Set[str]:
        """Convertit une chaîne séparée par des virgules en ensemble nettoyé."""
        return {item.strip() for item in raw_value.split(",") if item.strip()}

    def _load(self) -> None:
        """Lit les sections partagées et spécifiques de config.ini."""
        if not os.path.exists(self.config_path):
            return

        self._parser.read(self.config_path, encoding="utf-8")
        if "files" in self._parser:
            files_sec = self._parser["files"]
            path_keys = {
                "first_names_file": "first_names_file",
                "locations_file": "locations_file",
                "excluded_words_file": "excluded_words_file",
                "output_file": "indexed_contacts_file",
                "anonymized_output_file": "anonymized_contacts_file",
                "inverted_output_file": "contacts_file",
                "manual_contacts_file": "manual_contacts_file",
                "discovered_contacts_file": "discovered_contacts_file",
            }
            for ini_key, attr_name in path_keys.items():
                raw_val: str = files_sec.get(ini_key, fallback="").strip()
                if raw_val:
                    setattr(self, attr_name, self._resolve_path(raw_val))

        if "anonymizer" in self._parser:
            anon_sec = self._parser["anonymizer"]
            if "extra_locations" in anon_sec:
                self.masked_locations.update(
                    SharedCoreUtils.normalize_token(loc)
                    for loc in self._parse_csv_set(anon_sec["extra_locations"])
                )

        if "paths" in self._parser:
            paths_sec = self._parser["paths"]
            for key in (
                "root_dir", "locations_file", "excluded_words_file",
                "contacts_file", "manual_contacts_file",
                "discovered_contacts_file", "all_sms_numbers_file",
                "all_emails_file", "sources_dir", "transcriptions_dir",
                "results_dir", "audit_report_file", "audit_copy_file",
            ):
                if key in paths_sec:
                    setattr(self, key, self._resolve_path(paths_sec[key]))

        if "extraction" in self._parser:
            ext_sec = self._parser["extraction"]
            self.enable_ocr = ext_sec.getboolean("enable_ocr", fallback=self.enable_ocr)
            self.enable_audio = ext_sec.getboolean("enable_audio", fallback=self.enable_audio)
            self.whisper_model = ext_sec.get("whisper_model", fallback=self.whisper_model)
            self.defer_heavy_files = ext_sec.getboolean("defer_heavy_files", fallback=self.defer_heavy_files)
            self.heavy_file_threshold_mb = ext_sec.getfloat(
                "heavy_file_threshold_mb", fallback=self.heavy_file_threshold_mb
            )
            self.extraction_workers = ext_sec.getint("extraction_workers", fallback=self.extraction_workers)
            if "ignored_dirs" in ext_sec:
                self.ignored_dirs = self._parse_csv_set(ext_sec["ignored_dirs"])

        if "anonymization" in self._parser:
            anon_doc_sec = self._parser["anonymization"]
            raw_main: str = anon_doc_sec.get("main_character_name", fallback=self.main_character_name).strip()
            if raw_main:
                self.main_character_name = raw_main
            self.file_prefix = anon_doc_sec.get("file_prefix", fallback=self.file_prefix)
            self.secret_salt = anon_doc_sec.get("secret_salt", fallback=self.secret_salt)
            self.max_batch_bytes = anon_doc_sec.getint("max_batch_bytes", fallback=self.max_batch_bytes)
            self.max_batch_files = anon_doc_sec.getint("max_batch_files", fallback=self.max_batch_files)
            self.files_per_folder = anon_doc_sec.getint("files_per_folder", fallback=self.files_per_folder)
            self.min_audit_occurrences = anon_doc_sec.getint(
                "min_audit_occurrences", fallback=self.min_audit_occurrences
            )
            self.mask_ssn = anon_doc_sec.getboolean("mask_ssn", fallback=self.mask_ssn)
            self.mask_addresses = anon_doc_sec.getboolean("mask_addresses", fallback=self.mask_addresses)
            self.mask_urls = anon_doc_sec.getboolean("mask_urls", fallback=self.mask_urls)
            self.mask_financial_and_admin_ids = anon_doc_sec.getboolean(
                "mask_financial_and_admin_ids", fallback=self.mask_financial_and_admin_ids
            )
            if "masked_locations" in anon_doc_sec:
                self.masked_locations.update(
                    SharedCoreUtils.normalize_token(loc)
                    for loc in self._parse_csv_set(anon_doc_sec["masked_locations"])
                )
            if "known_first_names" in anon_doc_sec:
                self.known_first_names.update(
                    SharedCoreUtils.normalize_token(w)
                    for w in self._parse_csv_set(anon_doc_sec["known_first_names"])
                )
            if "excluded_words" in anon_doc_sec:
                self.excluded_words.update(
                    SharedCoreUtils.normalize_token(w)
                    for w in self._parse_csv_set(anon_doc_sec["excluded_words"])
                )
