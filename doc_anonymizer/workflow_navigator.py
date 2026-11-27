# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Utilisateur_A

import os
import threading
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from doc_anonymizer.duplicate_files_manager import DuplicateFilesManager
from doc_anonymizer.linked_sources_manager import LinkedSourcesManager


class WorkflowNavigator:
    """Pilote le pré-scan asynchrone non bloquant et les étapes actives."""

    def __init__(
        self,
        workspace_root: str,
        docs_dir: str,
        ignored_dirs: Optional[Set[str]] = None,
    ) -> None:
        """Initialise l'état de cache et les gestionnaires de sources."""
        self.workspace_root: str = os.path.abspath(workspace_root)
        self.docs_dir: str = os.path.abspath(docs_dir)
        self.ignored_dirs: Set[str] = set(ignored_dirs or set())
        self.links_mgr: LinkedSourcesManager = LinkedSourcesManager(self.workspace_root)
        self._lock: threading.Lock = threading.Lock()
        self._scanning: bool = False
        self._cached_sig: Optional[Tuple[Any, ...]] = None
        self._cached_duplicates: List[Dict[str, Any]] = []
        self._cached_files: List[str] = []
    def compute_sources_signature(self) -> Tuple[Any, ...]:
        """Calcule une empreinte légère de l'état des liens et documents."""
        links_mtime: float = 0.0
        if os.path.isfile(self.links_mgr.links_file):
            try:
                links_mtime = os.path.getmtime(self.links_mgr.links_file)
            except OSError:
                links_mtime = 0.0
        docs_entries: List[Tuple[str, int, float]] = []
        if os.path.isdir(self.docs_dir):
            for root_dir, dir_names, file_names in os.walk(self.docs_dir):
                dir_names[:] = [
                    d for d in dir_names
                    if d not in self.ignored_dirs and not d.startswith(".")
                ]
                for fname in sorted(file_names):
                    full_p: str = os.path.join(root_dir, fname)
                    try:
                        st = os.stat(full_p)
                        docs_entries.append((full_p, st.st_size, st.st_mtime))
                    except OSError:
                        continue
        return (links_mtime, tuple(docs_entries))

    def has_any_source(self) -> bool:
        """Indique immédiatement s'il existe au moins une source valide."""
        if self.links_mgr.load_links():
            return True
        if os.path.isdir(self.docs_dir):
            for _root, dir_names, file_names in os.walk(self.docs_dir):
                dir_names[:] = [
                    d for d in dir_names
                    if d not in self.ignored_dirs and not d.startswith(".")
                ]
                if file_names:
                    return True
        return False
    def trigger_background_scan(
        self, on_complete: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> bool:
        """Lance l'analyse des fichiers et doublons en arrière-plan."""
        current_sig: Tuple[Any, ...] = self.compute_sources_signature()
        with self._lock:
            if self._scanning:
                return False
            if self._cached_sig == current_sig:
                if on_complete is not None:
                    on_complete(self.get_cached_summary())
                return False
            self._scanning = True

        def _worker() -> None:
            """Exécute la résolution des fichiers et doublons."""
            try:
                expanded, _ = self.links_mgr.expand_linked_files(self.ignored_dirs)
                dup_mgr = DuplicateFilesManager(
                    {"workspace_root": self.workspace_root, "sources_dir": self.docs_dir}
                )
                dups: List[Dict[str, Any]] = dup_mgr.find_duplicate_items()
                with self._lock:
                    self._cached_files = expanded
                    self._cached_duplicates = dups
                    self._cached_sig = current_sig
            finally:
                with self._lock:
                    self._scanning = False
                if on_complete is not None:
                    on_complete(self.get_cached_summary())

        threading.Thread(target=_worker, daemon=True).start()
        return True

    def get_cached_summary(self) -> Dict[str, Any]:
        """Retourne l'état courant du cache et les étapes actives."""
        with self._lock:
            dup_count: int = len(self._cached_duplicates)
            scanning: bool = self._scanning
            files_count: int = len(self._cached_files)
            dups_copy: List[Dict[str, Any]] = list(self._cached_duplicates)
        steps: List[str] = ["documents"]
        if dup_count > 0:
            steps.append("duplicates")
        steps.extend(["filters_hub", "preview_export"])
        return {
            "scanning": scanning,
            "files_count": files_count,
            "duplicates_count": dup_count,
            "duplicates": dups_copy,
            "active_steps": steps,
        }
