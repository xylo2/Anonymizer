# Commandes pip à exécuter : Aucune dépendance externe requise

from collections import Counter, defaultdict
import hashlib
import json
import os
import re
from typing import Any, DefaultDict, Dict, List, Pattern, Set, Tuple
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_rules_loader import ContactRulesLoader
from doc_anonymizer.text_utils import DocumentTextUtils


class AuditAndStateManager:
    """
    Gère la persistance JSON de reprise, la pseudonymisation SHA-256
    et la mise à jour en temps réel du rapport d'audit.
    """

    PAIR_PATTERN: Pattern[str] = re.compile(
        r"\b([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]"
        r"[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç-]{1,25})[ \t]+"
        r"([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]"
        r"[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç-]{1,25})\b"
    )

    TITLE_PATTERN: Pattern[str] = re.compile(
        r"\b(?:Dr|Docteur|Pr|Professeur|Mme|Madame|M\.|Monsieur|"
        r"Mlle|Me|Maître)\.?\s+([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]"
        r"[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç-]{2,25})\b"
    )

    def __init__(
        self, config: PipelineConfig, rules: ContactRulesLoader
    ) -> None:
        self.config: PipelineConfig = config
        self.rules: ContactRulesLoader = rules
        self.already_processed: Set[str] = set()
        self.auto_cache: Dict[str, str] = {}
        self.counters: Dict[str, int] = {"TEL": 1, "EMAIL": 1}
        self.pair_counter: Counter[str] = Counter()
        self.files_by_name: DefaultDict[str, Set[str]] = defaultdict(set)
        self.file_idx: int = 1
        self.written_batches: int = 0

    def load(self) -> None:
        """Restaure l'état JSON depuis le disque s'il existe."""
        os.makedirs(self.config.results_dir, exist_ok=True)
        if not os.path.exists(self.config.resume_state_file):
            return
        try:
            with open(
                self.config.resume_state_file, "r", encoding="utf-8"
            ) as f:
                st: Dict[str, Any] = json.load(f)
            self.already_processed = set(st.get("fichiers_traites", []))
            self.auto_cache = st.get("cache_auto", {})
            self.counters = st.get("compteurs", {"TEL": 1, "EMAIL": 1})
            self.pair_counter = Counter(st.get("compteur_paires", {}))
            self.files_by_name = defaultdict(
                set,
                {
                    k: set(v)
                    for k, v in st.get("fichiers_par_nom", {}).items()
                },
            )
            self.file_idx = st.get("idx_fichier", 1)
            self.written_batches = st.get("nb_lots_ecrits", 0)
        except Exception:
            pass

    def save(self) -> None:
        """Sauvegarde l'état courant sur le disque."""
        os.makedirs(self.config.results_dir, exist_ok=True)
        payload: Dict[str, Any] = {
            "fichiers_traites": sorted(self.already_processed),
            "idx_fichier": self.file_idx,
            "nb_lots_ecrits": self.written_batches,
            "cache_auto": self.auto_cache,
            "compteurs": self.counters,
            "compteur_paires": dict(self.pair_counter),
            "fichiers_par_nom": {
                k: sorted(v) for k, v in self.files_by_name.items()
            },
        }
        with open(self.config.resume_state_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def pseudonymize_id(self, raw_val: str, category: str) -> str:
        """Remplace un téléphone ou e-mail par son alias ou un jeton SHA-256."""
        norm_id: str = DocumentTextUtils.normalize_identifier(raw_val)
        if norm_id in self.rules.contacts_id:
            return self.rules.contacts_id[norm_id]
        salted: bytes = (norm_id + self.config.secret_salt).encode("utf-8")
        digest: str = hashlib.sha256(salted).hexdigest()[:10]
        if digest not in self.auto_cache:
            self.auto_cache[digest] = (
                f"{category}_{self.counters[category]:03d}"
            )
            self.counters[category] += 1
        return self.auto_cache[digest]

    def _is_valid_word(self, word: str) -> bool:
        if len(word) < 2 or word.startswith(("TEL_", "EMAIL_", "AUTRE_")):
            return False
        norm: str = DocumentTextUtils.normalize_word(word)
        return (
            norm not in self.config.excluded_words
            and norm not in self.rules.alias_words
            and norm not in self.config.masked_locations
        )

    def scan_residual_names(self, text: str, display_path: str) -> None:
        """Détecte les noms propres résiduels potentiels dans un bloc."""
        for m in self.PAIR_PATTERN.finditer(text):
            p1, p2 = m.group(1), m.group(2)
            if not (self._is_valid_word(p1) and self._is_valid_word(p2)):
                continue
            f1: bool = self.rules.is_first_name(p1)
            f2: bool = self.rules.is_first_name(p2)
            if not (f1 or f2) or (f1 and f2):
                continue
            key: str = f"{p1} {p2}"
            nk: str = DocumentTextUtils.normalize_word(key)
            ni: str = DocumentTextUtils.normalize_word(f"{p2} {p1}")
            if (
                nk not in self.rules.full_targets
                and ni not in self.rules.full_targets
            ):
                self.pair_counter[key] += 1
                self.files_by_name[key].add(display_path)

        for m in self.TITLE_PATTERN.finditer(text):
            name: str = m.group(1)
            if (
                self._is_valid_word(name)
                and DocumentTextUtils.normalize_word(name)
                not in self.rules.full_targets
            ):
                self.pair_counter[name] += 1
                self.files_by_name[name].add(display_path)

    def write_report(self) -> int:
        """Actualise audit_noms_residuels.txt sur le disque."""
        results: List[Tuple[str, int]] = [
            (n, c)
            for n, c in self.pair_counter.most_common()
            if c >= self.config.min_audit_occurrences
        ]
        with open(self.config.audit_report_file, "w", encoding="utf-8") as f:
            f.write(
                f"# AUDIT DES NOMS PROPRES RÉSIDUELS"
                f" ({len(self.already_processed)} fichier(s) analysé(s))\n"
                "# Copiez les lignes pertinentes dans contacts.txt"
                " et remplacez 'A_MASQUER' :\n\n"
            )
            if not results:
                f.write(
                    "Aucun nouveau nom propre résiduel probable détecté.\n"
                )
            for name, count in results:
                files: str = ", ".join(sorted(self.files_by_name[name])[:2])
                extra: int = len(self.files_by_name[name]) - 2
                if extra > 0:
                    files += f" (+{extra} autres)"
                f.write(f"{name} = A_MASQUER   # ({count}x dans : {files})\n")
        return len(results)
