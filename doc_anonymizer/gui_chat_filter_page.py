import tkinter as tk
from typing import Any, Dict
from doc_anonymizer import gui_widgets as _gw
from doc_anonymizer.gui_widgets import (
    CleanSegmentedTabs, HAS_CTK, UI_COLORS, ctk, make_card,
    make_modern_dropdown, make_modern_entry, make_styled_button,
    register_scalable_font, scaled_size,
)


class GuiChatFilterPageMixin:
    """Construit l'écran de filtrage des messageries et chats (Étape 4)."""

    pages: Dict[str, Any]

    def _build_page_chats(self) -> None:
        use_ctk: bool = bool(
            HAS_CTK and ctk is not None and not _gw.SCREEN_READER_MODE
        )
        page = self.pages["chats"]
        card_ch = make_card(
            page,
            title="Étape 4 — Vérifier les exports de messageries et sélectionner les conversations",
            subtitle="Vos exports Google Chat, Teams, WhatsApp, Messenger et Signal sont détectés automatiquement.",
            accent_color=UI_COLORS["primary"],
        )
        self.chat_files_summary_var = tk.StringVar(
            value="Exports de messageries détectés : aucun."
        )
        lbl_cf = tk.Label(
            card_ch, textvariable=self.chat_files_summary_var,
            bg=UI_COLORS["card"], fg=UI_COLORS["muted"],
            font=("Segoe UI", scaled_size(8)),
        )
        lbl_cf.pack(anchor="w")
        register_scalable_font(lbl_cf, "Segoe UI", 8, "normal")

        self.chat_filter_summary_var = tk.StringVar(value="0 conversation(s).")
        lbl_cs = tk.Label(
            card_ch, textvariable=self.chat_filter_summary_var,
            bg=UI_COLORS["card"], fg="#1d4ed8",
            font=("Segoe UI", scaled_size(9), "bold"),
        )
        lbl_cs.pack(anchor="w", pady=(2, 6))
        register_scalable_font(lbl_cs, "Segoe UI", 9, "bold")
        bar_ch = tk.Frame(card_ch, bg=UI_COLORS["card"])
        bar_ch.pack(fill="x", pady=(0, 6))
        self.chat_filter_view_var = tk.StringVar(value="Tous")
        self.tabs_chat_view = CleanSegmentedTabs(
            bar_ch,
            [
                ("Tous (0)", "Tous"),
                ("Gardées (0)", "Gardées"),
                ("Mises de côté (0)", "Mises de côté"),
            ],
            self.chat_filter_view_var,
            command=lambda _v: self._on_chat_view_changed(),  # type: ignore[attr-defined]
        )
        self.tabs_chat_view.pack(side="left", padx=(0, 8))
        self.chat_min_msg_var = tk.StringVar(value="Tous msgs")
        self.combo_chat_min_msg = make_modern_dropdown(
            bar_ch,
            self.chat_min_msg_var,
            ["Tous msgs", "≥ 2 msgs", "≥ 5 msgs", "≥ 10 msgs", "≥ 50 msgs"],
            width=120,
            command=lambda _v: self._on_chat_view_changed(),  # type: ignore[attr-defined]
        )
        self.combo_chat_min_msg.pack(side="left", padx=(0, 6))
        self.chat_filter_search_var = tk.StringVar()
        self.ent_chat_search = make_modern_entry(
            bar_ch, textvariable=self.chat_filter_search_var,
            width=150, placeholder="Rechercher...",
        )
        self.ent_chat_search.pack(side="left", padx=(0, 6))
        for seq in ("<KeyRelease>", "<FocusOut>", "<<Paste>>", "<Control-v>", "<Control-V>"):
            self.ent_chat_search.bind(
                seq, lambda _e: self.after_idle(self._on_chat_search_typed), add="+"  # type: ignore[attr-defined]
            )
        make_styled_button(
            bar_ch, text="Tout cocher",
            command=lambda: self._set_all_chats_selected(True), variant="secondary",  # type: ignore[attr-defined]
        ).pack(side="left", padx=(0, 4))
        make_styled_button(
            bar_ch, text="Tout décocher",
            command=lambda: self._set_all_chats_selected(False), variant="secondary",  # type: ignore[attr-defined]
        ).pack(side="left")

        (
            self.chat_filter_tree,
            self.chat_page_info_var,
            self.btn_chat_prev_page,
            self.btn_chat_next_page,
        ) = self._build_tree_and_pager(  # type: ignore[attr-defined]
            card_ch,
            columns=("keep", "platform", "conversation", "participants", "count"),
            headers=(
                ("keep", "STATUT", 105, "center", lambda: self._sort_chats_by_column("keep")),  # type: ignore[attr-defined]
                ("platform", "PLATEFORME", 130, "w", lambda: self._sort_chats_by_column("platform")),  # type: ignore[attr-defined]
                ("conversation", "CONVERSATION", 210, "w", lambda: self._sort_chats_by_column("conversation")),  # type: ignore[attr-defined]
                ("participants", "PARTICIPANTS", 210, "w", lambda: self._sort_chats_by_column("participants")),  # type: ignore[attr-defined]
                ("count", "MESSAGES", 95, "center", lambda: self._sort_chats_by_column("count")),  # type: ignore[attr-defined]
            ),
            on_toggle_row=self._toggle_chat_row_by_id,  # type: ignore[attr-defined]
            on_space=self._toggle_selected_chat_filter,  # type: ignore[attr-defined]
            on_prev=lambda: self._change_chat_page(-1),  # type: ignore[attr-defined]
            on_next=lambda: self._change_chat_page(1),  # type: ignore[attr-defined]
        )

        nav_ch = tk.Frame(page, bg=UI_COLORS["bg"])
        nav_ch.pack(fill="x", pady=(6, 0))
        make_styled_button(
            nav_ch, text="<- Retour (Étape 3)",
            command=lambda: self._show_page("sms"), variant="secondary",  # type: ignore[attr-defined]
        ).pack(side="left")
        if use_ctk:
            btn_next_ch = ctk.CTkButton(
                nav_ch, text="Étape suivante : Choisir l'objectif ->",
                command=self._save_chat_filter_and_continue, fg_color=UI_COLORS["primary"],  # type: ignore[attr-defined]
                hover_color=UI_COLORS["primary_hover"], text_color="#ffffff",
                corner_radius=10, height=40, font=("Segoe UI", scaled_size(11), "bold"),
            )
            register_scalable_font(btn_next_ch, "Segoe UI", 11, "bold")
            btn_next_ch.pack(side="right")
        else:
            make_styled_button(
                nav_ch, text="Étape suivante : Choisir l'objectif ->",
                command=self._save_chat_filter_and_continue, variant="primary",  # type: ignore[attr-defined]
            ).pack(side="right")
