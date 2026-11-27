import hashlib
import json
import os
from typing import Any, Dict, List, Set, Tuple
from doc_anonymizer.linked_sources_manager import LinkedSourcesManager
from doc_anonymizer.text_utils import DocumentTextUtils


class DuplicateFilesManager:
    """Détecte les fichiers binaires strictement identiques avec cache."""

    IGNORED_SYS_DIRS: Set[str] = {
        "extracted_texts", "anonymized_results", "output_contacts",
        "audits", "pack_avocat", "retour_ia_brut", "retour_ia_nominatif",
        "data", "docs", "venv", ".venv", ".git", "__pycache__",
        "common", "tools", "tests",
        "sms_exports", "chat_exports", "input_contacts",
    }

    def __init__(self, paths: Dict[str, str]) -> None:
        self.paths: Dict[str, str] = paths
        ws_root: str = (
            paths.get("workspace_root")
            or os.path.dirname(paths["sources_dir"])
        )
        self.ws_root: str = os.path.abspath(ws_root)
        audits_dir: str = os.path.join(self.ws_root, "audits")
        self.selection_file: str = os.path.join(
            audits_dir, "ignored_duplicates.json"
        )
        self.cache_file: str = os.path.join(
            audits_dir, ".duplicates_hash_cache.json"
        )

    @staticmethod
    def _fingerprint(
        file_path: str, file_size: int, full: bool = False
    ) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f_bin:
            if full or file_size <= 131072:
                while True:
                    chunk: bytes = f_bin.read(1048576)
                    if not chunk:
                        break
                    h.update(chunk)
            else:
                h.update(f_bin.read(65536))
                f_bin.seek(max(0, file_size - 65536))
                h.update(f_bin.read(65536))
        return h.hexdigest()

    @staticmethod
    def format_size(num_bytes: int) -> str:
        if num_bytes < 1024:
            return f"{num_bytes} o"
        if num_bytes < 1048576:
            return f"{num_bytes / 1024.0:.1f} Ko"
        return f"{num_bytes / 1048576.0:.2f} Mo"
    def _collect_all_candidate_files(self) -> List[str]:
        candidates: List[str] = []
        seen: Set[str] = set()
        src_dir: str = self.paths["sources_dir"]
        if os.path.isdir(src_dir):
            for rp, dirs, files in os.walk(src_dir):
                dirs[:] = [
                    d for d in sorted(dirs)
                    if d not in self.IGNORED_SYS_DIRS and not d.startswith(".")
                ]
                for fn in sorted(files):
                    low: str = fn.lower()
                    if fn.startswith(".") or low.startswith(
                        ("anonymise_", "anonymized_")
                    ):
                        continue
                    fp: str = os.path.normpath(os.path.join(rp, fn))
                    if fp not in seen:
                        seen.add(fp)
                        candidates.append(fp)
        linked, _ = LinkedSourcesManager(self.ws_root).expand_linked_files(
            self.IGNORED_SYS_DIRS
        )
        for fp in linked:
            if fp not in seen:
                seen.add(fp)
                candidates.append(fp)
        return candidates

    def _load_hash_cache(self) -> Dict[str, List[Any]]:
        if not os.path.isfile(self.cache_file):
            return {}
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f_in:
                data = json.load(f_in)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_hash_cache(self, cache: Dict[str, List[Any]]) -> None:
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            DocumentTextUtils.atomic_write_text(
                self.cache_file,
                json.dumps(cache, ensure_ascii=False),
            )
        except OSError:
            pass

    def load_ignored_paths(self) -> Set[str]:
        if not os.path.isfile(self.selection_file):
            return set()
        try:
            with open(self.selection_file, "r", encoding="utf-8") as f_in:
                payload = json.load(f_in)
            raw = payload.get("ignored_paths", []) if isinstance(payload, dict) else []
            return {
                os.path.normcase(os.path.normpath(str(p)))
                for p in raw if str(p).strip()
            }
        except (OSError, json.JSONDecodeError):
            return set()

    def save_selection(self, items: List[Dict[str, Any]]) -> Tuple[int, int]:
        ignored: List[str] = [
            os.path.normpath(str(it["path"]))
            for it in items
            if not it.get("selected") and str(it.get("path") or "").strip()
        ]
        os.makedirs(os.path.dirname(self.selection_file), exist_ok=True)
        DocumentTextUtils.atomic_write_text(
            self.selection_file,
            json.dumps({"ignored_paths": ignored}, ensure_ascii=False, indent=2),
        )
        kept_cnt: int = sum(1 for it in items if it.get("selected"))
        return kept_cnt, len(ignored)

    def _get_cached_hash(
        self, fp: str, sz: int, mtime_ns: int, full: bool,
        cache: Dict[str, List[Any]], dirty: List[bool],
    ) -> str:
        k: str = f"{'F' if full else 'Q'}:{os.path.normcase(fp)}"
        rec = cache.get(k)
        if isinstance(rec, list) and len(rec) == 3:
            c_sz, c_mt, c_dig = rec
            if c_sz == sz and c_mt == mtime_ns:
                return str(c_dig)
        digest: str = self._fingerprint(fp, sz, full=full)
        cache[k] = [sz, mtime_ns, digest]
        dirty.append(True)
        return digest

    def find_duplicate_items(self) -> List[Dict[str, Any]]:
        """Retourne les fichiers appartenant à un groupe de doublons binaires stricts."""
        by_size: Dict[int, List[Tuple[str, int]]] = {}
        for fp in self._collect_all_candidate_files():
            try:
                st = os.stat(fp)
                by_size.setdefault(int(st.st_size), []).append((fp, int(st.st_mtime_ns)))
            except OSError:
                continue

        cache = self._load_hash_cache()
        dirty: List[bool] = []
        has_saved: bool = os.path.isfile(self.selection_file)
        saved_ignored: Set[str] = self.load_ignored_paths()
        items: List[Dict[str, Any]] = []
        group_num: int = 0

        for sz, group in sorted(by_size.items(), key=lambda kv: -next(iter(kv))):
            if len(group) < 2:
                continue
            q_cache: Dict[str, Tuple[str, int]] = {}
            q_counts: Dict[str, int] = {}
            for fp, mt in group:
                try:
                    qh = self._get_cached_hash(fp, sz, mt, False, cache, dirty)
                    q_cache[fp] = (qh, mt)
                    q_counts[qh] = q_counts.get(qh, 0) + 1
                except OSError:
                    continue
            by_full: Dict[str, List[str]] = {}
            for fp, (qh, mt) in q_cache.items():
                if q_counts.get(qh, 0) < 2:
                    continue
                try:
                    fh = self._get_cached_hash(fp, sz, mt, True, cache, dirty)
                    by_full.setdefault(fh, []).append(fp)
                except OSError:
                    continue
            for dup_paths in by_full.values():
                if len(dup_paths) < 2:
                    continue
                group_num += 1
                for idx, fp in enumerate(dup_paths):
                    norm_k = os.path.normcase(os.path.normpath(fp))
                    sel = (norm_k not in saved_ignored) if has_saved else (idx == 0)
                    items.append({
                        "group_id": f"Doublon #{group_num}",
                        "filename": os.path.basename(fp),
                        "path": fp,
                        "size_bytes": sz,
                        "size_display": self.format_size(sz),
                        "selected": sel,
                    })
        if dirty:
            self._save_hash_cache(cache)
        return items
