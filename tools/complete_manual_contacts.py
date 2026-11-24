# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import os
import re
import sys
from typing import List, Set, Tuple

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common.core_utils import SharedCoreUtils
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class ManualContactsAutoCompleter:
    """
    Lit output_contacts/manual_contacts.txt, repère les entrées sans valeur après '='
    et génère automatiquement leur alias avant de sauvegarder atomiquement.
    """

    def __init__(self, config: PipelineConfig, dry_run: bool = False) -> None:
        """
        Initialise le compléteur automatique avec la configuration active.

        :param config: Instance de PipelineConfig.
        :param dry_run: Si True, prévisualise sans modifier le fichier.
        """
        self.config: PipelineConfig = config
        self.dry_run: bool = dry_run
        self._auto_id_counter: int = 1

    def _is_first_name(self, token: str) -> bool:
        """
        Vérifie si un mot appartient au référentiel des prénoms connus.

        :param token: Jeton brut à tester.
        :return: True si le mot est un prénom connu.
        """
        norm: str = DocumentTextUtils.normalize_word(token)
        if norm in self.config.known_first_names:
            return True
        if "-" in norm:
            parts: List[str] = [p for p in norm.split("-") if p]
            return bool(parts) and all(p in self.config.known_first_names for p in parts)
        return False

    @staticmethod
    def _format_first_name(token: str) -> str:
        """
        Capitalise proprement un prénom simple ou composé.

        :param token: Prénom brut.
        :return: Prénom correctement capitalisé.
        """
        parts: List[str] = re.split(r"(-)", token.strip())
        return "".join(p.capitalize() if p != "-" else p for p in parts)

    @staticmethod
    def _extract_initial(last_name: str) -> str:
        """
        Extrait l'initiale en majuscule d'un nom de famille (gère les noms composés).

        :param last_name: Nom de famille brut.
        :return: Initiale suivie d'un point (ex. 'D.' ou 'L.-M.').
        """
        clean: str = last_name.strip()
        if not clean:
            return ""
        if "-" in clean:
            sub_initials: List[str] = [
                f"{p.strip()[:1].upper()}." for p in clean.split("-") if p.strip()
            ]
            if sub_initials:
                return "-".join(sub_initials)
        return f"{clean[:1].upper()}."
    def generate_alias(self, raw_target: str, used_aliases: Set[str]) -> str:
        """
        Génère un alias anonymisé à partir de la cible brute.

        :param raw_target: Texte situé à gauche du symbole '='.
        :param used_aliases: Ensemble des alias déjà présents dans le fichier.
        :return: Alias généré (ex. 'Aurélien D.').
        """
        target: str = raw_target.strip()
        if DocumentTextUtils.is_contact_identifier(target):
            norm_id: str = DocumentTextUtils.normalize_identifier(target)
            prefix: str = "Contact_Mail" if "@" in norm_id else "Contact_Tel"
            while True:
                candidate: str = f"{prefix}_{self._auto_id_counter:03d}"
                self._auto_id_counter += 1
                if candidate not in used_aliases:
                    return candidate

        tokens: List[str] = [t for t in target.split() if t]
        if len(tokens) == 2:
            f_cand, s_cand = tokens
            if self._is_first_name(s_cand) and not self._is_first_name(f_cand):
                first_tok, last_tok = s_cand, f_cand
            else:
                first_tok, last_tok = f_cand, s_cand
            return f"{self._format_first_name(first_tok)} {self._extract_initial(last_tok)}".strip()

        if len(tokens) > 2:
            first_tok, last_tok = next(iter(tokens)), tokens[-1]
            if self._is_first_name(first_tok):
                return f"{self._format_first_name(first_tok)} {self._extract_initial(last_tok)}"
            return " ".join(f"{tok[:1].upper()}." for tok in tokens if tok)

        single: str = next(iter(tokens), target)
        if self._is_first_name(single):
            return f"{self._format_first_name(single)} X."
        return self._extract_initial(single) or "Unknown_Contact"

    def process(self) -> Tuple[int, int]:
        """
        Parcourt manual_contacts.txt, complète les lignes vides et sauvegarde atomiquement.

        :return: Tuple (nombre_lignes_completees, total_lignes_regles).
        """
        manual_path: str = self.config.manual_contacts_file
        if not os.path.exists(manual_path):
            print(f"[ERREUR] Fichier introuvable : '{manual_path}'.", flush=True)
            return 0, 0

        with open(manual_path, "r", encoding="utf-8") as f_in:
            raw_lines: List[str] = f_in.readlines()

        used_aliases: Set[str] = set()
        for line in raw_lines:
            stripped: str = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                left_ex, right_ex = stripped.split("=", 1)
                if left_ex.strip() and right_ex.strip():
                    _, resolved_alias, _ = DocumentTextUtils.resolve_contact_pair(left_ex, right_ex)
                    if resolved_alias:
                        used_aliases.add(resolved_alias)

        updated_lines: List[str] = []
        completed_count: int = 0
        total_rules: int = 0
        for line in raw_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                updated_lines.append(line)
                continue
            total_rules += 1
            left_raw, right_raw = line.split("=", 1)
            left_c, right_c = left_raw.strip(), right_raw.strip()
            target_to_fill: str = left_c if (left_c and not right_c) else (right_c if (right_c and not left_c) else "")
            if target_to_fill:
                new_alias: str = self.generate_alias(target_to_fill, used_aliases)
                used_aliases.add(new_alias)
                updated_lines.append(f"{target_to_fill} = {new_alias}\n")
                completed_count += 1
                tag: str = "[PRÉVISUALISATION]" if self.dry_run else "[COMPLÉTÉ]"
                print(f"{tag} '{target_to_fill}' --> '{target_to_fill} = {new_alias}'", flush=True)
            else:
                updated_lines.append(line)

        if completed_count > 0 and not self.dry_run:
            SharedCoreUtils.atomic_write_text(manual_path, "".join(updated_lines))
            print(f"\n[OK] {completed_count} règle(s) enregistrée(s) dans '{manual_path}'.", flush=True)
        elif completed_count > 0:
            print(f"\n[SIMULATION] {completed_count} règle(s) seraient complétées.", flush=True)
        return completed_count, total_rules


def main() -> None:
    """Point d'entrée en ligne de commande."""
    parser = argparse.ArgumentParser(description="Complète les lignes vides dans manual_contacts.txt.")
    parser.add_argument("-c", "--config", default="config.ini", help="Chemin vers config.ini.")
    parser.add_argument("--dry-run", action="store_true", help="Prévisualise sans écrire.")
    args = parser.parse_args()
    cfg_path: str = SharedCoreUtils.resolve_config_path(args.config, ROOT_DIR)
    ManualContactsAutoCompleter(PipelineConfig(cfg_path), dry_run=args.dry_run).process()


if __name__ == "__main__":
    main()
