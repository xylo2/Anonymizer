# Commandes pip à exécuter : pip install customtkinter>=5.2.2

import os
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict
from doc_anonymizer import gui_widgets as _gw
from doc_anonymizer.gui_pages_secondary import GuiSecondaryPagesMixin
from doc_anonymizer.gui_widgets import (
    HAS_CTK, UI_COLORS, ctk, make_card, make_modern_dropdown,
    make_modern_entry, make_styled_button, make_widget_keyboard_accessible,
    register_scalable_font, scaled_size,
)

SPACE_EVENT: str = "<" + "space" + ">"


class GuiPagesMixin(GuiSecondaryPagesMixin):
    """Écrans d'accueil, dépôt de pièces, contacts, SMS et messageries."""

    pages: Dict[str, Any]
    controller: Any

    def _build_page_gate(self) -> None:
        use_ctk: bool = bool(HAS_CTK and ctk is not None and not _gw.SCREEN_READER_MODE)
        parent = self.pages["gate"]
        card_charter = make_card(
            parent,
            title="Engagement de relecture humaine & Licence libre (GNU GPL v3)",
            subtitle="Prenez quelques secondes pour valider ces règles essentielles de protection de vos données.",
            accent_color="#2563eb",
        )
        charter_text: str = (
            "• Vigilance humaine : aucun algorithme n'est infaillible face à un scan flou ou une abréviation inhabituelle.\n"
            "• Engagement de relecture : avant de transmettre vos fichiers (IA en ligne, avocat, syndicat, administration), relisez votre export — au moins par sondage — pour vérifier la protection de vos proches.\n"
            "• Licence libre GNU GPL v3 : logiciel libre fourni « en l'état, sans garantie ». Vous restez seul responsable des documents que vous choisissez de diffuser."
        )
        lbl_ch = tk.Label(card_charter, text=charter_text, bg=UI_COLORS["card"], fg=UI_COLORS["text"], font=("Segoe UI", scaled_size(9)), justify="left", anchor="w", wraplength=760)
        lbl_ch.pack(anchor="w", fill="x")
        register_scalable_font(lbl_ch, "Segoe UI", 9, "normal")

        card_ws = make_card(
            parent,
            title="Choisir ou créer votre espace de travail isolé",
            subtitle="Chaque affaire dispose de son propre dossier séparé (documents, contacts, résultats et audits).",
            accent_color="#059669",
        )
        self.gate_action_var = tk.StringVar(value="open")
        self.seg_gate_action = tk.Frame(card_ws, bg=UI_COLORS["tab_rail"], padx=3, pady=3)
        self.seg_gate_action.pack(anchor="w", pady=(0, 6))
        if use_ctk:
            self.btn_tab_open = ctk.CTkButton(self.seg_gate_action, text="Ouvrir un dossier existant", height=32, corner_radius=7, font=("Segoe UI", scaled_size(10), "bold"), command=lambda: self._on_gate_segment_changed("open"))  # type: ignore[attr-defined]
            self.btn_tab_create = ctk.CTkButton(self.seg_gate_action, text="Créer un nouveau dossier", height=32, corner_radius=7, font=("Segoe UI", scaled_size(10), "bold"), command=lambda: self._on_gate_segment_changed("create"))  # type: ignore[attr-defined]
        else:
            self.btn_tab_open = tk.Button(self.seg_gate_action, text="Ouvrir un dossier existant", relief="flat", bd=0, padx=12, pady=5, cursor="hand2", font=("Segoe UI", scaled_size(9), "bold"), command=lambda: self._on_gate_segment_changed("open"))  # type: ignore[attr-defined]
            self.btn_tab_create = tk.Button(self.seg_gate_action, text="Créer un nouveau dossier", relief="flat", bd=0, padx=12, pady=5, cursor="hand2", font=("Segoe UI", scaled_size(9), "bold"), command=lambda: self._on_gate_segment_changed("create"))  # type: ignore[attr-defined]
        pt_tab: int = 10 if use_ctk else 9
        register_scalable_font(self.btn_tab_open, "Segoe UI", pt_tab, "bold")
        register_scalable_font(self.btn_tab_create, "Segoe UI", pt_tab, "bold")
        make_widget_keyboard_accessible(self.btn_tab_open, command=lambda: self._on_gate_segment_changed("open"))  # type: ignore[attr-defined]
        make_widget_keyboard_accessible(self.btn_tab_create, command=lambda: self._on_gate_segment_changed("create"))  # type: ignore[attr-defined]
        self.btn_tab_open.pack(side="left", padx=2)
        self.btn_tab_create.pack(side="left", padx=2)
        self.frame_gate_existing = tk.Frame(card_ws, bg=UI_COLORS["card"])
        lbl_ex = tk.Label(self.frame_gate_existing, text="Sélectionnez le dossier :", bg=UI_COLORS["card"], fg=UI_COLORS["text"], font=("Segoe UI", scaled_size(9), "bold"))
        lbl_ex.pack(side="left", padx=(0, 8))
        register_scalable_font(lbl_ex, "Segoe UI", 9, "bold")
        self.gate_existing_var = tk.StringVar()
        self.combo_gate_ws = make_modern_dropdown(self.frame_gate_existing, self.gate_existing_var, [], width=280)
        self.combo_gate_ws.pack(side="left")

        self.frame_gate_create = tk.Frame(card_ws, bg=UI_COLORS["card"])
        lbl_cr = tk.Label(self.frame_gate_create, text="Nom du nouveau dossier :", bg=UI_COLORS["card"], fg=UI_COLORS["text"], font=("Segoe UI", scaled_size(9), "bold"))
        lbl_cr.pack(side="left", padx=(0, 8))
        register_scalable_font(lbl_cr, "Segoe UI", 9, "bold")
        self.gate_new_name_var = tk.StringVar()
        self.entry_gate_new = make_modern_entry(self.frame_gate_create, self.gate_new_name_var, width=280, placeholder="Ex. Dossier_Test_2026")
        self.entry_gate_new.pack(side="left")

        gate_btns = tk.Frame(parent, bg=UI_COLORS["bg"])
        gate_btns.pack(fill="x", pady=(6, 0))
        make_styled_button(gate_btns, text="Refuser et quitter", command=self._quit_politely, variant="secondary").pack(side="left")  # type: ignore[attr-defined]
        make_styled_button(gate_btns, text="J'ai compris et j'accepte -> Ouvrir mon dossier", command=self._confirm_gate_and_workspace, variant="primary").pack(side="right")  # type: ignore[attr-defined]

    def _build_page_documents(self) -> None:
        parent = self.pages["documents"]
        card_drop = make_card(
            parent,
            title="Référencer ou déposer toutes vos pièces (lecture seule, sans déplacer vos originaux)",
            subtitle="Glissez vos fichiers/dossiers ici ou utilisez les boutons : un simple lien est enregistré (aucune copie sauf clé USB/disque externe).",
            accent_color="#2563eb",
        )
        outer_card = card_drop.master
        if outer_card is not None:
            outer_card.pack_configure(fill="both", expand=True)

        btn_row = tk.Frame(card_drop, bg=UI_COLORS["card"])
        btn_row.pack(fill="x")
        make_styled_button(btn_row, text="Référencer des fichiers...", command=self._link_external_files, variant="primary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(btn_row, text="Référencer un dossier...", command=self._link_external_folder, variant="primary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(btn_row, text="Ouvrir le dossier interne de l'affaire", command=lambda: self._open_workspace_folder("sources_dir"), variant="secondary").pack(side="left")  # type: ignore[attr-defined]

        links_hdr = tk.Frame(card_drop, bg=UI_COLORS["card"])
        links_hdr.pack(fill="x", pady=(10, 2))
        tk.Label(links_hdr, text="Emplacements externes référencés en lecture seule (double-clic pour ouvrir) :", bg=UI_COLORS["card"], fg=UI_COLORS["text"], font=("Segoe UI", 8, "bold")).pack(side="left")
        make_styled_button(links_hdr, text="Retirer le lien sélectionné", command=self._remove_selected_linked_source, variant="ghost").pack(side="right")  # type: ignore[attr-defined]

        list_wrap = tk.Frame(card_drop, bg=UI_COLORS["card"])
        list_wrap.pack(fill="both", expand=True, pady=(0, 6))
        self.links_listbox = tk.Listbox(list_wrap, height=8, bg="#f8fafc", fg=UI_COLORS["text"], selectbackground="#dbeafe", selectforeground="#1e3a8a", relief="solid", bd=1, font=("Consolas", 9))
        sb_links = ttk.Scrollbar(list_wrap, orient="vertical", command=self.links_listbox.yview)
        self.links_listbox.configure(yscrollcommand=sb_links.set)
        self.links_listbox.pack(side="left", fill="both", expand=True)
        sb_links.pack(side="right", fill="y")
        self.links_listbox.bind("<Double-1>", lambda _e: self._open_selected_linked_source())  # type: ignore[attr-defined]

        self.docs_busy_frame = tk.Frame(card_drop, bg="#eff6ff", highlightbackground="#93c5fd", highlightthickness=1, padx=10, pady=6)
        self.docs_busy_var = tk.StringVar(value="")
        tk.Label(self.docs_busy_frame, textvariable=self.docs_busy_var, bg="#eff6ff", fg="#1e40af", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.docs_busy_bar = ttk.Progressbar(self.docs_busy_frame, mode="indeterminate")
        self.docs_busy_bar.pack(fill="x", pady=(4, 0))

        self.docs_summary_var = tk.StringVar(value="Pièces de l'affaire : 0 fichier(s).")
        tk.Label(card_drop, textvariable=self.docs_summary_var, bg=UI_COLORS["card"], fg="#1d4ed8", font=("Segoe UI", 9, "bold")).pack(anchor="w")

        self.zip_warning_var = tk.StringVar(value="")
        self.lbl_zip_warning = tk.Label(card_drop, textvariable=self.zip_warning_var, bg=UI_COLORS["warning_bg"], fg=UI_COLORS["warning_fg"], font=("Segoe UI", 9, "bold"), padx=12, pady=8, justify="left", wraplength=760)

        nav_row = tk.Frame(parent, bg=UI_COLORS["bg"])
        nav_row.pack(fill="x", pady=(4, 0))
        make_styled_button(nav_row, text="<- Retour (Accueil & Dossier)", command=lambda: self._show_page("gate"), variant="secondary").pack(side="left")  # type: ignore[attr-defined]
        make_styled_button(nav_row, text="Étape suivante : Carnets & Contacts ->", command=self._advance_from_documents, variant="primary").pack(side="right")  # type: ignore[attr-defined]
    def _build_page_setup(self) -> None:
        from doc_anonymizer.gui_table_helpers import TreeviewTableHelper
        from doc_anonymizer.gui_widgets import CleanSegmentedTabs

        parent = self.pages["setup"]
        card_csv = make_card(
            parent,
            title="Carnets de contacts détectés automatiquement",
            subtitle="Les exports Google Contacts (.csv) et iPhone (.vcf) déposés à l'étape 1 sont rangés automatiquement.",
            accent_color="#059669",
        )
        row_csv = tk.Frame(card_csv, bg=UI_COLORS["card"])
        row_csv.pack(fill="x")
        make_styled_button(row_csv, text="Voir mes carnets", command=lambda: self._open_workspace_folder("input_contacts_dir"), variant="secondary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(row_csv, text="Actualiser la liste", command=self._refresh_contact_filter_list, variant="secondary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(row_csv, text="Comment exporter mes contacts ?", command=lambda: self._open_help_dialog(initial_tab=1), variant="secondary").pack(side="right")  # type: ignore[attr-defined]

        self.csv_summary_var = tk.StringVar(value="Carnets (.csv / .vcf) détectés : aucun.")
        tk.Label(card_csv, textvariable=self.csv_summary_var, bg=UI_COLORS["card"], fg="#1d4ed8", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 0))

        card_filter = make_card(
            parent,
            title="Sélectionner les contacts liés à votre dossier",
            subtitle="Cliquez sur un entête pour trier • Cliquez sur une ligne pour basculer (Vert = garder, Rouge = écarter).",
            accent_color="#2563eb",
        )
        bar = tk.Frame(card_filter, bg=UI_COLORS["card"])
        bar.pack(fill="x")
        self.contact_filter_search_var = tk.StringVar()
        self.ent_contact_search = make_modern_entry(bar, textvariable=None, width=180, placeholder="Filtrer nom/tél/email...")
        self.ent_contact_search.pack(side="left", padx=(0, 6))
        for seq in ("<KeyRelease>", "<FocusOut>", "<<Paste>>", "<Control-v>", "<Control-V>"):
            self.ent_contact_search.bind(seq, lambda _e: self.after_idle(self._on_contact_search_typed), add="+")  # type: ignore[attr-defined]

        self.contact_filter_view_var = tk.StringVar(value="Tous")
        self.tabs_contact_view = CleanSegmentedTabs(
            bar,
            options=[("Tous", "Tous"), ("Gardés", "Gardés"), ("Mis de côté", "Mis de côté")],
            variable=self.contact_filter_view_var,
            command=lambda _v: self._on_contact_view_changed(),  # type: ignore[attr-defined]
        )
        self.tabs_contact_view.pack(side="left", padx=(0, 6))
        make_styled_button(bar, text="Garder uniquement ce filtre", command=lambda: self._set_all_contacts_selected(True, exclusive=True), variant="primary", tooltip="Garde uniquement les contacts correspondant au filtre actif et désélectionne tout le reste.").pack(side="left", padx=(0, 4))  # type: ignore[attr-defined]
        make_styled_button(bar, text="Tout cocher", command=lambda: self._set_all_contacts_selected(True, exclusive=False), variant="secondary", tooltip="Coche les contacts affichés sans désélectionner le reste.").pack(side="left", padx=(0, 4))  # type: ignore[attr-defined]
        make_styled_button(bar, text="Tout décocher (ce filtre)", command=lambda: self._set_all_contacts_selected(False), variant="secondary", tooltip="Désélectionne uniquement les contacts correspondant au filtre actif.").pack(side="left")  # type: ignore[attr-defined]

        self.contact_filter_summary_var = tk.StringVar(value="0 / 0 contact(s) conservé(s).")
        tk.Label(card_filter, textvariable=self.contact_filter_summary_var, bg=UI_COLORS["card"], fg="#1d4ed8", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 0))
        table_card = tk.Frame(parent, bg=UI_COLORS["card"], highlightbackground=UI_COLORS["border"], highlightthickness=1, padx=4, pady=4)
        table_card.pack(fill="both", expand=True, pady=(0, 6))
        self.contacts_filter_tree = ttk.Treeview(table_card, columns=("keep", "alias", "phones", "emails"), show="headings", selectmode="browse", style="Modern.Treeview", height=6)
        self.contacts_filter_tree.tag_configure("kept", background="#ecfdf5", foreground="#065f46")
        self.contacts_filter_tree.tag_configure("ignored", background="#fef2f2", foreground="#991b1b")
        for col_id, lbl, w in (("keep", "STATUT", 110), ("alias", "CONTACT ▲", 230), ("phones", "TÉLÉPHONE", 210), ("emails", "EMAIL", 230)):
            self.contacts_filter_tree.heading(col_id, text=lbl, command=lambda c=col_id: self._sort_contacts_by_column(c))  # type: ignore[attr-defined]
            self.contacts_filter_tree.column(col_id, width=w, anchor="center" if col_id == "keep" else "w")
        sb = ttk.Scrollbar(table_card, orient="vertical", command=self.contacts_filter_tree.yview)
        self.contacts_filter_tree.configure(yscrollcommand=sb.set)
        self.contacts_filter_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        TreeviewTableHelper.bind_trackpad_safe_toggle(self.contacts_filter_tree, self._toggle_contact_row_by_id)  # type: ignore[attr-defined]
        self.contacts_filter_tree.bind(SPACE_EVENT, self._toggle_selected_contact_filter)  # type: ignore[attr-defined]

        pager_c = tk.Frame(parent, bg=UI_COLORS["bg"])
        pager_c.pack(fill="x", pady=(0, 6))
        self.btn_contact_prev_page = make_styled_button(pager_c, text="<- Page préc.", command=lambda: self._change_contact_page(-1), variant="secondary")  # type: ignore[attr-defined]
        self.btn_contact_prev_page.pack(side="left", padx=(0, 8))
        self.contact_page_info_var = tk.StringVar(value="Page 1 / 1")
        tk.Label(pager_c, textvariable=self.contact_page_info_var, bg=UI_COLORS["bg"], fg="#334155", font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 8))
        self.btn_contact_next_page = make_styled_button(pager_c, text="Page suiv. ->", command=lambda: self._change_contact_page(1), variant="secondary")  # type: ignore[attr-defined]
        self.btn_contact_next_page.pack(side="left")

        nav_row = tk.Frame(parent, bg=UI_COLORS["bg"])
        nav_row.pack(fill="x", pady=(2, 0))
        make_styled_button(nav_row, text="<- Retour (Étape précédente)", command=self._go_back_from_setup, variant="secondary").pack(side="left")  # type: ignore[attr-defined]
        make_styled_button(nav_row, text="Étape suivante : Exports SMS & Numéros ->", command=self._save_contact_filter_and_continue, variant="primary").pack(side="right")  # type: ignore[attr-defined]
    def _build_page_sms(self) -> None:
        from doc_anonymizer.gui_table_helpers import TreeviewTableHelper
        from doc_anonymizer.gui_widgets import CleanSegmentedTabs

        parent = self.pages["sms"]
        card_sms_import = make_card(
            parent,
            title="Exports SMS / MMS détectés automatiquement (SMS Backup & Restore .xml)",
            subtitle="Les fichiers XML de SMS déposés à l'étape 1 sont rangés automatiquement dans le sous-dossier sms_exports.",
            accent_color="#059669",
        )
        row_sms = tk.Frame(card_sms_import, bg=UI_COLORS["card"])
        row_sms.pack(fill="x")
        make_styled_button(row_sms, text="Voir mes exports SMS", command=self._open_sms_exports_folder, variant="secondary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(row_sms, text="Actualiser la liste", command=self._refresh_sms_number_list, variant="secondary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(row_sms, text="Comment exporter mes SMS ?", command=lambda: self._open_help_dialog(initial_tab=2), variant="secondary").pack(side="right")  # type: ignore[attr-defined]

        self.sms_files_summary_var = tk.StringVar(value="Exports SMS (.xml) détectés : aucun.")
        tk.Label(card_sms_import, textvariable=self.sms_files_summary_var, bg=UI_COLORS["card"], fg="#1d4ed8", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 0))

        card_sms_filter = make_card(
            parent,
            title="Sélectionner les numéros de téléphone à conserver dans vos SMS",
            subtitle="Cliquez sur un entête pour trier • Cliquez sur une ligne pour basculer (Vert = conserver, Rouge = supprimer).",
            accent_color="#2563eb",
        )
        bar = tk.Frame(card_sms_filter, bg=UI_COLORS["card"])
        bar.pack(fill="x")
        self.sms_filter_search_var = tk.StringVar()
        self.ent_sms_search = make_modern_entry(bar, textvariable=None, width=165, placeholder="Filtrer numéro/nom...")
        self.ent_sms_search.pack(side="left", padx=(0, 6))
        for seq in ("<KeyRelease>", "<FocusOut>", "<<Paste>>", "<Control-v>", "<Control-V>"):
            self.ent_sms_search.bind(seq, lambda _e: self.after_idle(self._on_sms_search_typed), add="+")  # type: ignore[attr-defined]

        self.sms_filter_view_var = tk.StringVar(value="Tous")
        self.tabs_sms_view = CleanSegmentedTabs(
            bar,
            options=[("Tous", "Tous"), ("Gardés", "Gardés"), ("Mis de côté", "Mis de côté"), ("Numéros courts", "Numéros courts")],
            variable=self.sms_filter_view_var,
            command=lambda _v: self._on_sms_view_changed(),  # type: ignore[attr-defined]
        )
        self.tabs_sms_view.pack(side="left", padx=(0, 6))
        make_styled_button(bar, text="Garder uniquement ce filtre", command=lambda: self._set_all_sms_numbers_selected(True, exclusive=True), variant="primary").pack(side="left", padx=(0, 4))  # type: ignore[attr-defined]
        make_styled_button(bar, text="Tout cocher", command=lambda: self._set_all_sms_numbers_selected(True, exclusive=False), variant="secondary").pack(side="left", padx=(0, 4))  # type: ignore[attr-defined]
        make_styled_button(bar, text="Désélectionner les numéros courts", command=self._deselect_short_sms_numbers, variant="danger_soft").pack(side="left")  # type: ignore[attr-defined]

        self.sms_filter_summary_var = tk.StringVar(value="0 / 0 numéro(s) SMS conservé(s).")
        tk.Label(card_sms_filter, textvariable=self.sms_filter_summary_var, bg=UI_COLORS["card"], fg="#1d4ed8", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 0))
        table_card = tk.Frame(parent, bg=UI_COLORS["card"], highlightbackground=UI_COLORS["border"], highlightthickness=1, padx=4, pady=4)
        table_card.pack(fill="both", expand=True, pady=(0, 6))
        self.sms_filter_tree = ttk.Treeview(table_card, columns=("keep", "phone", "name", "count"), show="headings", selectmode="browse", style="Modern.Treeview", height=6)
        self.sms_filter_tree.tag_configure("kept", background="#ecfdf5", foreground="#065f46")
        self.sms_filter_tree.tag_configure("ignored", background="#fef2f2", foreground="#991b1b")
        for col_id, lbl, w in (("keep", "STATUT", 130), ("phone", "NUMÉRO DE TÉLÉPHONE", 180), ("name", "CONTACT ASSOCIÉ", 360), ("count", "MESSAGES ▼", 110)):
            self.sms_filter_tree.heading(col_id, text=lbl, command=lambda c=col_id: self._sort_sms_by_column(c))  # type: ignore[attr-defined]
            self.sms_filter_tree.column(col_id, width=w, anchor="center" if col_id in ("keep", "count") else "w")
        sb = ttk.Scrollbar(table_card, orient="vertical", command=self.sms_filter_tree.yview)
        self.sms_filter_tree.configure(yscrollcommand=sb.set)
        self.sms_filter_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        TreeviewTableHelper.bind_trackpad_safe_toggle(self.sms_filter_tree, self._toggle_sms_row_by_id)  # type: ignore[attr-defined]
        self.sms_filter_tree.bind(SPACE_EVENT, self._toggle_selected_sms_filter)  # type: ignore[attr-defined]
        pager_bar = tk.Frame(parent, bg=UI_COLORS["bg"])
        pager_bar.pack(fill="x", pady=(0, 6))
        self.btn_sms_prev_page = make_styled_button(pager_bar, text="<- Page préc.", command=lambda: self._change_sms_page(-1), variant="secondary")  # type: ignore[attr-defined]
        self.btn_sms_prev_page.pack(side="left", padx=(0, 8))
        self.sms_page_info_var = tk.StringVar(value="Page 1 / 1")
        tk.Label(pager_bar, textvariable=self.sms_page_info_var, bg=UI_COLORS["bg"], fg="#334155", font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 8))
        self.btn_sms_next_page = make_styled_button(pager_bar, text="Page suiv. ->", command=lambda: self._change_sms_page(1), variant="secondary")  # type: ignore[attr-defined]
        self.btn_sms_next_page.pack(side="left")

        nav_row = tk.Frame(parent, bg=UI_COLORS["bg"])
        nav_row.pack(fill="x", pady=(2, 0))
        make_styled_button(nav_row, text="<- Retour (Carnets & Contacts)", command=lambda: self._show_page("setup"), variant="secondary").pack(side="left")  # type: ignore[attr-defined]
        make_styled_button(nav_row, text="Étape suivante : Messageries & Chats ->", command=self._save_sms_filter_and_continue, variant="primary").pack(side="right")  # type: ignore[attr-defined]

    def _build_page_chats(self) -> None:
        from doc_anonymizer.gui_table_helpers import TreeviewTableHelper
        from doc_anonymizer.gui_widgets import CleanSegmentedTabs

        parent = self.pages["chats"]
        card_chat_import = make_card(
            parent,
            title="Exports de messageries détectés automatiquement (WhatsApp, Google Chat, Teams, Messenger, Signal)",
            subtitle="Les exports de discussions déposés à l'étape 1 sont rangés automatiquement dans le sous-dossier chat_exports.",
            accent_color="#059669",
        )
        row_chat = tk.Frame(card_chat_import, bg=UI_COLORS["card"])
        row_chat.pack(fill="x")
        make_styled_button(row_chat, text="Voir mes exports de chats", command=self._open_chat_exports_folder, variant="secondary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(row_chat, text="Actualiser la liste", command=self._refresh_chat_filter_list, variant="secondary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(row_chat, text="Comment exporter mes messageries ?", command=lambda: self._open_help_dialog(initial_tab=4), variant="secondary").pack(side="right")  # type: ignore[attr-defined]

        self.chat_files_summary_var = tk.StringVar(value="Exports de messageries détectés : aucun.")
        tk.Label(card_chat_import, textvariable=self.chat_files_summary_var, bg=UI_COLORS["card"], fg="#1d4ed8", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 0))
        card_chat_filter = make_card(
            parent,
            title="Sélectionner les conversations à conserver dans votre dossier",
            subtitle="Cliquez sur un entête pour trier • Cliquez sur une ligne pour basculer (Vert = conserver, Rouge = écarter).",
            accent_color="#2563eb",
        )
        bar = tk.Frame(card_chat_filter, bg=UI_COLORS["card"])
        bar.pack(fill="x")
        self.chat_filter_search_var = tk.StringVar()
        self.ent_chat_search = make_modern_entry(bar, textvariable=None, width=175, placeholder="Filtrer conversation/nom...")
        self.ent_chat_search.pack(side="left", padx=(0, 6))
        for seq in ("<KeyRelease>", "<FocusOut>", "<<Paste>>", "<Control-v>", "<Control-V>"):
            self.ent_chat_search.bind(seq, lambda _e: self.after_idle(self._on_chat_search_typed), add="+")  # type: ignore[attr-defined]

        self.chat_filter_view_var = tk.StringVar(value="Tous")
        self.tabs_chat_view = CleanSegmentedTabs(
            bar,
            options=[("Tous", "Tous"), ("Gardés", "Gardés"), ("Mis de côté", "Mis de côté")],
            variable=self.chat_filter_view_var,
            command=lambda _v: self._on_chat_view_changed(),  # type: ignore[attr-defined]
        )
        self.tabs_chat_view.pack(side="left", padx=(0, 6))
        make_styled_button(bar, text="Garder uniquement ce filtre", command=lambda: self._set_all_chats_selected(True, exclusive=True), variant="primary").pack(side="left", padx=(0, 4))  # type: ignore[attr-defined]
        make_styled_button(bar, text="Tout cocher", command=lambda: self._set_all_chats_selected(True, exclusive=False), variant="secondary").pack(side="left", padx=(0, 4))  # type: ignore[attr-defined]
        make_styled_button(bar, text="Tout décocher (ce filtre)", command=lambda: self._set_all_chats_selected(False), variant="secondary").pack(side="left")  # type: ignore[attr-defined]

        self.chat_filter_summary_var = tk.StringVar(value="0 / 0 conversation(s) conservée(s).")
        tk.Label(card_chat_filter, textvariable=self.chat_filter_summary_var, bg=UI_COLORS["card"], fg="#1d4ed8", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 0))

        table_card = tk.Frame(parent, bg=UI_COLORS["card"], highlightbackground=UI_COLORS["border"], highlightthickness=1, padx=4, pady=4)
        table_card.pack(fill="both", expand=True, pady=(0, 6))
        self.chat_filter_tree = ttk.Treeview(table_card, columns=("keep", "platform", "conversation", "participants", "count"), show="headings", selectmode="browse", style="Modern.Treeview", height=6)
        self.chat_filter_tree.tag_configure("kept", background="#ecfdf5", foreground="#065f46")
        self.chat_filter_tree.tag_configure("ignored", background="#fef2f2", foreground="#991b1b")
        for col_id, lbl, w in (("keep", "STATUT", 110), ("platform", "PLATEFORME", 130), ("conversation", "CONVERSATION", 210), ("participants", "INTERLOCUTEURS", 240), ("count", "MESSAGES ▼", 100)):
            self.chat_filter_tree.heading(col_id, text=lbl, command=lambda c=col_id: self._sort_chats_by_column(c))  # type: ignore[attr-defined]
            self.chat_filter_tree.column(col_id, width=w, anchor="center" if col_id in ("keep", "count") else "w")
        sb = ttk.Scrollbar(table_card, orient="vertical", command=self.chat_filter_tree.yview)
        self.chat_filter_tree.configure(yscrollcommand=sb.set)
        self.chat_filter_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        TreeviewTableHelper.bind_trackpad_safe_toggle(self.chat_filter_tree, self._toggle_chat_row_by_id)  # type: ignore[attr-defined]
        self.chat_filter_tree.bind(SPACE_EVENT, self._toggle_selected_chat_filter)  # type: ignore[attr-defined]

        pager_ch = tk.Frame(parent, bg=UI_COLORS["bg"])
        pager_ch.pack(fill="x", pady=(0, 6))
        self.btn_chat_prev_page = make_styled_button(pager_ch, text="<- Page préc.", command=lambda: self._change_chat_page(-1), variant="secondary")  # type: ignore[attr-defined]
        self.btn_chat_prev_page.pack(side="left", padx=(0, 8))
        self.chat_page_info_var = tk.StringVar(value="Page 1 / 1")
        tk.Label(pager_ch, textvariable=self.chat_page_info_var, bg=UI_COLORS["bg"], fg="#334155", font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 8))
        self.btn_chat_next_page = make_styled_button(pager_ch, text="Page suiv. ->", command=lambda: self._change_chat_page(1), variant="secondary")  # type: ignore[attr-defined]
        self.btn_chat_next_page.pack(side="left")

        nav_row = tk.Frame(parent, bg=UI_COLORS["bg"])
        nav_row.pack(fill="x", pady=(2, 0))
        make_styled_button(nav_row, text="<- Retour (Exports SMS & Numéros)", command=lambda: self._show_page("sms"), variant="secondary").pack(side="left")  # type: ignore[attr-defined]
        make_styled_button(nav_row, text="Étape suivante : Choisir l'objectif ->", command=self._save_chat_filter_and_continue, variant="primary").pack(side="right")  # type: ignore[attr-defined]
