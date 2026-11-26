# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import tkinter as tk
from typing import Any, Dict, List
from doc_anonymizer.gui_duplicate_helpers import DuplicateTableActionsMixin


class GuiDuplicateTableMixin(DuplicateTableActionsMixin):
    """Tableau interactif des doublons avec chemins abrégés, actions par dossier et survol."""

    controller: Any
    current_ini_var: tk.StringVar
    status_var: tk.StringVar

    @staticmethod
    def _compute_common_parent_dir(paths: List[str]) -> str:
        parents: List[str] = [os.path.dirname(p) for p in paths if p]
        if len(parents) < 2:
            return ""
        try:
            common: str = os.path.commonpath(parents)
        except ValueError:
            return ""
        if len(common) <= 3 or common in {"\\", "/"}:
            return ""
        return common

    @staticmethod
    def _format_abbreviated_path(full_path: str, common_root: str) -> str:
        if not common_root:
            return full_path
        try:
            rel: str = os.path.relpath(full_path, common_root)
            if not rel.startswith(".."):
                return f"…{os.sep}{rel}"
        except ValueError:
            pass
        return full_path

    @staticmethod
    def _extract_discriminator_folders(paths: List[str], common_root: str) -> List[str]:
        folders: List[str] = []
        seen: set[str] = set()
        for fp in paths:
            parent_d: str = os.path.dirname(fp)
            label: str = ""
            if common_root:
                try:
                    rel_d: str = os.path.relpath(parent_d, common_root)
                    if not rel_d.startswith("..") and rel_d != ".":
                        first_seg: str = next(iter(rel_d.split(os.sep)), "")
                        if first_seg:
                            label = first_seg
                except ValueError:
                    pass
            if not label:
                label = os.path.basename(parent_d) or parent_d
            low_l: str = label.lower()
            if label and low_l not in seen:
                seen.add(low_l)
                folders.append(label)
        return folders

    def _refresh_duplicate_filter_list(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        if not getattr(self, "duplicate_filter_items", None):
            self.duplicate_filter_items: List[Dict[str, Any]] = (
                self.controller.load_duplicate_file_items(ini_path)
            )
        self._render_duplicate_filter_tree()

    def _sync_duplicate_folder_dropdown(self, folders: List[str]) -> None:
        combo = getattr(self, "combo_dup_folder", None)
        var = getattr(self, "dup_priority_folder_var", None)
        if combo is None or var is None:
            return
        options: List[str] = folders if folders else ["Aucun sous-dossier"]
        combo.configure(values=options)
        if var.get() not in options:
            var.set(next(iter(options)))

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
