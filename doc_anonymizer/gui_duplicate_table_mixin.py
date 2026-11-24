# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import tkinter as tk
from typing import Any, Dict, List


class GuiDuplicateTableMixin:
    """Tableau interactif permettant de choisir quel exemplaire conserver parmi les doublons."""

    controller: Any
    current_ini_var: tk.StringVar
    status_var: tk.StringVar

    def _refresh_duplicate_filter_list(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        if not getattr(self, "duplicate_filter_items", None):
            self.duplicate_filter_items: List[Dict[str, Any]] = (
                self.controller.load_duplicate_file_items(ini_path)
            )
        self._render_duplicate_filter_tree()

    def _render_duplicate_filter_tree(self) -> None:
        if not hasattr(self, "duplicate_filter_tree"):
            return
        for iid in self.duplicate_filter_tree.get_children():  # type: ignore[attr-defined]
            self.duplicate_filter_tree.delete(iid)  # type: ignore[attr-defined]
        self.duplicate_filter_tree.tag_configure("kept", background="#ecfdf5", foreground="#065f46")  # type: ignore[attr-defined]
        self.duplicate_filter_tree.tag_configure("ignored", background="#fef2f2", foreground="#991b1b")  # type: ignore[attr-defined]

        items_list: List[Dict[str, Any]] = getattr(self, "duplicate_filter_items", [])
        kept_cnt: int = sum(1 for it in items_list if it.get("selected"))
        ign_cnt: int = len(items_list) - kept_cnt
        for idx, item in enumerate(items_list):
            is_kept: bool = bool(item.get("selected"))
            mark: str = "✓ Garder" if is_kept else "✕ Ignorer"
            row_tag: str = "kept" if is_kept else "ignored"
            self.duplicate_filter_tree.insert(  # type: ignore[attr-defined]
                "",
                "end",
                iid=str(idx),
                values=(
                    mark,
                    str(item.get("group_id") or ""),
                    str(item.get("filename") or ""),
                    str(item.get("size_display") or ""),
                    str(item.get("path") or ""),
                ),
                tags=(row_tag,),
            )
        if hasattr(self, "dup_filter_summary_var"):
            self.dup_filter_summary_var.set(  # type: ignore[attr-defined]
                f"{kept_cnt} fichier(s) conservé(s) (vert) • {ign_cnt} doublon(s) ignoré(s) (rouge) — "
                f"Les fichiers originaux ne sont jamais supprimés."
            )
    def _toggle_duplicate_row_by_id(self, row_id: str) -> None:
        items_list: List[Dict[str, Any]] = getattr(self, "duplicate_filter_items", [])
        if row_id and row_id.isdigit():
            idx: int = int(row_id)
            if 0 <= idx < len(items_list):
                items_list[idx]["selected"] = not bool(items_list[idx].get("selected"))
                self._render_duplicate_filter_tree()
                self.duplicate_filter_tree.selection_remove(  # type: ignore[attr-defined]
                    self.duplicate_filter_tree.selection()  # type: ignore[attr-defined]
                )

    def _toggle_selected_duplicate_filter(self, _event: object = None) -> None:
        sel = self.duplicate_filter_tree.selection()  # type: ignore[attr-defined]
        if sel:
            self._toggle_duplicate_row_by_id(next(iter(sel)))

    def _reset_default_duplicates_selection(self) -> None:
        seen_groups: set[str] = set()
        for item in getattr(self, "duplicate_filter_items", []):
            gid: str = str(item.get("group_id") or "")
            if gid not in seen_groups:
                seen_groups.add(gid)
                item["selected"] = True
            else:
                item["selected"] = False
        self._render_duplicate_filter_tree()

    def _save_duplicates_and_continue(self) -> None:
        ini_path: str = self.current_ini_var.get()
        items_list: List[Dict[str, Any]] = getattr(self, "duplicate_filter_items", [])
        if ini_path:
            kept, ignored = self.controller.save_duplicate_file_selection(ini_path, items_list)
            self.status_var.set(f"Doublons enregistrés : {kept} conservé(s), {ignored} ignoré(s).")
        self._show_page("setup")  # type: ignore[attr-defined]
