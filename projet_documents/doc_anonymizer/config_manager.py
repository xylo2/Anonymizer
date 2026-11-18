# Commandes pip à exécuter : Aucune dépendance externe requise

import configparser
import os
import unicodedata
from typing import Set


class PipelineConfig:
    """
    Charge et expose de manière typée les paramètres techniques d'extraction
    et d'anonymisation depuis le fichier config.ini unifié, en partageant
    prenoms.txt, extra_locations et les index de contacts.
    """

    def __init__(self, config_path: str = "config.ini") -> None:
        """
        Initialise les valeurs par défaut puis charge le fichier INI.

        :param config_path: Chemin vers le fichier config.ini.
        """
        self.config_path: str = os.path.abspath(config_path)
        self._base_dir: str = os.path.dirname(self.config_path)
        self._parser: configparser.ConfigParser = configparser.ConfigParser()

        self.root_dir: str = self._base_dir
        self.first_names_file: str = os.path.join(
            self._base_dir, "prenoms.txt"
        )
        self.contacts_file: str = os.path.join(
            self._base_dir, "contacts.txt"
        )
        self.indexed_contacts_file: str = os.path.join(
            self._base_dir, "contacts_indexes.txt"
        )
        self.anonymized_contacts_file: str = os.path.join(
            self._base_dir, "contacts_anonymises.txt"
        )
        self.all_sms_numbers_file: str = os.path.join(
            self._base_dir, "tous_numeros_sms.txt"
        )
        self.all_emails_file: str = os.path.join(
            self._base_dir, "tous_emails_trouves.txt"
        )
        self.sources_dir: str = os.path.join(
            self._base_dir, "fichiers sources"
        )
        self.transcriptions_dir: str = os.path.join(
            self._base_dir, "transcriptions"
        )
        self.results_dir: str = os.path.join(
            self._base_dir, "resultats_anonymisation"
        )
        self.audit_report_file: str = os.path.join(
            self._base_dir, "audit_noms_residuels.txt"
        )

        self.enable_ocr: bool = True
        self.enable_audio: bool = True
        self.whisper_model: str = "base"
        self.ignored_dirs: Set[str] = {
            "transcriptions", "resultats_anonymisation",
            "venv", ".venv", ".git", "__pycache__",
        }

        self.main_character_name: str = "Personnage_Principal"
        self.file_prefix: str = "anonymise_"
        self.secret_salt: str = "cle_secrete_a_modifier_987"
        self.max_batch_bytes: int = 180 * 1024
        self.files_per_folder: int = 10
        self.min_audit_occurrences: int = 1
        self.mask_ssn: bool = True
        self.mask_addresses: bool = True
        self.mask_financial_and_admin_ids: bool = True
        self.masked_locations: Set[str] = set()
        self.known_first_names: Set[str] = set()
        self.excluded_words: Set[str] = set()

        self._load()
        self._load_first_names_from_file()
        self.sms_tracking_file: str = os.path.join(
            self.transcriptions_dir, ".sms_numeros_traites.txt"
        )
        self.extraction_tracking_file: str = os.path.join(
            self.transcriptions_dir, ".fichiers_extraits.txt"
        )
        self.resume_state_file: str = os.path.join(
            self.results_dir, ".etat_anonymisation.json"
        )

    def _resolve_path(self, raw_path: str) -> str:
        """
        Résout un chemin relativement au dossier contenant config.ini.

        :param raw_path: Chemin lu dans le fichier INI.
        :return: Chemin absolu normalisé.
        """
        cleaned: str = raw_path.strip()
        if os.path.isabs(cleaned):
            return os.path.normpath(cleaned)
        return os.path.normpath(os.path.join(self._base_dir, cleaned))

    def _parse_csv_set(self, raw_value: str) -> Set[str]:
        """
        Convertit une chaîne séparée par des virgules en ensemble nettoyé.

        :param raw_value: Chaîne brute issue du fichier INI.
        :return: Ensemble des éléments non vides.
        """
        return {item.strip() for item in raw_value.split(",") if item.strip()}
    def _load_first_names_from_file(self) -> None:
        """
        Charge et normalise les prénoms depuis le fichier prenoms.txt partagé
        avec google_contacts_parser.
        """
        if not os.path.exists(self.first_names_file):
            return
        with open(self.first_names_file, "r", encoding="utf-8") as f:
            for raw_line in f:
                line: str = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                nfkd: str = unicodedata.normalize("NFD", line.lower())
                norm: str = "".join(
                    ch for ch in nfkd if unicodedata.category(ch) != "Mn"
                )
                if norm:
                    self.known_first_names.add(norm)

    def _load(self) -> None:
        """
        Lit les sections partagées ([files], [anonymizer]) et spécifiques
        ([paths], [extraction], [anonymization]) de config.ini.
        """
        if not os.path.exists(self.config_path):
            return

        self._parser.read(self.config_path, encoding="utf-8")
        if "files" in self._parser:
            f_sec = self._parser["files"]
            raw_fn: str = f_sec.get("first_names_file", fallback="").strip()
            if raw_fn:
                self.first_names_file = self._resolve_path(raw_fn)
            raw_out: str = f_sec.get("output_file", fallback="").strip()
            if raw_out:
                self.indexed_contacts_file = self._resolve_path(raw_out)
            raw_ano: str = f_sec.get(
                "anonymized_output_file", fallback=""
            ).strip()
            if raw_ano:
                self.anonymized_contacts_file = self._resolve_path(raw_ano)
            raw_inv: str = f_sec.get(
                "inverted_output_file", fallback=""
            ).strip()
            if raw_inv:
                self.contacts_file = self._resolve_path(raw_inv)

        if "anonymizer" in self._parser:
            az = self._parser["anonymizer"]
            if "extra_locations" in az:
                self.masked_locations.update(
                    loc.lower()
                    for loc in self._parse_csv_set(az["extra_locations"])
                )

        if "paths" in self._parser:
            p = self._parser["paths"]
            if "root_dir" in p:
                self.root_dir = self._resolve_path(p["root_dir"])
            if "contacts_file" in p:
                self.contacts_file = self._resolve_path(p["contacts_file"])
            if "all_sms_numbers_file" in p:
                self.all_sms_numbers_file = self._resolve_path(
                    p["all_sms_numbers_file"]
                )
            if "all_emails_file" in p:
                self.all_emails_file = self._resolve_path(
                    p["all_emails_file"]
                )
            if "sources_dir" in p:
                self.sources_dir = self._resolve_path(p["sources_dir"])
            if "transcriptions_dir" in p:
                self.transcriptions_dir = self._resolve_path(
                    p["transcriptions_dir"]
                )
            if "results_dir" in p:
                self.results_dir = self._resolve_path(p["results_dir"])
            if "audit_report_file" in p:
                self.audit_report_file = self._resolve_path(
                    p["audit_report_file"]
                )

        if "extraction" in self._parser:
            e = self._parser["extraction"]
            self.enable_ocr = e.getboolean(
                "enable_ocr", fallback=self.enable_ocr
            )
            self.enable_audio = e.getboolean(
                "enable_audio", fallback=self.enable_audio
            )
            self.whisper_model = e.get(
                "whisper_model", fallback=self.whisper_model
            )
            if "ignored_dirs" in e:
                self.ignored_dirs = self._parse_csv_set(e["ignored_dirs"])

        if "anonymization" in self._parser:
            a = self._parser["anonymization"]
            raw_main: str = a.get(
                "main_character_name", fallback=self.main_character_name
            ).strip()
            if raw_main:
                self.main_character_name = raw_main
            self.file_prefix = a.get("file_prefix", fallback=self.file_prefix)
            self.secret_salt = a.get("secret_salt", fallback=self.secret_salt)
            self.max_batch_bytes = a.getint(
                "max_batch_bytes", fallback=self.max_batch_bytes
            )
            self.files_per_folder = a.getint(
                "files_per_folder", fallback=self.files_per_folder
            )
            self.min_audit_occurrences = a.getint(
                "min_audit_occurrences", fallback=self.min_audit_occurrences
            )
            self.mask_ssn = a.getboolean("mask_ssn", fallback=self.mask_ssn)
            self.mask_addresses = a.getboolean(
                "mask_addresses", fallback=self.mask_addresses
            )
            self.mask_financial_and_admin_ids = a.getboolean(
                "mask_financial_and_admin_ids",
                fallback=self.mask_financial_and_admin_ids,
            )
            if "masked_locations" in a:
                self.masked_locations.update(
                    loc.lower()
                    for loc in self._parse_csv_set(a["masked_locations"])
                )
            if "known_first_names" in a:
                self.known_first_names.update(
                    w.lower() for w in self._parse_csv_set(a["known_first_names"])
                )
            if "excluded_words" in a:
                self.excluded_words = {
                    w.lower() for w in self._parse_csv_set(a["excluded_words"])
                }
