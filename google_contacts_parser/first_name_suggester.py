# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import csv
import os
import re
from typing import Dict, FrozenSet, List, Set, Tuple
from common.core_utils import SharedCoreUtils
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.text_utils import ContactTextUtils


class MissingFirstNamesSuggester:
    """
    Analyse les colonnes de prénoms des exports CSV Google/Outlook, filtre les
    sociétés, initiales et pseudos techniques, et génère un fichier listant
    les prénoms absents de prenoms.txt.
    """

    FIRST_NAME_COLUMNS: Tuple[str, ...] = (
        "first name",
        "given name",
        "prénom",
        "prenom",
    )

    NON_FIRST_NAME_STOPWORDS: FrozenSet[str] = frozenset({
        "accueil", "admin", "agence", "association", "asso", "atelier",
        "banque", "boulangerie", "bureau", "cabinet", "caisse", "centre",
        "chateau", "clinique", "club", "college", "comite", "compagnie",
        "conseil", "contact", "creche", "cuisine", "direction", "docteur",
        "dr", "ecole", "entreprise", "equipe", "espace", "et", "ets",
        "famille", "fondation", "garage", "groupe", "hopital", "hotel",
        "imagerie", "info", "institut", "laboratoire", "le", "la", "les",
        "lycee", "madame", "maitre", "mairie", "maison", "me", "mme",
        "monsieur", "mr", "mutuelle", "office", "organisation", "paris",
        "pharmacie", "pole", "prefecture", "presse", "pr",
        "professeur", "restaurant", "sarl", "sas", "secretariat", "service",
        "services", "societe", "studio", "succursale", "syndicat", "team",
        "tribunal", "union", "universite", "urssaf", "ville", "votre",
    })

    def __init__(self, config: ContactsConfig) -> None:
        """
        Initialise le détecteur de prénoms manquants avec la configuration.

        :param config: Instance de ContactsConfig.
        """
        self.config: ContactsConfig = config
        self.known_first_names: Set[str] = {
            SharedCoreUtils.normalize_token(fn.replace("\u00a0", " ").replace("\ufeff", ""))
            for fn in SharedCoreUtils.load_first_names_set(config.first_names_file)
            if fn.strip()
        }

    @staticmethod
    def _detect_delimiter(sample: str) -> str:
        """
        Détecte automatiquement le séparateur CSV (',' ou ';').

        :param sample: Début du contenu CSV.
        :return: Délimiteur détecté.
        """
        first_line: str = next(iter(sample.splitlines()), "")
        return ";" if first_line.count(";") > first_line.count(",") else ","

    def _is_organization_marker(self, token: str) -> bool:
        """
        Indique si un mot signale une enseigne, société ou administration.

        :param token: Jeton brut issu du champ prénom.
        :return: True si le jeton est un marqueur d'organisation.
        """
        norm_tok: str = SharedCoreUtils.normalize_token(token)
        compact_tok: str = ContactTextUtils.normalize_text(token)
        return (
            norm_tok in self.NON_FIRST_NAME_STOPWORDS
            or compact_tok in self.config.entity_prefixes
            or compact_tok in self.config.all_company_keywords_norm
        )

    def _is_valid_first_name_candidate(self, raw_token: str) -> bool:
        """
        Vérifie qu'un jeton est un prénom plausible (alphabétique, >= 3 lettres,
        ni mot-outil, ni lieu, ni mot-clé d'entreprise, ni nom tout en majuscules).

        :param raw_token: Jeton extrait d'une colonne prénom.
        :return: True si le jeton est un prénom candidat valide.
        """
        cleaned: str = raw_token.replace("\u00a0", " ").replace("\ufeff", "").strip().strip('"').strip()
        if len(cleaned) < 3 or cleaned.endswith(".") or cleaned.isupper():
            return False
        if any(ch.isdigit() for ch in cleaned):
            return False
        if "@" in cleaned or "/" in cleaned or "_" in cleaned:
            return False
        if not re.match(
            r"^[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç']+$", cleaned
        ):
            return False

        norm_tok: str = SharedCoreUtils.normalize_token(cleaned)
        compact_tok: str = ContactTextUtils.normalize_text(cleaned)
        if len(norm_tok) < 3 or norm_tok in self.known_first_names:
            return False
        if (
            self._is_organization_marker(cleaned)
            or compact_tok in self.config.all_excluded_locations_norm
            or compact_tok in self.config.all_ignored_domains_norm
        ):
            return False
        return True
    def _extract_candidates_from_row(
        self, row: Dict[str, str], target_cols: List[str]
    ) -> List[str]:
        """
        Extrait les prénoms candidats (simples ou composés) depuis une ligne CSV,
        en ignorant intégralement les cellules désignant une organisation.

        :param row: Dictionnaire représentant la ligne CSV courante.
        :param target_cols: Liste des colonnes de prénoms détectées.
        :return: Liste des prénoms normalisés en minuscules retenus.
        """
        candidates: List[str] = []
        raw_last: str = (
            row.get("Last Name")
            or row.get("Family Name")
            or row.get("Nom de famille")
            or row.get("Nom")
            or ""
        ).strip()

        for col in target_cols:
            raw_val: str = (row.get(col) or "").replace("\u00a0", " ").strip()
            if not raw_val:
                continue
            words_in_field: List[str] = [
                w for w in re.split(r"[\s\-/,&]+", raw_val) if w.strip()
            ]
            if not raw_last and len(words_in_field) >= 3:
                continue
            if any(self._is_organization_marker(w) for w in words_in_field):
                continue
            for token in words_in_field:
                if self._is_valid_first_name_candidate(token):
                    candidates.append(token.strip().lower())
        return candidates

    def collect_missing_first_names(self, csv_files: List[str]) -> List[str]:
        """
        Parcourt tous les fichiers CSV fournis et retourne la liste triée
        des prénoms inédits détectés.

        :param csv_files: Liste des chemins de fichiers CSV à analyser.
        :return: Liste triée sans doublon des prénoms suggérés.
        """
        discovered_by_norm: Dict[str, str] = {}
        for csv_path in csv_files:
            if not os.path.exists(csv_path):
                continue
            with open(
                csv_path, mode="r", encoding=self.config.encoding, newline=""
            ) as f_csv:
                sample: str = f_csv.read(4096)
                f_csv.seek(0)
                delimiter: str = self._detect_delimiter(sample)
                reader: csv.DictReader = csv.DictReader(
                    f_csv, delimiter=delimiter
                )
                if not reader.fieldnames:
                    continue
                target_cols: List[str] = [
                    col
                    for col in reader.fieldnames
                    if col and col.strip().lower() in self.FIRST_NAME_COLUMNS
                ]
                if not target_cols:
                    continue
                for row in reader:
                    for cand in self._extract_candidates_from_row(row, target_cols):
                        norm_key: str = SharedCoreUtils.normalize_token(cand)
                        if (
                            norm_key not in self.known_first_names
                            and norm_key not in discovered_by_norm
                        ):
                            discovered_by_norm[norm_key] = cand

        return [
            discovered_by_norm[k]
            for k in sorted(discovered_by_norm.keys())
        ]

    def generate_suggestions_file(self, csv_files: List[str]) -> int:
        """
        Génère le fichier prenoms_suggeres.txt si de nouveaux prénoms sont trouvés,
        ou supprime un ancien fichier obsolète s'il n'y a plus aucune suggestion.

        :param csv_files: Liste des fichiers CSV analysés.
        :return: Nombre de nouveaux prénoms suggérés.
        """
        suggestions: List[str] = self.collect_missing_first_names(csv_files)
        out_path: str = self.config.suggested_first_names_file

        if not suggestions:
            if os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except OSError:
                    pass
            return 0

        header_lines: List[str] = [
            "# PRÉNOMS DÉTECTÉS DANS LES CONTACTS CSV ABSENTS DE prenoms.txt\n",
            "# Vérifiez cette liste et copiez les prénoms valides dans prenoms.txt :\n\n",
        ]
        body_lines: List[str] = [f"{name}\n" for name in suggestions]
        SharedCoreUtils.atomic_write_text(
            target_path=out_path,
            content="".join(header_lines + body_lines),
            encoding="utf-8",
        )
        return len(suggestions)
