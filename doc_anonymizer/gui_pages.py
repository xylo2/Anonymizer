# Commandes pip à exécuter : pip install customtkinter>=5.2.2

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List
from doc_anonymizer import gui_widgets as _gw
from doc_anonymizer.gui_pages_filters import GuiPagesFiltersMixin
from doc_anonymizer.gui_pages_secondary import GuiSecondaryPagesMixin
from doc_anonymizer.gui_widgets import (
    HAS_CTK, UI_COLORS, ctk, make_card, make_modern_dropdown,
    make_modern_entry, make_styled_button, register_scalable_font,
    scaled_size,
)


class GuiPagesMixin(GuiPagesFiltersMixin, GuiSecondaryPagesMixin):
    """Construit les écrans d'accueil (0) et de dépôt des pièces (1)."""

    pages: Dict[str, Any]
    gate_action_var: tk.StringVar
    gate_existing_var: tk.StringVar
    gate_new_name_var: tk.StringVar
    docs_summary_var: tk.StringVar
    zip_warning_var: tk.StringVar

    def _build_page_gate(self) -> None:
        use_ctk: bool = bool(HAS_CTK and ctk is not None and not _gw.SCREEN_READER_MODE)
        page = self.pages["gate"]
        card_license = make_card(
            page,
            title="Engagement de vigilance humaine & Licence (GNU GPL v3)",
            subtitle="Logiciel libre et gratuit (GNU General Public License v3.0 — sans aucune garantie).",
            accent_color="#d97706",
        )
        msg_warn: str = (
            "ATTENTION — RELECTURE HUMAINE OBLIGATOIRE AVANT TOUT ENVOI :\n"
            "Cet outil automatise la préparation et le masquage des données personnelles, mais aucune "
            "détection automatique n'est infaillible (fautes de frappe, écriture manuscrite, pièces scannées). "
            "Vous devez impérativement relire l'intégralité des fichiers générés avant de les transmettre "
            "à une intelligence artificielle ou à un tiers. L'auteur décline toute responsabilité en cas "
            "de divulgation résiduelle d'informations personnelles."
        )
        banner = tk.Frame(card_license, bg="#fffbeb", highlightbackground="#f59e0b", highlightthickness=1, padx=12, pady=8)
        banner.pack(fill="x", pady=(2, 0))
        lbl_b = tk.Label(
            banner, text=msg_warn, bg="#fffbeb", fg="#78350f",
            font=("Segoe UI", scaled_size(9)), justify="left", anchor="w", wraplength=740,
        )
        lbl_b.pack(anchor="w", fill="x")
        register_scalable_font(lbl_b, "Segoe UI", 9, "normal")
        card_license.bind(
            "<Configure>",
            lambda e, lbl=lbl_b: lbl.configure(wraplength=max(320, e.width - 56)) if getattr(e, "width", 0) > 120 else None,
        )
        card_ws = make_card(
            page,
            title="Choix obligatoire du dossier de travail (affaire isolée)",
            subtitle="Chaque affaire possède son propre espace isolé sous dossiers/<nom>/.",
            accent_color=UI_COLORS["primary"],
        )
        self.gate_action_var = tk.StringVar(value="create")
        self.seg_gate_action = tk.Frame(card_ws, bg=UI_COLORS["tab_rail"], padx=3, pady=3)
        self.btn_tab_open = tk.Button(
            self.seg_gate_action, text="Ouvrir un dossier existant",
            relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
            font=("Segoe UI", scaled_size(9), "bold"),
            command=lambda: self._on_gate_segment_changed("open"),  # type: ignore[attr-defined]
        )
        self.btn_tab_open.pack(side="left", padx=(0, 3))
        register_scalable_font(self.btn_tab_open, "Segoe UI", 9, "bold")
        self.btn_tab_create = tk.Button(
            self.seg_gate_action, text="Créer un nouveau dossier",
            relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
            font=("Segoe UI", scaled_size(9), "bold"),
            command=lambda: self._on_gate_segment_changed("create"),  # type: ignore[attr-defined]
        )
        self.btn_tab_create.pack(side="left")
        register_scalable_font(self.btn_tab_create, "Segoe UI", 9, "bold")

        self.frame_gate_existing = tk.Frame(card_ws, bg=UI_COLORS["card"])
        lbl_ex = tk.Label(
            self.frame_gate_existing, text="Dossier existant à ouvrir :",
            bg=UI_COLORS["card"], fg=UI_COLORS["text"],
            font=("Segoe UI", scaled_size(9), "bold"),
        )
        lbl_ex.pack(anchor="w", pady=(0, 4))
        register_scalable_font(lbl_ex, "Segoe UI", 9, "bold")
        self.gate_existing_var = tk.StringVar()
        self.combo_gate_ws = make_modern_dropdown(self.frame_gate_existing, self.gate_existing_var, [], width=340)
        self.combo_gate_ws.pack(anchor="w")

        self.frame_gate_create = tk.Frame(card_ws, bg=UI_COLORS["card"])
        lbl_nw = tk.Label(
            self.frame_gate_create, text="Nom du nouveau dossier (obligatoire) :",
            bg=UI_COLORS["card"], fg=UI_COLORS["text"],
            font=("Segoe UI", scaled_size(9), "bold"),
        )
        lbl_nw.pack(anchor="w", pady=(0, 4))
        register_scalable_font(lbl_nw, "Segoe UI", 9, "bold")
        self.gate_new_name_var = tk.StringVar()
        self.entry_gate_new = make_modern_entry(
            self.frame_gate_create, textvariable=self.gate_new_name_var,
            width=360, placeholder="Ex: Prudhommes_2026 ou Famille_JAF",
        )
        self.ent_gate_new = self.entry_gate_new
        self.entry_gate_new.pack(anchor="w")
        self.entry_gate_new.bind("<Return>", lambda _e: self._confirm_gate_and_workspace())  # type: ignore[attr-defined]

        actions = tk.Frame(page, bg=UI_COLORS["bg"])
        actions.pack(fill="x", pady=(6, 0))
        make_styled_button(actions, text="Je refuse et je quitte l'application", command=self._quit_politely, variant="danger_soft").pack(side="left")  # type: ignore[attr-defined]
        if use_ctk:
            self.btn_accept_gate = ctk.CTkButton(
                actions, text="J'ai compris, je relirai les fichiers — Continuer ->",
                command=self._confirm_gate_and_workspace, fg_color=UI_COLORS["success"],  # type: ignore[attr-defined]
                hover_color=UI_COLORS["success_hover"], text_color="#ffffff",
                corner_radius=10, height=40, font=("Segoe UI", scaled_size(11), "bold"),
            )
            register_scalable_font(self.btn_accept_gate, "Segoe UI", 11, "bold")
            self.btn_accept_gate.pack(side="right")
        else:
            self.btn_accept_gate = make_styled_button(
                actions, text="J'ai compris, je relirai les fichiers — Continuer ->",
                command=self._confirm_gate_and_workspace, variant="success",  # type: ignore[attr-defined]
            )
            self.btn_accept_gate.pack(side="right")
    def _build_page_documents(self) -> None:
        use_ctk: bool = bool(HAS_CTK and ctk is not None and not _gw.SCREEN_READER_MODE)
        page = self.pages["documents"]
        card_d = make_card(
            page,
            title="Étape 1 — Déposer ou référencer toutes vos pièces",
            subtitle="Glissez vos fichiers/dossiers ici ou utilisez les boutons ci-dessous (lecture seule sans copie sur PC, copie proposée sur clé USB).",
            accent_color=UI_COLORS["primary"],
        )
        self.docs_summary_var = tk.StringVar(value="Pièces de l'affaire : 0 fichier(s).")
        lbl_sum = tk.Label(
            card_d, textvariable=self.docs_summary_var,
            bg=UI_COLORS["card"], fg=UI_COLORS["text"],
            font=("Segoe UI", scaled_size(10), "bold"),
        )
        lbl_sum.pack(anchor="w", pady=(0, 8))
        register_scalable_font(lbl_sum, "Segoe UI", 10, "bold")

        btn_row = tk.Frame(card_d, bg=UI_COLORS["card"])
        btn_row.pack(fill="x", pady=(0, 8))
        make_styled_button(btn_row, text="+ Ajouter des fichiers", command=self._link_external_files, variant="primary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(btn_row, text="+ Ajouter un dossier", command=self._link_external_folder, variant="secondary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(btn_row, text="Ouvrir le dossier interne", command=lambda: self._open_workspace_folder("sources_dir"), variant="secondary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(btn_row, text="Guide des exports...", command=self._show_export_guide_popup, variant="secondary").pack(side="left")  # type: ignore[attr-defined]

        self.docs_busy_var = tk.StringVar(value="")
        self.docs_busy_frame = tk.Frame(card_d, bg="#eff6ff", highlightbackground="#93c5fd", highlightthickness=1, padx=10, pady=6)
        self.docs_busy_bar = ttk.Progressbar(self.docs_busy_frame, mode="indeterminate", length=200)
        self.docs_busy_bar.pack(side="left", padx=(0, 10))
        lbl_busy = tk.Label(
            self.docs_busy_frame, textvariable=self.docs_busy_var,
            bg="#eff6ff", fg="#1e3a8a", font=("Segoe UI", scaled_size(9), "bold"),
        )
        lbl_busy.pack(side="left")
        register_scalable_font(lbl_busy, "Segoe UI", 9, "bold")

        lbl_lnk = tk.Label(
            card_d, text="Emplacements externes référencés (lus sur place sans copie) :",
            bg=UI_COLORS["card"], fg=UI_COLORS["muted"],
            font=("Segoe UI", scaled_size(9), "bold"),
        )
        lbl_lnk.pack(anchor="w", pady=(4, 4))
        register_scalable_font(lbl_lnk, "Segoe UI", 9, "bold")
        self.links_listbox = tk.Listbox(
            card_d, height=6, font=("Consolas", scaled_size(9)),
            bg="#f8fafc", fg=UI_COLORS["text"], relief="solid", bd=1,
            selectbackground="#dbeafe", selectforeground="#1e3a8a",
        )
        self.links_listbox.pack(fill="both", expand=True)
        register_scalable_font(self.links_listbox, "Consolas", 9, "normal")

        lnk_bar = tk.Frame(card_d, bg=UI_COLORS["card"])
        lnk_bar.pack(fill="x", pady=(6, 0))
        make_styled_button(lnk_bar, text="Ouvrir l'emplacement sélectionné", command=self._open_selected_linked_source, variant="secondary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(lnk_bar, text="Retirer la référence", command=self._remove_selected_linked_source, variant="danger_soft").pack(side="left")  # type: ignore[attr-defined]

        self.zip_warning_var = tk.StringVar(value="")
        self.lbl_zip_warning = tk.Label(
            card_d, textvariable=self.zip_warning_var,
            bg=UI_COLORS["warning_bg"], fg=UI_COLORS["warning_fg"],
            font=("Segoe UI", scaled_size(9), "bold"), padx=12, pady=8,
            justify="left", anchor="w", wraplength=740,
        )
        register_scalable_font(self.lbl_zip_warning, "Segoe UI", 9, "bold")

        nav_d = tk.Frame(page, bg=UI_COLORS["bg"])
        nav_d.pack(fill="x", pady=(6, 0))
        make_styled_button(nav_d, text="<- Changer de dossier", command=lambda: self._show_page("gate"), variant="secondary").pack(side="left")  # type: ignore[attr-defined]
        if use_ctk:
            btn_next_d = ctk.CTkButton(
                nav_d, text="Continuer vers les contacts ->",
                command=self._advance_from_documents, fg_color=UI_COLORS["primary"],  # type: ignore[attr-defined]
                hover_color=UI_COLORS["primary_hover"], text_color="#ffffff",
                corner_radius=10, height=40, font=("Segoe UI", scaled_size(11), "bold"),
            )
            register_scalable_font(btn_next_d, "Segoe UI", 11, "bold")
            btn_next_d.pack(side="right")
        else:
            make_styled_button(nav_d, text="Continuer vers les contacts ->", command=self._advance_from_documents, variant="primary").pack(side="right")  # type: ignore[attr-defined]

    def _go_back_from_setup(self) -> None:
        if getattr(self, "duplicate_filter_items", None):
            self._show_page("duplicates")  # type: ignore[attr-defined]
        else:
            self._show_page("documents")  # type: ignore[attr-defined]

    def _open_manual_contacts_editor(self) -> None:
        ini_path: str = self.current_ini_var.get()  # type: ignore[attr-defined]
        if not ini_path:
            return
        man_path: str = self.controller.ensure_manual_contacts_file(ini_path)  # type: ignore[attr-defined]
        self._open_path_in_os(man_path)  # type: ignore[attr-defined]
