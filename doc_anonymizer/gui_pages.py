# Commandes pip à exécuter : Aucune dépendance externe requise

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict
from doc_anonymizer.gui_widgets import UI_COLORS, make_card, make_styled_button


class GuiPagesMixin:
    """Mixin regroupant la construction des écrans de l'interface graphique."""

    pages: Dict[str, tk.Frame]
    controller: Any

    def _build_page_gate(self) -> None:
        parent = self.pages["gate"]
        card = make_card(
            parent,
            title="1. Vigilance humaine & Licence libre (GNU GPL v3)",
            subtitle="Prenez 30 secondes pour lire cet engagement essentiel à la sécurité de vos données.",
        )
        body_txt = (
            "• NE FAITES JAMAIS ENTIÈREMENT CONFIANCE À UNE MACHINE : aucun algorithme n'est infaillible face à "
            "un scan flou ou une abréviation inhabituelle.\n"
            "• VOTRE ENGAGEMENT DE RELECTURE : avant de transmettre vos fichiers (IA en ligne, avocat, syndicat, "
            "administration), vous vous engagez à relire votre export — au moins par sondage — pour vérifier "
            "que le résultat protège suffisamment vos proches.\n"
            "• LICENCE LIBRE GNU GPL v3 : logiciel libre fourni « en l'état, sans garantie ». Vous restez seul "
            "responsable des documents que vous choisissez de diffuser."
        )
        tk.Label(
            card,
            text=body_txt,
            bg=UI_COLORS["card"],
            fg=UI_COLORS["text"],
            font=("Segoe UI", 9),
            justify="left",
            wraplength=780,
        ).pack(anchor="w", pady=(2, 4))

        self.card_gate_ws = make_card(
            parent,
            title="2. Choisir ou créer votre dossier de travail (obligatoire)",
            subtitle="Chaque affaire dispose de son propre espace isolé (documents, contacts, résultats et audits).",
        )
        self.gate_action_var = tk.StringVar(value="create")
        self.gate_existing_var = tk.StringVar()
        self.gate_new_name_var = tk.StringVar()

        self.frame_gate_existing = tk.Frame(self.card_gate_ws, bg=UI_COLORS["card"])
        tk.Radiobutton(
            self.frame_gate_existing,
            text="Ouvrir un dossier existant :",
            variable=self.gate_action_var,
            value="open",
            bg=UI_COLORS["card"],
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 8))
        self.combo_gate_ws = ttk.Combobox(
            self.frame_gate_existing, textvariable=self.gate_existing_var, state="readonly", width=36
        )
        self.combo_gate_ws.pack(side="left")

        self.frame_gate_create = tk.Frame(self.card_gate_ws, bg=UI_COLORS["card"])
        self.rb_gate_create = tk.Radiobutton(
            self.frame_gate_create,
            text="Créer un nouveau dossier :",
            variable=self.gate_action_var,
            value="create",
            bg=UI_COLORS["card"],
            font=("Segoe UI", 9, "bold"),
        )
        self.lbl_gate_create_only = tk.Label(
            self.frame_gate_create,
            text="Nom du nouveau dossier à créer :",
            bg=UI_COLORS["card"],
            font=("Segoe UI", 9, "bold"),
        )
        self.entry_gate_new = tk.Entry(
            self.frame_gate_create,
            textvariable=self.gate_new_name_var,
            width=34,
            relief="solid",
            bd=1,
            font=("Segoe UI", 9),
        )
        self.entry_gate_new.bind("<KeyPress>", lambda _e: self.gate_action_var.set("create"))

        row_actions = tk.Frame(parent, bg=UI_COLORS["bg"])
        row_actions.pack(fill="x", pady=(6, 0))
        make_styled_button(
            row_actions,
            text="Refuser et quitter poliment",
            command=self._quit_politely,  # type: ignore[attr-defined]
            variant="secondary",
        ).pack(side="left")
        make_styled_button(
            row_actions,
            text="J'ai compris et j'accepte -> Ouvrir mon dossier",
            command=self._confirm_gate_and_workspace,  # type: ignore[attr-defined]
            variant="primary",
        ).pack(side="right")
    def _build_page_mode(self) -> None:
        parent = self.pages["mode"]
        make_card(
            parent,
            title="Quel est votre besoin aujourd'hui ?",
            subtitle=(
                "Choisissez votre parcours selon le destinataire de vos documents. "
                "Vous pourrez basculer d'un mode à l'autre à tout moment depuis la barre du haut."
            ),
        )
        cols = tk.Frame(parent, bg=UI_COLORS["bg"])
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)

        c_ia = tk.Frame(cols, bg="#ffffff", highlightbackground="#2563eb", highlightthickness=2, padx=16, pady=16)
        c_ia.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(
            c_ia, text="OPTION A — Pré-analyse avec une IA (Anonymisé)", bg="#ffffff", fg="#1d4ed8", font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(0, 8))
        tk.Label(
            c_ia,
            text=(
                "• Pourquoi anonymiser ? Les assistants IA en ligne (ChatGPT, Claude, Mistral...) peuvent conserver "
                "ou analyser vos textes. Ne leur envoyez jamais de vrais noms, adresses ou numéros.\n\n"
                "• Ce que fait ce mode : remplace les identités par des codes stables (Camille D., Dr M., TEL_001), "
                "vous permet de contrôler les noms restants, puis vous fournit des requêtes IA prêtes à copier "
                "pour identifier les pièces utiles."
            ),
            bg="#ffffff",
            fg="#0f172a",
            font=("Segoe UI", 9),
            justify="left",
            wraplength=360,
        ).pack(anchor="w", fill="x", pady=(0, 14))
        make_styled_button(
            c_ia,
            text="Choisir le Mode IA (Anonymisé) ->",
            command=lambda: self._set_workflow_mode("ia", navigate=True),  # type: ignore[attr-defined]
            variant="primary",
        ).pack(anchor="w")

        c_law = tk.Frame(cols, bg="#ffffff", highlightbackground="#16a34a", highlightthickness=2, padx=16, pady=16)
        c_law.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(
            c_law, text="OPTION B — Dossier pour un Avocat / Syndicat (Nominatif)", bg="#ffffff", fg="#15803d", font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(0, 8))
        tk.Label(
            c_law,
            text=(
                "• Pourquoi garder les vrais noms ? Votre avocat ou défenseur syndical a besoin des identités, "
                "dates et pièces exactes pour défendre vos droits.\n\n"
                "• Ce que fait ce mode : extrait et classe chronologiquement toutes vos pièces sans les anonymiser, "
                "ajoute une transcription à côté de chaque audio, applique l'OCR sur chaque image, et génère "
                "un recueil Word + bordereau CSV (complet ou filtré selon la liste de l'IA)."
            ),
            bg="#ffffff",
            fg="#0f172a",
            font=("Segoe UI", 9),
            justify="left",
            wraplength=360,
        ).pack(anchor="w", fill="x", pady=(0, 14))
        make_styled_button(
            c_law,
            text="Choisir le Mode Avocat (Nominatif) ->",
            command=lambda: self._set_workflow_mode("lawyer", navigate=True),  # type: ignore[attr-defined]
            variant="success",
        ).pack(anchor="w")
    def _build_page_setup(self) -> None:
        parent = self.pages["setup"]
        card_ws = make_card(
            parent,
            title="1A — Espace de travail actif (« dossier »)",
            subtitle="Chaque dossier isole vos documents, contacts et résultats d'une affaire à l'autre.",
        )
        row_sel = tk.Frame(card_ws, bg=UI_COLORS["card"])
        row_sel.pack(fill="x", pady=(0, 6))
        tk.Label(row_sel, text="Dossier actif :", bg=UI_COLORS["card"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))
        self.combo_ws = ttk.Combobox(row_sel, textvariable=self.workspace_choice_var, state="readonly", width=36)  # type: ignore[attr-defined]
        self.combo_ws.pack(side="left", padx=(0, 12))
        self.combo_ws.bind("<<ComboboxSelected>>", self._on_workspace_selected)  # type: ignore[attr-defined]

        tk.Label(row_sel, text="Ou créer :", bg=UI_COLORS["card"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        tk.Entry(row_sel, textvariable=self.new_ws_name_var, width=22, relief="solid", bd=1, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6), ipady=3)  # type: ignore[attr-defined]
        make_styled_button(row_sel, text="Créer", command=self._create_new_workspace, variant="secondary").pack(side="left")  # type: ignore[attr-defined]

        card_files = make_card(
            parent,
            title="1B — Déposer vos pièces justificatives",
            subtitle="Copiez-collez vos PDF, scans, Word, SMS (.xml), WhatsApp (.txt), Teams/Messenger (.json/.vtt), e-mails (.mbox/.eml), agendas (.ics), images ou audios.",
        )
        row_docs = tk.Frame(card_files, bg=UI_COLORS["card"])
        row_docs.pack(fill="x")
        make_styled_button(
            row_docs,
            text="Ouvrir le dossier des documents",
            command=lambda: self._open_workspace_folder("sources_dir"),  # type: ignore[attr-defined]
            variant="primary",
        ).pack(side="left", padx=(0, 8))
        make_styled_button(row_docs, text="Actualiser le compteur", command=self._refresh_workspace_counters, variant="secondary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(
            row_docs,
            text="Exporter un agenda (.ics) ?",
            command=self._show_calendar_export_popup,  # type: ignore[attr-defined]
            variant="secondary",
            tooltip="Explique comment exporter votre calendrier Google, Outlook ou Apple au format .ics.",
        ).pack(side="right")

        self.docs_summary_var = tk.StringVar(value="Documents sources déposés : 0 fichier.")
        tk.Label(card_files, textvariable=self.docs_summary_var, bg=UI_COLORS["card"], fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 0))

        self.zip_warning_var = tk.StringVar(value="")
        self.lbl_zip_warning = tk.Label(
            card_files,
            textvariable=self.zip_warning_var,
            bg=UI_COLORS["warning_bg"],
            fg=UI_COLORS["warning_fg"],
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=6,
            justify="left",
            wraplength=760,
        )

        self.card_csv = make_card(
            parent,
            title="1C — Ajouter vos carnets de contacts (.csv) & Aide exports",
            subtitle="Importez vos exports Google Contacts ou Outlook (.csv) pour masquer immédiatement proches, collègues et médecins.",
        )
        row_csv = tk.Frame(self.card_csv, bg=UI_COLORS["card"])
        row_csv.pack(fill="x")
        make_styled_button(row_csv, text="Ajouter un carnet (.csv)", command=self._import_csv_dialog, variant="success").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(row_csv, text="Voir mes carnets", command=lambda: self._open_workspace_folder("input_contacts_dir"), variant="secondary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(
            row_csv,
            text="Exporter un agenda (.ics) ?",
            command=self._show_calendar_export_popup,  # type: ignore[attr-defined]
            variant="secondary",
            tooltip="Affiche la marche à suivre pour exporter votre agenda (Google, Outlook, Apple) au format .ics.",
        ).pack(side="right")
        self.csv_summary_var = tk.StringVar(value="Carnets (.csv) chargés : aucun.")
        tk.Label(self.card_csv, textvariable=self.csv_summary_var, bg=UI_COLORS["card"], fg="#2563eb", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(6, 0))

        nav_next = tk.Frame(parent, bg=UI_COLORS["bg"])
        nav_next.pack(fill="x", pady=(4, 0))
        make_styled_button(
            nav_next,
            text="Passer à l'étape 2 : Lancer l'analyse ->",
            command=lambda: self._show_page("run"),  # type: ignore[attr-defined]
            variant="primary",
        ).pack(side="right")
    def _build_page_run(self) -> None:
        parent = self.pages["run"]
        card_ctrl = make_card(
            parent,
            title="Lancer le traitement de vos documents",
            subtitle="Le traitement s'exécute 100 % hors-ligne sur votre ordinateur.",
        )
        row_btn = tk.Frame(card_ctrl, bg=UI_COLORS["card"])
        row_btn.pack(fill="x", pady=(0, 8))

        self.btn_main_run = make_styled_button(
            row_btn,
            text="Lancer l'extraction et l'anonymisation",
            command=self._start_primary_workflow_job,  # type: ignore[attr-defined]
            variant="primary",
        )
        self.btn_main_run.pack(side="left", padx=(0, 8))

        self.btn_fast_reanon = make_styled_button(
            row_btn,
            text="Ré-anonymiser uniquement (rapide)",
            command=lambda: self._start_job("anonymize_only"),  # type: ignore[attr-defined]
            variant="secondary",
        )
        self.btn_fast_reanon.pack(side="left", padx=(0, 8))

        self.btn_stop = make_styled_button(row_btn, text="Arrêter", command=self._stop_current_job, variant="danger")  # type: ignore[attr-defined]
        self.btn_stop.configure(state="disabled")
        self.btn_stop.pack(side="right")

        self.progress = ttk.Progressbar(card_ctrl, mode="indeterminate")
        self.progress.pack(fill="x")

        dash_card = make_card(parent, title="Tableau de bord — Résumé des traitements et protections")
        grid_stats = tk.Frame(dash_card, bg=UI_COLORS["card"])
        grid_stats.pack(fill="x")
        self.stat_vars: Dict[str, tk.StringVar] = {}
        stat_defs = [
            ("docs", "Documents traités", "#e0f2fe", "#0369a1"),
            ("names", "Noms / Identités masqués", "#dcfce7", "#166534"),
            ("coords", "E-mails / Tél. / URLs", "#fef3c7", "#92400e"),
            ("ids", "NIR / IBAN / Réf. admin.", "#f3e8ff", "#6b21a8"),
            ("locs", "Adresses / Lieux / Dates", "#ffe4e6", "#9f1239"),
        ]
        for idx, (skey, slabel, bg_c, fg_c) in enumerate(stat_defs):
            grid_stats.columnconfigure(idx, weight=1)
            box = tk.Frame(grid_stats, bg=bg_c, padx=10, pady=8)
            box.grid(row=0, column=idx, sticky="nsew", padx=4)
            v = tk.StringVar(value="0")
            self.stat_vars[skey] = v
            tk.Label(box, textvariable=v, bg=bg_c, fg=fg_c, font=("Segoe UI", 14, "bold")).pack()
            tk.Label(box, text=slabel, bg=bg_c, fg=fg_c, font=("Segoe UI", 8)).pack()

        self.dash_zip_var = tk.StringVar(value="")
        self.lbl_dash_zip = tk.Label(
            dash_card,
            textvariable=self.dash_zip_var,
            bg=UI_COLORS["warning_bg"],
            fg=UI_COLORS["warning_fg"],
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=6,
            justify="left",
            wraplength=760,
        )

        log_header = tk.Frame(parent, bg=UI_COLORS["bg"])
        log_header.pack(fill="x", pady=(2, 4))
        make_styled_button(
            log_header,
            text="Afficher / Masquer le journal technique",
            command=self._toggle_log_panel,  # type: ignore[attr-defined]
            variant="secondary",
        ).pack(side="left")

        self.btn_after_run_next = make_styled_button(
            log_header,
            text="Étape suivante ->",
            command=self._go_to_step_after_run,  # type: ignore[attr-defined]
            variant="success",
        )
        self.btn_after_run_next.pack(side="right")

        self.log_text = tk.Text(
            parent,
            height=9,
            wrap="word",
            font=("Consolas", 8),
            bg=UI_COLORS["log_bg"],
            fg=UI_COLORS["log_fg"],
            relief="flat",
            padx=8,
            pady=6,
            state="disabled",
        )
    def _build_page_audit(self) -> None:
        parent = self.pages["audit"]
        card_info = make_card(
            parent,
            title="Contrôle des noms potentiels restants (Relecture assistée)",
            subtitle=(
                "Cliquez sur une ligne pour voir l'extrait Avant / Après dans le document, "
                "masquer les personnes oubliées ou ignorer les mots courants."
            ),
        )
        top_info = tk.Frame(card_info, bg=UI_COLORS["card"])
        top_info.pack(fill="x")
        self.audit_count_var = tk.StringVar(value="0 élément(s) à vérifier.")
        tk.Label(top_info, textvariable=self.audit_count_var, bg=UI_COLORS["card"], font=("Segoe UI", 9, "bold")).pack(side="left")

        make_styled_button(top_info, text="Actualiser", command=self._refresh_audit_list, variant="secondary").pack(side="right", padx=(6, 0))  # type: ignore[attr-defined]
        make_styled_button(
            top_info,
            text="Voir dans le document (Avant / Après)",
            command=self._open_before_after_preview,  # type: ignore[attr-defined]
            variant="primary",
        ).pack(side="right")

        table_card = tk.Frame(parent, bg=UI_COLORS["card"], highlightbackground=UI_COLORS["border"], highlightthickness=1, padx=8, pady=8)
        table_card.pack(fill="both", expand=True, pady=(0, 8))

        self.audit_tree = ttk.Treeview(table_card, columns=("candidate", "alias"), show="headings", selectmode="browse", style="Modern.Treeview", height=9)
        self.audit_tree.heading("candidate", text="Mot ou nom repéré")
        self.audit_tree.heading("alias", text="Code de remplacement")
        self.audit_tree.column("candidate", width=400)
        self.audit_tree.column("alias", width=320)
        self.audit_tree.pack(fill="both", expand=True)
        self.audit_tree.bind("<<TreeviewSelect>>", self._on_audit_row_selected)  # type: ignore[attr-defined]
        self.audit_tree.bind("<Double-1>", lambda _e: self._open_before_after_preview())  # type: ignore[attr-defined]

        edit_row = tk.Frame(parent, bg=UI_COLORS["bg"])
        edit_row.pack(fill="x", pady=(0, 6))
        tk.Label(edit_row, text="Code de remplacement :", bg=UI_COLORS["bg"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        self.audit_alias_edit_var = tk.StringVar()
        tk.Entry(edit_row, textvariable=self.audit_alias_edit_var, width=28, relief="solid", bd=1, font=("Segoe UI", 9)).pack(side="left", ipady=3)

        act_row = tk.Frame(parent, bg=UI_COLORS["bg"])
        act_row.pack(fill="x")
        make_styled_button(act_row, text="Masquer ce nom", command=self._approve_selected_audit, variant="primary").pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
        make_styled_button(act_row, text="Ignorer (faux positif)", command=self._exclude_selected_audit, variant="secondary").pack(side="left")  # type: ignore[attr-defined]
        make_styled_button(
            act_row,
            text="Appliquer et passer à l'étape 4 ->",
            command=self._apply_audit_and_go_export,  # type: ignore[attr-defined]
            variant="success",
        ).pack(side="right")

    def _build_page_export(self) -> None:
        parent = self.pages["export"]

        self.frame_export_ia = tk.Frame(parent, bg=UI_COLORS["bg"])
        card_ia_out = make_card(
            self.frame_export_ia,
            title="Vos fichiers anonymisés sont prêts pour une pré-analyse IA",
            subtitle=(
                "Rappel : relisez au moins un échantillon avant de les copier dans un assistant IA. "
                "Demandez à l'IA de vous lister les chemins (# SOURCE TRANSCRIPTION : ...) des pièces utiles."
            ),
        )
        row_ia_btn = tk.Frame(card_ia_out, bg=UI_COLORS["card"])
        row_ia_btn.pack(fill="x")
        make_styled_button(
            row_ia_btn,
            text="Ouvrir le dossier des lots anonymisés (.txt)",
            command=lambda: self._open_workspace_folder("results_dir"),  # type: ignore[attr-defined]
            variant="primary",
        ).pack(side="left", padx=(0, 8))
        make_styled_button(
            row_ia_btn,
            text="Basculer en Mode Avocat pour exporter les pièces retenues ->",
            command=lambda: self._set_workflow_mode("lawyer", navigate=True),  # type: ignore[attr-defined]
            variant="success",
        ).pack(side="right")

        card_prompts = make_card(
            self.frame_export_ia,
            title="Exemples de requêtes IA prêtes à copier (avec sélection des pièces)",
            subtitle="Choisissez un modèle adapté à votre situation et cliquez sur « Copier la requête » :",
        )
        sel_p_row = tk.Frame(card_prompts, bg=UI_COLORS["card"])
        sel_p_row.pack(fill="x", pady=(0, 6))
        self.prompt_choice_var = tk.StringVar()
        prompt_labels = [lbl for lbl, _ in self.controller.AI_PROMPT_TEMPLATES]
        self.combo_prompts = ttk.Combobox(sel_p_row, textvariable=self.prompt_choice_var, values=prompt_labels, state="readonly", width=52)
        self.combo_prompts.pack(side="left", padx=(0, 8))
        self.combo_prompts.bind("<<ComboboxSelected>>", self._on_prompt_selected)  # type: ignore[attr-defined]
        make_styled_button(sel_p_row, text="Copier cette requête", command=self._copy_selected_prompt, variant="primary").pack(side="left")  # type: ignore[attr-defined]

        self.txt_prompt_preview = tk.Text(card_prompts, height=6, wrap="word", font=("Segoe UI", 9), bg="#f8fafc", relief="solid", bd=1, padx=8, pady=6)
        self.txt_prompt_preview.pack(fill="x")
        if prompt_labels:
            self.combo_prompts.current(0)
            self._on_prompt_selected()  # type: ignore[attr-defined]

        self.frame_export_lawyer = tk.Frame(parent, bg=UI_COLORS["bg"])
        card_law_out = make_card(
            self.frame_export_lawyer,
            title="Générer le Pack Avocat Nominatif (Originaux + Transcriptions Audio + OCR)",
            subtitle=(
                "Attention : ce recueil contient les identités et pièces d'origine. "
                "Ne le transmettez qu'à votre avocat, défenseur syndical ou juridiction."
            ),
        )
        self.lawyer_filter_mode_var = tk.StringVar(value="all")
        tk.Radiobutton(
            card_law_out,
            text="Exporter l'intégralité des pièces extraites du dossier (classées par date)",
            variable=self.lawyer_filter_mode_var,
            value="all",
            bg=UI_COLORS["card"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Radiobutton(
            card_law_out,
            text="Filtrer uniquement les pièces pertinentes recommandées par l'IA (collez la liste ci-dessous) :",
            variable=self.lawyer_filter_mode_var,
            value="ai_list",
            bg=UI_COLORS["card"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(4, 4))

        self.txt_ai_pieces_list = tk.Text(card_law_out, height=6, wrap="word", font=("Consolas", 8), bg="#f8fafc", relief="solid", bd=1, padx=8, pady=6)
        self.txt_ai_pieces_list.pack(fill="x", pady=(0, 8))
        make_styled_button(
            card_law_out,
            text="Générer le Pack Avocat (.docx + Bordereau CSV + Originaux + ZIP)",
            command=self._export_lawyer_pack,  # type: ignore[attr-defined]
            variant="success",
        ).pack(anchor="w")
