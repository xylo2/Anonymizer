# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
from typing import Dict, List, Set, Tuple
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_rules_loader import ContactRulesLoader
from doc_anonymizer.text_utils import DocumentTextUtils


class AuditManualContactsImporter:
    """
    Analyse les détections haute confiance de l'audit des noms résiduels
    et les importe automatiquement dans contacts_manuels.txt sans doublon.
    """

    AUDIT_LINE_PATTERN = re.compile(
        r"^\s*([A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-\s]+?)\s*=\s*"
        r"([A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-\.\s_]+?)"
        r"(?:\s*#\s*\[\s*(\d+)\s*x\s*\].*|\s*#\s*(\d+)\s*occ\.)?\s*$"
    )

    def __init__(
        self,
        config: PipelineConfig,
        rules: ContactRulesLoader,
        min_occurrences: int = 3,
    ) -> None:
        """Initialise l'importateur automatique depuis le rapport d'audit."""
        self.config: PipelineConfig = config
        self.rules: ContactRulesLoader = rules
        self.min_occurrences: int = min_occurrences

    def _load_existing_manual_keys(self) -> Tuple[Set[str], List[str]]:
        """Charge les cibles déjà présentes dans contacts_manuels.txt."""
        existing_keys: Set[str] = set()
        lines: List[str] = []
        path: str = self.config.manual_contacts_file
        if not os.path.exists(path):
            return existing_keys, lines
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                lines.append(raw_line.rstrip("\r\n"))
                stripped: str = raw_line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" in stripped:
                    left, _ = stripped.split("=", 1)
                    existing_keys.add(DocumentTextUtils.normalize_word(left))
        return existing_keys, lines

    def _is_valid_import_candidate(self, name: str, alias: str) -> bool:
        """Vérifie qu'un nom issu de l'audit est éligible à l'import automatique."""
        if not name or not alias:
            return False
        words: List[str] = [w for w in name.split() if w]
        if len(words) < 2:
            return False
        for w in words:
            norm: str = DocumentTextUtils.normalize_word(w)
            if (
                norm in self.config.excluded_words
                or norm in self.config.masked_locations
                or norm in DocumentTextUtils.ORG_GENERIC_WORDS
            ):
                return False
        return True

    def _format_default_alias(self, name: str) -> str:
        """Génère un alias 'Prénom I.' par défaut si l'audit indique A_MASQUER."""
        tokens: List[str] = [t for t in name.split() if t]
        if len(tokens) >= 2:
            first_tok: str = tokens[0]
            return f"{first_tok.capitalize()} {tokens[-1][:1].upper()}."
        return f"{name[:1].upper()}."

    def import_high_confidence_from_audit(self) -> int:
        """Importe dans contacts_manuels.txt les noms dépassant min_occurrences."""
        source_path: str = (
            self.config.audit_report_file
            if os.path.exists(self.config.audit_report_file)
            else self.config.audit_copy_file
        )
        if not os.path.exists(source_path):
            return 0

        existing_keys, lines = self._load_existing_manual_keys()
        new_entries: Dict[str, str] = {}

        with open(source_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                stripped: str = raw_line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                m = self.AUDIT_LINE_PATTERN.match(stripped)
                if not m:
                    continue
                name: str = m.group(1).strip()
                raw_alias: str = m.group(2).strip()
                occ_str: str = m.group(3) or m.group(4) or "0"
                occ: int = int(occ_str)
                if occ < self.min_occurrences:
                    continue
                norm_name: str = DocumentTextUtils.normalize_word(name)
                if norm_name in existing_keys or norm_name in new_entries:
                    continue
                alias: str = (
                    self._format_default_alias(name)
                    if raw_alias == "A_MASQUER"
                    else raw_alias
                )
                if self._is_valid_import_candidate(name, alias):
                    new_entries[norm_name] = f"{name} = {alias}"

        if not new_entries:
            return 0

        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(sorted(new_entries.values(), key=str.lower))
        DocumentTextUtils.atomic_write_text(
            self.config.manual_contacts_file,
            "\n".join(lines) + "\n",
        )
        return len(new_entries)
