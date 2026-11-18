# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
from typing import Dict, List, Optional, Set, Tuple
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class DiscoveredEmailContactsBuilder:
    """
    Génère et enrichit le fichier contacts_emails_decouverts.txt à partir
    de tous_emails_trouves.txt pour compléter contacts.txt et
    contacts_manuels.txt sans doublon, puis purge tous_emails_trouves.txt.
    """

    def __init__(self, config: PipelineConfig) -> None:
        """
        Initialise le générateur de contacts découverts.

        :param config: Instance de PipelineConfig.
        """
        self.config: PipelineConfig = config

    def _collect_existing_targets(self) -> Set[str]:
        """
        Lit contacts.txt et contacts_manuels.txt afin de recenser toutes
        les cibles (e-mails ou noms) déjà couvertes.

        :return: Ensemble des cibles normalisées déjà définies.
        """
        covered: Set[str] = set()
        for path in (
            self.config.contacts_file,
            self.config.manual_contacts_file,
        ):
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                for raw_line in f:
                    line: str = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    for sep in ("=", ";", ","):
                        if sep in line:
                            left_p, right_p = line.split(sep, 1)
                            target, alias, _ = (
                                DocumentTextUtils.resolve_contact_pair(
                                    left_p, right_p
                                )
                            )
                            if target and alias:
                                covered.add(
                                    DocumentTextUtils.normalize_identifier(
                                        target
                                    )
                                )
                                covered.add(
                                    DocumentTextUtils.normalize_word(target)
                                )
                            break
        return covered

    def _load_existing_discovered(self) -> Dict[str, str]:
        """
        Charge les règles déjà générées dans contacts_emails_decouverts.txt
        afin de préserver les alias existants entre deux exécutions.

        :return: Dictionnaire cible -> alias existant.
        """
        existing: Dict[str, str] = {}
        disc_path: str = self.config.discovered_contacts_file
        if not os.path.exists(disc_path):
            return existing
        with open(disc_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line: str = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                left_p, right_p = line.split("=", 1)
                target, alias, _ = DocumentTextUtils.resolve_contact_pair(
                    left_p, right_p
                )
                if target and alias:
                    existing[target] = alias
        return existing

    def _infer_full_name_from_email(self, email: str) -> Optional[str]:
        """
        Déduit 'Prénom Nom' si l'adresse e-mail est au format
        'prenom.nom@domaine' ou 'nom.prenom@domaine' avec un prénom connu.

        :param email: Adresse e-mail normalisée.
        :return: Chaîne 'Prénom Nom' capitalisée ou None.
        """
        if "@" not in email:
            return None
        local_part, _ = email.split("@", 1)
        tokens: List[str] = [
            t for t in re.split(r"[\.\-_]+", local_part.strip()) if t
        ]
        if len(tokens) != 2:
            return None
        first_tok, second_tok = tokens
        if any(ch.isdigit() for ch in first_tok + second_tok):
            return None
        if len(first_tok) < 2 or len(second_tok) < 2:
            return None

        norm_1: str = DocumentTextUtils.normalize_word(first_tok)
        norm_2: str = DocumentTextUtils.normalize_word(second_tok)
        is_fn_1: bool = norm_1 in self.config.known_first_names
        is_fn_2: bool = norm_2 in self.config.known_first_names

        if is_fn_1 and not is_fn_2:
            return f"{first_tok.capitalize()} {second_tok.capitalize()}"
        if is_fn_2 and not is_fn_1:
            return f"{second_tok.capitalize()} {first_tok.capitalize()}"
        return None
    def _next_alias_index(self, existing_rules: Dict[str, str]) -> int:
        """
        Détermine le prochain numéro disponible pour les alias Contact_Mail_XXX.

        :param existing_rules: Dictionnaire des règles déjà présentes.
        :return: Prochain index entier >= 1.
        """
        max_idx: int = 0
        for alias in existing_rules.values():
            match = re.match(r"^Contact_Mail_(\d+)$", alias.strip())
            if match:
                max_idx = max(max_idx, int(match.group(1)))
        return max_idx + 1

    @staticmethod
    def _sort_discovered_item(item: Tuple[str, str]) -> Tuple[str, str]:
        """
        Calcule la clé de tri alphabétique pour une entrée découverte.

        :param item: Tuple (cible, alias).
        :return: Tuple normalisé pour le tri.
        """
        target_key, _ = item
        return (
            DocumentTextUtils.normalize_word(target_key),
            target_key.lower(),
        )

    def build_or_update(self) -> Tuple[int, int]:
        """
        Lit tous_emails_trouves.txt, complète contacts_emails_decouverts.txt
        avec les adresses et noms déduits absents des deux autres fichiers,
        puis purge tous_emails_trouves.txt de façon atomique.

        :return: Tuple (nouvelles_regles_ajoutees, total_regles_fichier).
        """
        emails_path: str = self.config.all_emails_file
        if not os.path.exists(emails_path):
            return 0, 0

        covered_targets: Set[str] = self._collect_existing_targets()
        discovered_rules: Dict[str, str] = self._load_existing_discovered()
        existing_norm_keys: Set[str] = {
            DocumentTextUtils.normalize_identifier(k)
            for k in discovered_rules.keys()
        } | {
            DocumentTextUtils.normalize_word(k)
            for k in discovered_rules.keys()
        }

        next_idx: int = self._next_alias_index(discovered_rules)
        added_count: int = 0

        with open(emails_path, "r", encoding="utf-8") as f_mail:
            raw_emails: List[str] = [
                DocumentTextUtils.normalize_identifier(ln)
                for ln in f_mail
                if "@" in ln
            ]

        for email in sorted(set(raw_emails)):
            if (
                not email
                or email in covered_targets
                or email in existing_norm_keys
            ):
                continue

            alias: str = f"Contact_Mail_{next_idx:03d}"
            next_idx += 1

            discovered_rules[email] = alias
            existing_norm_keys.add(email)
            added_count += 1

            inferred_name: Optional[str] = self._infer_full_name_from_email(
                email
            )
            if inferred_name:
                norm_name: str = DocumentTextUtils.normalize_word(
                    inferred_name
                )
                if (
                    norm_name not in covered_targets
                    and norm_name not in existing_norm_keys
                ):
                    discovered_rules[inferred_name] = alias
                    existing_norm_keys.add(norm_name)
                    added_count += 1

        if added_count > 0 or not os.path.exists(
            self.config.discovered_contacts_file
        ):
            out_path: str = self.config.discovered_contacts_file
            sorted_items: List[Tuple[str, str]] = sorted(
                discovered_rules.items(),
                key=self._sort_discovered_item,
            )
            out_lines: List[str] = [
                "# CONTACTS DÉCOUVERTS AUTOMATIQUEMENT DEPUIS "
                "tous_emails_trouves.txt\n",
                "# Complète contacts.txt et contacts_manuels.txt.\n\n",
            ]
            for target_k, alias_v in sorted_items:
                out_lines.append(f"{target_k} = {alias_v}\n")
            DocumentTextUtils.atomic_write_text(out_path, "".join(out_lines))

        DocumentTextUtils.atomic_write_text(emails_path, "")

        return added_count, len(discovered_rules)
