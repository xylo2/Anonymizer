# Commandes pip à exécuter : pip install customtkinter>=5.2.2

import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, List, Tuple
from doc_anonymizer import gui_widgets as _gw
from doc_anonymizer.gui_gate_mixin import GuiGateMixin
from doc_anonymizer.gui_widgets import (
    HAS_CTK,
    UI_COLORS,
    ctk,
    make_styled_button,
    make_widget_keyboard_accessible,
    register_scalable_font,
    scaled_size,
)


class GuiNavigationMixin(GuiGateMixin):
    """Gère la structure visuelle, la navigation latérale et le changement d'écran."""

    controller: Any
    current_ini_var: tk.StringVar
    active_ws_badge_var: tk.StringVar
    mode_badge_var: tk.StringVar
    status_var: tk.StringVar
    workflow_mode: str
    active_page_key: str
    pages: Dict[str, Any]
    nav_buttons: Dict[str, Any]
    nav_container: tk.Frame
    page_heading_var: tk.StringVar

    def _build_layout(self) -> None:
        use_ctk: bool = bool(HAS_CTK and ctk is not None and not _gw.SCREEN_READER_MODE)
        shell = tk.Frame(self, bg=UI_COLORS["bg"])  # type: ignore[arg-type]
        shell.pack(fill="both", expand=True)
        sb_w: int = int(round(268 * max(1.0, _gw.UI_FONT_SCALE)))
        self.sidebar = tk.Frame(shell, bg=UI_COLORS["sidebar"], width=sb_w)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        brand_box = tk.Frame(self.sidebar, bg=UI_COLORS["sidebar"], padx=20, pady=22)
        brand_box.pack(fill="x")
        lbl_b1 = tk.Label(
            brand_box, text="ANONVAULT", bg=UI_COLORS["sidebar"],
            fg="#60a5fa", font=("Segoe UI", scaled_size(9), "bold"),
        )
        lbl_b1.pack(anchor="w")
        register_scalable_font(lbl_b1, "Segoe UI", 9, "bold")
        lbl_b2 = tk.Label(
            brand_box, text="Pièces protégées", bg=UI_COLORS["sidebar"],
            fg="#ffffff", font=("Segoe UI", scaled_size(14), "bold"),
        )
        lbl_b2.pack(anchor="w", pady=(2, 2))
        register_scalable_font(lbl_b2, "Segoe UI", 14, "bold")
        lbl_b3 = tk.Label(
            brand_box, text="Santé • Famille • Prud'hommes",
            bg=UI_COLORS["sidebar"], fg="#94a3b8",
            font=("Segoe UI", scaled_size(8)),
        )
        lbl_b3.pack(anchor="w")
        register_scalable_font(lbl_b3, "Segoe UI", 8, "normal")
        tk.Frame(self.sidebar, bg="#1e293b", height=1).pack(fill="x", padx=16, pady=(0, 12))
        self.nav_container = tk.Frame(self.sidebar, bg=UI_COLORS["sidebar"])
        self.nav_container.pack(fill="x")

        if use_ctk:
            shield_card = ctk.CTkFrame(
                self.sidebar, fg_color="#111827", border_width=1,
                border_color="#1e293b", corner_radius=12,
            )
            shield_card.pack(side="bottom", fill="x", padx=14, pady=16)
            lbl_s1 = ctk.CTkLabel(
                shield_card, text="100 % HORS-LIGNE",
                text_color="#34d399", font=("Segoe UI", scaled_size(10), "bold"),
            )
            lbl_s1.pack(anchor="w", padx=14, pady=(10, 0))
            register_scalable_font(lbl_s1, "Segoe UI", 10, "bold")
            lbl_s2 = ctk.CTkLabel(
                shield_card,
                text="Aucun envoi vers le cloud.\nVos fichiers restent sur ce PC.",
                text_color="#94a3b8", font=("Segoe UI", scaled_size(10)), justify="left",
            )
            lbl_s2.pack(anchor="w", padx=14, pady=(2, 10))
            register_scalable_font(lbl_s2, "Segoe UI", 10, "normal")
        else:
            shield_tk = tk.Frame(
                self.sidebar, bg="#111827", highlightbackground="#1e293b",
                highlightthickness=1, padx=14, pady=12,
            )
            shield_tk.pack(side="bottom", fill="x", padx=14, pady=16)
            lbl_s1_tk = tk.Label(
                shield_tk, text="100 % HORS-LIGNE", bg="#111827",
                fg="#34d399", font=("Segoe UI", scaled_size(8), "bold"),
            )
            lbl_s1_tk.pack(anchor="w")
            register_scalable_font(lbl_s1_tk, "Segoe UI", 8, "bold")
            lbl_s2_tk = tk.Label(
                shield_tk,
                text="Aucun envoi vers le cloud.\nVos fichiers restent sur ce PC.",
                bg="#111827", fg="#94a3b8",
                font=("Segoe UI", scaled_size(8)), justify="left",
            )
            lbl_s2_tk.pack(anchor="w", pady=(2, 0))
            register_scalable_font(lbl_s2_tk, "Segoe UI", 8, "normal")
        main_area = tk.Frame(shell, bg=UI_COLORS["bg"])
        main_area.pack(side="left", fill="both", expand=True)
        top_bar = tk.Frame(main_area, bg="#ffffff", padx=18, pady=10)
        top_bar.pack(fill="x")
        tk.Frame(main_area, bg=UI_COLORS["border"], height=1).pack(fill="x")

        right_controls = tk.Frame(top_bar, bg="#ffffff")
        right_controls.pack(side="right", padx=(10, 0))
        sr_label: str = (
            "Revenir au mode standard" if _gw.SCREEN_READER_MODE else "Lecteur d'écran"
        )
        sr_variant: str = "primary" if _gw.SCREEN_READER_MODE else "secondary"
        self.btn_screen_reader = make_styled_button(
            right_controls, text=sr_label, command=self._toggle_screen_reader_mode,  # type: ignore[attr-defined]
            variant=sr_variant,
            tooltip="Bascule entre le mode lecteur d'écran natif et le mode standard.",
        )
        self.btn_screen_reader.pack(side="right", padx=(6, 0))
        make_styled_button(
            right_controls, text="Paramètres",
            command=self._open_workspace_settings_dialog, variant="secondary",  # type: ignore[attr-defined]
            tooltip="Configurer les dates de naissance, l'OCR, Whisper et les balises.",
        ).pack(side="right", padx=(6, 0))
        make_styled_button(
            right_controls, text="Aide & Exports",
            command=self._show_export_guide_popup, variant="secondary",  # type: ignore[attr-defined]
            tooltip="Affiche comment exporter vos fichiers.",
        ).pack(side="right", padx=(6, 0))
        self.btn_font_up = make_styled_button(
            right_controls, text="A+",
            command=lambda: self._adjust_font_scale(0.1), variant="secondary",  # type: ignore[attr-defined]
            tooltip="Agrandir le texte (Ctrl + +).",
        )
        self.btn_font_up.pack(side="right", padx=(4, 0))
        self.btn_font_down = make_styled_button(
            right_controls, text="A-",
            command=lambda: self._adjust_font_scale(-0.1), variant="secondary",  # type: ignore[attr-defined]
            tooltip="Réduire le texte (Ctrl + -).",
        )
        self.btn_font_down.pack(side="right", padx=(6, 0))
        if use_ctk:
            self.btn_font_up.configure(width=40)
            self.btn_font_down.configure(width=40)
        title_col = tk.Frame(top_bar, bg="#ffffff")
        title_col.pack(side="left", fill="x", expand=True)

        self.page_heading_var = tk.StringVar(value="Engagement de relecture & Licence")
        self.lbl_page_heading = tk.Label(
            title_col, textvariable=self.page_heading_var, bg="#ffffff",
            fg=UI_COLORS["text"], font=("Segoe UI", scaled_size(11), "bold"),
            justify="left", anchor="w", wraplength=540,
        )
        self.lbl_page_heading.pack(anchor="w", fill="x")
        register_scalable_font(self.lbl_page_heading, "Segoe UI", 11, "bold")

        lbl_ws = tk.Label(
            title_col, textvariable=self.active_ws_badge_var, bg="#f1f5f9",
            fg="#1e3a8a", font=("Segoe UI", scaled_size(9), "bold"), padx=8, pady=2,
        )
        lbl_ws.pack(anchor="w", pady=(4, 0))
        register_scalable_font(lbl_ws, "Segoe UI", 9, "bold")

        def _update_heading_wrap(event: Any = None) -> None:
            bar_w: int = getattr(event, "width", 0) or top_bar.winfo_width()
            if bar_w > 200:
                avail: int = max(360, bar_w - right_controls.winfo_reqwidth() - 48)
                self.lbl_page_heading.configure(wraplength=avail)

        top_bar.bind("<Configure>", _update_heading_wrap)

        self.content_container = tk.Frame(main_area, bg=UI_COLORS["bg"], padx=22, pady=16)
        self.content_container.pack(fill="both", expand=True)
        for key in (
            "gate", "documents", "setup", "sms", "chats",
            "duplicates", "mode", "run", "audit", "export", "deanon",
        ):
            self.pages[key] = tk.Frame(self.content_container, bg=UI_COLORS["bg"])
        for build_fn in (
            self._build_page_gate, self._build_page_documents, self._build_page_setup,  # type: ignore[attr-defined]
            self._build_page_sms, self._build_page_chats, self._build_page_duplicates,  # type: ignore[attr-defined]
            self._build_page_mode, self._build_page_run, self._build_page_audit,  # type: ignore[attr-defined]
            self._build_page_export, self._build_page_deanonymize,  # type: ignore[attr-defined]
        ):
            build_fn()

        tk.Frame(main_area, bg=UI_COLORS["border"], height=1).pack(fill="x", side="bottom")
        footer = tk.Frame(main_area, bg="#ffffff", height=30)
        footer.pack(fill="x", side="bottom")
        lbl_st = tk.Label(
            footer, textvariable=self.status_var, bg="#ffffff",
            fg=UI_COLORS["muted"], font=("Segoe UI", scaled_size(8)),
        )
        lbl_st.pack(side="left", padx=20, pady=5)
        register_scalable_font(lbl_st, "Segoe UI", 8, "normal")
    def _rebuild_sidebar_nav(self) -> None:
        use_ctk: bool = bool(HAS_CTK and ctk is not None and not _gw.SCREEN_READER_MODE)
        for child in self.nav_container.winfo_children():
            child.destroy()
        self.nav_buttons.clear()
        has_workspace: bool = bool(self.current_ini_var.get())
        nav_items: List[Tuple[str, str, str]] = [
            ("gate", "0", "Accueil & Dossier"),
            ("documents", "1", "Déposer mes pièces"),
            ("setup", "2", "Carnets & Contacts"),
            ("sms", "3", "Exports SMS & Numéros"),
            ("chats", "4", "Messageries & Chats"),
            ("mode", "5", "Choisir l'objectif"),
        ]
        if self.workflow_mode == "lawyer":
            nav_items.extend([
                ("run", "6", "Extraire & Classer"),
                ("export", "7", "Pack Avocat Nominatif"),
                ("deanon", "8", "Désanonymiser retour IA"),
            ])
        else:
            nav_items.extend([
                ("run", "6", "Analyser & Anonymiser"),
                ("audit", "7", "Vérifier les noms"),
                ("export", "8", "Récupérer & Requêtes IA"),
                ("deanon", "9", "Désanonymiser retour IA"),
            ])

        for key, step_num, label in nav_items:
            enabled: bool = key == "gate" or has_workspace
            is_active: bool = (
                key == self.active_page_key
                or (key == "documents" and self.active_page_key == "duplicates")
            ) and enabled
            act_cmd = (lambda k=key: self._show_page(k)) if enabled else None
            w_str: str = "bold" if is_active else "normal"
            if use_ctk:
                fg_c: str = (
                    "#ffffff" if is_active else ("#e2e8f0" if enabled else "#64748b")
                )
                btn_ctk = ctk.CTkButton(
                    self.nav_container, text=f"  {step_num}   {label}", anchor="w",
                    fg_color=UI_COLORS["sidebar_active"] if is_active else "transparent",
                    hover_color=UI_COLORS["sidebar_active"] if is_active else UI_COLORS["sidebar_hover"],
                    text_color=fg_c, text_color_disabled="#64748b", corner_radius=10,
                    height=max(36, int(round(36 * _gw.UI_FONT_SCALE))),
                    state="normal" if enabled else "disabled",
                    font=("Segoe UI", scaled_size(11), w_str), command=act_cmd,
                )
                register_scalable_font(btn_ctk, "Segoe UI", 11, w_str)
                if enabled:
                    make_widget_keyboard_accessible(btn_ctk, command=act_cmd)
                btn_ctk.pack(fill="x", padx=12, pady=2)
                self.nav_buttons[key] = btn_ctk
            else:
                fg_tk: str = (
                    "#ffffff" if is_active else ("#e2e8f0" if enabled else "#94a3b8")
                )
                btn = tk.Button(
                    self.nav_container, text=f"  {step_num}. {label}", anchor="w",
                    bg=UI_COLORS["sidebar_active"] if is_active else UI_COLORS["sidebar"],
                    fg=fg_tk, disabledforeground="#64748b",
                    activebackground=UI_COLORS["sidebar_hover"] if enabled else UI_COLORS["sidebar"],
                    activeforeground=fg_tk, relief="flat", bd=0, padx=12, pady=7,
                    state="normal" if enabled else "disabled",
                    cursor="hand2" if enabled else "arrow",
                    font=("Segoe UI", scaled_size(9), w_str), command=act_cmd,
                )
                register_scalable_font(btn, "Segoe UI", 9, w_str)
                if enabled:
                    make_widget_keyboard_accessible(btn, command=act_cmd)
                btn.pack(fill="x", padx=10, pady=2)
                self.nav_buttons[key] = btn

    def _show_page(self, key: str) -> None:
        if key != "gate" and not self.current_ini_var.get():
            key = "gate"
        export_title: str = (
            "Étape 7 — Générer le Pack Avocat Nominatif"
            if self.workflow_mode == "lawyer"
            else "Étape 8 — Récupérer les fichiers anonymisés & Requêtes IA"
        )
        titles = {
            "gate": "Vigilance Humaine, Licence (GNU GPL v3) & Choix du Dossier",
            "documents": "Étape 1 — Déposer toutes mes pièces (contacts, SMS, chats et documents)",
            "duplicates": "Étape 1 bis — Fichiers identiques détectés (choisir les doublons à ignorer)",
            "setup": "Étape 2 — Vérifier les carnets détectés et sélectionner les contacts à garder",
            "sms": "Étape 3 — Vérifier les exports SMS détectés et filtrer les numéros",
            "chats": "Étape 4 — Vérifier les exports de messageries et sélectionner les conversations",
            "mode": "Étape 5 — Choisir votre objectif : Pré-analyse IA ou Dossier Avocat",
            "run": "Étape 6 — Extraction et traitement des documents",
            "audit": "Étape 7 — Vérifier les noms restants (Avant / Après)",
            "export": export_title,
            "deanon": "Désanonymisation — Remettre les vraies identités dans l'analyse de l'IA",
        }
        self.active_page_key = key
        self._rebuild_sidebar_nav()
        self.page_heading_var.set(titles.get(key, ""))
        for k, frame in self.pages.items():
            frame.pack(fill="both", expand=True) if k == key else frame.pack_forget()
        if key == "gate":
            self._refresh_gate_workspace_panel()
        elif key == "documents":
            self._refresh_workspace_counters()  # type: ignore[attr-defined]
        elif key == "setup":
            self._update_setup_mode_visibility()
        elif key == "sms":
            self._refresh_sms_number_list()  # type: ignore[attr-defined]
        elif key == "chats":
            self._refresh_chat_filter_list()  # type: ignore[attr-defined]
        elif key == "duplicates":
            self._refresh_duplicate_filter_list()  # type: ignore[attr-defined]
        elif key == "run":
            self._refresh_dashboard_cards()  # type: ignore[attr-defined]
        elif key == "export":
            self._update_export_mode_visibility()  # type: ignore[attr-defined]
        elif key == "deanon":
            self._sync_archived_deanon_files()  # type: ignore[attr-defined]

    def _set_workflow_mode(self, mode: str, navigate: bool = True) -> None:
        if not self.current_ini_var.get():
            self._show_page("gate")
            return
        self.workflow_mode = "lawyer" if mode == "lawyer" else "ia"
        self.mode_badge_var.set(
            "Mode : Avocat (Nominatif)"
            if self.workflow_mode == "lawyer"
            else "Mode : IA (Anonymisé)"
        )
        if navigate:
            self._show_page("run")

    def _quit_politely(self) -> None:
        messagebox.showinfo(
            "Fermeture de l'application",
            "Merci de votre visite.\n\nAucun fichier n'a été lu ni modifié. "
            "L'application va maintenant se fermer.",
        )
        self._on_close_requested()  # type: ignore[attr-defined]

    def _update_setup_mode_visibility(self) -> None:
        self._refresh_workspace_counters()  # type: ignore[attr-defined]
        self._refresh_contact_filter_list()  # type: ignore[attr-defined]
