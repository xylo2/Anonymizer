# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import os
import re
from typing import Dict, List, Set, Tuple
from common.core_utils import SharedCoreUtils
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class DiscoveredChatContactsBuilder:
    """
    Extrait automatiquement les noms complets des expéditeurs et participants
    depuis les transcriptions de chats (Google Chat, Teams, WhatsApp, Messenger,
    Signal) et alimente output_contacts/discovered_chat_contacts.txt.
    """

    HEADER_SENDER_REGEX: re.Pattern[str] = re.compile(
        r"(?m)^(?:\[[^\]]+\]\s*DE|DE|PARTICIPANTS|WHATSAPP|MESSENGER|SIGNAL|TEAMS|GOOGLE CHAT)\s*:\s*(.+)$"
    )

    def __init__(self, config: PipelineConfig) -> None:
        """
        Initialise le constructeur avec la configuration du pipeline.

        :param config: Instance de PipelineConfig.
        """
        self.config: PipelineConfig = config

    def _load_existing_rules(self, file_path: str) -> Dict[str, str]:
        """Charge les règles déjà présentes dans un fichier clé = valeur."""
        rules: Dict[str, str] = {}
        if not file_path or not os.path.exists(file_path):
            return rules
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f_in:
            for raw_line in f_in:
                line: str = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                left, right = line.split("=", 1)
                k: str = left.strip()
                v: str = right.strip()
                if k and v:
                    rules[k] = v
        return rules

    def _collect_known_targets_norm(self) -> Set[str]:
        """Rassemble les cibles déjà couvertes par les autres fichiers de contacts."""
        known: Set[str] = set()
        for path in (
            self.config.contacts_file,
            self.config.discovered_contacts_file,
            self.config.manual_contacts_file,
            self.config.discovered_chats_file,
        ):
            for key in self._load_existing_rules(path):
                norm: str = SharedCoreUtils.normalize_compact_text(key)
                if norm:
                    known.add(norm)
        return known

    def _format_candidate_pair(self, raw_name: str) -> Tuple[str, str]:
        """
        Valide un nom extrait d'un chat et génère la paire (Nom Complet, Alias).

        :param raw_name: Chaîne brute extraite d'un en-tête de chat.
        :return: Couple (cible, alias) ou ('', '') si non pertinent.
        """
        cleaned: str = re.sub(r"\([^)]*\)", " ", raw_name)
        cleaned = re.sub(r"<[^>]*>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:;.,\"'[]()")
        if not cleaned or len(cleaned) < 4:
            return "", ""
        if "@" in cleaned or any(ch.isdigit() for ch in cleaned):
            return "", ""

        lower_val: str = cleaned.lower()
        if lower_val.startswith(("email_", "tel_", "pseudo_", "personnage_")):
            return "", ""
        if lower_val in {
            "inconnu", "moi", "vous", "systeme", "système",
            "conversation signal", "discussion whatsapp", "_chat",
        }:
            return "", ""

        tokens: List[str] = [t for t in cleaned.split(" ") if t]
        if len(tokens) < 2 or len(tokens) > 4:
            return "", ""
        if not all(t[0].isupper() for t in tokens if t):
            return "", ""

        norm_tokens: List[str] = [DocumentTextUtils.normalize_word(t) for t in tokens]
        if any(len(nt) < 2 for nt in norm_tokens):
            return "", ""
        if any(
            nt in self.config.excluded_words
            or nt in self.config.masked_locations
            or nt in DocumentTextUtils.ORG_GENERIC_WORDS
            for nt in norm_tokens
        ):
            return "", ""

        if self.config.known_first_names:
            first_tok: str = norm_tokens[0]
            first_ok: bool = (
                first_tok in self.config.known_first_names
                or any(p in self.config.known_first_names for p in first_tok.split("-"))
            )
            if not first_ok:
                return "", ""

        first_part: str = " ".join(tokens[:-1])
        last_initial: str = tokens[-1][0].upper()
        alias: str = f"{first_part} {last_initial}."
        return cleaned, alias

    def _scan_chat_transcriptions(self) -> Dict[str, str]:
        """Parcourt les transcriptions dans extracted_texts/**/Chats/."""
        discovered: Dict[str, str] = {}
        trans_dir: str = self.config.transcriptions_dir
        if not os.path.isdir(trans_dir):
            return discovered

        for root_p, _, files in os.walk(trans_dir):
            if os.path.basename(root_p).lower() != "chats":
                continue
            for fname in sorted(files):
                if fname.startswith(".") or not fname.lower().endswith(".txt"):
                    continue
                full_p: str = os.path.join(root_p, fname)
                try:
                    with open(full_p, "r", encoding="utf-8", errors="ignore") as f_in:
                        content: str = f_in.read()
                except OSError:
                    continue

                for match in self.HEADER_SENDER_REGEX.finditer(content):
                    raw_field: str = match.group(1)
                    for candidate in re.split(r"[,;]+", raw_field):
                        target, alias = self._format_candidate_pair(candidate)
                        if target and alias:
                            discovered[target] = alias
        return discovered

    def build_or_update(self) -> Tuple[int, int]:
        """
        Met à jour output_contacts/discovered_chat_contacts.txt sans doublon.

        :return: Tuple (nombre_ajouts, nombre_total).
        """
        existing: Dict[str, str] = self._load_existing_rules(
            self.config.discovered_chats_file
        )
        known_norm: Set[str] = self._collect_known_targets_norm()
        candidates: Dict[str, str] = self._scan_chat_transcriptions()

        added: int = 0
        for target, alias in sorted(candidates.items()):
            norm_t: str = SharedCoreUtils.normalize_compact_text(target)
            if not norm_t or norm_t in known_norm:
                continue
            existing[target] = alias
            known_norm.add(norm_t)
            added += 1

        if added > 0 or not os.path.exists(self.config.discovered_chats_file):
            out_dir: str = os.path.dirname(
                os.path.abspath(self.config.discovered_chats_file)
            )
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            lines: List[str] = [
                "# CONTACTS DÉCOUVERTS AUTOMATIQUEMENT DANS LES CHATS\n",
                "# Généré depuis extracted_texts/**/Chats/ (Google Chat, Teams, WhatsApp, Messenger, Signal)\n\n",
            ]
            for k in sorted(existing.keys(), key=lambda s: s.lower()):
                lines.append(f"{k} = {existing[k]}\n")
            DocumentTextUtils.atomic_write_text(
                self.config.discovered_chats_file, "".join(lines)
            )

        return added, len(existing)
