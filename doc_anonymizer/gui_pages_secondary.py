# Commandes pip à exécuter : pip install customtkinter>=5.2.2

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict
from doc_anonymizer import gui_widgets as _gw
from doc_anonymizer.gui_deanon_page_mixin import GuiDeanonPageMixin
from doc_anonymizer.gui_widgets import (
    HAS_CTK,
    UI_COLORS,
    ctk,
    make_card,
    make_modern_dropdown,
    make_modern_entry,
    make_stat_tile,
    make_styled_button,
    register_scalable_font,
)


class GuiSecondaryPagesMixin(GuiDeanonPageMixin):
    """Écrans doublons, mode, traitement, audit, export, désanonymisation."""

    pages: Dict[str, Any]
    controller: Any

    def _build_page_duplicates(self) -> None:
        from doc_anonymizer.gui_table_helpers import TreeviewTableHelper

        parent = self.pages["duplicates"]
        top = make_card(
            parent,
            title="Fichiers identiques détectés (doublons binaires stricts)",
            subtitle="Cliquez sur une ligne pour basculer (Vert = garder, Rouge = ignorer). Survolez une ligne pour voir le chemin complet.",
            accent_color="#d97706",
        )
        self.dup_filter_summary_var = tk.StringVar(value="0 doublon(s).")
        tk.Label(
            top, textvariable=self.dup_filter_summary_var,
            bg=UI_COLORS["card"], fg="#1d4ed8", font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        bar = tk.Frame(top, bg=UI_COLORS["card"])
        bar.pack(fill="x")
        tk.Label(
            bar, text="Dossier :", bg=UI_COLORS["card"],
            fg=UI_COLORS["text"], font=("Segoe UI", 8, "bold"),
        ).pack(side="left", padx=(0, 6))
        self.dup_priority_folder_var = tk.StringVar(value="Aucun sous-dossier")
        self.combo_dup_folder = make_modern_dropdown(
            bar, self.dup_priority_folder_var, ["Aucun sous-dossier"], width=180
        )
        self.combo_dup_folder.pack(side="left", padx=(0, 6))
        make_styled_button(
            bar, text="Garder en priorité",
            command=self._prioritize_duplicate_folder,  # type: ignore[attr-defined]
            variant="primary",
        ).pack(side="left", padx=(0, 6))
        make_styled_button(
            bar, text="Ignorer ce dossier",
            command=self._ignore_duplicate_folder,  # type: ignore[attr-defined]
            variant="danger_soft",
        ).pack(side="left", padx=(0, 6))
        make_styled_button(
            bar, text="1 copie / groupe",
            command=self._reset_default_duplicates_selection,  # type: ignore[attr-defined]
            variant="secondary",
        ).pack(side="right")
        table_card = tk.Frame(
            parent, bg=UI_COLORS["card"],
            highlightbackground=UI_COLORS["border"],
            highlightthickness=1, padx=4, pady=4,
        )
        table_card.pack(fill="both", expand=True, pady=(0, 8))
        cols = ("keep", "group", "filename", "size", "path")
        self.duplicate_filter_tree = ttk.Treeview(
            table_card, columns=cols, show="headings",
            selectmode="browse", style="Modern.Treeview", height=8,
        )
        headers = (
            ("keep", "STATUT", 100),
            ("group", "GROUPE", 100),
            ("filename", "FICHIER", 220),
            ("size", "TAILLE", 85),
            ("path", "EMPLACEMENT (ABRÉGÉ)", 330),
        )
        for col_id, lbl, w in headers:
            self.duplicate_filter_tree.heading(col_id, text=lbl)
            anc = "center" if col_id in ("keep", "group", "size") else "w"
            self.duplicate_filter_tree.column(col_id, width=w, anchor=anc)
        sb = ttk.Scrollbar(
            table_card, orient="vertical",
            command=self.duplicate_filter_tree.yview,
        )
        self.duplicate_filter_tree.configure(yscrollcommand=sb.set)
        self.duplicate_filter_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        TreeviewTableHelper.bind_trackpad_safe_toggle(
            self.duplicate_filter_tree,
            self._toggle_duplicate_row_by_id,  # type: ignore[attr-defined]
        )
        self.duplicate_filter_tree.bind(
            "<space>", self._toggle_selected_duplicate_filter  # type: ignore[attr-defined]
        )
        self._bind_duplicate_hover_tooltip()  # type: ignore[attr-defined]

        nav_row = tk.Frame(parent, bg=UI_COLORS["bg"])
        nav_row.pack(fill="x", pady=(2, 0))
        make_styled_button(
            nav_row, text="<- Retour (Déposer mes pièces)",
            command=lambda: self._show_page("documents"), variant="secondary",  # type: ignore[attr-defined]
        ).pack(side="left")
        make_styled_button(
            nav_row, text="Continuer vers Carnets & Contacts ->",
            command=self._save_duplicates_and_continue, variant="primary",  # type: ignore[attr-defined]
        ).pack(side="right")

    def _go_back_from_setup(self) -> None:
        ini_path: str = getattr(self, "current_ini_var", tk.StringVar()).get()
        dups = self.controller.load_duplicate_file_items(ini_path) if ini_path else []
        if dups:
            self.duplicate_filter_items = dups  # type: ignore[attr-defined]
            self._show_page("duplicates")  # type: ignore[attr-defined]
        else:
            self._show_page("documents")  # type: ignore[attr-defined]
    def _build_page_mode(self) -> None:
        use_ctk = bool(HAS_CTK and ctk is not None and not _gw.SCREEN_READER_MODE)
        parent = self.pages["mode"]
        grid = tk.Frame(parent, bg=UI_COLORS["bg"])
        grid.pack(fill="both", expand=True, pady=(0, 8))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        ia_desc: str = (
            "• Masque identités, téléphones, e-mails, NIR et IBAN.\n"
            "• Audit humain Avant/Après inclus.\n"
            "• Désanonymisation automatique du retour de l'IA."
        )
        law_desc: str = (
            "• Conserve tous les vrais noms, dates et lieux.\n"
            "• OCR sur les images + transcription des audios.\n"
            "• Génère un recueil chronologique numéroté."
        )
        if use_ctk and ctk is not None:
            left = ctk.CTkFrame(
                grid, fg_color="#ffffff", border_width=2,
                border_color="#2563eb", corner_radius=14,
            )
            left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
            ctk.CTkLabel(
                left, text="OPTION A — PRÉ-ANALYSE PAR UNE IA",
                text_color="#2563eb", font=("Segoe UI", 10, "bold"),
            ).pack(anchor="w", padx=18, pady=(14, 0))
            ctk.CTkLabel(
                left, text="Mode Anonymisé (Protégé)",
                text_color="#0f172a", font=("Segoe UI", 14, "bold"),
            ).pack(anchor="w", padx=18, pady=(2, 8))
            ctk.CTkLabel(
                left, text=ia_desc, text_color="#334155",
                font=("Segoe UI", 10), justify="left", wraplength=350,
            ).pack(anchor="w", padx=18, pady=(0, 14))
            make_styled_button(
                left, text="Choisir le Mode IA (Anonymisé) ->",
                command=lambda: self._set_workflow_mode("ia", navigate=True),  # type: ignore[attr-defined]
                variant="primary",
            ).pack(anchor="w", padx=18, pady=(0, 16))

            right = ctk.CTkFrame(
                grid, fg_color="#ffffff", border_width=2,
                border_color="#059669", corner_radius=14,
            )
            right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
            ctk.CTkLabel(
                right, text="OPTION B — TRANSMETTRE À MON AVOCAT",
                text_color="#059669", font=("Segoe UI", 10, "bold"),
            ).pack(anchor="w", padx=18, pady=(14, 0))
            ctk.CTkLabel(
                right, text="Mode Nominatif (Vrais noms)",
                text_color="#0f172a", font=("Segoe UI", 14, "bold"),
            ).pack(anchor="w", padx=18, pady=(2, 8))
            ctk.CTkLabel(
                right, text=law_desc, text_color="#334155",
                font=("Segoe UI", 10), justify="left", wraplength=350,
            ).pack(anchor="w", padx=18, pady=(0, 14))
            make_styled_button(
                right, text="Choisir le Mode Avocat (Nominatif) ->",
                command=lambda: self._set_workflow_mode("lawyer", navigate=True),  # type: ignore[attr-defined]
                variant="success",
            ).pack(anchor="w", padx=18, pady=(0, 16))
        else:
            left_tk = tk.Frame(
                grid, bg=UI_COLORS["card"], highlightbackground="#2563eb",
                highlightthickness=2, padx=16, pady=14,
            )
            left_tk.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
            tk.Label(left_tk, text="OPTION A — PRÉ-ANALYSE PAR UNE IA", bg=UI_COLORS["card"], fg="#2563eb", font=("Segoe UI", 9, "bold")).pack(anchor="w")
            tk.Label(left_tk, text="Mode Anonymisé (Protégé)", bg=UI_COLORS["card"], fg="#0f172a", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(2, 6))
            tk.Label(left_tk, text=ia_desc, bg=UI_COLORS["card"], fg="#334155", font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(0, 12))
            make_styled_button(
                left_tk, text="Choisir le Mode IA (Anonymisé) ->",
                command=lambda: self._set_workflow_mode("ia", navigate=True),  # type: ignore[attr-defined]
                variant="primary",
            ).pack(anchor="w")

            right_tk = tk.Frame(
                grid, bg=UI_COLORS["card"], highlightbackground="#059669",
                highlightthickness=2, padx=16, pady=14,
            )
            right_tk.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
            tk.Label(right_tk, text="OPTION B — TRANSMETTRE À MON AVOCAT", bg=UI_COLORS["card"], fg="#059669", font=("Segoe UI", 9, "bold")).pack(anchor="w")
            tk.Label(right_tk, text="Mode Nominatif (Vrais noms)", bg=UI_COLORS["card"], fg="#0f172a", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(2, 6))
            tk.Label(right_tk, text=law_desc, bg=UI_COLORS["card"], fg="#334155", font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(0, 12))
            make_styled_button(
                right_tk, text="Choisir le Mode Avocat (Nominatif) ->",
                command=lambda: self._set_workflow_mode("lawyer", navigate=True),  # type: ignore[attr-defined]
                variant="success",
            ).pack(anchor="w")
        nav_mode = tk.Frame(parent, bg=UI_COLORS["bg"])
        nav_mode.pack(fill="x", pady=(2, 0))
        make_styled_button(
            nav_mode, text="<- Retour (Messageries & Chats)",
            command=lambda: self._show_page("chats"), variant="secondary",  # type: ignore[attr-defined]
        ).pack(side="left")
    def _build_page_run(self) -> None:
        parent = self.pages["run"]
        card = make_card(
            parent,
            title="Lancer le traitement et suivre la protection en temps réel",
            subtitle="Cliquez sur le bouton principal. Les compteurs évoluent en direct.",
            accent_color="#2563eb",
        )
        btn_row = tk.Frame(card, bg=UI_COLORS["card"])
        btn_row.pack(fill="x", pady=(0, 8))
        self.btn_main_run = make_styled_button(
            btn_row, text="Lancer l'extraction et l'anonymisation",
            command=self._start_primary_workflow_job, variant="primary",  # type: ignore[attr-defined]
        )
        self.btn_main_run.pack(side="left", padx=(0, 8))
        self.btn_fast_reanon = make_styled_button(
            btn_row, text="Ré-anonymiser uniquement",
            command=lambda: self._start_job("anonymize_only"), variant="secondary",  # type: ignore[attr-defined]
        )
        self.btn_fast_reanon.pack(side="left", padx=(0, 8))
        self.btn_stop = make_styled_button(
            btn_row, text="Arrêter",
            command=self._stop_current_job, variant="secondary",  # type: ignore[attr-defined]
        )
        self.btn_stop.pack(side="left")
        make_styled_button(
            btn_row, text="Journal technique",
            command=self._toggle_log_panel, variant="secondary",  # type: ignore[attr-defined]
        ).pack(side="right")

        self.run_progress_label_var = tk.StringVar(
            value="Prêt à démarrer le traitement."
        )
        tk.Label(
            card, textvariable=self.run_progress_label_var,
            bg=UI_COLORS["card"], fg="#1d4ed8", font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", pady=(0, 4))
        self.progress = ttk.Progressbar(card, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 10))
        self.dash_zip_var = tk.StringVar(value="")
        self.lbl_dash_zip = tk.Label(
            card, textvariable=self.dash_zip_var,
            bg=UI_COLORS["warning_bg"], fg=UI_COLORS["warning_fg"],
            font=("Segoe UI", 9, "bold"), padx=12, pady=8,
            justify="left", wraplength=780,
        )
        tiles_grid = tk.Frame(parent, bg=UI_COLORS["bg"])
        tiles_grid.pack(fill="x", pady=(0, 10))
        for i in range(5):
            tiles_grid.columnconfigure(i, weight=1)
        keys = ("docs", "names", "coords", "ids", "locs")
        self.stat_vars = {k: tk.StringVar(value="0") for k in keys}
        tiles_meta = [
            ("docs", "Documents traités", "#1d4ed8", "#eff6ff"),
            ("names", "Identités protégées", "#047857", "#ecfdf5"),
            ("coords", "Tél. / E-mails", "#6d28d9", "#f5f3ff"),
            ("ids", "NIR / IBAN / Réf.", "#b45309", "#fffbeb"),
            ("locs", "Lieux / Dates", "#0f766e", "#f0fdfa"),
        ]
        for idx, (k, lbl, acc, bg_c) in enumerate(tiles_meta):
            tile = make_stat_tile(tiles_grid, self.stat_vars[k], lbl, acc, bg_c)
            px_l = 0 if idx == 0 else 4
            px_r = 0 if idx == 4 else 4
            tile.grid(row=0, column=idx, sticky="nsew", padx=(px_l, px_r))
        self.log_text = tk.Text(
            parent, height=7, bg=UI_COLORS["log_bg"], fg=UI_COLORS["log_fg"],
            font=("Consolas", 9), state="disabled", relief="flat", padx=10, pady=8,
        )
        nav_row = tk.Frame(parent, bg=UI_COLORS["bg"])
        nav_row.pack(fill="x", pady=(4, 0))
        make_styled_button(
            nav_row, text="<- Retour (Choisir l'objectif)",
            command=lambda: self._show_page("mode"), variant="secondary",  # type: ignore[attr-defined]
        ).pack(side="left")
        self.btn_after_run_next = make_styled_button(
            nav_row, text="Étape suivante ->",
            command=self._go_to_step_after_run, variant="primary",  # type: ignore[attr-defined]
        )
        self.btn_after_run_next.pack(side="right")

    def _build_page_audit(self) -> None:
        parent = self.pages["audit"]
        top = make_card(
            parent,
            title="Contrôle qualité humain — Vérifier les noms propres restants",
            subtitle="Entrée = Avant/Après, M = Masquer, I = Ignorer.",
            accent_color="#2563eb",
        )
        bar = tk.Frame(top, bg=UI_COLORS["card"])
        bar.pack(fill="x")
        self.audit_count_var = tk.StringVar(value="0 élément(s) à vérifier.")
        tk.Label(
            bar, textvariable=self.audit_count_var,
            bg=UI_COLORS["card"], fg="#1d4ed8", font=("Segoe UI", 9, "bold"),
        ).pack(side="left")
        make_styled_button(
            bar, text="Voir dans le document (Avant / Après)",
            command=self._open_before_after_preview, variant="primary",  # type: ignore[attr-defined]
        ).pack(side="right", padx=(6, 0))
        make_styled_button(
            bar, text="Actualiser",
            command=self._refresh_audit_list, variant="secondary",  # type: ignore[attr-defined]
        ).pack(side="right")
        table_card = tk.Frame(
            parent, bg=UI_COLORS["card"],
            highlightbackground=UI_COLORS["border"],
            highlightthickness=1, padx=4, pady=4,
        )
        table_card.pack(fill="both", expand=True, pady=(0, 10))
        self.audit_tree = ttk.Treeview(
            table_card, columns=("occ", "candidate", "alias"),
            show="headings", selectmode="browse", style="Modern.Treeview", height=7,
        )
        self.audit_tree.heading("occ", text="OCC.")
        self.audit_tree.heading("candidate", text="NOM DÉTECTÉ DANS LES TEXTES")
        self.audit_tree.heading("alias", text="REMPLACEMENT PROPOSÉ")
        self.audit_tree.column("occ", width=70, anchor="center")
        self.audit_tree.column("candidate", width=330)
        self.audit_tree.column("alias", width=330)
        sb = ttk.Scrollbar(
            table_card, orient="vertical", command=self.audit_tree.yview
        )
        self.audit_tree.configure(yscrollcommand=sb.set)
        self.audit_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.audit_tree.bind("<<TreeviewSelect>>", self._on_audit_row_selected)  # type: ignore[attr-defined]
        self.audit_tree.bind("<Double-1>", lambda _e: self._open_before_after_preview())  # type: ignore[attr-defined]
        self.audit_tree.bind("<Return>", lambda _e: self._open_before_after_preview())  # type: ignore[attr-defined]
        self.audit_tree.bind("m", lambda _e: self._approve_selected_audit())  # type: ignore[attr-defined]
        self.audit_tree.bind("M", lambda _e: self._approve_selected_audit())  # type: ignore[attr-defined]
        self.audit_tree.bind("i", lambda _e: self._exclude_selected_audit())  # type: ignore[attr-defined]
        self.audit_tree.bind("I", lambda _e: self._exclude_selected_audit())  # type: ignore[attr-defined]
        self.audit_tree.bind("<Delete>", lambda _e: self._exclude_selected_audit())  # type: ignore[attr-defined]
        act_card = make_card(parent, title="Décision rapide sur la ligne sélectionnée")
        act_row = tk.Frame(act_card, bg=UI_COLORS["card"])
        act_row.pack(fill="x")
        tk.Label(
            act_row, text="Remplacer par :", bg=UI_COLORS["card"],
            fg=UI_COLORS["text"], font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 8))
        self.audit_alias_edit_var = tk.StringVar()
        make_modern_entry(act_row, self.audit_alias_edit_var, width=220).pack(side="left", padx=(0, 10))
        make_styled_button(act_row, text="Masquer ce nom", command=self._approve_selected_audit, variant="primary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(act_row, text="Ignorer (faux positif)", command=self._exclude_selected_audit, variant="secondary").pack(side="left")  # type: ignore[attr-defined]

        nav_row = tk.Frame(parent, bg=UI_COLORS["bg"])
        nav_row.pack(fill="x", pady=(2, 0))
        make_styled_button(nav_row, text="<- Retour (Traitement)", command=lambda: self._show_page("run"), variant="secondary").pack(side="left")  # type: ignore[attr-defined]
        make_styled_button(nav_row, text="Appliquer et passer à l'étape finale ->", command=self._apply_audit_and_go_export, variant="success").pack(side="right")  # type: ignore[attr-defined]

    def _build_page_export(self) -> None:
        parent = self.pages["export"]
        self.frame_export_ia = tk.Frame(parent, bg=UI_COLORS["bg"])
        card_ia = make_card(
            self.frame_export_ia,
            title="Récupérer vos fichiers anonymisés & Requêtes IA prêtes à copier",
            subtitle="1) Ouvrez le dossier des résultats.\n2) Copiez une requête pour ChatGPT, Claude ou Mistral.",
            accent_color="#2563eb",
        )
        row_ia = tk.Frame(card_ia, bg=UI_COLORS["card"])
        row_ia.pack(fill="x", pady=(0, 10))
        make_styled_button(row_ia, text="Ouvrir mes fichiers anonymisés", command=lambda: self._open_workspace_folder("results_dir"), variant="success").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(row_ia, text="Passer au Mode Avocat (Nominatif) ->", command=lambda: self._set_workflow_mode("lawyer", navigate=True), variant="secondary").pack(side="right")  # type: ignore[attr-defined]

        prompt_bar = tk.Frame(card_ia, bg=UI_COLORS["card"])
        prompt_bar.pack(fill="x", pady=(0, 8))
        lbl_mod = tk.Label(prompt_bar, text="Modèle de requête :", bg=UI_COLORS["card"], fg=UI_COLORS["text"], font=("Segoe UI", 10, "bold"))
        lbl_mod.pack(side="left", padx=(0, 8))
        register_scalable_font(lbl_mod, "Segoe UI", 10, "bold")
        prompt_titles = [lbl for lbl, _ in self.controller.AI_PROMPT_TEMPLATES]
        self.prompt_choice_var = tk.StringVar(value=next(iter(prompt_titles), ""))
        make_modern_dropdown(prompt_bar, self.prompt_choice_var, prompt_titles, width=360, command=self._on_prompt_selected).pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(prompt_bar, text="Copier cette requête", command=self._copy_selected_prompt, variant="primary").pack(side="left")  # type: ignore[attr-defined]

        self.txt_prompt_preview = tk.Text(
            card_ia, height=8, wrap="word", font=("Segoe UI", 10),
            bg="#ffffff", fg="#0f172a", relief="flat", bd=0,
            highlightthickness=1, highlightbackground=UI_COLORS["border_strong"],
            padx=12, pady=10,
        )
        self.txt_prompt_preview.pack(fill="both", expand=True)
        register_scalable_font(self.txt_prompt_preview, "Segoe UI", 10, "normal")
        self._on_prompt_selected()  # type: ignore[attr-defined]

        self.frame_export_lawyer = tk.Frame(parent, bg=UI_COLORS["bg"])
        card_law = make_card(
            self.frame_export_lawyer,
            title="Générer le Pack Avocat Nominatif (Word, CSV & Médias originaux)",
            subtitle="Chaque audio et image est copié côte à côte avec sa transcription.",
            accent_color="#059669",
        )
        self.lawyer_filter_mode_var = tk.StringVar(value="all")
        tk.Radiobutton(card_law, text="Exporter l'intégralité des pièces du dossier", variable=self.lawyer_filter_mode_var, value="all", bg=UI_COLORS["card"], fg=UI_COLORS["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Radiobutton(card_law, text="Exporter uniquement les pièces recommandées par l'IA :", variable=self.lawyer_filter_mode_var, value="ai_list", bg=UI_COLORS["card"], fg=UI_COLORS["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 6))
        self.txt_ai_pieces_list = tk.Text(
            card_law, height=6, wrap="word", font=("Consolas", 9),
            bg="#ffffff", fg="#0f172a", relief="flat", bd=0,
            highlightthickness=1, highlightbackground=UI_COLORS["border_strong"],
            padx=10, pady=8,
        )
        self.txt_ai_pieces_list.pack(fill="x", pady=(0, 10))
        make_styled_button(card_law, text="Générer le Pack Avocat Nominatif", command=self._export_lawyer_pack, variant="success").pack(anchor="w")  # type: ignore[attr-defined]
