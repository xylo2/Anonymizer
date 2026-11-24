# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import csv
import os
import re
from typing import Dict, List, Optional, Set, Tuple
from common.core_utils import SharedCoreUtils
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.text_utils import ContactTextUtils
from google_contacts_parser.vcard_reader import VCardContactsReader


class ContactsAnonymizer:
    """
    Lit les CSV/vCard et le fichier d'indexation pour remplacer les noms de famille
    par leurs initiales, exporter les noms de famille uniques, préserver les enseignes/sociétés
    et différencier les homonymes.
    """

    def __init__(self, config: ContactsConfig) -> None:
        """
        Initialise l'anonymiseur et les index internes de noms, prénoms et d'e-mails.

        :param config: Instance de ContactsConfig contenant les chemins et règles.
        """
        self.config: ContactsConfig = config
        self.known_last_names_norm: Set[str] = set()
        self.frequent_first_names: Set[str] = self._load_first_names()
        self.name_to_last_name: Dict[str, str] = {}
        self.name_to_first_email: Dict[str, str] = {}

    def _load_first_names(self) -> Set[str]:
        """
        Charge la liste des prénoms fréquents depuis le fichier partagé prenoms.txt.

        :return: Ensemble des prénoms normalisés compacts.
        """
        raw_names: Set[str] = SharedCoreUtils.load_first_names_set(
            self.config.first_names_file
        )
        return {
            ContactTextUtils.normalize_text(name)
            for name in raw_names
            if name.strip()
        }

    def _extract_row_identity(self, row: Dict[str, str]) -> Tuple[str, str, str]:
        """
        Extrait le prénom (simple ou composé avec Middle Name), le nom de famille et le nom complet.

        :param row: Dictionnaire représentant une ligne du CSV ou d'une fiche vCard.
        :return: Tuple (prénom, nom_de_famille, nom_complet).
        """
        raw_first: str = (row.get("First Name") or row.get("Given Name") or row.get("Prénom") or "").strip()
        raw_middle: str = (row.get("Middle Name") or row.get("Additional Name") or row.get("Deuxième prénom") or "").strip()
        first_name: str = f"{raw_first}-{raw_middle}" if (raw_first and raw_middle) else (raw_first or raw_middle)
        last_name: str = (row.get("Last Name") or row.get("Family Name") or row.get("Nom de famille") or row.get("Nom") or "").strip()

        full_name: str = f"{first_name} {last_name}".strip()
        if not full_name:
            full_name = (row.get("Name") or row.get("Nom complet") or "").strip()
            if full_name and " " in full_name and not last_name:
                p_first, p_last = full_name.split(" ", 1)
                first_name, last_name = p_first.strip(), p_last.strip()

        return first_name, last_name, full_name

    def _extract_first_email(self, row: Dict[str, str], fieldnames: List[str]) -> str:
        """
        Récupère la première adresse e-mail renseignée pour un contact dans la ligne.

        :param row: Dictionnaire représentant une ligne.
        :param fieldnames: Liste des colonnes disponibles.
        :return: Première adresse e-mail trouvée, ou chaîne vide.
        """
        for col in fieldnames:
            lower_col: str = col.lower()
            if "mail" in lower_col and "type" not in lower_col and "label" not in lower_col:
                raw_val: str = (row.get(col) or "").strip()
                if raw_val:
                    first_val: str = next(iter(raw_val.split(":::")), "").strip()
                    if first_val:
                        return first_val.lower() if self.config.lowercase_emails else first_val
        return ""

    def _clean_label_text(self, raw_label: str) -> str:
        """
        Retire les mentions de fournisseurs de messagerie et abrège les emplacements
        géographiques par leur première lettre suivie d'un point.

        :param raw_label: Libellé brut du contact ou de l'entité.
        :return: Libellé nettoyé prêt pour l'anonymisation.
        """
        without_provider: str = ContactTextUtils.strip_provider_suffix(raw_label, self.config.ignored_domains)
        return ContactTextUtils.abbreviate_locations_in_text(
            without_provider, self.config.all_excluded_locations_norm
        )

    @staticmethod
    def _detect_csv_delimiter(sample: str) -> str:
        """
        Détecte automatiquement si le CSV utilise ',' ou ';'.

        :param sample: Début du fichier CSV.
        :return: Délimiteur détecté.
        """
        lines: List[str] = sample.splitlines()
        first_line: str = next(iter(lines), "")
        return ";" if first_line.count(";") > first_line.count(",") else ","
    def _register_metadata_row(self, row: Dict[str, str], fieldnames: List[str]) -> None:
        """Enregistre le nom de famille et le premier e-mail d'une fiche contact (CSV ou vCard)."""
        _, last_name, full_name = self._extract_row_identity(row)
        if not full_name:
            return
        cleaned_full: str = self._clean_label_text(full_name)
        base_name, _, is_rfc = ContactTextUtils.clean_display_name(cleaned_full)
        if not is_rfc and last_name:
            cleaned_last_raw: str = self._clean_label_text(last_name)
            clean_last, _, _ = ContactTextUtils.clean_display_name(cleaned_last_raw)
            if (
                clean_last
                and ContactTextUtils.normalize_text(clean_last)
                not in self.config.all_excluded_locations_norm
            ):
                self.known_last_names_norm.add(ContactTextUtils.normalize_text(clean_last))
                for part in re.split(r"[\s\-]+", clean_last):
                    if len(part) >= 2:
                        self.known_last_names_norm.add(ContactTextUtils.normalize_text(part))
                if base_name not in self.name_to_last_name:
                    self.name_to_last_name[base_name] = clean_last

        first_email: str = self._extract_first_email(row, fieldnames)
        if first_email:
            if cleaned_full not in self.name_to_first_email:
                self.name_to_first_email[cleaned_full] = first_email
            if base_name not in self.name_to_first_email:
                self.name_to_first_email[base_name] = first_email

    def _load_csv_metadata(self) -> None:
        """
        Parcourt tous les fichiers CSV et vCard (.vcf) détectés pour mémoriser
        les noms de famille et la première adresse e-mail de chaque contact.
        """
        vcf_reader = VCardContactsReader(config=self.config)
        for contact_path in self.config.get_csv_files():
            if not os.path.exists(contact_path):
                continue
            if contact_path.lower().endswith(".vcf"):
                for row in vcf_reader.parse_file_rows(contact_path):
                    self._register_metadata_row(row, list(row.keys()))
                continue
            with open(contact_path, mode="r", encoding=self.config.encoding, newline="") as f:
                sample: str = f.read(4096)
                f.seek(0)
                delimiter: str = self._detect_csv_delimiter(sample)
                reader: csv.DictReader = csv.DictReader(f, delimiter=delimiter)
                if not reader.fieldnames:
                    continue
                fieldnames: List[str] = list(reader.fieldnames)
                for row in reader:
                    self._register_metadata_row(row, fieldnames)

    def _format_domain_display(self, domain_root: str) -> str:
        """Formate l'affichage d'un nom de domaine."""
        lower_root: str = domain_root.strip().lower()
        if lower_root in self.config.domain_aliases:
            display_val: str = self.config.domain_aliases[lower_root]
        elif "-" in lower_root:
            words: List[str] = [w.capitalize() for w in lower_root.split("-") if w]
            display_val = " ".join(words)
        else:
            display_val = domain_root
        return ContactTextUtils.abbreviate_locations_in_text(
            display_val, self.config.all_excluded_locations_norm
        )

    def _get_domain_suffix(self, email: str, contact_last_name: str, base_name: str = "") -> str:
        """Retourne ' (domaine)' sans extension si le domaine n'est pas redondant."""
        domain_root: str = ContactTextUtils.extract_domain_root(email)
        if not domain_root or domain_root in self.config.ignored_domains:
            return ""
        norm_domain: str = ContactTextUtils.normalize_text(domain_root)
        if norm_domain in self.known_last_names_norm or norm_domain in self.config.all_excluded_locations_norm:
            return ""
        if contact_last_name and norm_domain == ContactTextUtils.normalize_text(contact_last_name):
            return ""
        if base_name:
            norm_base: str = ContactTextUtils.normalize_text(base_name)
            if norm_domain == norm_base or (len(norm_domain) >= 4 and norm_domain in norm_base):
                return ""
        return f" ({self._format_domain_display(domain_root)})"

    def _anonymize_full_name(self, base_name: str, extra_chars: int = 0) -> Tuple[str, str]:
        """Formate le prénom et remplace le nom de famille par ses initiales."""
        couple_match: Optional[re.Match[str]] = re.match(r"^(.+?)\s+(et|&)\s+(.+)", base_name, flags=re.IGNORECASE)
        if couple_match:
            anon_l, last_l = self._anonymize_full_name(couple_match.group(1).strip(), extra_chars=extra_chars)
            anon_r, last_r = self._anonymize_full_name(couple_match.group(3).strip(), extra_chars=extra_chars)
            return f"{anon_l} {couple_match.group(2)} {anon_r}", f"{last_l} {last_r}".strip()

        last_name: Optional[str] = self.name_to_last_name.get(base_name)
        if last_name and base_name.endswith(last_name):
            first_part: str = ContactTextUtils.format_first_name(base_name[: -len(last_name)].strip())
            initials: str = ContactTextUtils.format_initials(last_name, extra_chars=extra_chars)
            return (f"{first_part} {initials}".strip() if first_part else initials), last_name

        if " " in base_name:
            first_raw, guessed_last = base_name.rsplit(" ", 1)
            return f"{ContactTextUtils.format_first_name(first_raw)} {ContactTextUtils.format_initials(guessed_last, extra_chars=extra_chars)}".strip(), guessed_last

        return ContactTextUtils.format_first_name(base_name), ""
    def _resolve_homonym_collision(
        self, base_name: str, initial_name: str, last_name: str, suffix: str,
        assigned_owners: Dict[str, str], identity_to_display: Dict[str, str],
    ) -> str:
        """Résout les collisions d'homonymes par extension à 2 lettres ou compteur (-2, -3)."""
        norm_id: str = ContactTextUtils.normalize_text(base_name)
        if norm_id in identity_to_display:
            return identity_to_display[norm_id]

        initial_disp: str = ContactTextUtils.sanitize_final_line(f"{initial_name}{suffix}")
        if assigned_owners.get(initial_disp) in (None, norm_id):
            assigned_owners[initial_disp] = norm_id
            identity_to_display[norm_id] = initial_disp
            return initial_disp

        base_counter: str = initial_name
        if last_name and len("".join(c for c in last_name if c.isalpha())) >= 2:
            alt_name, _ = self._anonymize_full_name(base_name, extra_chars=1)
            cand: str = ContactTextUtils.sanitize_final_line(f"{alt_name}{suffix}")
            if assigned_owners.get(cand) in (None, norm_id):
                assigned_owners[cand] = norm_id
                identity_to_display[norm_id] = cand
                return cand
            base_counter = alt_name

        stem: str = base_counter.rstrip(".")
        counter: int = 2
        while True:
            fallback: str = ContactTextUtils.sanitize_final_line(f"{stem}-{counter}{suffix}")
            if assigned_owners.get(fallback) in (None, norm_id):
                assigned_owners[fallback] = norm_id
                identity_to_display[norm_id] = fallback
                return fallback
            counter += 1

    def _has_known_first_name_in_label(self, base_name: str, raw_last: str) -> bool:
        """Vérifie qu'au moins un mot hors nom de famille est un prénom ou titre connu."""
        title_markers: Set[str] = {
            "dr", "docteur", "pr", "professeur", "mme", "madame", "m", "monsieur", "me", "maitre"
        }
        last_norm: str = ContactTextUtils.normalize_text(raw_last)
        for tok in re.split(r"[\s\-'\u2019]+", base_name.strip()):
            norm_tok: str = ContactTextUtils.normalize_text(tok)
            if not norm_tok or norm_tok == last_norm:
                continue
            if norm_tok in self.frequent_first_names or norm_tok in title_markers:
                return True
        return False

    @staticmethod
    def _extract_surname_alias_from_display(base_name: str, last_name: str, final_display: str) -> str:
        """Extrait le suffixe d'initiale attribué au nom de famille dans le libellé final."""
        clean_disp: str = re.sub(r"\s*\([^)]+\)\s*$", "", final_display).strip()
        if last_name and base_name.endswith(last_name):
            first_raw: str = base_name[: -len(last_name)].strip()
            formatted_first: str = ContactTextUtils.format_first_name(first_raw)
            if formatted_first and clean_disp.startswith(formatted_first + " "):
                extracted: str = clean_disp[len(formatted_first) :].strip()
                if extracted:
                    return extracted
        tokens: List[str] = clean_disp.split()
        return tokens[-1] if len(tokens) >= 2 else f"{last_name.strip()[:1].upper()}."

    def export_surnames_file(self, resolved_surname_aliases: Optional[Dict[str, str]] = None) -> int:
        """Exporte les noms de famille uniques de personnes physiques dans contact_surnames.txt."""
        from doc_anonymizer.audit_state_manager import AuditAndStateManager
        from doc_anonymizer.text_utils import DocumentTextUtils

        resolved_map: Dict[str, str] = resolved_surname_aliases or {}
        surnames_map: Dict[str, str] = {}
        for base_name, raw_last in self.name_to_last_name.items():
            if ContactTextUtils.is_non_person_entity(
                base_name, "", self.config.entity_prefixes,
                self.config.company_keywords, self.frequent_first_names,
            ):
                continue
            if not self._has_known_first_name_in_label(base_name, raw_last):
                continue
            for part in re.split(r"[\s\-]+", raw_last.strip()):
                clean_part: str = re.sub(r"[^A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç']", "", part)
                if len(clean_part) < 4 or any(ch.isdigit() for ch in part):
                    continue
                norm_part: str = SharedCoreUtils.normalize_token(clean_part)
                compact_part: str = ContactTextUtils.normalize_text(clean_part)
                if (
                    len(norm_part) < 4
                    or norm_part in self.frequent_first_names
                    or compact_part in self.frequent_first_names
                    or norm_part in self.config.surname_collisions
                    or norm_part in self.config.excluded_words
                    or norm_part in AuditAndStateManager.COMMON_FRENCH_STOPWORDS
                    or norm_part in DocumentTextUtils.ORG_GENERIC_WORDS
                    or compact_part in self.config.all_excluded_locations_norm
                    or compact_part in self.config.all_company_keywords_norm
                    or compact_part in self.config.all_ignored_domains_norm
                ):
                    continue
                if norm_part not in surnames_map:
                    display_last: str = clean_part.capitalize()
                    alias_val: str = resolved_map.get(norm_part, f"{display_last[:1].upper()}.")
                    surnames_map[norm_part] = f"{display_last} = {alias_val}"

        sorted_lines: List[str] = [
            "# NOMS DE FAMILLE EXTRAITS DES CONTACTS (GÉNÉRÉ AUTOMATIQUEMENT)\n\n"
        ] + [f"{surnames_map[k]}\n" for k in sorted(surnames_map.keys())]
        SharedCoreUtils.atomic_write_text(self.config.surnames_output_file, "".join(sorted_lines), encoding="utf-8")
        return len(surnames_map)

    def process(self) -> int:
        """Exécute l'anonymisation complète, exporte les noms de famille et écrit le fichier de sortie."""
        self._load_csv_metadata()
        if not os.path.exists(self.config.output_file):
            raise FileNotFoundError(f"Le fichier d'indexation '{self.config.output_file}' est introuvable.")

        assigned_owners: Dict[str, str] = {}
        identity_to_display: Dict[str, str] = {}
        resolved_surname_aliases: Dict[str, str] = {}
        output_lines: List[str] = []

        with open(self.config.output_file, mode="r", encoding="utf-8") as in_file:
            for raw_line in in_file:
                line: str = raw_line.rstrip("\r\n")
                if not line or self.config.separator not in line:
                    continue
                contact_val, raw_full_name = line.split(self.config.separator, 1)
                contact_val = contact_val.strip()
                base_name, existing_paren, is_rfc = ContactTextUtils.clean_display_name(
                    self._clean_label_text(raw_full_name)
                )
                if is_rfc:
                    output_lines.append(f"{contact_val}{self.config.separator}{ContactTextUtils.sanitize_final_line(base_name)}\n")
                    continue

                is_entity: bool = ContactTextUtils.is_non_person_entity(
                    base_name, contact_val, self.config.entity_prefixes,
                    self.config.company_keywords, self.frequent_first_names,
                )
                if is_entity:
                    ent_label: str = ContactTextUtils.format_entity_label(base_name)
                    email_ref: str = contact_val if "@" in contact_val else self.name_to_first_email.get(base_name, "")
                    suffix: str = existing_paren or (self._get_domain_suffix(email_ref, "", base_name) if email_ref else "")
                    output_lines.append(f"{contact_val}{self.config.separator}{ContactTextUtils.sanitize_final_line(f'{ent_label}{suffix}')}\n")
                    continue

                anon_name, last_name = self._anonymize_full_name(base_name)
                email_ref = contact_val if "@" in contact_val else self.name_to_first_email.get(base_name, "")
                suffix = existing_paren or (self._get_domain_suffix(email_ref, last_name, base_name) if email_ref else "")
                final_right: str = self._resolve_homonym_collision(
                    base_name, anon_name, last_name, suffix, assigned_owners, identity_to_display
                )
                if last_name:
                    norm_last: str = SharedCoreUtils.normalize_token(last_name)
                    surname_alias: str = self._extract_surname_alias_from_display(base_name, last_name, final_right)
                    if norm_last and surname_alias and norm_last not in resolved_surname_aliases:
                        resolved_surname_aliases[norm_last] = surname_alias
                output_lines.append(f"{contact_val}{self.config.separator}{final_right}\n")

        SharedCoreUtils.atomic_write_text(self.config.anonymized_output_file, "".join(output_lines), encoding="utf-8")
        self.export_surnames_file(resolved_surname_aliases=resolved_surname_aliases)
        return len(output_lines)
