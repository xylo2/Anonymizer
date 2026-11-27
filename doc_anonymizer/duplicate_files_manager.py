# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Utilisateur_A

import hashlib
import json
import os
from typing import Any, Dict, List, Set, Tuple
from doc_anonymizer.linked_sources_manager import LinkedSourcesManager
from doc_anonymizer.text_utils import DocumentTextUtils


class DuplicateFilesManager:
    """Détecte les fichiers identiques par typologie (extension, taille) et SHA-256."""

    def __init__(self, paths: Dict[str, str]) -> None:
        """Initialise le gestionnaire avec les chemins et le cache SHA-256."""
        self.paths: Dict[str, str] = paths
        self.workspace_root: str = paths.get("workspace_root") or os.path.dirname(
            paths.get("sources_dir", ".")
        )
        self.sources_dir: str = paths.get("sources_dir", "")
        audits_dir: str = os.path.join(self.workspace_root, "audits")
        self.selection_file: str = os.path.join(audits_dir, "ignored_duplicates.json")
        self.cache_file: str = os.path.join(audits_dir, ".sha256_cache.json")

    @staticmethod
    def compute_sha256(file_path: str, chunk_size: int = 65536) -> str:
        """Calcule l'empreinte SHA-256 d'un fichier par blocs."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f_in:
            while True:
                chunk: bytes = f_in.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def format_size_display(size_bytes: int) -> str:
        """Formate une taille en octets sous forme lisible (Ko / Mo)."""
        if size_bytes >= 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} Mo"
        if size_bytes >= 1024:
            return f"{max(1, size_bytes // 1024)} Ko"
        return f"{size_bytes} o"

    def _load_hash_cache(self) -> Dict[str, List[Any]]:
        """Charge le cache disque des empreintes SHA-256."""
        if not os.path.isfile(self.cache_file):
            return {}
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f_in:
                data = json.load(f_in)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_hash_cache(self, cache: Dict[str, List[Any]]) -> None:
        """Sauvegarde atomiquement le cache des empreintes SHA-256."""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            DocumentTextUtils.atomic_write_text(
                self.cache_file,
                json.dumps(cache, ensure_ascii=False),
            )
        except OSError:
            pass
    def _get_cached_sha256(
        self, file_path: str, cache: Dict[str, List[Any]], state: Dict[str, bool]
    ) -> str:
        """Retourne l'empreinte SHA-256 depuis le cache si taille et mtime correspondent."""
        st = os.stat(file_path)
        key: str = os.path.normcase(os.path.abspath(file_path))
        entry = cache.get(key)
        if (
            isinstance(entry, list)
            and len(entry) == 3
            and entry[0] == int(st.st_size)
            and entry[1] == int(st.st_mtime_ns)
            and isinstance(entry[2], str)
        ):
            return entry[2]
        digest: str = self.compute_sha256(file_path)
        cache[key] = [int(st.st_size), int(st.st_mtime_ns), digest]
        state["dirty"] = True
        return digest

    def load_ignored_paths(self) -> Set[str]:
        """Charge les chemins normalisés des doublons marqués à ignorer."""
        if not os.path.isfile(self.selection_file):
            return set()
        try:
            with open(self.selection_file, "r", encoding="utf-8") as f_in:
                payload = json.load(f_in)
            raw_list = payload.get("ignored_paths", []) if isinstance(payload, dict) else []
            return {os.path.normcase(os.path.normpath(str(p))) for p in raw_list if str(p).strip()}
        except (OSError, json.JSONDecodeError):
            return set()

    def save_selection(self, items: List[Dict[str, Any]]) -> Tuple[int, int]:
        """Enregistre la sélection des doublons conservés et ignorés."""
        ignored: List[str] = [os.path.normpath(str(it["path"])) for it in items if not it.get("selected") and it.get("path")]
        kept_count: int = sum(1 for it in items if it.get("selected"))
        os.makedirs(os.path.dirname(self.selection_file), exist_ok=True)
        DocumentTextUtils.atomic_write_text(self.selection_file, json.dumps({"ignored_paths": ignored}, ensure_ascii=False, indent=2))
        return kept_count, len(ignored)

    def find_duplicate_items(self) -> List[Dict[str, Any]]:
        """Regroupe les doublons par (extension, taille) puis SHA-256 avec cache."""
        candidates: List[Tuple[str, str]] = []
        seen_paths: Set[str] = set()
        if self.sources_dir and os.path.isdir(self.sources_dir):
            for root_dir, dir_names, file_names in os.walk(self.sources_dir):
                dir_names[:] = [d for d in sorted(dir_names) if not d.startswith(".")]
                for file_name in sorted(file_names):
                    if file_name.startswith("."):
                        continue
                    full_p: str = os.path.normpath(os.path.join(root_dir, file_name))
                    norm_p: str = os.path.normcase(full_p)
                    if norm_p not in seen_paths:
                        seen_paths.add(norm_p)
                        candidates.append((full_p, "copied"))
        linked_files, _ = LinkedSourcesManager(self.workspace_root).expand_linked_files(set())
        for linked_p in linked_files:
            norm_p = os.path.normcase(linked_p)
            if norm_p not in seen_paths:
                seen_paths.add(norm_p)
                candidates.append((linked_p, "linked"))

        by_type_and_size: Dict[Tuple[str, int], List[Tuple[str, str]]] = {}
        for full_p, origin in candidates:
            try:
                file_size: int = os.path.getsize(full_p)
            except OSError:
                continue
            if file_size <= 0:
                continue
            _, raw_ext = os.path.splitext(full_p)
            by_type_and_size.setdefault((raw_ext.lower(), file_size), []).append((full_p, origin))

        hash_cache = self._load_hash_cache()
        cache_state: Dict[str, bool] = {"dirty": False}
        ignored_saved: Set[str] = self.load_ignored_paths()
        has_saved: bool = os.path.isfile(self.selection_file)
        results: List[Dict[str, Any]] = []
        group_idx: int = 0
        for (_ext, file_size), group in sorted(by_type_and_size.items()):
            if len(group) < 2:
                continue
            by_hash: Dict[str, List[Tuple[str, str]]] = {}
            for full_p, origin in group:
                try:
                    digest: str = self._get_cached_sha256(full_p, hash_cache, cache_state)
                    by_hash.setdefault(digest, []).append((full_p, origin))
                except OSError:
                    continue
            for digest, same_items in by_hash.items():
                if len(same_items) < 2:
                    continue
                group_idx += 1
                gid: str = f"Groupe {group_idx:02d}"
                same_items.sort(key=lambda item: (0 if item[1] == "copied" else 1, item[0].lower()))
                for idx_in_grp, (fp, origin) in enumerate(same_items):
                    is_sel: bool = (os.path.normcase(fp) not in ignored_saved) if has_saved else (idx_in_grp == 0)
                    results.append({"group_id": gid, "path": fp, "filename": os.path.basename(fp), "origin": origin, "size": file_size, "size_display": self.format_size_display(file_size), "sha256": digest, "selected": is_sel})
        if cache_state["dirty"]:
            self._save_hash_cache(hash_cache)
        return results
