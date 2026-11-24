# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
import tkinter as tk
from typing import Any, Callable, Dict, List, Tuple
from doc_anonymizer.gui_chat_table_mixin import GuiChatTableMixin
from doc_anonymizer.gui_duplicate_table_mixin import GuiDuplicateTableMixin
from doc_anonymizer.gui_table_helpers import TreeviewTableHelper


class GuiTablesMixin(GuiChatTableMixin, GuiDuplicateTableMixin):
    """Tableaux filtrables, paginés et triables des contacts, SMS, chats et doublons."""

    TABLE_PAGE_SIZE: int = 150
    SMS_PAGE_SIZE: int = 150

    controller: Any
    current_ini_var: tk.StringVar
    status_var: tk.StringVar
    contact_filter_items: List[Dict[str, Any]]
    sms_filter_items: List[Dict[str, Any]]
    contact_sort_col: str
    contact_sort_reverse: bool
    sms_sort_col: str
    sms_sort_reverse: bool

    def _schedule_debounced_save(
        self, timer_attr: str, callback: Callable[[], None]
    ) -> None:
        pending_id = getattr(self, timer_attr, None)
        if pending_id is not None and hasattr(self, "after_cancel"):
            try:
                self.after_cancel(pending_id)  # type: ignore[attr-defined]
            except Exception:
                pass
        if hasattr(self, "after"):
            setattr(self, timer_attr, self.after(400, callback))  # type: ignore[attr-defined]
        else:
            callback()

    def _paginate_and_update_controls(
        self,
        filtered: List[Tuple[int, Dict[str, Any]]],
        page_attr: str,
        info_var_attr: str,
        prev_btn_attr: str,
        next_btn_attr: str,
    ) -> List[Tuple[int, Dict[str, Any]]]:
        total_pages: int = max(
            1, (len(filtered) + self.TABLE_PAGE_SIZE - 1) // self.TABLE_PAGE_SIZE
        )
        cur_page: int = min(max(0, getattr(self, page_attr, 0)), total_pages - 1)
        setattr(self, page_attr, cur_page)
        start_i: int = cur_page * self.TABLE_PAGE_SIZE
        page_slice = filtered[start_i : start_i + self.TABLE_PAGE_SIZE]
        if hasattr(self, info_var_attr):
            getattr(self, info_var_attr).set(
                f"Page {cur_page + 1} / {total_pages} "
                f"({len(page_slice)} affiché(s) sur {len(filtered)})"
            )
        if hasattr(self, prev_btn_attr):
            getattr(self, prev_btn_attr).configure(
                state="normal" if cur_page > 0 else "disabled"
            )
        if hasattr(self, next_btn_attr):
            getattr(self, next_btn_attr).configure(
                state="normal" if (cur_page + 1) < total_pages else "disabled"
            )
        return page_slice
    def _refresh_contact_filter_list(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        self.contact_page_index: int = 0
        self.contact_filter_items = self.controller.load_contact_filter_items(ini_path)
        self._render_contact_filter_tree()

    def _persist_contact_filter_now(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if ini_path and self.contact_filter_items:
            kept: int = self.controller.save_contact_filter_selection(
                ini_path, self.contact_filter_items
            )
            self.status_var.set(
                f"Sélection enregistrée : {kept} contact(s) conservé(s)."
            )

    def _on_contact_view_changed(self) -> None:
        self.contact_page_index = 0
        self._render_contact_filter_tree()

    def _change_contact_page(self, delta: int) -> None:
        self.contact_page_index = max(0, getattr(self, "contact_page_index", 0) + delta)
        self._render_contact_filter_tree()

    def _on_contact_search_typed(self, _event: object = None) -> None:
        if hasattr(self, "ent_contact_search"):
            self.contact_filter_search_var.set(self.ent_contact_search.get())  # type: ignore[attr-defined]
        self.contact_page_index = 0
        self._render_contact_filter_tree()

    def _sort_contacts_by_column(self, col_id: str) -> None:
        if self.contact_sort_col == col_id:
            self.contact_sort_reverse = not self.contact_sort_reverse
        else:
            self.contact_sort_col = col_id
            self.contact_sort_reverse = False
        self.contact_page_index = 0
        self._render_contact_filter_tree()

    @staticmethod
    def _matches_search_query(query: str, *fields: str) -> bool:
        """Compare la recherche en tolérant les espaces/tirets dans les numéros."""
        if not query:
            return True
        compact_q: str = re.sub(r"[\s.\-]+", "", query)
        for field in fields:
            low_f: str = field.lower()
            if query in low_f:
                return True
            if compact_q and compact_q in re.sub(r"[\s.\-]+", "", low_f):
                return True
        return False

    def _contact_sort_key(self, item: Dict[str, Any]) -> Tuple[Any, ...]:
        name_low: str = str(
            item.get("display_name") or item.get("alias") or ""
        ).lower()
        phones_str, emails_str = TreeviewTableHelper.split_contact_identifiers(
            item.get("identifiers", [])
        )
        phones_low: str = phones_str.lower()
        emails_low: str = emails_str.lower()
        if self.contact_sort_col == "keep":
            return (0 if item.get("selected") else 1, name_low)
        if self.contact_sort_col == "phones":
            return (phones_low == "", phones_low, name_low)
        if self.contact_sort_col == "emails":
            return (emails_low == "", emails_low, name_low)
        return (name_low, phones_low, emails_low)
    def _render_contact_filter_tree(self) -> None:
        for iid in self.contacts_filter_tree.get_children():  # type: ignore[attr-defined]
            self.contacts_filter_tree.delete(iid)  # type: ignore[attr-defined]
        self.contacts_filter_tree.tag_configure("kept", background="#ecfdf5", foreground="#065f46")  # type: ignore[attr-defined]
        self.contacts_filter_tree.tag_configure("ignored", background="#fef2f2", foreground="#991b1b")  # type: ignore[attr-defined]
        base_titles = {"keep": "STATUT", "alias": "CONTACT", "phones": "TÉLÉPHONE", "emails": "EMAIL"}
        for col_id, base_lbl in base_titles.items():
            arrow: str = (" ▼" if self.contact_sort_reverse else " ▲") if self.contact_sort_col == col_id else ""
            self.contacts_filter_tree.heading(col_id, text=f"{base_lbl}{arrow}", command=lambda c=col_id: self._sort_contacts_by_column(c))  # type: ignore[attr-defined]

        query: str = self.contact_filter_search_var.get().strip().lower()  # type: ignore[attr-defined]
        view_mode: str = self.contact_filter_view_var.get() if hasattr(self, "contact_filter_view_var") else "Tous"
        kept_total: int = sum(1 for it in self.contact_filter_items if it.get("selected"))
        ignored_total: int = len(self.contact_filter_items) - kept_total
        indexed = list(enumerate(self.contact_filter_items))
        indexed.sort(key=lambda pair: self._contact_sort_key(next(reversed(pair))), reverse=self.contact_sort_reverse)

        filtered: List[Tuple[int, Dict[str, Any]]] = []
        for orig_idx, item in indexed:
            is_kept: bool = bool(item.get("selected"))
            if view_mode in ("Gardés uniquement", "Gardés") and not is_kept:
                continue
            if view_mode in ("Mis de côté uniquement", "Mis de côté") and is_kept:
                continue
            name_str: str = str(item.get("display_name") or item.get("alias") or "")
            phones_str, emails_str = TreeviewTableHelper.split_contact_identifiers(item.get("identifiers", []))
            if not self._matches_search_query(query, name_str, phones_str, emails_str):
                continue
            filtered.append((orig_idx, item))

        page_slice = self._paginate_and_update_controls(filtered, "contact_page_index", "contact_page_info_var", "btn_contact_prev_page", "btn_contact_next_page")
        for orig_idx, item in page_slice:
            is_kept = bool(item.get("selected"))
            name_str = str(item.get("display_name") or item.get("alias") or "")
            phones_str, emails_str = TreeviewTableHelper.split_contact_identifiers(item.get("identifiers", []))
            mark: str = "✓ Garder" if is_kept else "✕ Mis de côté"
            self.contacts_filter_tree.insert("", "end", iid=str(orig_idx), values=(mark, name_str, phones_str, emails_str), tags=("kept" if is_kept else "ignored",))  # type: ignore[attr-defined]

        self.contact_filter_summary_var.set(f"{kept_total} gardé(s) (vert) • {ignored_total} mis de côté (rouge) — Total : {len(self.contact_filter_items)} contact(s).")  # type: ignore[attr-defined]
        if hasattr(self, "tabs_contact_view"):
            self.tabs_contact_view.set_option_labels({"Tous": f"Tous ({len(self.contact_filter_items)})", "Gardés": f"Gardés ({kept_total})", "Mis de côté": f"Mis de côté ({ignored_total})"})  # type: ignore[attr-defined]

    def _toggle_contact_row_by_id(self, row_id: str) -> None:
        if row_id and row_id.isdigit() and 0 <= int(row_id) < len(self.contact_filter_items):
            idx: int = int(row_id)
            self.contact_filter_items[idx]["selected"] = not bool(self.contact_filter_items[idx].get("selected"))
            self._render_contact_filter_tree()
            self.contacts_filter_tree.selection_remove(self.contacts_filter_tree.selection())  # type: ignore[attr-defined]
            self._schedule_debounced_save("_contact_save_after_id", self._persist_contact_filter_now)

    def _toggle_selected_contact_filter(self, _event: object = None) -> None:
        sel = self.contacts_filter_tree.selection()  # type: ignore[attr-defined]
        if sel:
            self._toggle_contact_row_by_id(next(iter(sel)))

    def _set_all_contacts_selected(self, selected: bool, exclusive: bool = False) -> None:
        query: str = self.contact_filter_search_var.get().strip().lower()  # type: ignore[attr-defined]
        for item in self.contact_filter_items:
            name_str: str = str(item.get("display_name") or item.get("alias") or "")
            phones_str, emails_str = TreeviewTableHelper.split_contact_identifiers(item.get("identifiers", []))
            if self._matches_search_query(query, name_str, phones_str, emails_str):
                item["selected"] = selected
            elif exclusive and selected:
                item["selected"] = False
        self._render_contact_filter_tree()
        self.contacts_filter_tree.selection_remove(self.contacts_filter_tree.selection())  # type: ignore[attr-defined]
        self._persist_contact_filter_now()

    def _save_contact_filter_and_continue(self) -> None:
        self._persist_contact_filter_now()
        self._show_page("sms")  # type: ignore[attr-defined]

    def _refresh_sms_number_list(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        xml_list = self.controller.list_sms_export_files(ini_path)
        self.sms_files_summary_var.set(f"Exports SMS (.xml) détectés ({len(xml_list)}) : {', '.join(os.path.basename(p) for p in xml_list[:5])}" if xml_list else "Exports SMS (.xml) détectés : aucun.")  # type: ignore[attr-defined]
        self.sms_page_index: int = 0
        self.sms_filter_items = self.controller.load_sms_number_filter_items(ini_path)
        self._render_sms_filter_tree()

    def _persist_sms_filter_now(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if ini_path and self.sms_filter_items:
            kept: int = self.controller.save_sms_number_filter_selection(ini_path, self.sms_filter_items)
            self.status_var.set(f"Numéros SMS enregistrés : {kept} numéro(s) conservé(s).")

    def _on_sms_view_changed(self) -> None:
        self.sms_page_index = 0
        self._render_sms_filter_tree()

    def _change_sms_page(self, delta: int) -> None:
        self.sms_page_index = max(0, getattr(self, "sms_page_index", 0) + delta)
        self._render_sms_filter_tree()

    def _on_sms_search_typed(self, _event: object = None) -> None:
        if hasattr(self, "ent_sms_search"):
            self.sms_filter_search_var.set(self.ent_sms_search.get())  # type: ignore[attr-defined]
        self.sms_page_index = 0
        self._render_sms_filter_tree()

    def _sort_sms_by_column(self, col_id: str) -> None:
        if self.sms_sort_col == col_id:
            self.sms_sort_reverse = not self.sms_sort_reverse
        else:
            self.sms_sort_col = col_id
            self.sms_sort_reverse = col_id == "count"
        self.sms_page_index = 0
        self._render_sms_filter_tree()

    def _sms_sort_key(self, item: Dict[str, Any]) -> Tuple[Any, ...]:
        phone_low: str = str(item.get("phone") or "").lower()
        name_low: str = str(item.get("display_name") or "").lower()
        cnt: int = int(item.get("count", 0))
        if self.sms_sort_col == "keep":
            return (0 if item.get("selected") else 1, -cnt, phone_low)
        if self.sms_sort_col == "phone":
            return (phone_low, -cnt)
        if self.sms_sort_col == "name":
            is_def: bool = name_low.startswith(("[numéro court]", "correspondant sms"))
            return (is_def, name_low, -cnt)
        return (cnt, phone_low)

    @staticmethod
    def _is_short_sms_item(item: Dict[str, Any]) -> bool:
        from doc_anonymizer.sms_filter_manager import SmsFilterManager

        if "is_short" in item:
            return bool(item["is_short"])
        return SmsFilterManager.is_short_number(str(item.get("phone") or ""))
    def _render_sms_filter_tree(self) -> None:
        for iid in self.sms_filter_tree.get_children():  # type: ignore[attr-defined]
            self.sms_filter_tree.delete(iid)  # type: ignore[attr-defined]
        self.sms_filter_tree.tag_configure("kept", background="#ecfdf5", foreground="#065f46")  # type: ignore[attr-defined]
        self.sms_filter_tree.tag_configure("ignored", background="#fef2f2", foreground="#991b1b")  # type: ignore[attr-defined]
        base_titles = {"keep": "STATUT", "phone": "NUMÉRO DE TÉLÉPHONE", "name": "CONTACT ASSOCIÉ", "count": "MESSAGES"}
        for col_id, base_lbl in base_titles.items():
            arrow: str = (" ▼" if self.sms_sort_reverse else " ▲") if self.sms_sort_col == col_id else ""
            self.sms_filter_tree.heading(col_id, text=f"{base_lbl}{arrow}", command=lambda c=col_id: self._sort_sms_by_column(c))  # type: ignore[attr-defined]

        query: str = self.sms_filter_search_var.get().strip().lower()  # type: ignore[attr-defined]
        view_mode: str = self.sms_filter_view_var.get() if hasattr(self, "sms_filter_view_var") else "Tous"  # type: ignore[attr-defined]
        kept_total: int = sum(1 for it in self.sms_filter_items if it.get("selected"))
        short_total: int = sum(1 for it in self.sms_filter_items if self._is_short_sms_item(it))
        ignored_total: int = len(self.sms_filter_items) - kept_total
        indexed = list(enumerate(self.sms_filter_items))
        indexed.sort(key=lambda pair: self._sms_sort_key(next(reversed(pair))), reverse=self.sms_sort_reverse)

        filtered: List[Tuple[int, Dict[str, Any]]] = []
        for orig_idx, item in indexed:
            is_kept: bool = bool(item.get("selected"))
            is_short: bool = self._is_short_sms_item(item)
            if (view_mode == "Gardés" and not is_kept) or (view_mode == "Mis de côté" and is_kept) or (view_mode == "Numéros courts" and not is_short):
                continue
            phone_str: str = str(item.get("phone") or "")
            name_str: str = str(item.get("display_name") or "")
            if not self._matches_search_query(query, phone_str, name_str):
                continue
            filtered.append((orig_idx, item))

        page_slice = self._paginate_and_update_controls(filtered, "sms_page_index", "sms_page_info_var", "btn_sms_prev_page", "btn_sms_next_page")
        for orig_idx, item in page_slice:
            is_kept = bool(item.get("selected"))
            mark: str = "✓ Garder" if is_kept else "✕ Supprimer"
            row_tag: str = "kept" if is_kept else "ignored"
            self.sms_filter_tree.insert("", "end", iid=str(orig_idx), values=(mark, str(item.get("phone") or ""), str(item.get("display_name") or ""), f"{item.get('count', 0)} SMS"), tags=(row_tag,))  # type: ignore[attr-defined]

        self.sms_filter_summary_var.set(f"{kept_total} conservé(s) (vert) • {ignored_total} supprimé(s) (rouge) • {short_total} numéro(s) court(s) — Total : {len(self.sms_filter_items)}.")  # type: ignore[attr-defined]
        if hasattr(self, "tabs_sms_view"):
            self.tabs_sms_view.set_option_labels({"Tous": f"Tous ({len(self.sms_filter_items)})", "Gardés": f"Gardés ({kept_total})", "Mis de côté": f"Mis de côté ({ignored_total})", "Numéros courts": f"Numéros courts ({short_total})"})  # type: ignore[attr-defined]

    def _toggle_sms_row_by_id(self, row_id: str) -> None:
        if row_id and row_id.isdigit() and 0 <= int(row_id) < len(self.sms_filter_items):
            idx: int = int(row_id)
            self.sms_filter_items[idx]["selected"] = not bool(self.sms_filter_items[idx].get("selected"))
            self._render_sms_filter_tree()
            self.sms_filter_tree.selection_remove(self.sms_filter_tree.selection())  # type: ignore[attr-defined]
            self._schedule_debounced_save("_sms_save_after_id", self._persist_sms_filter_now)

    def _toggle_selected_sms_filter(self, _event: object = None) -> None:
        sel = self.sms_filter_tree.selection()  # type: ignore[attr-defined]
        if sel:
            self._toggle_sms_row_by_id(next(iter(sel)))

    def _deselect_short_sms_numbers(self) -> None:
        changed: int = 0
        for item in self.sms_filter_items:
            if self._is_short_sms_item(item) and item.get("selected"):
                item["selected"] = False
                changed += 1
        self._render_sms_filter_tree()
        self.sms_filter_tree.selection_remove(self.sms_filter_tree.selection())  # type: ignore[attr-defined]
        self._persist_sms_filter_now()
        self.status_var.set(f"{changed} numéro(s) court(s) désélectionné(s).")

    def _set_all_sms_numbers_selected(self, selected: bool, exclusive: bool = False) -> None:
        query: str = self.sms_filter_search_var.get().strip().lower()  # type: ignore[attr-defined]
        view_mode: str = self.sms_filter_view_var.get() if hasattr(self, "sms_filter_view_var") else "Tous"
        for item in self.sms_filter_items:
            in_view: bool = (view_mode != "Numéros courts") or self._is_short_sms_item(item)
            if in_view and self._matches_search_query(query, str(item.get("phone") or ""), str(item.get("display_name") or "")):
                item["selected"] = selected
            elif exclusive and selected:
                item["selected"] = False
        self._render_sms_filter_tree()
        self.sms_filter_tree.selection_remove(self.sms_filter_tree.selection())  # type: ignore[attr-defined]
        self._persist_sms_filter_now()

    def _save_sms_filter_and_continue(self) -> None:
        self._persist_sms_filter_now()
        self._show_page("chats")  # type: ignore[attr-defined]
