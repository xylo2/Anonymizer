import configparser
import os
from typing import Dict, List, Set
from common.core_utils import SharedCoreUtils


class ContactsConfig:
    """
    Gère le chargement des paramètres du pipeline contacts depuis config.ini.
    """

    DEFAULT_CONFIG_PATH: str = "config.ini"

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH) -> None:
        """Initialise et lit la configuration INI."""
        self.config_path: str = os.path.abspath(config_path)
        self.base_dir: str = os.path.dirname(self.config_path) or os.getcwd()
        self.parser: configparser.ConfigParser = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            self.parser.read(self.config_path, encoding="utf-8")

        default_csv_dir: str = (
            self.parser.get("paths", "input_contacts_dir", fallback="").strip()
            or "input_contacts"
        )
        self.csv_directory: str = self._resolve_path(
            "files", "csv_directory", default_csv_dir
        )
        raw_prefixes: str = self.parser.get(
            "files", "csv_prefixes", fallback=""
        )
        self.csv_prefixes: List[str] = [
            p.strip().lower() for p in raw_prefixes.split(",") if p.strip()
        ]
        self.encoding: str = self.parser.get(
            "files", "encoding", fallback="utf-8-sig"
        ).strip()

        self.first_names_file: str = self._resolve_path(
            "files", "first_names_file", "data/prenoms.txt"
        )
        self.suggested_first_names_file: str = self._resolve_path(
            "files",
            "suggested_first_names_file",
            "output_contacts/.intermediates/suggested_first_names.txt",
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
        self.output_file: str = self._resolve_path(
            "files", "output_file", "output_contacts/.intermediates/indexed_contacts.txt"
        )
        self.anonymized_output_file: str = self._resolve_path(
            "files",
            "anonymized_output_file",
            "output_contacts/.intermediates/anonymized_contacts.txt",
        )
        self.surnames_output_file: str = self._resolve_path(
            "files",
            "surnames_output_file",
            "output_contacts/.intermediates/contact_surnames.txt",
        )
        self.deduplicated_output_file: str = self._resolve_path(
            "files",
            "deduplicated_output_file",
            "output_contacts/.intermediates/deduplicated_contacts.txt",
        )
        self.inverted_output_file: str = self._resolve_path(
            "files", "inverted_output_file", "output_contacts/contacts.txt"
        )
        self.manual_contacts_file: str = self._resolve_path(
            "files", "manual_contacts_file", "output_contacts/manual_contacts.txt"
        )
        self.discovered_contacts_file: str = self._resolve_path(
            "files",
            "discovered_contacts_file",
            "output_contacts/discovered_email_contacts.txt",
        )
        self.clean_phone_spaces: bool = self.parser.getboolean(
            "formatting", "clean_phone_spaces", fallback=False
        )
        self.lowercase_emails: bool = self.parser.getboolean(
            "formatting", "lowercase_emails", fallback=True
        )
        self.separator: str = self.parser.get(
            "formatting", "separator", fallback="="
        ).strip()
        self.merge_separator: str = self.parser.get(
            "formatting", "merge_separator", fallback="et"
        ).strip()

        self.ignored_domains: Set[str] = self._parse_csv_set(
            "anonymizer",
            "ignored_domains",
            "gmail, yahoo, hotmail, outlook, orange, free, sfr, laposte, icloud",
        )
        self.all_ignored_domains_norm: Set[str] = set(self.ignored_domains)

        self.entity_prefixes: Set[str] = self._parse_csv_set(
            "anonymizer",
            "entity_prefixes",
            "cabinet, mairie, clinique, hopital, pharmacie, laboratoire, banque, sarl, sas",
        )
        self.all_entity_prefixes_norm: Set[str] = set(self.entity_prefixes)

        self.company_keywords: Set[str] = self._parse_csv_set(
            "anonymizer",
            "company_keywords",
            "immobilier, communication, conseil, assurance, banque, sante, services",
        )
        self.all_company_keywords_norm: Set[str] = set(self.company_keywords)

        self.known_first_names: Set[str] = SharedCoreUtils.load_first_names_set(
            self.first_names_file
        )
        self.masked_locations: Set[str] = SharedCoreUtils.load_locations_set(
            self.locations_file
        )
        self.extra_locations: Set[str] = self._parse_csv_set(
            "anonymizer", "extra_locations", ""
        )
        self.masked_locations.update(self.extra_locations)
        self.all_excluded_locations_norm: Set[str] = set(self.masked_locations)
        self.surname_collisions: Set[str] = SharedCoreUtils.load_words_set(
            self.surname_collisions_file
        )
        self.excluded_words: Set[str] = SharedCoreUtils.load_words_set(
            self.excluded_words_file
        )
        self.domain_aliases: Dict[str, str] = self._load_domain_aliases()

    def get_csv_files(self) -> List[str]:
        """Retourne la liste des fichiers CSV et vCard (.vcf) dans csv_directory."""
        if not os.path.isdir(self.csv_directory):
            return []
        matched: List[str] = []
        for fname in sorted(os.listdir(self.csv_directory)):
            low: str = fname.lower()
            if not low.endswith((".csv", ".vcf")):
                continue
            if not self.csv_prefixes or any(low.startswith(p) for p in self.csv_prefixes):
                matched.append(os.path.join(self.csv_directory, fname))
        return matched

    def _resolve_path(self, section: str, key: str, default: str) -> str:
        """Résout un chemin relatif par rapport à config.ini."""
        raw: str = self.parser.get(section, key, fallback=default).strip()
        if os.path.isabs(raw):
            return os.path.normpath(raw)
        return os.path.normpath(os.path.join(self.base_dir, raw))

    def _parse_csv_set(self, section: str, key: str, default: str) -> Set[str]:
        """Parse une liste séparée par des virgules en ensemble normalisé."""
        raw: str = self.parser.get(section, key, fallback=default)
        res: Set[str] = set()
        for item in raw.split(","):
            norm: str = SharedCoreUtils.normalize_compact_text(item)
            if norm:
                res.add(norm)
        return res

    def _load_domain_aliases(self) -> Dict[str, str]:
        """Charge la section [domain_aliases] en minuscules."""
        aliases: Dict[str, str] = {}
        if self.parser.has_section("domain_aliases"):
            for k, v in self.parser.items("domain_aliases"):
                ck: str = k.strip().lower()
                cv: str = v.strip()
                if ck and cv:
                    aliases[ck] = cv
        return aliases
