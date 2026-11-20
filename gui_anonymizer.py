# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.gui_controller import AnonymizerGuiController


class Tooltip:
    """Infobulle simple affichée au survol d'un bouton ou champ de saisie."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget: tk.Widget = widget
        self.text: str = text
        self.tip_win: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, _event: object = None) -> None:
        if self.tip_win is not None or not self.text:
            return
        x: int = self.widget.winfo_rootx() + 18
        y: int = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        win = tk.Toplevel(self.widget)
        win.wm_overrideredirect(True)
        win.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            win,
            text=self.text,
            justify="left",
            background="#fffbe6",
            foreground="#222222",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=5,
            wraplength=420,
            font=("Segoe UI", 9),
        )
        lbl.pack()
        self.tip_win = win

    def _hide(self, _event: object = None) -> None:
        if self.tip_win is not None:
            self.tip_win.destroy()
            self.tip_win = None


class AnonymizerGuiApp(tk.Tk):
    """Interface graphique guidée pour préparer et anonymiser des dossiers confidentiels."""

    GUIDE_SECTIONS: List[Tuple[str, str, str]] = [
        (
            "sec_intro",
            "1. Principe",
            "1. À QUOI SERT CE LOGICIEL ?\n"
            "Cet outil prépare vos documents confidentiels (comptes rendus médicaux, bilans orthophoniques, "
            "attestations scolaires, échanges entre parents, SMS, e-mails, courriers employeur) "
            "en remplaçant automatiquement les noms, adresses, téléphones et numéros sensibles par des codes neutres "
            "(ex. « Camille D. », « Dr M. », « [ADRESSE_MASQUEE] », « [NUM_SECU_MASQUE] »).\n"
            "Vos fichiers originaux ne sont jamais modifiés et rien n'est envoyé sur Internet.\n\n",
        ),
        (
            "sec_folder",
            "2. Dossier",
            "2. QU'EST-CE QU'UN « DOSSIER » DANS CE LOGICIEL ?\n"
            "Un dossier (ou espace de travail) est un tiroir numérique totalement étanche créé sur votre ordinateur "
            "pour une affaire précise (ex. « Dossier_Enfant » ou « Dossier_Salarie »).\n"
            "Chaque dossier possède ses propres documents, ses propres contacts et ses propres résultats : "
            "les noms d'une affaire ne se mélangent jamais avec ceux d'une autre.\n\n",
        ),
        (
            "sec_csv",
            "3. Export contacts (.csv)",
            "3. QU'EST-CE QUE L'EXPORT CONTACTS (.CSV) ET POURQUOI L'IMPORTER ?\n"
            "Le format .csv est un format de fichier tableau standard (ouvrable avec Excel ou LibreOffice) "
            "utilisé par les messageries et téléphones pour exporter un carnet d'adresses.\n"
            "Dans ce logiciel, importer l'export CSV de vos contacts à l'étape 1 est FORTEMENT RECOMMANDÉ : "
            "cela aide considérablement le programme à reconnaître et masquer vos proches, médecins ou interlocuteurs "
            "dès le 1er passage (y compris en cas de faute de frappe ou de scan flou).\n\n",
        ),
        (
            "sec_exports",
            "4. Exporter vos fichiers",
            "4. COMMENT EXPORTER VOS FICHIERS POUR LES DONNER AU LOGICIEL ?\n"
            "  • Carnet d'adresses (.csv) :\n"
            "      - Google Contacts (://google.com) : menu de gauche -> « Exporter » -> choisir « Google CSV ».\n"
            "      - Outlook : Fichier -> Ouvrir et exporter -> Importer/Exporter -> « Exporter vers un fichier » -> « CSV ».\n"
            "  • SMS / MMS Android (.xml) :\n"
            "      - Application gratuite « SMS Backup & Restore » sur Android -> « Configurer une sauvegarde » -> cocher « Messages » -> récupérer le fichier .xml.\n"
            "  • WhatsApp (.txt) :\n"
            "      - Ouvrir la discussion sur téléphone -> menu (3 points) -> « Plus » -> « Exporter la discussion » -> choisir « Sans médias ».\n"
            "  • Google Chat / Hangouts (.json) :\n"
            "      - Aller sur ://google.com -> tout désélectionner -> cocher « Google Chat » -> télécharger et décompresser l'archive.\n"
            "  • Microsoft Teams (.json ou .vtt) :\n"
            "      - Discussions : sur ://microsoft.com -> « Télécharger vos données » -> cocher les messages Teams (format .json).\n"
            "      - Transcriptions de réunions : dans Teams -> ouvrir la réunion passée -> onglet « Enregistrement et transcription » -> « Télécharger » -> choisir le format .vtt.\n"
            "  • Facebook Messenger & Instagram (.json) :\n"
            "      - Paramètres Meta -> « Vos informations et autorisations » -> « Télécharger vos informations » -> cocher « Messages » -> choisir le format JSON (pas HTML).\n"
            "  • Signal (astuce) :\n"
            "      - Signal n'a pas d'export direct : sur ordinateur (Signal Desktop), copiez-collez les échanges utiles dans un fichier .txt (ou imprimez en .pdf) et déposez-le dans vos documents.\n"
            "  • E-mails Gmail / Outlook / Thunderbird (.mbox ou .eml) :\n"
            "      - Gmail : ://google.com -> cocher « Mail » (donne un fichier .mbox).\n"
            "      - Thunderbird / Outlook : glissez-déposez les e-mails sur le bureau (donne des fichiers .eml) ou exportez le dossier en .mbox.\n",
        ),
    ]
    def __init__(self) -> None:
        super().__init__()
        self.title("Anonymiseur de Documents Confidentiels (100 % Local & Hors-Ligne)")
        self.geometry("980x740")
        self.minsize(880, 640)

        self.controller: AnonymizerGuiController = AnonymizerGuiController(ROOT_DIR)
        self.workspaces: List[Tuple[str, str]] = []
        self.current_ini_var: tk.StringVar = tk.StringVar()
        self.workspace_choice_var: tk.StringVar = tk.StringVar()
        self.new_ws_name_var: tk.StringVar = tk.StringVar()
        self.status_var: tk.StringVar = tk.StringVar(value="Prêt — Cliquez sur une rubrique ou passez à l'étape 1.")
        self.is_running: bool = False

        self._build_ui()
        self._bind_trackpad_scroll()
        self._refresh_workspaces()

    def _bind_trackpad_scroll(self) -> None:
        """Rend le défilement au trackpad fluide sur Windows (deltas fins) et Linux."""
        def _on_mousewheel(event: tk.Event) -> None:
            widget = self.winfo_containing(event.x_root, event.y_root)
            if widget is None:
                return
            delta: int = getattr(event, "delta", 0)
            if delta == 0:
                return
            step: int = -1 if delta > 0 else 1
            if abs(delta) >= 120:
                step = int(-delta / 120)
            target = widget
            while target is not None:
                if hasattr(target, "yview_scroll"):
                    target.yview_scroll(step, "units")
                    break
                target = getattr(target, "master", None)

        self.bind_all("<MouseWheel>", _on_mousewheel, add="+")
        self.bind_all("<Button-4>", lambda e: self._scroll_linux(e, -1), add="+")
        self.bind_all("<Button-5>", lambda e: self._scroll_linux(e, 1), add="+")

    def _scroll_linux(self, event: tk.Event, step: int) -> None:
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if hasattr(widget, "yview_scroll"):
                widget.yview_scroll(step, "units")
                break
            widget = getattr(widget, "master", None)

    def _build_ui(self) -> None:
        """Construit l'en-tête et les 4 onglets guidés de l'interface."""
        header = ttk.Frame(self, padding=(14, 10))
        header.pack(fill="x")

        ttk.Label(
            header,
            text="Anonymiseur Local de Documents (Santé, Garde d'enfant, Prud'hommes)",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            header,
            text="100 % hors-ligne sur votre ordinateur • Vos originaux restent intacts • Cliquez sur une rubrique ci-dessous.",
            foreground="#1f4e79",
        ).pack(anchor="w", pady=(3, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(4, 6))

        self.tab_help = ttk.Frame(self.notebook, padding=14)
        self.tab_setup = ttk.Frame(self.notebook, padding=14)
        self.tab_run = ttk.Frame(self.notebook, padding=14)
        self.tab_audit = ttk.Frame(self.notebook, padding=14)

        self.notebook.add(self.tab_help, text="0. Mode d'emploi & Exports")
        self.notebook.add(self.tab_setup, text="1. Dossier & Documents")
        self.notebook.add(self.tab_run, text="2. Lancer l'anonymisation")
        self.notebook.add(self.tab_audit, text="3. Vérifier les noms restants")

        self._build_tab_help()
        self._build_tab_setup()
        self._build_tab_run()
        self._build_tab_audit()

        footer = ttk.Frame(self, padding=(14, 6))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var, foreground="#1f4e79").pack(side="left")

    def _select_guide_card(self, idx: int) -> None:
        """Affiche directement la fiche demandée sans aucun défilement requis."""
        if not (0 <= idx < len(self.GUIDE_SECTIONS)):
            return
        _, _, body = self.GUIDE_SECTIONS[idx]
        lines = body.strip().split("\n", 1)
        self.guide_title_var.set(lines[0])
        self.guide_body_var.set(lines[1].strip() if len(lines) > 1 else "")
        for b_idx, btn in enumerate(self.guide_nav_buttons):
            btn.state(["disabled"] if b_idx == idx else ["!disabled"])

    def _build_tab_help(self) -> None:
        """Onglet 0 : navigation par fiches cliquables sans défilement au trackpad."""
        nav_cards = ttk.Frame(self.tab_help)
        nav_cards.pack(fill="x", pady=(0, 10))

        self.guide_nav_buttons: List[ttk.Button] = []
        for idx, (_, short_label, _) in enumerate(self.GUIDE_SECTIONS):
            btn = ttk.Button(
                nav_cards,
                text=short_label,
                command=lambda i=idx: self._select_guide_card(i),
            )
            btn.pack(side="left", padx=(0, 8), ipadx=6, ipady=3)
            self.guide_nav_buttons.append(btn)

        card_frame = ttk.LabelFrame(self.tab_help, text="Fiche explicative", padding=16)
        card_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.guide_title_var = tk.StringVar()
        self.guide_body_var = tk.StringVar()

        ttk.Label(
            card_frame,
            textvariable=self.guide_title_var,
            font=("Segoe UI", 11, "bold"),
            foreground="#1f4e79",
        ).pack(anchor="w", pady=(0, 8))

        ttk.Label(
            card_frame,
            textvariable=self.guide_body_var,
            font=("Segoe UI", 10),
            justify="left",
            wraplength=880,
        ).pack(anchor="w", fill="x")

        self._select_guide_card(0)

        nav_row = ttk.Frame(self.tab_help)
        nav_row.pack(fill="x")
        btn_next = ttk.Button(
            nav_row,
            text="Commencer à l'étape 1 : Préparer mon dossier ->",
            command=lambda: self.notebook.select(self.tab_setup),
        )
        btn_next.pack(side="right", ipadx=6, ipady=3)
        Tooltip(btn_next, "Passe à l'onglet 1 pour créer votre espace de travail et y déposer vos fichiers.")
    def _show_export_guide_popup(self) -> None:
        """Affiche une aide détaillée sur l'export de tous les services gérés."""
        messagebox.showinfo(
            "Comment exporter vos fichiers ?",
            "• Contacts (.csv) : Google Contacts (Exporter -> Google CSV) ou Outlook (Fichier -> Exporter -> CSV).\n\n"
            "• SMS Android (.xml) : App « SMS Backup & Restore » -> Configurer une sauvegarde -> fichier .xml.\n\n"
            "• WhatsApp (.txt) : Ouvrir la discussion -> menu (3 points) -> Plus -> Exporter la discussion (Sans médias).\n\n"
            "• Google Chat (.json) : ://google.com -> cocher « Google Chat » -> décompresser le ZIP.\n\n"
            "• Microsoft Teams (.json / .vtt) :\n"
            "  - Messages : ://microsoft.com -> Télécharger vos données -> Messages Teams (.json).\n"
            "  - Réunions : onglet « Enregistrement et transcription » -> Télécharger -> format .vtt.\n\n"
            "• Facebook Messenger & Instagram (.json) : Paramètres Meta -> Télécharger vos informations -> Messages -> format JSON.\n\n"
            "• Signal : Pas d'export natif — copiez-collez les échanges depuis Signal Desktop dans un fichier .txt ou .pdf.\n\n"
            "• E-mails (.mbox / .eml) : Google Takeout (Mail -> .mbox) ou glisser-déposer depuis Thunderbird/Outlook (.eml).",
        )

    def _build_tab_setup(self) -> None:
        """Onglet 1 : choix ou création d'un dossier isolé et dépôt des fichiers."""
        grp_ws = ttk.LabelFrame(
            self.tab_setup,
            text="Étape 1A — Choisir ou créer un « dossier » (espace de travail isolé)",
            padding=10,
        )
        grp_ws.pack(fill="x", pady=(0, 10))

        ttk.Label(
            grp_ws,
            text="Qu'est-ce qu'un dossier ici ? C'est un espace séparé créé sur votre PC pour une affaire (ex. un enfant ou un salarié). "
            "Ses contacts et documents restent totalement isolés des autres dossiers.",
            foreground="#444444",
            wraplength=880,
        ).pack(anchor="w", pady=(0, 8))

        row_sel = ttk.Frame(grp_ws)
        row_sel.pack(fill="x", pady=(0, 6))
        ttk.Label(row_sel, text="Dossier actuellement ouvert :").pack(side="left", padx=(0, 8))
        self.combo_ws = ttk.Combobox(
            row_sel, textvariable=self.workspace_choice_var, state="readonly", width=44
        )
        self.combo_ws.pack(side="left", padx=(0, 8))
        self.combo_ws.bind("<<ComboboxSelected>>", self._on_workspace_selected)
        Tooltip(
            self.combo_ws,
            "Sélectionnez le dossier sur lequel vous voulez travailler. Chaque dossier garde ses propres règles et résultats.",
        )

        row_new = ttk.Frame(grp_ws)
        row_new.pack(fill="x")
        ttk.Label(row_new, text="Créer un nouveau dossier (ex. Dossier_Enfant) :").pack(
            side="left", padx=(0, 8)
        )
        entry_ws = ttk.Entry(row_new, textvariable=self.new_ws_name_var, width=26)
        entry_ws.pack(side="left", padx=(0, 8))
        Tooltip(
            entry_ws,
            "Saisissez un nom court sans caractères spéciaux (ex. Dossier_Enfant, Dossier_Salarie).",
        )
        btn_create_ws = ttk.Button(
            row_new, text="Créer ce dossier", command=self._create_new_workspace
        )
        btn_create_ws.pack(side="left")
        Tooltip(
            btn_create_ws,
            "Crée automatiquement les sous-dossiers nécessaires (documents sources, contacts, résultats) pour cette affaire.",
        )

        grp_files = ttk.LabelFrame(
            self.tab_setup,
            text="Étape 1B — Déposer vos documents et importer votre carnet de contacts (.csv)",
            padding=10,
        )
        grp_files.pack(fill="x", pady=(0, 10))

        ttk.Label(
            grp_files,
            text="Qu'est-ce qu'un CSV ? C'est le fichier tableau exporté depuis Google Contacts ou Outlook contenant les noms, "
            "téléphones et e-mails de vos interlocuteurs. L'importer aide considérablement le logiciel dès le 1er passage.",
            wraplength=880,
            foreground="#444444",
        ).pack(anchor="w", pady=(0, 8))

        btn_row1 = ttk.Frame(grp_files)
        btn_row1.pack(fill="x")

        btn_src = ttk.Button(
            btn_row1,
            text="1. Ouvrir le dossier où déposer mes documents",
            command=lambda: self._open_workspace_folder("sources_dir"),
        )
        btn_src.pack(side="left", padx=(0, 8))
        Tooltip(
            btn_src,
            "Ouvre le dossier 'input_documents' dans votre Explorateur : copiez-collez dedans vos PDF, scans, Word, "
            "SMS (.xml), WhatsApp (.txt), Google Chat/Teams/Messenger (.json/.vtt), e-mails (.mbox/.eml) ou vocaux.",
        )

        btn_csv = ttk.Button(
            btn_row1,
            text="2. Importer un carnet de contacts (.csv) (fortement recommandé)",
            command=self._import_csv_dialog,
        )
        btn_csv.pack(side="left", padx=(0, 8))
        Tooltip(
            btn_csv,
            "Choisissez un fichier .csv exporté depuis Google Contacts ou Outlook. Le logiciel en extrait automatiquement "
            "les noms, numéros et e-mails pour les masquer partout (même en cas de faute de scan).",
        )

        btn_how = ttk.Button(
            btn_row1,
            text="? Comment exporter mes fichiers",
            command=self._show_export_guide_popup,
        )
        btn_how.pack(side="right")
        Tooltip(
            btn_how,
            "Affiche la marche à suivre pour exporter vos contacts CSV, SMS, WhatsApp, Teams, Google Chat, Messenger/Instagram, Signal ou e-mails.",
        )

        grp_out = ttk.LabelFrame(
            self.tab_setup,
            text="Étape 1C — Récupérer vos fichiers anonymisés (une fois le traitement terminé)",
            padding=10,
        )
        grp_out.pack(fill="x")

        btn_res = ttk.Button(
            grp_out,
            text="Ouvrir le dossier des résultats anonymisés",
            command=lambda: self._open_workspace_folder("results_dir"),
        )
        btn_res.pack(side="left", padx=(0, 8))
        Tooltip(
            btn_res,
            "Ouvre le dossier 'anonymized_results' contenant les fichiers texte nettoyés et classés par mois (batch_01, batch_02...).",
        )

        btn_man = ttk.Button(
            grp_out,
            text="Voir ma liste de noms masqués (manual_contacts.txt)",
            command=lambda: self._open_workspace_file("manual_contacts_file"),
        )
        btn_man.pack(side="left", padx=(0, 8))
        Tooltip(
            btn_man,
            "Ouvre le fichier texte contenant les règles manuelles spécifiques à ce dossier (format : Nom = Alias).",
        )

        btn_go_run = ttk.Button(
            grp_out,
            text="Étape suivante : Lancer l'anonymisation ->",
            command=lambda: self.notebook.select(self.tab_run),
        )
        btn_go_run.pack(side="right")
        Tooltip(btn_go_run, "Passe à l'onglet 2 pour démarrer l'extraction et l'anonymisation.")
    def _build_tab_run(self) -> None:
        """Onglet 2 : lancement du pipeline avec explications simples et infobulles."""
        help_box = ttk.LabelFrame(
            self.tab_run, text="Quel bouton choisir ?", padding=10
        )
        help_box.pack(fill="x", pady=(0, 10))
        ttk.Label(
            help_box,
            text=(
                "• « 1er passage : Extraire et anonymiser tout » : à utiliser la première fois ou quand vous ajoutez de nouveaux documents.\n"
                "• « 2e passage rapide : Ré-anonymiser uniquement » : à utiliser après avoir ajouté un nom à masquer (dure quelques secondes).\n"
                "• « Mettre à jour les contacts » : relit votre carnet CSV et pré-scanne les interlocuteurs de vos chats et e-mails."
            ),
            wraplength=880,
            justify="left",
        ).pack(anchor="w")

        ctrl_row = ttk.Frame(self.tab_run)
        ctrl_row.pack(fill="x", pady=(0, 10))

        self.btn_full = ttk.Button(
            ctrl_row,
            text="1er passage : Extraire et anonymiser tout",
            command=lambda: self._start_job("full"),
        )
        self.btn_full.pack(side="left", padx=(0, 8))
        Tooltip(
            self.btn_full,
            "Lit tous vos documents sources (PDF, scans OCR, Word, SMS, chats, e-mails, audios) et génère les lots anonymisés.",
        )

        self.btn_anon_only = ttk.Button(
            ctrl_row,
            text="2e passage rapide : Ré-anonymiser uniquement",
            command=lambda: self._start_job("anonymize_only"),
        )
        self.btn_anon_only.pack(side="left", padx=(0, 8))
        Tooltip(
            self.btn_anon_only,
            "Ré-applique instantanément les règles de masquage sur les textes déjà extraits, sans relire les PDF ni les audios.",
        )

        self.btn_contacts = ttk.Button(
            ctrl_row,
            text="Mettre à jour les contacts",
            command=lambda: self._start_job("contacts"),
        )
        self.btn_contacts.pack(side="left")
        Tooltip(
            self.btn_contacts,
            "Traite les fichiers CSV importés, pré-scanne vos chats/e-mails et unifie tous les contacts dans contacts.txt.",
        )

        self.progress = ttk.Progressbar(self.tab_run, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 8))

        ttk.Label(
            self.tab_run,
            text="Suivi détaillé du traitement en cours :",
            foreground="#444444",
        ).pack(anchor="w", pady=(0, 4))

        self.log_text = tk.Text(
            self.tab_run, height=18, wrap="word", font=("Consolas", 9), state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)

    def _build_tab_audit(self) -> None:
        """Onglet 3 : validation visuelle de audits/residual_names_copy.txt avec infobulles."""
        help_audit = ttk.LabelFrame(
            self.tab_audit, text="Comment vérifier cette liste ?", padding=10
        )
        help_audit.pack(fill="x", pady=(0, 8))
        ttk.Label(
            help_audit,
            text=(
                "Après chaque passage, le logiciel liste ci-dessous les mots avec majuscule qui pourraient encore être des noms de personnes.\n"
                "1) Cliquez sur une ligne : si c'est une personne ou un organisme à cacher, cliquez sur « Masquer ce nom ».\n"
                "2) Si c'est un mot normal (ex. « Tribunal », « Orthophoniste »), cliquez sur « Ignorer ce mot ».\n"
                "3) Quand vous avez fini, cliquez sur « Appliquer mes corrections » en bas à droite."
            ),
            wraplength=880,
            justify="left",
        ).pack(anchor="w")

        top_info = ttk.Frame(self.tab_audit)
        top_info.pack(fill="x", pady=(0, 6))
        self.audit_count_var = tk.StringVar(value="0 élément(s) à vérifier.")
        ttk.Label(top_info, textvariable=self.audit_count_var, font=("Segoe UI", 9, "bold")).pack(
            side="left"
        )
        btn_refresh = ttk.Button(
            top_info, text="Actualiser la liste", command=self._refresh_audit_list
        )
        btn_refresh.pack(side="right")
        Tooltip(btn_refresh, "Recharge la liste des noms potentiels détectés lors du dernier passage.")

        cols = ("candidate", "alias")
        self.audit_tree = ttk.Treeview(
            self.tab_audit, columns=cols, show="headings", selectmode="browse", height=13
        )
        self.audit_tree.heading("candidate", text="Mot ou nom repéré dans vos documents")
        self.audit_tree.heading("alias", text="Code qui le remplacera")
        self.audit_tree.column("candidate", width=420)
        self.audit_tree.column("alias", width=340)
        self.audit_tree.pack(fill="both", expand=True, pady=(0, 10))
        Tooltip(
            self.audit_tree,
            "Sélectionnez une ligne puis choisissez en bas si ce mot doit être masqué ou ignoré.",
        )

        act_row = ttk.Frame(self.tab_audit)
        act_row.pack(fill="x")

        btn_mask = ttk.Button(
            act_row,
            text="Masquer ce nom (c'est une personne)",
            command=self._approve_selected_audit,
        )
        btn_mask.pack(side="left", padx=(0, 10))
        Tooltip(
            btn_mask,
            "Ajoute ce nom dans 'manual_contacts.txt' pour qu'il soit remplacé par son code lors de la ré-anonymisation.",
        )

        btn_ignore = ttk.Button(
            act_row,
            text="Ignorer ce mot (faux positif)",
            command=self._exclude_selected_audit,
        )
        btn_ignore.pack(side="left", padx=(0, 10))
        Tooltip(
            btn_ignore,
            "Ajoute ce mot dans le dictionnaire des mots courants exclus ('data/mots_exclus.txt') pour ne plus être alerté.",
        )

        btn_apply = ttk.Button(
            act_row,
            text="Appliquer mes corrections (2e passage rapide)",
            command=lambda: self._start_job("anonymize_only"),
        )
        btn_apply.pack(side="right")
        Tooltip(
            btn_apply,
            "Relance immédiatement le nettoyage rapide des fichiers avec les nouveaux noms ajoutés.",
        )
    def _append_log(self, line: str) -> None:
        """Ajoute une ligne dans la zone de journal."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _refresh_workspaces(self, select_ini: Optional[str] = None) -> None:
        """Recharge la liste des dossiers disponibles."""
        self.workspaces = self.controller.list_workspaces()
        labels: List[str] = [lbl for lbl, _ in self.workspaces]
        self.combo_ws["values"] = labels
        if not self.workspaces:
            return
        target_idx: int = 0
        if select_ini:
            for idx, (_, p_ini) in enumerate(self.workspaces):
                if os.path.abspath(p_ini) == os.path.abspath(select_ini):
                    target_idx = idx
                    break
        self.combo_ws.current(target_idx)
        _, selected_ini = self.workspaces[target_idx]
        self.current_ini_var.set(selected_ini)
        self._refresh_audit_list()

    def _on_workspace_selected(self, _event: object = None) -> None:
        """Met à jour le fichier config.ini actif lors du changement de dossier."""
        idx: int = self.combo_ws.current()
        if 0 <= idx < len(self.workspaces):
            lbl, p_ini = self.workspaces[idx]
            self.current_ini_var.set(p_ini)
            self._refresh_audit_list()
            self.status_var.set(f"Dossier actif : {lbl}")

    def _create_new_workspace(self) -> None:
        """Crée un nouveau profil isolé et le sélectionne."""
        raw_name: str = self.new_ws_name_var.get().strip()
        if not raw_name:
            messagebox.showwarning("Nom requis", "Veuillez saisir un nom de dossier (ex. Dossier_Enfant).")
            return
        try:
            ini_path: str = self.controller.create_workspace(raw_name)
            self.new_ws_name_var.set("")
            self._refresh_workspaces(select_ini=ini_path)
            self.status_var.set(f"Dossier prêt : {os.path.dirname(ini_path)}")
            messagebox.showinfo(
                "Dossier créé",
                "Votre nouvel espace est prêt !\n\n"
                "Cliquez maintenant sur « 1. Ouvrir le dossier où déposer mes documents » pour y glisser vos fichiers.",
            )
        except OSError as exc:
            messagebox.showerror("Erreur", str(exc))

    def _open_path_in_os(self, target_path: str) -> None:
        """Ouvre un dossier ou un fichier dans le gestionnaire natif du système."""
        if not os.path.exists(target_path):
            messagebox.showinfo("Information", f"Aucun fichier généré pour le moment :\n{target_path}")
            return
        if os.name == "nt":
            os.startfile(target_path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target_path])
        else:
            subprocess.Popen(["xdg-open", target_path])

    def _open_workspace_folder(self, key: str) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        paths: Dict[str, str] = self.controller.resolve_workspace_paths(ini_path)
        os.makedirs(paths[key], exist_ok=True)
        self._open_path_in_os(paths[key])

    def _open_workspace_file(self, key: str) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        paths: Dict[str, str] = self.controller.resolve_workspace_paths(ini_path)
        self._open_path_in_os(paths[key])

    def _import_csv_dialog(self) -> None:
        """Sélectionne un CSV de contacts, le copie et lance son extraction."""
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        csv_file: str = filedialog.askopenfilename(
            title="Sélectionner un export de contacts CSV",
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")],
        )
        if not csv_file:
            return
        try:
            dest: str = self.controller.import_contacts_csv(ini_path, csv_file)
            self._append_log(f"[CONTACTS] Carnet importé : {dest}")
            self._start_job("contacts")
        except OSError as exc:
            messagebox.showerror("Erreur d'import", str(exc))

    def _set_buttons_state(self, enabled: bool) -> None:
        state_val: str = "normal" if enabled else "disabled"
        self.btn_full.configure(state=state_val)
        self.btn_anon_only.configure(state=state_val)
        self.btn_contacts.configure(state=state_val)

    def _start_job(self, mode: str) -> None:
        """Exécute le script Python correspondant dans un thread secondaire."""
        if self.is_running:
            return
        ini_path: str = self.current_ini_var.get()
        if not ini_path or not os.path.isfile(ini_path):
            messagebox.showwarning("Configuration manquante", "Aucun dossier sélectionné.")
            return

        self.is_running = True
        self._set_buttons_state(False)
        self.progress.start(12)
        self.notebook.select(self.tab_run)
        self.status_var.set("Traitement en cours, veuillez patienter...")

        cmd: List[str] = self.controller.build_cli_command(ini_path, mode)
        self._append_log(f"\n>>> Lancement : {' '.join(cmd)}")

        def _worker() -> None:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.Popen(
                cmd,
                cwd=ROOT_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc.stdout:
                for raw_ln in proc.stdout:
                    ln: str = raw_ln.rstrip("\r\n")
                    if ln:
                        self.after(0, self._append_log, ln)
            ret: int = proc.wait()
            self.after(0, self._on_job_finished, ret, mode)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_job_finished(self, return_code: int, mode: str) -> None:
        """Réactive l'interface et actualise l'audit une fois le traitement terminé."""
        self.progress.stop()
        self.is_running = False
        self._set_buttons_state(True)
        self._refresh_audit_list()
        if return_code == 0:
            self.status_var.set("Traitement terminé avec succès.")
            self._append_log("[OK] Traitement terminé.")
            if mode in {"full", "anonymize_only"}:
                cands = self.controller.load_audit_candidates(self.current_ini_var.get())
                if cands:
                    self.notebook.select(self.tab_audit)
                    messagebox.showinfo(
                        "Vérification recommandée",
                        f"Le traitement est terminé !\n\n"
                        f"{len(cands)} nom(s) potentiel(s) sont affichés dans l'onglet 3 pour contrôle rapide.",
                    )
                else:
                    messagebox.showinfo(
                        "Terminé — 0 nom résiduel",
                        "Tout est propre ! Aucun nom résiduel n'a été détecté.\n"
                        "Vous pouvez ouvrir le dossier des résultats anonymisés dans l'onglet 1.",
                    )
        else:
            self.status_var.set(f"Traitement terminé avec avertissement (code {return_code}).")
            self._append_log(f"[ATTENTION] Code retour : {return_code}")

    def _refresh_audit_list(self) -> None:
        """Recharge les candidats de residual_names_copy.txt dans le tableau."""
        for item in self.audit_tree.get_children():
            self.audit_tree.delete(item)
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            self.audit_count_var.set("0 élément(s) à vérifier.")
            return
        candidates: List[Tuple[str, str]] = self.controller.load_audit_candidates(ini_path)
        for cand, alias in candidates:
            self.audit_tree.insert("", "end", values=(cand, alias))
        self.audit_count_var.set(f"{len(candidates)} élément(s) à vérifier dans ce dossier.")

    def _approve_selected_audit(self) -> None:
        """Enregistre la ligne sélectionnée dans manual_contacts.txt."""
        sel = self.audit_tree.selection()
        if not sel:
            messagebox.showinfo("Sélection requise", "Cliquez d'abord sur une ligne du tableau.")
            return
        vals = self.audit_tree.item(next(iter(sel)), "values")
        if len(vals) < 2:
            return
        cand_txt, alias_txt = str(vals), str(vals)
        ini_path: str = self.current_ini_var.get()
        self.controller.approve_audit_mask(ini_path, cand_txt, alias_txt)
        self._refresh_audit_list()
        self.status_var.set(f"Ajouté aux noms à masquer : {cand_txt} -> {alias_txt}")

    def _exclude_selected_audit(self) -> None:
        """Ajoute les mots de la ligne sélectionnée dans data/mots_exclus.txt."""
        sel = self.audit_tree.selection()
        if not sel:
            messagebox.showinfo("Sélection requise", "Cliquez d'abord sur une ligne du tableau.")
            return
        vals = self.audit_tree.item(next(iter(sel)), "values")
        if not vals:
            return
        cand_txt: str = str(vals)
        ini_path: str = self.current_ini_var.get()
        self.controller.exclude_audit_false_positive(ini_path, cand_txt)
        self._refresh_audit_list()
        self.status_var.set(f"Mot courant ignoré : {cand_txt}")


def main() -> None:
    """Point d'entrée de l'interface graphique."""
    app = AnonymizerGuiApp()
    app.mainloop()


if __name__ == "__main__":
    main()
