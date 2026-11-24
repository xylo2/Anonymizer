# Commandes pip à exécuter : Aucune dépendance externe requise

import ctypes
import json
import os
import shutil
from typing import Any, Dict, List, Set, Tuple
from doc_anonymizer.text_utils import DocumentTextUtils


class LinkedSourcesManager:
    """
    Gère les fichiers et dossiers référencés à distance (linked_sources.json)
    sans jamais modifier, renommer ni déplacer les fichiers d'origine.
    """

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root: str = os.path.abspath(workspace_root)
        self.links_file: str = os.path.join(self.workspace_root, "linked_sources.json")

    def load_links(self) -> List[Dict[str, str]]:
        """Charge la liste des chemins référencés depuis linked_sources.json."""
        if not os.path.isfile(self.links_file):
            return []
        try:
            with open(self.links_file, "r", encoding="utf-8") as f_in:
                payload = json.load(f_in)
            items = payload.get("links", []) if isinstance(payload, dict) else []
            if not isinstance(items, list):
                return []
            valid: List[Dict[str, str]] = []
            for it in items:
                if isinstance(it, dict) and str(it.get("path") or "").strip():
                    valid.append({
                        "path": os.path.normpath(str(it["path"]).strip()),
                        "kind": str(it.get("kind") or ("dir" if os.path.isdir(str(it["path"])) else "file")),
                        "storage": str(it.get("storage") or "local"),
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
    def classify_storage_location(target_path: str, reference_dir: str) -> Tuple[bool, str]:
        """
        Détermine si target_path est sur un support externe/réseau ou un autre disque.
        Retourne (needs_user_prompt, storage_label).
        """
        raw: str = target_path.strip()
        if raw.startswith(("\\\\", "//")):
            return True, "Réseau / NAS (UNC)"

        abs_target: str = os.path.abspath(raw)
        abs_ref: str = os.path.abspath(reference_dir)

        if os.name == "nt":
            drive_t: str = os.path.splitdrive(abs_target)[0].upper()
            drive_r: str = os.path.splitdrive(abs_ref)[0].upper()
            if drive_t:
                try:
                    drive_type: int = ctypes.windll.kernel32.GetDriveTypeW(f"{drive_t}\\")  # type: ignore[attr-defined]
                    if drive_type == 4:
                        return True, f"Lecteur réseau ({drive_t})"
                    if drive_type == 2:
                        return True, f"Support amovible / USB ({drive_t})"
                except Exception:
                    pass
            if drive_t and drive_r and drive_t != drive_r:
                return True, f"Disque séparé ({drive_t})"
            return False, f"Disque local ({drive_t or 'interne'})"

        norm_unix: str = abs_target.replace("\\", "/")
        if norm_unix.startswith(("/media/", "/mnt/", "/run/media/", "/Volumes/")):
            return True, "Support externe / réseau"
        return False, "Disque local"

    def add_links(self, paths_to_add: List[str], storage_label: str = "local") -> int:
        """Ajoute des fichiers ou dossiers à linked_sources.json sans doublon ni copie."""
        existing: List[Dict[str, str]] = self.load_links()
        seen: Set[str] = {os.path.normcase(os.path.abspath(it["path"])) for it in existing}
        added: int = 0
        for raw_p in paths_to_add:
            if not raw_p or not os.path.exists(raw_p):
                continue
            abs_p: str = os.path.normpath(os.path.abspath(raw_p))
            norm_k: str = os.path.normcase(abs_p)
            if norm_k in seen:
                continue
            seen.add(norm_k)
            existing.append({
                "path": abs_p,
                "kind": "dir" if os.path.isdir(abs_p) else "file",
                "storage": storage_label,
            })
            added += 1
        if added > 0:
            self.save_links(existing)
        return added

    def remove_link(self, target_path: str) -> bool:
        """Retire une référence de linked_sources.json sans jamais toucher au fichier sur disque."""
        norm_target: str = os.path.normcase(os.path.normpath(os.path.abspath(target_path)))
        existing: List[Dict[str, str]] = self.load_links()
        kept: List[Dict[str, str]] = [
            it for it in existing if os.path.normcase(os.path.abspath(it["path"])) != norm_target
        ]
        if len(kept) != len(existing):
            self.save_links(kept)
            return True
        return False
    def copy_paths_into_directory(self, paths_to_copy: List[str], dest_dir: str) -> int:
        """Copie des fichiers ou dossiers choisis dans input_documents/ (mode copie locale)."""
        os.makedirs(dest_dir, exist_ok=True)
        copied: int = 0
        for raw_p in paths_to_copy:
            if not raw_p or not os.path.exists(raw_p):
                continue
            abs_src: str = os.path.abspath(raw_p)
            base_name: str = os.path.basename(abs_src)
            dest_p: str = os.path.join(dest_dir, base_name)
            if os.path.abspath(os.path.dirname(abs_src)) == os.path.abspath(dest_dir):
                continue
            if os.path.isdir(abs_src):
                if os.path.exists(dest_p):
                    shutil.copytree(abs_src, dest_p, dirs_exist_ok=True)
                else:
                    shutil.copytree(abs_src, dest_p)
                copied += 1
            elif os.path.isfile(abs_src):
                if os.path.exists(dest_p):
                    stem, ext = os.path.splitext(base_name)
                    idx: int = 2
                    while os.path.exists(os.path.join(dest_dir, f"{stem}_{idx}{ext}")):
                        idx += 1
                    dest_p = os.path.join(dest_dir, f"{stem}_{idx}{ext}")
                shutil.copy2(abs_src, dest_p)
                copied += 1
        return copied

    def expand_linked_files(self, ignored_dirs: Set[str]) -> Tuple[List[str], List[str]]:
        """
        Parcourt toutes les références actives en lecture seule.
        Retourne (fichiers_disponibles, chemins_indisponibles).
        """
        available: List[str] = []
        missing: List[str] = []
        seen: Set[str] = set()

        for entry in self.load_links():
            root_target: str = entry["path"]
            if not os.path.exists(root_target):
                missing.append(root_target)
                continue
            if os.path.isfile(root_target):
                fn: str = os.path.basename(root_target)
                if not fn.startswith(".") and not fn.lower().startswith(("anonymise_", "anonymized_")):
                    norm_f: str = os.path.normpath(root_target)
                    if norm_f not in seen:
                        seen.add(norm_f)
                        available.append(norm_f)
            elif os.path.isdir(root_target):
                for rp, dirs, files in os.walk(root_target):
                    dirs[:] = [d for d in sorted(dirs) if d not in ignored_dirs and not d.startswith(".")]
                    for fn in sorted(files):
                        if fn.startswith(".") or fn.lower().startswith(("anonymise_", "anonymized_")):
                            continue
                        norm_f = os.path.normpath(os.path.join(rp, fn))
                        if norm_f not in seen:
                            seen.add(norm_f)
                            available.append(norm_f)
        return available, missing
