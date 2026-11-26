# Commandes pip à exécuter : pip install customtkinter>=5.2.2

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, Tuple
from doc_anonymizer import gui_widgets as _gw
from doc_anonymizer.gui_chat_filter_page import GuiChatFilterPageMixin
from doc_anonymizer.gui_table_helpers import TreeviewTableHelper
from doc_anonymizer.gui_widgets import (
    CleanSegmentedTabs, HAS_CTK, UI_COLORS, ctk, make_card,
    make_modern_entry, make_styled_button, register_scalable_font,
    scaled_size,
)


class GuiPagesFiltersMixin(GuiChatFilterPageMixin):
    """Construit les écrans de filtrage des carnets (2) et des SMS (3)."""

    pages: Dict[str, Any]

    @staticmethod
    def _build_tree_and_pager(
        parent_card: tk.Frame, columns: Tuple[str, ...],
        headers: Tuple[Tuple[str, str, int, str, Callable[[], None]], ...],
        on_toggle_row: Callable[[str], None], on_space: Callable[[Any], None],
        on_prev: Callable[[], None], on_next: Callable[[], None],
    ) -> Tuple[ttk.Treeview, tk.StringVar, Any, Any]:
        box = tk.Frame(parent_card, bg=UI_COLORS["card"], highlightbackground=UI_COLORS["border"], highlightthickness=1)
        box.pack(fill="both", expand=True, pady=(0, 6))
        tree = ttk.Treeview(box, columns=columns, show="headings", selectmode="browse", style="Modern.Treeview", height=8)
        for col_id, lbl, width, anchor, sort_cb in headers:
            tree.heading(col_id, text=lbl, command=sort_cb)
            tree.column(col_id, width=width, minwidth=40, anchor=anchor)  # type: ignore[arg-type]
        sb = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        TreeviewTableHelper.bind_trackpad_safe_toggle(tree, on_toggle_row)
        tree.bind("<space>", on_space)
        pager = tk.Frame(parent_card, bg=UI_COLORS["card"])
        pager.pack(fill="x")
        info_var = tk.StringVar(value="Page 1 / 1")
        lbl_p = tk.Label(pager, textvariable=info_var, bg=UI_COLORS["card"], fg=UI_COLORS["muted"], font=("Segoe UI", scaled_size(8)))
        lbl_p.pack(side="left")
        register_scalable_font(lbl_p, "Segoe UI", 8, "normal")
        btn_next = make_styled_button(pager, text="Suivant >", command=on_next, variant="secondary")
        btn_next.pack(side="right", padx=(4, 0))
        btn_prev = make_styled_button(pager, text="< Précédent", command=on_prev, variant="secondary")
        btn_prev.pack(side="right")
        return tree, info_var, btn_prev, btn_next
    def _build_page_setup(self) -> None:
        use_ctk: bool = bool(HAS_CTK and ctk is not None and not _gw.SCREEN_READER_MODE)
        page = self.pages["setup"]
        card_c = make_card(page, title="Étape 2 — Vérifier les carnets détectés et les contacts à anonymiser", subtitle="Cliquez pour basculer (Vert = garder, Rouge = mis de côté).", accent_color=UI_COLORS["primary"])
        top_c = tk.Frame(card_c, bg=UI_COLORS["card"])
        top_c.pack(fill="x", pady=(0, 6))
        self.contact_filter_summary_var = tk.StringVar(value="0 contact(s).")
        lbl_sum = tk.Label(top_c, textvariable=self.contact_filter_summary_var, bg=UI_COLORS["card"], fg="#1d4ed8", font=("Segoe UI", scaled_size(9), "bold"))
        lbl_sum.pack(side="left")
        register_scalable_font(lbl_sum, "Segoe UI", 9, "bold")
        make_styled_button(top_c, text="Règles manuelles...", command=self._open_manual_contacts_editor, variant="secondary").pack(side="right")  # type: ignore[attr-defined]
        bar_c = tk.Frame(card_c, bg=UI_COLORS["card"])
        bar_c.pack(fill="x", pady=(0, 6))
        self.contact_filter_view_var = tk.StringVar(value="Tous")
        self.tabs_contact_view = CleanSegmentedTabs(bar_c, [("Tous (0)", "Tous"), ("Gardés (0)", "Gardés"), ("Mis de côté (0)", "Mis de côté")], self.contact_filter_view_var, command=lambda _v: self._on_contact_view_changed())  # type: ignore[attr-defined]
        self.tabs_contact_view.pack(side="left", padx=(0, 8))
        self.contact_filter_search_var = tk.StringVar()
        self.ent_contact_search = make_modern_entry(bar_c, textvariable=self.contact_filter_search_var, width=150, placeholder="Rechercher...")
        self.ent_contact_search.pack(side="left", padx=(0, 6))
        for seq in ("<KeyRelease>", "<FocusOut>", "<<Paste>>", "<Control-v>", "<Control-V>"):
            self.ent_contact_search.bind(seq, lambda _e: self.after_idle(self._on_contact_search_typed), add="+")  # type: ignore[attr-defined]
        make_styled_button(bar_c, text="Tout décocher", command=lambda: self._set_all_contacts_selected(False), variant="secondary").pack(side="right")  # type: ignore[attr-defined]
        make_styled_button(bar_c, text="Tout cocher", command=lambda: self._set_all_contacts_selected(True), variant="secondary").pack(side="right", padx=(0, 4))  # type: ignore[attr-defined]
        self.contacts_filter_tree, self.contact_page_info_var, self.btn_contact_prev_page, self.btn_contact_next_page = self._build_tree_and_pager(card_c, ("keep", "alias", "phones", "emails"), (("keep", "STATUT", 100, "center", lambda: self._sort_contacts_by_column("keep")), ("alias", "CONTACT", 180, "w", lambda: self._sort_contacts_by_column("alias")), ("phones", "TÉLÉPHONE", 175, "w", lambda: self._sort_contacts_by_column("phones")), ("emails", "EMAIL", 205, "w", lambda: self._sort_contacts_by_column("emails"))), self._toggle_contact_row_by_id, self._toggle_selected_contact_filter, lambda: self._change_contact_page(-1), lambda: self._change_contact_page(1))  # type: ignore[attr-defined]
        nav_c = tk.Frame(page, bg=UI_COLORS["bg"])
        nav_c.pack(fill="x", pady=(6, 0))
        make_styled_button(nav_c, text="<- Retour (Étape 1)", command=self._go_back_from_setup, variant="secondary").pack(side="left")  # type: ignore[attr-defined]
        if use_ctk:
            btn_next_c = ctk.CTkButton(nav_c, text="Étape suivante : Exports SMS ->", command=self._save_contact_filter_and_continue, fg_color=UI_COLORS["primary"], hover_color=UI_COLORS["primary_hover"], text_color="#ffffff", corner_radius=10, height=40, font=("Segoe UI", scaled_size(11), "bold"))  # type: ignore[attr-defined]
            register_scalable_font(btn_next_c, "Segoe UI", 11, "bold")
            btn_next_c.pack(side="right")
        else:
            make_styled_button(nav_c, text="Étape suivante : Exports SMS ->", command=self._save_contact_filter_and_continue, variant="primary").pack(side="right")  # type: ignore[attr-defined]

    def _build_page_sms(self) -> None:
        use_ctk: bool = bool(HAS_CTK and ctk is not None and not _gw.SCREEN_READER_MODE)
        page = self.pages["sms"]
        card_s = make_card(page, title="Étape 3 — Vérifier les exports SMS détectés et filtrer les numéros", subtitle="Cliquez pour basculer (Vert = garder, Rouge = supprimer).", accent_color=UI_COLORS["primary"])
        self.sms_files_summary_var = tk.StringVar(value="Exports SMS (.xml) détectés : aucun.")
        lbl_f = tk.Label(card_s, textvariable=self.sms_files_summary_var, bg=UI_COLORS["card"], fg=UI_COLORS["muted"], font=("Segoe UI", scaled_size(8)))
        lbl_f.pack(anchor="w")
        register_scalable_font(lbl_f, "Segoe UI", 8, "normal")
        self.sms_filter_summary_var = tk.StringVar(value="0 numéro(s).")
        lbl_s = tk.Label(card_s, textvariable=self.sms_filter_summary_var, bg=UI_COLORS["card"], fg="#1d4ed8", font=("Segoe UI", scaled_size(9), "bold"))
        lbl_s.pack(anchor="w", pady=(2, 6))
        register_scalable_font(lbl_s, "Segoe UI", 9, "bold")
        bar_s = tk.Frame(card_s, bg=UI_COLORS["card"])
        bar_s.pack(fill="x", pady=(0, 6))
        self.sms_filter_view_var = tk.StringVar(value="Tous")
        self.tabs_sms_view = CleanSegmentedTabs(bar_s, [("Tous (0)", "Tous"), ("Gardés (0)", "Gardés"), ("Mis de côté (0)", "Mis de côté"), ("Numéros courts (0)", "Numéros courts")], self.sms_filter_view_var, command=lambda _v: self._on_sms_view_changed())  # type: ignore[attr-defined]
        self.tabs_sms_view.pack(side="left", padx=(0, 8))
        self.sms_filter_search_var = tk.StringVar()
        self.ent_sms_search = make_modern_entry(bar_s, textvariable=self.sms_filter_search_var, width=140, placeholder="Rechercher...")
        self.ent_sms_search.pack(side="left", padx=(0, 6))
        for seq in ("<KeyRelease>", "<FocusOut>", "<<Paste>>", "<Control-v>", "<Control-V>"):
            self.ent_sms_search.bind(seq, lambda _e: self.after_idle(self._on_sms_search_typed), add="+")  # type: ignore[attr-defined]
        make_styled_button(bar_s, text="Tout cocher", command=lambda: self._set_all_sms_numbers_selected(True), variant="secondary").pack(side="left", padx=(0, 4))  # type: ignore[attr-defined]
        make_styled_button(bar_s, text="Exclure courts", command=self._deselect_short_sms_numbers, variant="secondary").pack(side="left")  # type: ignore[attr-defined]
        self.sms_filter_tree, self.sms_page_info_var, self.btn_sms_prev_page, self.btn_sms_next_page = self._build_tree_and_pager(card_s, ("keep", "phone", "name", "count"), (("keep", "STATUT", 100, "center", lambda: self._sort_sms_by_column("keep")), ("phone", "NUMÉRO DE TÉLÉPHONE", 170, "w", lambda: self._sort_sms_by_column("phone")), ("name", "CONTACT ASSOCIÉ", 250, "w", lambda: self._sort_sms_by_column("name")), ("count", "MESSAGES", 100, "center", lambda: self._sort_sms_by_column("count"))), self._toggle_sms_row_by_id, self._toggle_selected_sms_filter, lambda: self._change_sms_page(-1), lambda: self._change_sms_page(1))  # type: ignore[attr-defined]
        nav_s = tk.Frame(page, bg=UI_COLORS["bg"])
        nav_s.pack(fill="x", pady=(6, 0))
        make_styled_button(nav_s, text="<- Retour (Étape 2)", command=lambda: self._show_page("setup"), variant="secondary").pack(side="left")  # type: ignore[attr-defined]
        if use_ctk:
            btn_next_s = ctk.CTkButton(nav_s, text="Étape suivante : Messageries & Chats ->", command=self._save_sms_filter_and_continue, fg_color=UI_COLORS["primary"], hover_color=UI_COLORS["primary_hover"], text_color="#ffffff", corner_radius=10, height=40, font=("Segoe UI", scaled_size(11), "bold"))  # type: ignore[attr-defined]
            register_scalable_font(btn_next_s, "Segoe UI", 11, "bold")
            btn_next_s.pack(side="right")
        else:
            make_styled_button(nav_s, text="Étape suivante : Messageries & Chats ->", command=self._save_sms_filter_and_continue, variant="primary").pack(side="right")  # type: ignore[attr-defined]
