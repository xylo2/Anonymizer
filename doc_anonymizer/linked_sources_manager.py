# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Utilisateur_A

import ctypes
import json
import os
import shutil
from typing import Any, Dict, List, Set, Tuple
from doc_anonymizer.text_utils import DocumentTextUtils


class LinkedSourcesManager:
    """Gère les fichiers et dossiers référencés (linked_sources.json)."""

    def __init__(self, workspace_root: str) -> None:
        """Initialise le gestionnaire avec le dossier du workspace."""
        self.workspace_root: str = os.path.abspath(workspace_root)
        self.links_file: str = os.path.join(
            self.workspace_root, "linked_sources.json"
        )

    def load_links(self) -> List[Dict[str, str]]:
        """Charge les chemins référencés depuis linked_sources.json."""
        if not os.path.isfile(self.links_file):
            return []
        try:
            with open(self.links_file, "r", encoding="utf-8") as f_in:
                payload = json.load(f_in)
            items = payload.get("links", []) if isinstance(payload, dict) else []
            if not isinstance(items, list):
                return []
            valid: List[Dict[str, str]] = []
            for item in items:
                if isinstance(item, dict) and str(item.get("path") or "").strip():
                    raw_path: str = str(item["path"]).strip()
                    valid.append({
                        "path": os.path.normpath(raw_path),
                        "kind": str(
                            item.get("kind")
                            or ("dir" if os.path.isdir(raw_path) else "file")
                        ),
                        "storage": str(item.get("storage") or "Local"),
                    })
            return valid
        except (OSError, json.JSONDecodeError):
            return []

    def save_links(self, links: List[Dict[str, str]]) -> None:
        """Sauvegarde atomiquement linked_sources.json."""
        os.makedirs(self.workspace_root, exist_ok=True)
        payload: Dict[str, Any] = {
            "total_links": len(links),
            "links": links,
        }
        DocumentTextUtils.atomic_write_text(
            self.links_file,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )

    @staticmethod
    def _is_same_or_child(candidate_norm: str, parent_dir_norm: str) -> bool:
        """Indique si candidate_norm est identique ou inclus dans parent_dir_norm."""
        if candidate_norm == parent_dir_norm:
            return True
        prefix: str = parent_dir_norm.rstrip(chr(92) + "/") + os.sep
        return candidate_norm.startswith(prefix)
    def add_links(self, paths_to_add: List[str], storage_label: str = "Local") -> int:
        """Ajoute des références en fusionnant enfants et dossiers parents."""
        existing: List[Dict[str, str]] = self.load_links()
        changed: bool = False
        added: int = 0
        ordered_paths: List[str] = sorted(
            [p for p in paths_to_add if p and os.path.exists(p)],
            key=lambda p: (0 if os.path.isdir(p) else 1, len(os.path.abspath(p))),
        )
        for raw_path in ordered_paths:
            abs_path: str = os.path.normpath(os.path.abspath(raw_path))
            norm_key: str = os.path.normcase(abs_path)
            is_dir: bool = os.path.isdir(abs_path)
            covered: bool = any(
                item.get("kind") == "dir"
                and self._is_same_or_child(
                    norm_key, os.path.normcase(os.path.abspath(item["path"]))
                )
                for item in existing
            )
            if covered:
                continue
            if is_dir:
                before_len: int = len(existing)
                existing = [
                    item for item in existing
                    if not self._is_same_or_child(
                        os.path.normcase(os.path.abspath(item["path"])), norm_key
                    )
                ]
                if len(existing) != before_len:
                    changed = True
            existing.append({
                "path": abs_path,
                "kind": "dir" if is_dir else "file",
                "storage": storage_label,
            })
            added += 1
            changed = True
        if changed:
            self.save_links(existing)
        return added

    def remove_link(self, target_path: str) -> bool:
        """Retire une référence du fichier linked_sources.json sans toucher au disque."""
        norm_target: str = os.path.normcase(os.path.normpath(os.path.abspath(target_path)))
        existing: List[Dict[str, str]] = self.load_links()
        kept: List[Dict[str, str]] = [
            item for item in existing
            if os.path.normcase(os.path.abspath(item["path"])) != norm_target
        ]
        if len(kept) == len(existing):
            return False
        self.save_links(kept)
        return True

    def expand_linked_files(
        self, ignored_dirs: Set[str]
    ) -> Tuple[List[str], List[str]]:
        """Résout tous les fichiers valides et liste les emplacements absents."""
        files: List[str] = []
        missing: List[str] = []
        seen: Set[str] = set()
        for item in self.load_links():
            path_val: str = item.get("path", "")
            if not path_val:
                continue
            if not os.path.exists(path_val):
                missing.append(path_val)
                continue
            if os.path.isfile(path_val):
                norm_f: str = os.path.normcase(os.path.abspath(path_val))
                if norm_f not in seen:
                    seen.add(norm_f)
                    files.append(os.path.normpath(os.path.abspath(path_val)))
            elif os.path.isdir(path_val):
                for root_dir, dir_names, file_names in os.walk(path_val):
                    dir_names[:] = [
                        d for d in dir_names
                        if d not in ignored_dirs and not d.startswith(".")
                    ]
                    for file_name in sorted(file_names):
                        if file_name.startswith("."):
                            continue
                        full_f: str = os.path.normpath(
                            os.path.abspath(os.path.join(root_dir, file_name))
                        )
                        norm_f = os.path.normcase(full_f)
                        if norm_f not in seen:
                            seen.add(norm_f)
                            files.append(full_f)
        return sorted(files), missing
    @staticmethod
    def classify_storage_location(
        target_path: str, workspace_root: str = ""
    ) -> Tuple[bool, str]:
        """Indique si target_path est sur support externe/réseau et son libellé."""
        raw_str: str = str(target_path or "").strip()
        if raw_str.startswith("\\\\") or raw_str.startswith("//"):
            parts: List[str] = [p for p in raw_str.lstrip("\\/").split("\\") if p]
            if len(parts) <= 1 and "/" in raw_str.lstrip("/"):
                parts = [p for p in raw_str.lstrip("/").split("/") if p]
            host: str = next(iter(parts), "partage")
            return True, f"Réseau ({host})"
        abs_p: str = os.path.abspath(target_path)
        if os.name == "nt":
            drive, _ = os.path.splitdrive(abs_p)
            if drive:
                try:
                    drive_type: int = ctypes.windll.kernel32.GetDriveTypeW(
                        drive + "\\"
                    )
                    if drive_type == 4:
                        return True, f"Lecteur réseau ({drive})"
                    if drive_type in (2, 5):
                        return True, f"Support externe ({drive})"
                except Exception:
                    pass
        if workspace_root:
            ws_drive, _ = os.path.splitdrive(os.path.abspath(workspace_root))
            tg_drive, _ = os.path.splitdrive(abs_p)
            if ws_drive and tg_drive and ws_drive.lower() != tg_drive.lower():
                return True, f"Disque ({tg_drive})"
        return False, "Local"

    @staticmethod
    def copy_paths_into_directory(
        source_paths: List[str], dest_dir: str
    ) -> int:
        """Copie fichiers et dossiers sélectionnés vers le répertoire cible."""
        os.makedirs(dest_dir, exist_ok=True)
        copied: int = 0
        for raw_p in source_paths:
            if not raw_p or not os.path.exists(raw_p):
                continue
            src: str = os.path.abspath(raw_p)
            base_name: str = os.path.basename(src)
            target: str = os.path.join(dest_dir, base_name)
            try:
                if os.path.abspath(target) == src:
                    continue
                if os.path.isdir(src):
                    shutil.copytree(src, target, dirs_exist_ok=True)
                    copied += 1
                elif os.path.isfile(src):
                    shutil.copy2(src, target)
                    copied += 1
            except OSError:
                continue
        return copied
