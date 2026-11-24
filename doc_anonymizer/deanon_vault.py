# Commandes pip à exécuter : Aucune dépendance externe requise

from collections import Counter
import json
import os
from typing import Any, Dict, List, Tuple
from doc_anonymizer.text_utils import DocumentTextUtils


class DeanonVaultManager:
    """
    Coffre local de réversibilité (audits/deanon_vault.json) mémorisant toutes les
    correspondances Jeton_Anonymisé -> Valeur_Originale créées lors du masquage.
    """

    def __init__(self, vault_path: str) -> None:
        self.vault_path: str = os.path.abspath(vault_path)
        self._records: Dict[str, Dict[str, Any]] = {}
        self._forward_index: Dict[Tuple[str, str], str] = {}
        self._category_counters: Counter[str] = Counter()

    def load(self) -> None:
        """Charge le coffre depuis le disque s'il existe."""
        if not self.vault_path or not os.path.isfile(self.vault_path):
            return
        try:
            with open(self.vault_path, "r", encoding="utf-8") as f_in:
                payload = json.load(f_in)
            entries = payload.get("entries", {}) if isinstance(payload, dict) else {}
            if isinstance(entries, dict):
                self._records = dict(entries)
                for token, info in self._records.items():
                    if not isinstance(info, dict):
                        continue
                    cat: str = str(info.get("category") or "")
                    variants = info.get("variants", {})
                    if isinstance(variants, dict):
                        for orig_val in variants:
                            norm_orig: str = str(orig_val).strip().lower()
                            if cat and norm_orig:
                                self._forward_index[(cat, norm_orig)] = token
                    if token.startswith("[") and "_" in token and token.endswith("]"):
                        stem, num_s = token[1:-1].rsplit("_", 1)
                        if num_s.isdigit():
                            self._category_counters[stem] = max(self._category_counters[stem], int(num_s))
        except Exception:
            pass

    def get_or_create_numbered_token(self, prefix: str, original_value: str, category: str) -> str:
        """Retourne un jeton déterministe numéroté [PREFIX_01] et enregistre la valeur d'origine."""
        clean_orig: str = original_value.strip()
        if not clean_orig:
            return f"[{prefix}_MASQUE]"
        norm_key: str = (category, clean_orig.lower())
        token: str = self._forward_index.get(norm_key, "")
        if not token:
            self._category_counters[prefix] += 1
            token = f"[{prefix}_{self._category_counters[prefix]:02d}]"
            self._forward_index[norm_key] = token
        self.record_mapping(token, clean_orig, category)
        return token

    def record_mapping(self, token: str, original_value: str, category: str) -> None:
        """Enregistre une correspondance Jeton -> Valeur d'origine avec compteur d'occurrences."""
        clean_tok: str = token.strip()
        clean_orig: str = original_value.strip()
        if not clean_tok or not clean_orig or clean_tok.lower() == clean_orig.lower():
            return
        entry = self._records.setdefault(clean_tok, {"category": category, "variants": {}})
        variants: Dict[str, int] = entry.setdefault("variants", {})
        variants[clean_orig] = int(variants.get(clean_orig, 0)) + 1

    def get_all_ranked_entries(self) -> Dict[str, List[Tuple[str, str]]]:
        """Retourne {jeton: [(valeur_originale, catégorie), ...]} trié par fréquence décroissante."""
        ranked_out: Dict[str, List[Tuple[str, str]]] = {}
        for token, info in self._records.items():
            if not isinstance(info, dict):
                continue
            cat: str = str(info.get("category") or "Coffre")
            variants = info.get("variants", {})
            if not isinstance(variants, dict):
                continue
            sorted_vars = sorted(variants.items(), key=lambda kv: (-int(kv[1]), kv[0].lower()))
            ranked_out[token] = [(orig_v, cat) for orig_v, _ in sorted_vars if orig_v.strip()]
        return ranked_out

    def save(self) -> None:
        """Sauvegarde atomiquement le coffre de réversibilité sur disque."""
        if not self.vault_path:
            return
        parent_dir: str = os.path.dirname(self.vault_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        payload: Dict[str, Any] = {
            "total_tokens": len(self._records),
            "entries": dict(sorted(self._records.items(), key=lambda kv: kv[0].lower())),
        }
        DocumentTextUtils.atomic_write_text(
            self.vault_path,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
