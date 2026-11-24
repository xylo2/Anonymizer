# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import tkinter as tk
from typing import Any, Dict, List, Tuple


class GuiChatTableMixin:
    """Tableau filtrable, paginé et triable des conversations de messageries."""

    controller: Any
    current_ini_var: tk.StringVar
    status_var: tk.StringVar

    def _refresh_chat_filter_list(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        chat_files = self.controller.list_chat_export_files(ini_path)
        self.chat_files_summary_var.set(  # type: ignore[attr-defined]
            f"Exports de messageries détectés ({len(chat_files)}) : "
            f"{', '.join(os.path.basename(p) for p in chat_files[:5])}"
            if chat_files
            else "Exports de messageries détectés : aucun."
        )
        self.chat_page_index: int = 0
        self.chat_filter_items = (
            self.controller.load_chat_conversation_filter_items(ini_path)
        )
        self._render_chat_filter_tree()

    def _persist_chat_filter_now(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if ini_path and hasattr(self, "chat_filter_items"):
            kept: int = (
                self.controller.save_chat_conversation_filter_selection(
                    ini_path, self.chat_filter_items
                )
            )
            self.status_var.set(
                f"Conversations enregistrées : {kept} conservée(s)."
            )

    def _on_chat_view_changed(self) -> None:
        self.chat_page_index = 0
        self._render_chat_filter_tree()

    def _change_chat_page(self, delta: int) -> None:
        self.chat_page_index = max(
            0, getattr(self, "chat_page_index", 0) + delta
        )
        self._render_chat_filter_tree()

    def _on_chat_search_typed(self, _event: object = None) -> None:
        if hasattr(self, "ent_chat_search"):
            self.chat_filter_search_var.set(self.ent_chat_search.get())  # type: ignore[attr-defined]
        self.chat_page_index = 0
        self._render_chat_filter_tree()

    def _sort_chats_by_column(self, col_id: str) -> None:
        if getattr(self, "chat_sort_col", "count") == col_id:
            self.chat_sort_reverse = not getattr(
                self, "chat_sort_reverse", True
            )
        else:
            self.chat_sort_col = col_id
            self.chat_sort_reverse = col_id == "count"
        self.chat_page_index = 0
        self._render_chat_filter_tree()

    def _chat_sort_key(self, item: Dict[str, Any]) -> Tuple[Any, ...]:
        plat_low: str = str(item.get("platform") or "").lower()
        conv_low: str = str(item.get("conversation") or "").lower()
        part_raw: str = str(
            item.get("participants_display")
            or ", ".join(item.get("participants", []))
        )
        part_low: str = part_raw.lower()
        cnt: int = int(item.get("count", 0))
        sort_c: str = getattr(self, "chat_sort_col", "count")
        if sort_c == "keep":
            return (0 if item.get("selected") else 1, -cnt, conv_low)
        if sort_c == "platform":
            return (plat_low, conv_low, -cnt)
        if sort_c == "conversation":
            return (conv_low, part_low, -cnt)
        if sort_c == "participants":
            return (part_low, conv_low, -cnt)
        return (cnt, conv_low)
    def _render_chat_filter_tree(self) -> None:
        if not hasattr(self, "chat_filter_tree"):
            return
        for iid in self.chat_filter_tree.get_children():  # type: ignore[attr-defined]
            self.chat_filter_tree.delete(iid)  # type: ignore[attr-defined]
        self.chat_filter_tree.tag_configure("kept", background="#ecfdf5", foreground="#065f46")  # type: ignore[attr-defined]
        self.chat_filter_tree.tag_configure("ignored", background="#fef2f2", foreground="#991b1b")  # type: ignore[attr-defined]
        base_titles = {"keep": "STATUT", "platform": "PLATEFORME", "conversation": "CONVERSATION", "participants": "PARTICIPANTS", "count": "MESSAGES"}
        for col_id, base_lbl in base_titles.items():
            arrow: str = (" ▼" if getattr(self, "chat_sort_reverse", True) else " ▲") if getattr(self, "chat_sort_col", "count") == col_id else ""
            self.chat_filter_tree.heading(col_id, text=f"{base_lbl}{arrow}", command=lambda c=col_id: self._sort_chats_by_column(c))  # type: ignore[attr-defined]

        items_all: List[Dict[str, Any]] = getattr(self, "chat_filter_items", [])
        query: str = self.chat_filter_search_var.get().strip().lower() if hasattr(self, "chat_filter_search_var") else ""  # type: ignore[attr-defined]
        view_mode: str = self.chat_filter_view_var.get() if hasattr(self, "chat_filter_view_var") else "Tous"  # type: ignore[attr-defined]
        kept_total: int = sum(1 for it in items_all if it.get("selected"))
        ignored_total: int = len(items_all) - kept_total
        indexed = list(enumerate(items_all))
        indexed.sort(key=lambda pair: self._chat_sort_key(next(reversed(pair))), reverse=getattr(self, "chat_sort_reverse", True))

        filtered: List[Tuple[int, Dict[str, Any]]] = []
        for orig_idx, item in indexed:
            is_kept: bool = bool(item.get("selected"))
            if (view_mode == "Gardées" and not is_kept) or (view_mode == "Mises de côté" and is_kept):
                continue
            plat_s: str = str(item.get("platform") or "")
            conv_s: str = str(item.get("conversation") or "")
            part_s: str = str(item.get("participants_display") or ", ".join(item.get("participants", [])))
            if not self._matches_search_query(query, plat_s, conv_s, part_s):  # type: ignore[attr-defined]
                continue
            filtered.append((orig_idx, item))

        page_slice = self._paginate_and_update_controls(filtered, "chat_page_index", "chat_page_info_var", "btn_chat_prev_page", "btn_chat_next_page")  # type: ignore[attr-defined]
        for orig_idx, item in page_slice:
            is_kept = bool(item.get("selected"))
            mark: str = "✓ Garder" if is_kept else "✕ Écarter"
            part_disp: str = str(item.get("participants_display") or ", ".join(item.get("participants", [])))
            self.chat_filter_tree.insert("", "end", iid=str(orig_idx), values=(mark, str(item.get("platform") or ""), str(item.get("conversation") or ""), part_disp, f"{item.get('count', 0)} msg"), tags=("kept" if is_kept else "ignored",))  # type: ignore[attr-defined]

        if hasattr(self, "chat_filter_summary_var"):
            self.chat_filter_summary_var.set(f"{kept_total} gardée(s) (vert) • {ignored_total} mise(s) de côté (rouge) — Total : {len(items_all)} conversation(s).")  # type: ignore[attr-defined]
        if hasattr(self, "tabs_chat_view"):
            self.tabs_chat_view.set_option_labels({"Tous": f"Tous ({len(items_all)})", "Gardées": f"Gardées ({kept_total})", "Mises de côté": f"Mises de côté ({ignored_total})"})  # type: ignore[attr-defined]

    def _toggle_chat_row_by_id(self, row_id: str) -> None:
        items_list: List[Dict[str, Any]] = getattr(self, "chat_filter_items", [])
        if row_id and row_id.isdigit() and 0 <= int(row_id) < len(items_list):
            idx: int = int(row_id)
            items_list[idx]["selected"] = not bool(items_list[idx].get("selected"))
            self._render_chat_filter_tree()
            self.chat_filter_tree.selection_remove(self.chat_filter_tree.selection())  # type: ignore[attr-defined]
            self._schedule_debounced_save("_chat_save_after_id", self._persist_chat_filter_now)  # type: ignore[attr-defined]

    def _toggle_selected_chat_filter(self, _event: object = None) -> None:
        sel = self.chat_filter_tree.selection()  # type: ignore[attr-defined]
        if sel:
            self._toggle_chat_row_by_id(next(iter(sel)))

    def _set_all_chats_selected(self, selected: bool, exclusive: bool = False) -> None:
        query: str = self.chat_filter_search_var.get().strip().lower() if hasattr(self, "chat_filter_search_var") else ""  # type: ignore[attr-defined]
        for item in getattr(self, "chat_filter_items", []):
            plat_s: str = str(item.get("platform") or "")
            conv_s: str = str(item.get("conversation") or "")
            part_s: str = str(item.get("participants_display") or ", ".join(item.get("participants", [])))
            if self._matches_search_query(query, plat_s, conv_s, part_s):  # type: ignore[attr-defined]
                item["selected"] = selected
            elif exclusive and selected:
                item["selected"] = False
        self._render_chat_filter_tree()
        self.chat_filter_tree.selection_remove(self.chat_filter_tree.selection())  # type: ignore[attr-defined]
        self._persist_chat_filter_now()

    def _save_chat_filter_and_continue(self) -> None:
        self._persist_chat_filter_now()
        self._show_page("mode")  # type: ignore[attr-defined]
