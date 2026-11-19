# Commandes pip à exécuter : Aucune dépendance externe requise

import configparser
import os
from typing import Dict, List, Set
from common.core_utils import SharedCoreUtils
from google_contacts_parser.geo_data import FrenchGeoCatalog


class ContactsConfig:
    """
    Charge et expose de manière typée la configuration du pipeline de contacts
    depuis le fichier config.ini unifié, villes_masquees.txt et collisions_noms.txt.
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
        self.suggested_first_names_file: str = os.path.join(
            self._base_dir, "prenoms_suggeres.txt"
        )
        self.locations_file: str = os.path.join(self._base_dir, "villes_masquees.txt")
        self.surname_collisions_file: str = os.path.join(self._base_dir, "collisions_noms.txt")
        self.excluded_words_file: str = os.path.join(self._base_dir, "mots_exclus.txt")
        self.output_file: str = os.path.join(self._base_dir, "contacts_indexes.txt")
        self.anonymized_output_file: str = os.path.join(self._base_dir, "contacts_anonymises.txt")
        self.surnames_output_file: str = os.path.join(self._base_dir, "noms_famille_contacts.txt")
        self.deduplicated_output_file: str = os.path.join(self._base_dir, "contacts_dedoublonnes.txt")
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
        self.extra_locations.update(
            SharedCoreUtils.load_locations_set(self.locations_file)
        )
        self.surname_collisions: Set[str] = SharedCoreUtils.load_words_set(
            self.surname_collisions_file
        )
        self.excluded_words: Set[str] = SharedCoreUtils.load_words_set(
            self.excluded_words_file
        )

        base_locs: Set[str] = self._collect_geo_catalog_locations()
        self.all_excluded_locations_norm: Set[str] = {
            SharedCoreUtils.normalize_compact_text(loc)
            for loc in (base_locs | self.extra_locations)
            if loc.strip()
        }
        self.all_ignored_domains_norm: Set[str] = {
            SharedCoreUtils.normalize_compact_text(dom)
            for dom in self.ignored_domains
            if dom.strip()
        }
        self.all_company_keywords_norm: Set[str] = {
            SharedCoreUtils.normalize_compact_text(kw)
            for kw in self.company_keywords
            if kw.strip()
        }
    @staticmethod
    def _collect_geo_catalog_locations() -> Set[str]:
        """
        Récupère dynamiquement tous les lieux définis dans FrenchGeoCatalog.

        :return: Ensemble des lieux français de référence.
        """
        collected: Set[str] = set()
        for attr_name in dir(FrenchGeoCatalog):
            if attr_name.startswith("_"):
                continue
            val = getattr(FrenchGeoCatalog, attr_name)
            if isinstance(val, (set, list, tuple)):
                collected.update(str(item) for item in val if isinstance(item, str))
        return collected

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

    @staticmethod
    def _parse_csv_list(raw_val: str) -> List[str]:
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
            path_keys: Dict[str, str] = {
                "csv_directory": "csv_directory",
                "first_names_file": "first_names_file",
                "suggested_first_names_file": "suggested_first_names_file",
                "locations_file": "locations_file",
                "surname_collisions_file": "surname_collisions_file",
                "excluded_words_file": "excluded_words_file",
                "output_file": "output_file",
                "anonymized_output_file": "anonymized_output_file",
                "surnames_output_file": "surnames_output_file",
                "deduplicated_output_file": "deduplicated_output_file",
                "inverted_output_file": "inverted_output_file",
            }
            for ini_key, attr_name in path_keys.items():
                if ini_key in f:
                    setattr(self, attr_name, self._resolve_path(f[ini_key]))
            if "csv_prefixes" in f:
                self.csv_prefixes = [p.lower() for p in self._parse_csv_list(f["csv_prefixes"])]
            self.encoding = f.get("encoding", fallback=self.encoding)

        if "formatting" in self._parser:
            fmt = self._parser["formatting"]
            self.clean_phone_spaces = fmt.getboolean("clean_phone_spaces", fallback=self.clean_phone_spaces)
            self.lowercase_emails = fmt.getboolean("lowercase_emails", fallback=self.lowercase_emails)
            self.separator = fmt.get("separator", fallback=self.separator)
            self.merge_separator = fmt.get("merge_separator", fallback=self.merge_separator)

        if "anonymizer" in self._parser:
            az = self._parser["anonymizer"]
            if "ignored_domains" in az:
                self.ignored_domains = {d.lower() for d in self._parse_csv_list(az["ignored_domains"])}
            if "entity_prefixes" in az:
                self.entity_prefixes = {
                    SharedCoreUtils.normalize_compact_text(p)
                    for p in self._parse_csv_list(az["entity_prefixes"])
                }
            if "company_keywords" in az:
                self.company_keywords = {
                    SharedCoreUtils.normalize_compact_text(k)
                    for k in self._parse_csv_list(az["company_keywords"])
                }
            if "extra_locations" in az:
                self.extra_locations = {loc.lower() for loc in self._parse_csv_list(az["extra_locations"])}

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
            if lower_name.endswith(".csv") and any(lower_name.startswith(pref) for pref in self.csv_prefixes):
                matched.append(os.path.join(self.csv_directory, fname))
        return matched

    def get_csv_files(self) -> List[str]:
        """
        Alias rétrocompatible de get_matching_csv_files().

        :return: Liste triée des chemins complets des fichiers CSV trouvés.
        """
        return self.get_matching_csv_files()
