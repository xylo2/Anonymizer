# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
from typing import Dict, List, Optional, Set, Tuple
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class DiscoveredEmailContactsBuilder:
    """
    Génère et enrichit le fichier contacts_emails_decouverts.txt à partir
    de tous_emails_trouves.txt (adresses et noms d'affichage MIME) pour compléter
    contacts.txt et contacts_manuels.txt sans doublon.
    """

    TECHNICAL_EMAIL_SUFFIXES: Tuple[str, ...] = (
        "@chat.google.com",
        "@bot.chat.google.com",
        "chat.google.com",
    )

    def __init__(self, config: PipelineConfig) -> None:
        """
        Initialise le générateur de contacts découverts.

        :param config: Instance de PipelineConfig.
        """
        self.config: PipelineConfig = config

    @classmethod
    def is_valid_discoverable_email(cls, email: str) -> bool:
        """
        Vérifie qu'une adresse e-mail n'est ni un identifiant technique RCS
        ni une chaîne corrompue contenant '=' ou plusieurs '@'.

        :param email: Adresse e-mail normalisée.
        :return: True si l'adresse est exploitable comme règle de contact.
        """
        low: str = email.strip().lower()
        if not low or "=" in low or low.count("@") != 1:
            return False
        local_p, domain_p = low.split("@", 1)
        if not local_p or "." not in domain_p:
            return False
        return not any(low.endswith(suf) for suf in cls.TECHNICAL_EMAIL_SUFFIXES)

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
                    if not line or line.startswith("#") or line.count("=") > 1:
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
        Charge les règles valides déjà générées dans contacts_emails_decouverts.txt
        en écartant toute ancienne ligne technique corrompue.

        :return: Dictionnaire cible -> alias existant.
        """
        existing: Dict[str, str] = {}
        disc_path: str = self.config.discovered_contacts_file
        if not os.path.exists(disc_path):
            return existing
        with open(disc_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line: str = raw_line.strip()
                if (
                    not line
                    or line.startswith("#")
                    or line.count("=") != 1
                ):
                    continue
                left_p, right_p = line.split("=", 1)
                target, alias, _ = DocumentTextUtils.resolve_contact_pair(
                    left_p, right_p
                )
                if not target or not alias:
                    continue
                if "@" in target and not self.is_valid_discoverable_email(target):
                    continue
                existing[target] = alias
        return existing
    def _validate_display_name(self, raw_disp: str) -> Optional[str]:
        """
        Vérifie si un nom d'affichage MIME contient un prénom connu et un nom valide.

        :param raw_disp: Libellé brut issu d'un en-tête From/To.
        :return: 'Prénom Nom' normalisé ou None.
        """
        tokens: List[str] = [t for t in raw_disp.strip().split() if t]
        if len(tokens) != 2:
            return None
        t1, t2 = tokens
        if any(ch.isdigit() for ch in t1 + t2):
            return None
        n1: str = DocumentTextUtils.normalize_word(t1)
        n2: str = DocumentTextUtils.normalize_word(t2)
        if n1 in self.config.masked_locations or n2 in self.config.masked_locations:
            return None
        is_fn1: bool = n1 in self.config.known_first_names
        is_fn2: bool = n2 in self.config.known_first_names
        if is_fn1 and not is_fn2 and len(n2) >= 3:
            return f"{t1.capitalize()} {t2.capitalize()}"
        if is_fn2 and not is_fn1 and len(n1) >= 3:
            return f"{t2.capitalize()} {t1.capitalize()}"
        return None

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
        avec les adresses valides et noms déduits, puis purge tous_emails_trouves.txt.

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

        email_to_display: Dict[str, str] = {}
        with open(emails_path, "r", encoding="utf-8") as f_mail:
            for raw_ln in f_mail:
                ln: str = raw_ln.strip()
                if "@" not in ln:
                    continue
                if "|" in ln:
                    raw_em, raw_disp = ln.split("|", 1)
                    norm_em: str = DocumentTextUtils.normalize_identifier(raw_em)
                    valid_disp: Optional[str] = self._validate_display_name(raw_disp)
                    if self.is_valid_discoverable_email(norm_em):
                        email_to_display.setdefault(norm_em, valid_disp or "")
                        if valid_disp and not email_to_display[norm_em]:
                            email_to_display[norm_em] = valid_disp
                else:
                    norm_em = DocumentTextUtils.normalize_identifier(ln)
                    if self.is_valid_discoverable_email(norm_em):
                        email_to_display.setdefault(norm_em, "")

        next_idx: int = self._next_alias_index(discovered_rules)
        added_count: int = 0

        for email, header_name in sorted(email_to_display.items()):
            alias: str = ""
            if email not in covered_targets and email not in existing_norm_keys:
                alias = f"Contact_Mail_{next_idx:03d}"
                next_idx += 1
                discovered_rules[email] = alias
                existing_norm_keys.add(email)
                added_count += 1
            else:
                alias = discovered_rules.get(email, "")

            inferred_name: Optional[str] = header_name or self._infer_full_name_from_email(email)
            if inferred_name and alias:
                norm_name: str = DocumentTextUtils.normalize_word(inferred_name)
                if norm_name not in covered_targets and norm_name not in existing_norm_keys:
                    discovered_rules[inferred_name] = alias
                    existing_norm_keys.add(norm_name)
                    added_count += 1

        if added_count > 0 or os.path.exists(self.config.discovered_contacts_file):
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
