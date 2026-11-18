# Commandes pip à exécuter : Aucune dépendance externe requise

import configparser
import os
from typing import Dict, List, Set


class ContactsConfig:
    """
    Charge et expose de manière typée la configuration du pipeline de contacts
    depuis le fichier config.ini unifié.
    """

    def __init__(self, config_path: str = "config.ini") -> None:
        """
        Initialise les paramètres par défaut puis charge le fichier INI.

        :param config_path: Chemin vers le fichier config.ini.
        """
        self.config_path: str = os.path.abspath(config_path)
        self._base_dir: str = os.path.dirname(self.config_path)
        self._parser: configparser.ConfigParser = configparser.ConfigParser()

        self.csv_directory: str = os.path.join(self._base_dir, "export_contacts")
        self.csv_prefixes: List[str] = ["contacts", "autres contacts"]
        self.first_names_file: str = os.path.join(self._base_dir, "prenoms.txt")
        self.output_file: str = os.path.join(self._base_dir, "contacts_indexes.txt")
        self.anonymized_output_file: str = os.path.join(
            self._base_dir, "contacts_anonymises.txt"
        )
        self.deduplicated_output_file: str = os.path.join(
            self._base_dir, "contacts_dedoublonnes.txt"
        )
        self.inverted_output_file: str = os.path.join(self._base_dir, "contacts.txt")
        self.encoding: str = "utf-8-sig"

        self.clean_phone_spaces: bool = False
        self.lowercase_emails: bool = True
        self.separator: str = "="
        self.merge_separator: str = "et"

        self.ignored_domains: Set[str] = set()
        self.entity_prefixes: Set[str] = set()
        self.company_keywords: Set[str] = set()
        self.extra_locations: Set[str] = set()
        self.domain_aliases: Dict[str, str] = {}

        self._load()

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

    def _parse_csv_list(self, raw_val: str) -> List[str]:
        """
        Convertit une chaîne séparée par des virgules en liste nettoyée.

        :param raw_val: Chaîne brute issue du INI.
        :return: Liste des éléments non vides.
        """
        return [item.strip() for item in raw_val.split(",") if item.strip()]

    def _load(self) -> None:
        """
        Lit les sections [files], [formatting], [anonymizer] et [domain_aliases].
        """
        if not os.path.exists(self.config_path):
            return

        self._parser.read(self.config_path, encoding="utf-8")
        if "files" in self._parser:
            f = self._parser["files"]
            if "csv_directory" in f:
                self.csv_directory = self._resolve_path(f["csv_directory"])
            if "csv_prefixes" in f:
                self.csv_prefixes = [
                    p.lower() for p in self._parse_csv_list(f["csv_prefixes"])
                ]
            if "first_names_file" in f:
                self.first_names_file = self._resolve_path(f["first_names_file"])
            if "output_file" in f:
                self.output_file = self._resolve_path(f["output_file"])
            if "anonymized_output_file" in f:
                self.anonymized_output_file = self._resolve_path(
                    f["anonymized_output_file"]
                )
            if "deduplicated_output_file" in f:
                self.deduplicated_output_file = self._resolve_path(
                    f["deduplicated_output_file"]
                )
            if "inverted_output_file" in f:
                self.inverted_output_file = self._resolve_path(
                    f["inverted_output_file"]
                )
            self.encoding = f.get("encoding", fallback=self.encoding)

        if "formatting" in self._parser:
            fmt = self._parser["formatting"]
            self.clean_phone_spaces = fmt.getboolean(
                "clean_phone_spaces", fallback=self.clean_phone_spaces
            )
            self.lowercase_emails = fmt.getboolean(
                "lowercase_emails", fallback=self.lowercase_emails
            )
            self.separator = fmt.get("separator", fallback=self.separator)
            self.merge_separator = fmt.get(
                "merge_separator", fallback=self.merge_separator
            )

        if "anonymizer" in self._parser:
            az = self._parser["anonymizer"]
            if "ignored_domains" in az:
                self.ignored_domains = {
                    d.lower() for d in self._parse_csv_list(az["ignored_domains"])
                }
            if "entity_prefixes" in az:
                self.entity_prefixes = {
                    p.lower() for p in self._parse_csv_list(az["entity_prefixes"])
                }
            if "company_keywords" in az:
                self.company_keywords = {
                    k.lower() for k in self._parse_csv_list(az["company_keywords"])
                }
            if "extra_locations" in az:
                self.extra_locations = {
                    loc.lower() for loc in self._parse_csv_list(az["extra_locations"])
                }

        if "domain_aliases" in self._parser:
            self.domain_aliases = {
                k.strip().lower(): v.strip()
                for k, v in self._parser["domain_aliases"].items()
                if k.strip() and v.strip()
            }

    def get_matching_csv_files(self) -> List[str]:
        """
        Recherche dans csv_directory tous les fichiers .csv dont le nom
        commence par l'un des préfixes configurés.

        :return: Liste triée des chemins complets des fichiers CSV trouvés.
        """
        if not os.path.isdir(self.csv_directory):
            return []
        matched: List[str] = []
        for fname in sorted(os.listdir(self.csv_directory)):
            lower_name: str = fname.lower()
            if lower_name.endswith(".csv") and any(
                lower_name.startswith(pref) for pref in self.csv_prefixes
            ):
                matched.append(os.path.join(self.csv_directory, fname))
        return matched
