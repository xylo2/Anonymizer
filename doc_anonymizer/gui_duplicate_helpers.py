# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List


class DuplicateTableActionsMixin:
    """Actions groupées par dossier, infobulle de survol et rendu des doublons."""

    duplicate_filter_tree: ttk.Treeview
    duplicate_filter_items: List[Dict[str, Any]]
    dup_priority_folder_var: tk.StringVar
    current_ini_var: tk.StringVar
    status_var: tk.StringVar
    controller: Any

    def _render_duplicate_filter_tree(self) -> None:
        if not hasattr(self, "duplicate_filter_tree"):
            return
        tree = self.duplicate_filter_tree
        for iid in tree.get_children():
            tree.delete(iid)
        tree.tag_configure("kept_even", background="#ecfdf5", foreground="#065f46")
        tree.tag_configure("kept_odd", background="#d1fae5", foreground="#064e3b")
        tree.tag_configure("ignored_even", background="#fef2f2", foreground="#991b1b")
        tree.tag_configure("ignored_odd", background="#fee2e2", foreground="#7f1d1d")

        items_list: List[Dict[str, Any]] = getattr(self, "duplicate_filter_items", [])
        all_paths: List[str] = [str(it.get("path") or "") for it in items_list]
        common_root: str = self._compute_common_parent_dir(all_paths)  # type: ignore[attr-defined]
        self._dup_common_root: str = common_root
        folders: List[str] = self._extract_discriminator_folders(all_paths, common_root)  # type: ignore[attr-defined]
        self._sync_duplicate_folder_dropdown(folders)  # type: ignore[attr-defined]

        kept_cnt: int = sum(1 for it in items_list if it.get("selected"))
        ign_cnt: int = len(items_list) - kept_cnt
        group_parity: Dict[str, int] = {}
        for idx, item in enumerate(items_list):
            gid: str = str(item.get("group_id") or "")
            if gid not in group_parity:
                group_parity[gid] = len(group_parity) % 2
            is_kept: bool = bool(item.get("selected"))
            mark: str = "✓ Garder" if is_kept else "✕ Ignorer"
            parity_suf: str = "odd" if group_parity[gid] == 1 else "even"
            row_tag: str = f"{'kept' if is_kept else 'ignored'}_{parity_suf}"
            short_p: str = self._format_abbreviated_path(str(item.get("path") or ""), common_root)  # type: ignore[attr-defined]
            tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    mark,
                    gid,
                    str(item.get("filename") or ""),
                    str(item.get("size_display") or ""),
                    short_p,
                ),
                tags=(row_tag,),
            )
        if hasattr(self, "dup_filter_summary_var"):
            root_hint: str = f" • Racine commune : {common_root}" if common_root else ""
            self.dup_filter_summary_var.set(  # type: ignore[attr-defined]
                f"{kept_cnt} fichier(s) conservé(s) (vert) • {ign_cnt} doublon(s) ignoré(s) (rouge){root_hint}"
            )

    def _item_matches_folder_tag(self, item: Dict[str, Any], folder_tag: str) -> bool:
        full_p: str = str(item.get("path") or "")
        common_root: str = getattr(self, "_dup_common_root", "")
        short_p: str = self._format_abbreviated_path(full_p, common_root)  # type: ignore[attr-defined]
        parts_low: List[str] = [p.lower() for p in short_p.split(os.sep) if p and p != "…"]
        parent_parts: List[str] = parts_low[:-1] if len(parts_low) > 1 else parts_low
        return folder_tag.lower() in parent_parts

    def _prioritize_duplicate_folder(self) -> None:
        target_folder: str = getattr(self, "dup_priority_folder_var", tk.StringVar()).get().strip()
        if not target_folder or target_folder == "Aucun sous-dossier":
            return
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for item in getattr(self, "duplicate_filter_items", []):
            groups.setdefault(str(item.get("group_id") or ""), []).append(item)
        for grp_items in groups.values():
            preferred = [it for it in grp_items if self._item_matches_folder_tag(it, target_folder)]
            chosen = next(iter(preferred), next(iter(grp_items), None))
            for it in grp_items:
                it["selected"] = it is chosen
        self._render_duplicate_filter_tree()
        self.status_var.set(f"Priorité donnée au dossier « {target_folder} ».")

    def _ignore_duplicate_folder(self) -> None:
        target_folder: str = getattr(self, "dup_priority_folder_var", tk.StringVar()).get().strip()
        if not target_folder or target_folder == "Aucun sous-dossier":
            return
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for item in getattr(self, "duplicate_filter_items", []):
            groups.setdefault(str(item.get("group_id") or ""), []).append(item)
        for grp_items in groups.values():
            for it in grp_items:
                if self._item_matches_folder_tag(it, target_folder):
                    it["selected"] = False
            if not any(it.get("selected") for it in grp_items) and grp_items:
                next(iter(grp_items))["selected"] = True
        self._render_duplicate_filter_tree()
        self.status_var.set(f"Doublons du dossier « {target_folder} » ignorés (1 copie conservée).")

    def _bind_duplicate_hover_tooltip(self) -> None:
        tree = getattr(self, "duplicate_filter_tree", None)
        if tree is None:
            return
        tip_state: Dict[str, Any] = {"win": None, "iid": ""}

        def _hide(_ev: Any = None) -> None:
            win = tip_state.get("win")
            if win is not None:
                try:
                    win.destroy()
                except tk.TclError:
                    pass
                tip_state["win"] = None
                tip_state["iid"] = ""

        def _on_motion(ev: Any) -> None:
            iid: str = tree.identify_row(ev.y)
            items_list: List[Dict[str, Any]] = getattr(self, "duplicate_filter_items", [])
            if not iid or not iid.isdigit() or int(iid) >= len(items_list):
                _hide()
                return
            if tip_state.get("iid") == iid and tip_state.get("win") is not None:
                return
            _hide()
            item = items_list[int(iid)]
            tip_txt: str = f"{item.get('filename', '')}\n{item.get('path', '')}"
            tw = tk.Toplevel(tree)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{int(ev.x_root) + 14}+{int(ev.y_root) + 12}")
            tk.Label(
                tw, text=tip_txt, bg="#0f172a", fg="#ffffff",
                font=("Segoe UI", 8), padx=10, pady=6, justify="left",
            ).pack()
            tip_state["win"] = tw
            tip_state["iid"] = iid

        tree.bind("<Motion>", _on_motion, add="+")
        tree.bind("<Leave>", _hide, add="+")
