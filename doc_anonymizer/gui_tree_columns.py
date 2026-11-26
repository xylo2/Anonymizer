# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any, Dict, List, Optional, Set, Tuple


class TreeviewColumnLayoutManager:
    """Gère l'ordre, la visibilité, l'auto-ajustement et la persistance des colonnes."""

    _MANAGERS: Dict[str, "TreeviewColumnLayoutManager"] = {}
    _HOOK_INSTALLED: bool = False

    def __init__(
        self, tree: ttk.Treeview, table_id: str, prefs_path: str
    ) -> None:
        self.tree: ttk.Treeview = tree
        self.table_id: str = table_id
        self.prefs_path: str = prefs_path
        self.all_columns: List[str] = [str(c) for c in tree["columns"]]
        self.default_meta: Dict[str, Tuple[str, int, str]] = {}
        for cid in self.all_columns:
            lbl: str = str(tree.heading(cid, "text") or cid)
            w: int = int(tree.column(cid, "width") or 120)
            anc: str = str(tree.column(cid, "anchor") or "w")
            self.default_meta[cid] = (lbl, w, anc)
        self._locked_widths: Set[str] = set()
        self._drag_col: Optional[str] = None
        self._drag_start_x: int = 0
        self._dragging: bool = False

    def _read_prefs(self) -> Dict[str, Any]:
        if not self.prefs_path or not os.path.isfile(self.prefs_path):
            return {}
        try:
            with open(self.prefs_path, "r", encoding="utf-8") as f_in:
                data = json.load(f_in)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_prefs(self, payload: Dict[str, Any]) -> None:
        if not self.prefs_path:
            return
        try:
            parent_d: str = os.path.dirname(os.path.abspath(self.prefs_path))
            if parent_d:
                os.makedirs(parent_d, exist_ok=True)
            with open(self.prefs_path, "w", encoding="utf-8") as f_out:
                json.dump(payload, f_out, ensure_ascii=False, indent=2)
        except OSError:
            pass
    def get_visible_columns(self) -> List[str]:
        raw = self.tree.cget("displaycolumns")
        if not raw or tuple(raw) == ("#all",):
            return list(self.all_columns)
        return [str(c) for c in raw if str(c) in self.all_columns]

    def _sync_column_stretch(self) -> None:
        """Conserve la largeur des colonnes ajustées et laisse la page globale défiler."""
        visible: List[str] = self.get_visible_columns()
        total_w: int = sum(int(self.tree.column(c, "width") or 100) for c in visible)
        view_w: int = self.tree.winfo_width()
        allow_stretch: bool = view_w > 40 and total_w <= view_w
        for cid in visible:
            self.tree.column(
                cid, stretch=(allow_stretch and cid not in self._locked_widths)
            )

    def save_layout(self) -> None:
        self._sync_column_stretch()
        visible: List[str] = self.get_visible_columns()
        widths: Dict[str, int] = {
            cid: int(self.tree.column(cid, "width") or 100)
            for cid in self.all_columns
        }
        prefs: Dict[str, Any] = self._read_prefs()
        layouts = prefs.setdefault("tree_layouts", {})
        if isinstance(layouts, dict):
            layouts[self.table_id] = {
                "visible": visible,
                "widths": widths,
                "locked": sorted(self._locked_widths),
            }
            self._write_prefs(prefs)

    def apply_saved_layout(self) -> None:
        prefs: Dict[str, Any] = self._read_prefs()
        layouts = prefs.get("tree_layouts")
        entry = layouts.get(self.table_id) if isinstance(layouts, dict) else None
        if isinstance(entry, dict):
            raw_vis = entry.get("visible")
            if isinstance(raw_vis, list):
                valid_vis: List[str] = [
                    str(c) for c in raw_vis if str(c) in self.all_columns
                ]
                if valid_vis:
                    self.tree["displaycolumns"] = tuple(valid_vis)
            raw_locked = entry.get("locked")
            if isinstance(raw_locked, list):
                self._locked_widths = {
                    str(c) for c in raw_locked if str(c) in self.all_columns
                }
            raw_w = entry.get("widths")
            if isinstance(raw_w, dict):
                for cid, w_val in raw_w.items():
                    if cid in self.all_columns and isinstance(w_val, int) and w_val >= 35:
                        def_w: int = self.default_meta[cid][1]
                        if w_val != def_w:
                            self._locked_widths.add(cid)
                        self.tree.column(
                            cid, width=w_val, stretch=(cid not in self._locked_widths)
                        )
        self._sync_column_stretch()
    def auto_fit_column(self, col_id: str) -> int:
        if col_id not in self.all_columns:
            return 0
        col_idx: int = self.all_columns.index(col_id)
        try:
            body_f = tkfont.nametofont("TkDefaultFont")
        except tk.TclError:
            body_f = None
        hdr_txt: str = str(self.tree.heading(col_id, "text") or col_id)
        max_px: int = (body_f.measure(hdr_txt) + 34) if body_f else (len(hdr_txt) * 8 + 34)
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            if isinstance(vals, (list, tuple)) and col_idx < len(vals):
                cell_txt: str = str(vals[col_idx] or "")
                px: int = (body_f.measure(cell_txt) + 28) if body_f else (len(cell_txt) * 8 + 28)
                if px > max_px:
                    max_px = px
        fitted_w: int = max(55, min(1200, max_px))
        self._locked_widths.add(col_id)
        self.tree.column(col_id, width=fitted_w, stretch=False)
        self.save_layout()
        return fitted_w

    def toggle_column_visibility(self, col_id: str) -> None:
        visible: List[str] = self.get_visible_columns()
        if col_id in visible:
            if len(visible) <= 1:
                return
            visible = [c for c in visible if c != col_id]
        else:
            idx: int = self.all_columns.index(col_id)
            inserted: bool = False
            new_vis: List[str] = []
            for cur in visible:
                if not inserted and self.all_columns.index(cur) > idx:
                    new_vis.append(col_id)
                    inserted = True
                new_vis.append(cur)
            if not inserted:
                new_vis.append(col_id)
            visible = new_vis
        self.tree["displaycolumns"] = tuple(visible)
        self.save_layout()

    def move_column_to_x(self, col_id: str, target_x: int) -> None:
        visible: List[str] = self.get_visible_columns()
        if col_id not in visible or len(visible) < 2:
            return
        acc_x: int = 0
        target_idx: int = len(visible) - 1
        for idx, cid in enumerate(visible):
            col_w: int = int(self.tree.column(cid, "width") or 100)
            if target_x < acc_x + (col_w // 2):
                target_idx = idx
                break
            acc_x += col_w
        reordered: List[str] = [c for c in visible if c != col_id]
        reordered.insert(min(target_idx, len(reordered)), col_id)
        if reordered != visible:
            self.tree["displaycolumns"] = tuple(reordered)
            self.save_layout()
    def reset_to_default(self) -> None:
        self._locked_widths.clear()
        self.tree["displaycolumns"] = tuple(self.all_columns)
        for cid, (_, def_w, _) in self.default_meta.items():
            self.tree.column(cid, width=def_w, stretch=True)
        self._sync_column_stretch()
        prefs: Dict[str, Any] = self._read_prefs()
        layouts = prefs.get("tree_layouts")
        if isinstance(layouts, dict) and self.table_id in layouts:
            del layouts[self.table_id]
            self._write_prefs(prefs)

    def _col_at_x(self, x_pos: int) -> Optional[str]:
        ident: str = self.tree.identify_column(x_pos)
        if not ident.startswith("#") or not ident[1:].isdigit():
            return None
        vis_idx: int = int(ident[1:]) - 1
        visible: List[str] = self.get_visible_columns()
        return visible[vis_idx] if 0 <= vis_idx < len(visible) else None

    def open_columns_menu(self, x_root: int, y_root: int) -> None:
        menu = tk.Menu(self.tree, tearoff=0)
        visible: List[str] = self.get_visible_columns()
        for cid in self.all_columns:
            lbl, _, _ = self.default_meta[cid]
            var = tk.BooleanVar(value=(cid in visible))
            state: str = "disabled" if (cid in visible and len(visible) <= 1) else "normal"
            menu.add_checkbutton(
                label=lbl.strip(" ▲▼"), variable=var, state=state,
                command=lambda c=cid: self.toggle_column_visibility(c),
            )
        menu.add_separator()
        menu.add_command(
            label="Ajuster toutes les colonnes au contenu",
            command=lambda: [self.auto_fit_column(c) for c in self.get_visible_columns()],
        )
        menu.add_command(
            label="Réinitialiser l'affichage par défaut",
            command=self.reset_to_default,
        )
        menu.tk_popup(x_root, y_root)

    def bind_events(self) -> None:
        def _on_press(ev: Any) -> None:
            if self.tree.identify_region(ev.x, ev.y) == "heading":
                self._drag_col = self._col_at_x(ev.x)
                self._drag_start_x = int(ev.x)
                self._dragging = False

        def _on_motion(ev: Any) -> None:
            if self._drag_col and abs(int(ev.x) - self._drag_start_x) >= 10:
                self._dragging = True
                self.tree.configure(cursor="sb_h_double_arrow")
        def _on_release(ev: Any) -> str | None:
            self.tree.configure(cursor="")
            if self._drag_col and self._dragging:
                moved: str = self._drag_col
                self._drag_col = None
                self._dragging = False
                self.move_column_to_x(moved, int(ev.x))
                return "break"
            self._drag_col = None
            self._dragging = False
            if self.tree.identify_region(ev.x, ev.y) == "separator":
                sep_col = self._col_at_x(max(1, int(ev.x) - 4))
                if sep_col:
                    self._locked_widths.add(sep_col)
                self.tree.after(50, self.save_layout)
            return None

        def _on_double_click(ev: Any) -> str | None:
            region: str = self.tree.identify_region(ev.x, ev.y)
            if region in {"heading", "separator"}:
                x_probe: int = max(1, int(ev.x) - 4) if region == "separator" else int(ev.x)
                col_id: Optional[str] = self._col_at_x(x_probe)
                if col_id:
                    self.auto_fit_column(col_id)
                    return "break"
            return None

        def _on_right_click(ev: Any) -> None:
            if self.tree.identify_region(ev.x, ev.y) == "heading":
                self.open_columns_menu(int(ev.x_root), int(ev.y_root))

        self.tree.bind("<ButtonPress-1>", _on_press, add="+")
        self.tree.bind("<B1-Motion>", _on_motion, add="+")
        self.tree.bind("<ButtonRelease-1>", _on_release, add="+")
        self.tree.bind("<Double-Button-1>", _on_double_click, add="+")
        self.tree.bind("<Button-3>", _on_right_click, add="+")
        self.tree.bind("<Configure>", lambda _e: self._sync_column_stretch(), add="+")

    @classmethod
    def attach_to_tree(cls, tree: ttk.Treeview) -> "TreeviewColumnLayoutManager":
        from doc_anonymizer.gui_tree_toolbar import inject_tree_column_toolbar

        existing = getattr(tree, "_col_layout_mgr", None)
        if isinstance(existing, cls):
            return existing
        cols: List[str] = [str(c) for c in tree["columns"]]
        table_id: str = "_".join(cols)
        top = tree.winfo_toplevel()
        prefs_p: str = str(getattr(top, "_ui_prefs_file", "") or "")
        mgr = cls(tree, table_id, prefs_p)
        mgr.apply_saved_layout()
        mgr.bind_events()
        setattr(tree, "_col_layout_mgr", mgr)
        cls._MANAGERS[str(tree)] = mgr
        inject_tree_column_toolbar(tree, mgr)
        return mgr

    @classmethod
    def install_global_hook(cls) -> None:
        if cls._HOOK_INSTALLED:
            return
        root = getattr(tk, "_default_root", None)
        if root is None:
            return
        cls._HOOK_INSTALLED = True

        def _on_tree_map(ev: Any) -> None:
            w = getattr(ev, "widget", None)
            if isinstance(w, ttk.Treeview) and str(w.cget("style")) == "Modern.Treeview":
                cls.attach_to_tree(w)

        root.bind_class("Treeview", "<Map>", _on_tree_map, add="+")
