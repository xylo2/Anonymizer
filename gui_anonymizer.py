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
    """Infobulle moderne affichée au survol d'un élément."""

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
        x: int = self.widget.winfo_rootx() + 14
        y: int = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        win = tk.Toplevel(self.widget)
        win.wm_overrideredirect(True)
        win.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            win,
            text=self.text,
            justify="left",
            background="#1e293b",
            foreground="#f8fafc",
            relief="flat",
            padx=10,
            pady=6,
            wraplength=400,
            font=("Segoe UI", 9),
        )
        lbl.pack()
        self.tip_win = win

    def _hide(self, _event: object = None) -> None:
        if self.tip_win is not None:
            self.tip_win.destroy()
            self.tip_win = None


class AnonymizerGuiApp(tk.Tk):
    """Interface graphique moderne et guidée pour anonymiser des dossiers confidentiels."""

    COLORS: Dict[str, str] = {
        "bg": "#f1f5f9",
        "card": "#ffffff",
        "border": "#cbd5e1",
        "sidebar": "#0f172a",
        "sidebar_hover": "#1e293b",
        "sidebar_active": "#2563eb",
        "text": "#0f172a",
        "muted": "#475569",
        "primary": "#2563eb",
        "primary_hover": "#1d4ed8",
        "success": "#16a34a",
        "success_hover": "#15803d",
        "secondary": "#e2e8f0",
        "secondary_hover": "#cbd5e1",
        "badge_bg": "#dcfce7",
        "badge_fg": "#166534",
        "log_bg": "#0f172a",
        "log_fg": "#e2e8f0",
    }

    GUIDE_SECTIONS: List[Tuple[str, str, str]] = [
        (
            "sec_intro",
            "1. Principe",
            "1. À QUOI SERT CE LOGICIEL ?\n"
            "Cet outil prépare vos documents confidentiels (comptes rendus médicaux, bilans orthophoniques, "
            "attestations scolaires, échanges entre parents, SMS, e-mails, courriers employeur) "
            "en remplaçant automatiquement les noms, adresses, téléphones et numéros sensibles par des codes neutres "
            "(ex. « Camille D. », « Dr M. », « [ADRESSE_MASQUEE] », « [NUM_SECU_MASQUE] »).\n"
            "Vos fichiers originaux ne sont jamais modifiés et rien n'est envoyé sur Internet.",
        ),
        (
            "sec_folder",
            "2. Dossier",
            "2. QU'EST-CE QU'UN « DOSSIER » DANS CE LOGICIEL ?\n"
            "Un dossier (ou espace de travail) est un tiroir numérique totalement étanche créé sur votre ordinateur "
            "pour une affaire précise (ex. « Dossier_Enfant » ou « Dossier_Salarie »).\n"
            "Chaque dossier possède ses propres documents, ses propres contacts et ses propres résultats : "
            "les noms d'une affaire ne se mélangent jamais avec ceux d'une autre.",
        ),
        (
            "sec_csv",
            "3. Export contacts (.csv)",
            "3. QU'EST-CE QUE L'EXPORT CONTACTS (.CSV) ET POURQUOI L'IMPORTER ?\n"
            "Le format .csv est un format de fichier tableau standard (ouvrable avec Excel ou LibreOffice) "
            "utilisé par les messageries et téléphones pour exporter un carnet d'adresses.\n"
            "Dans ce logiciel, importer l'export CSV de vos contacts à l'étape 1 est FORTEMENT RECOMMANDÉ : "
            "cela aide considérablement le programme à reconnaître et masquer vos proches, médecins ou interlocuteurs "
            "dès le 1er passage (y compris en cas de faute de frappe ou de scan flou).",
        ),
        (
            "sec_exports",
            "4. Exporter vos fichiers",
            "4. COMMENT EXPORTER VOS FICHIERS POUR LES DONNER AU LOGICIEL ?\n"
            "• Carnet d'adresses (.csv) : Google Contacts (://google.com -> Exporter -> Google CSV) ou Outlook (Fichier -> Exporter -> CSV).\n"
            "• SMS / MMS Android (.xml) : App gratuite « SMS Backup & Restore » -> Configurer une sauvegarde -> cocher Messages -> fichier .xml.\n"
            "• WhatsApp (.txt) : Ouvrir la discussion -> menu (3 points) -> Plus -> Exporter la discussion -> Sans médias.\n"
            "• Google Chat (.json) : ://google.com -> tout désélectionner -> cocher Google Chat -> décompresser le ZIP.\n"
            "• Microsoft Teams (.json / .vtt) : Messages via ://microsoft.com (.json) ; Réunions via onglet Enregistrement et transcription -> Télécharger (.vtt).\n"
            "• Facebook Messenger & Instagram (.json) : Paramètres Meta -> Télécharger vos informations -> Messages -> format JSON.\n"
            "• Signal (astuce) : Pas d'export direct — sur Signal Desktop, copiez-collez les échanges utiles dans un fichier .txt ou .pdf.\n"
            "• E-mails (.mbox / .eml) : Gmail via ://google.com (.mbox) ou glisser-déposer depuis Thunderbird/Outlook (.eml).",
        ),
        (
            "sec_license",
            "5. Licence (GPL v3)",
            "5. VOS DROITS ET GARANTIES (LICENCE LIBRE GNU GPL v3)\n"
            "Ce logiciel est un bien commun numérique distribué gratuitement sous licence libre GNU GPL v3 :\n"
            "• Liberté d'utilisation : vous pouvez l'utiliser librement, gratuitement et sans limite (usage personnel, familial, associatif ou syndical).\n"
            "• Liberté de partage : vous pouvez le copier et le transmettre à d'autres personnes ou associations.\n"
            "• Garantie d'ouverture (Copyleft) : quiconque modifie ce logiciel et le redistribue a l'obligation légale de partager ses améliorations sous la même licence libre (interdiction d'en faire une version fermée ou propriétaire).\n"
            "• Relecture recommandée : ce logiciel est fourni tel quel sans garantie juridique ; vérifiez toujours les fichiers générés à l'étape 3 avant de les transmettre.",
        ),
    ]
    def __init__(self) -> None:
        super().__init__()
        self.title("Anonymiseur Local de Documents Confidentiels")
        self.geometry("1080x780")
        self.minsize(920, 660)
        self.configure(bg=self.COLORS["bg"])

        self.controller: AnonymizerGuiController = AnonymizerGuiController(ROOT_DIR)
        self.workspaces: List[Tuple[str, str]] = []
        self.current_ini_var: tk.StringVar = tk.StringVar()
        self.active_ws_badge_var: tk.StringVar = tk.StringVar(value="Dossier : aucun")
        self.workspace_choice_var: tk.StringVar = tk.StringVar()
        self.new_ws_name_var: tk.StringVar = tk.StringVar()
        self.status_var: tk.StringVar = tk.StringVar(
            value="Prêt — Survolez un bouton pour afficher son aide."
        )
        self.is_running: bool = False
        self.current_proc: Optional[subprocess.Popen] = None
        self.pages: Dict[str, tk.Frame] = {}
        self.nav_buttons: Dict[str, tk.Button] = {}
        self.active_page_key: str = "help"

        self._configure_ttk_styles()
        self._build_layout()
        self._bind_trackpad_scroll()
        self._refresh_workspaces()
        self._show_page("help")

    def _configure_ttk_styles(self) -> None:
        """Configure un thème ttk épuré et lisible."""
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(
            "Modern.Treeview",
            background="#ffffff",
            foreground="#0f172a",
            fieldbackground="#ffffff",
            rowheight=28,
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Modern.Treeview.Heading",
            background="#e2e8f0",
            foreground="#0f172a",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Modern.Treeview",
            background=[("selected", "#dbeafe")],
            foreground=[("selected", "#1e3a8a")],
        )
        style.configure("TCombobox", padding=5)

    def _make_button(
        self,
        parent: tk.Widget,
        text: str,
        command: object,
        variant: str = "primary",
        tooltip: str = "",
    ) -> tk.Button:
        """Crée un bouton plat moderne avec effet au survol."""
        bg_map = {
            "primary": (self.COLORS["primary"], self.COLORS["primary_hover"], "#ffffff"),
            "success": (self.COLORS["success"], self.COLORS["success_hover"], "#ffffff"),
            "danger": ("#dc2626", "#b91c1c", "#ffffff"),
            "secondary": (self.COLORS["secondary"], self.COLORS["secondary_hover"], "#0f172a"),
        }
        bg, hover_bg, fg = bg_map.get(variant, bg_map["primary"])
        btn = tk.Button(
            parent,
            text=text,
            command=command,  # type: ignore[arg-type]
            bg=bg,
            fg=fg,
            activebackground=hover_bg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=14,
            pady=7,
            cursor="hand2",
            font=("Segoe UI", 9, "bold" if variant != "secondary" else "normal"),
        )
        btn.bind("<Enter>", lambda _e: btn.configure(bg=hover_bg) if btn["state"] == "normal" else None)
        btn.bind("<Leave>", lambda _e: btn.configure(bg=bg) if btn["state"] == "normal" else None)
        if tooltip:
            Tooltip(btn, tooltip)
        return btn

    def _make_card(self, parent: tk.Widget, title: str, subtitle: str = "") -> tk.Frame:
        """Crée une carte blanche à bordure fine pour regrouper les actions."""
        outer = tk.Frame(
            parent,
            bg=self.COLORS["card"],
            highlightbackground=self.COLORS["border"],
            highlightthickness=1,
            padx=16,
            pady=13,
        )
        outer.pack(fill="x", pady=(0, 11))
        tk.Label(
            outer,
            text=title,
            bg=self.COLORS["card"],
            fg=self.COLORS["text"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        if subtitle:
            tk.Label(
                outer,
                text=subtitle,
                bg=self.COLORS["card"],
                fg=self.COLORS["muted"],
                font=("Segoe UI", 9),
                wraplength=760,
                justify="left",
            ).pack(anchor="w", pady=(3, 9))
        return outer
    def _build_layout(self) -> None:
        """Construit la barre latérale de navigation et la zone principale."""
        shell = tk.Frame(self, bg=self.COLORS["bg"])
        shell.pack(fill="both", expand=True)

        sidebar = tk.Frame(shell, bg=self.COLORS["sidebar"], width=235)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar,
            text="ANONYMISEUR",
            bg=self.COLORS["sidebar"],
            fg="#ffffff",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=18, pady=(20, 2))
        tk.Label(
            sidebar,
            text="Santé • Famille • Prud'hommes",
            bg=self.COLORS["sidebar"],
            fg="#94a3b8",
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=18, pady=(0, 20))

        nav_items: List[Tuple[str, str]] = [
            ("help", "0. Mode d'emploi & Exports"),
            ("setup", "1. Dossier & Documents"),
            ("run", "2. Anonymisation"),
            ("audit", "3. Vérifier les noms"),
        ]
        for key, label in nav_items:
            btn = tk.Button(
                sidebar,
                text=f"  {label}",
                anchor="w",
                bg=self.COLORS["sidebar"],
                fg="#e2e8f0",
                activebackground=self.COLORS["sidebar_hover"],
                activeforeground="#ffffff",
                relief="flat",
                bd=0,
                padx=14,
                pady=11,
                cursor="hand2",
                font=("Segoe UI", 9, "bold"),
                command=lambda k=key: self._show_page(k),
            )
            btn.pack(fill="x", padx=10, pady=3)
            self.nav_buttons[key] = btn

        badge = tk.Label(
            sidebar,
            text="100 % LOCAL & HORS-LIGNE\nVos fichiers restent sur ce PC",
            bg="#1e293b",
            fg="#86efac",
            font=("Segoe UI", 8),
            justify="left",
            padx=12,
            pady=10,
        )
        badge.pack(side="bottom", fill="x", padx=12, pady=14)

        main_area = tk.Frame(shell, bg=self.COLORS["bg"])
        main_area.pack(side="left", fill="both", expand=True)

        top_bar = tk.Frame(main_area, bg="#ffffff", height=54)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        self.page_heading_var = tk.StringVar(value="Mode d'emploi & Exports")
        tk.Label(
            top_bar,
            textvariable=self.page_heading_var,
            bg="#ffffff",
            fg=self.COLORS["text"],
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left", padx=20)

        tk.Label(
            top_bar,
            text="Originaux protégés • Hors-ligne",
            bg=self.COLORS["badge_bg"],
            fg=self.COLORS["badge_fg"],
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=4,
        ).pack(side="right", padx=(6, 20))

        tk.Label(
            top_bar,
            textvariable=self.active_ws_badge_var,
            bg="#e0f2fe",
            fg="#0369a1",
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=4,
        ).pack(side="right", padx=6)

        self.content_container = tk.Frame(main_area, bg=self.COLORS["bg"], padx=18, pady=14)
        self.content_container.pack(fill="both", expand=True)

        for key in ("help", "setup", "run", "audit"):
            frame = tk.Frame(self.content_container, bg=self.COLORS["bg"])
            self.pages[key] = frame

        self._build_page_help()
        self._build_page_setup()
        self._build_page_run()
        self._build_page_audit()

        footer = tk.Frame(main_area, bg="#e2e8f0", height=28)
        footer.pack(fill="x", side="bottom")
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg="#e2e8f0",
            fg="#1e293b",
            font=("Segoe UI", 8),
        ).pack(side="left", padx=16, pady=4)

    def _show_page(self, key: str) -> None:
        """Affiche la page demandée et met en surbrillance le menu actif."""
        titles = {
            "help": "0. Mode d'emploi & Guide des exports",
            "setup": "1. Préparer mon dossier et déposer mes documents",
            "run": "2. Lancer l'extraction et l'anonymisation",
            "audit": "3. Vérifier et corriger les noms restants",
        }
        self.active_page_key = key
        self.page_heading_var.set(titles.get(key, ""))
        for k, frame in self.pages.items():
            if k == key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        for k, btn in self.nav_buttons.items():
            btn.configure(
                bg=self.COLORS["sidebar_active"] if k == key else self.COLORS["sidebar"],
                fg="#ffffff",
            )
    def _bind_trackpad_scroll(self) -> None:
        """Rend le défilement au trackpad fluide sur Windows et Linux."""
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

    def _select_guide_card(self, idx: int) -> None:
        """Affiche directement la fiche demandée sans aucun défilement requis."""
        if not (0 <= idx < len(self.GUIDE_SECTIONS)):
            return
        _, _, body = self.GUIDE_SECTIONS[idx]
        title_line, *rest = body.strip().split("\n", 1)
        self.guide_title_var.set(title_line.strip())
        self.guide_body_var.set(next(iter(rest)).strip() if rest else "")
        for b_idx, btn in enumerate(self.guide_nav_buttons):
            if b_idx == idx:
                btn.configure(bg=self.COLORS["primary"], fg="#ffffff")
            else:
                btn.configure(bg=self.COLORS["secondary"], fg=self.COLORS["text"])

    def _build_page_help(self) -> None:
        """Page 0 : fiches cliquables sans aucun défilement au trackpad."""
        parent = self.pages["help"]
        nav_cards = tk.Frame(parent, bg=self.COLORS["bg"])
        nav_cards.pack(fill="x", pady=(0, 12))

        self.guide_nav_buttons: List[tk.Button] = []
        for idx, (_, short_label, _) in enumerate(self.GUIDE_SECTIONS):
            btn = tk.Button(
                nav_cards,
                text=short_label,
                command=lambda i=idx: self._select_guide_card(i),
                relief="flat",
                bd=0,
                padx=14,
                pady=8,
                cursor="hand2",
                font=("Segoe UI", 9, "bold"),
            )
            btn.pack(side="left", padx=(0, 8))
            self.guide_nav_buttons.append(btn)

        card = tk.Frame(
            parent,
            bg=self.COLORS["card"],
            highlightbackground=self.COLORS["border"],
            highlightthickness=1,
            padx=20,
            pady=18,
        )
        card.pack(fill="both", expand=True, pady=(0, 12))

        self.guide_title_var = tk.StringVar()
        self.guide_body_var = tk.StringVar()

        tk.Label(
            card,
            textvariable=self.guide_title_var,
            bg=self.COLORS["card"],
            fg=self.COLORS["primary"],
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        tk.Label(
            card,
            textvariable=self.guide_body_var,
            bg=self.COLORS["card"],
            fg=self.COLORS["text"],
            font=("Segoe UI", 10),
            justify="left",
            wraplength=740,
        ).pack(anchor="w", fill="x")

        self._select_guide_card(0)

        nav_row = tk.Frame(parent, bg=self.COLORS["bg"])
        nav_row.pack(fill="x")
        self._make_button(
            nav_row,
            text="Commencer à l'étape 1 : Préparer mon dossier ->",
            command=lambda: self._show_page("setup"),
            variant="primary",
            tooltip="Passe à l'étape 1 pour créer votre espace de travail et y déposer vos fichiers.",
        ).pack(side="right")

    def _show_export_guide_popup(self) -> None:
        """Affiche une aide détaillée sur l'export de tous les services gérés."""
        messagebox.showinfo(
            "Comment exporter vos fichiers ?",
            "• Export contacts (.csv) : Google Contacts (Exporter -> Google CSV) ou Outlook (Fichier -> Exporter -> CSV).\n\n"
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
    def _build_page_setup(self) -> None:
        """Page 1 : choix ou création d'un dossier isolé et dépôt des fichiers."""
        parent = self.pages["setup"]

        card_ws = self._make_card(
            parent,
            title="Étape 1A — Choisir ou créer un « dossier » (espace de travail étanche)",
            subtitle="Un dossier est un espace séparé créé sur votre ordinateur pour une affaire (ex. Dossier_Enfant ou Dossier_Salarie). Ses contacts et documents restent isolés des autres affaires.",
        )

        row_sel = tk.Frame(card_ws, bg=self.COLORS["card"])
        row_sel.pack(fill="x", pady=(0, 8))
        tk.Label(
            row_sel,
            text="Dossier actif :",
            bg=self.COLORS["card"],
            fg=self.COLORS["text"],
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 8))
        self.combo_ws = ttk.Combobox(
            row_sel, textvariable=self.workspace_choice_var, state="readonly", width=42
        )
        self.combo_ws.pack(side="left", padx=(0, 8))
        self.combo_ws.bind("<<ComboboxSelected>>", self._on_workspace_selected)
        Tooltip(
            self.combo_ws,
            "Sélectionnez le dossier sur lequel vous voulez travailler. Chaque dossier garde ses propres règles et résultats.",
        )

        row_new = tk.Frame(card_ws, bg=self.COLORS["card"])
        row_new.pack(fill="x")
        tk.Label(
            row_new,
            text="Nouveau dossier :",
            bg=self.COLORS["card"],
            fg=self.COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 8))
        entry_ws = tk.Entry(
            row_new,
            textvariable=self.new_ws_name_var,
            width=26,
            relief="solid",
            bd=1,
            font=("Segoe UI", 9),
        )
        entry_ws.pack(side="left", padx=(0, 8), ipady=4)
        Tooltip(
            entry_ws,
            "Saisissez un nom court sans caractères spéciaux (ex. Dossier_Enfant, Dossier_Salarie).",
        )
        self._make_button(
            row_new,
            text="Créer ce dossier",
            command=self._create_new_workspace,
            variant="secondary",
            tooltip="Crée automatiquement les sous-dossiers nécessaires (documents sources, contacts, résultats) pour cette affaire.",
        ).pack(side="left")

        card_files = self._make_card(
            parent,
            title="Étape 1B — Déposer vos documents et ajouter vos carnets de contacts (.csv)",
            subtitle="Vous avez plusieurs carnets (Google Contacts, Outlook, téléphone...) dans différents dossiers ? Cliquez plusieurs fois sur « Ajouter un carnet (.csv) » : chaque fichier est copié ici et fusionné avec les précédents.",
        )

        btn_row1 = tk.Frame(card_files, bg=self.COLORS["card"])
        btn_row1.pack(fill="x")

        self._make_button(
            btn_row1,
            text="1. Ouvrir le dossier des documents",
            command=lambda: self._open_workspace_folder("sources_dir"),
            variant="primary",
            tooltip="Ouvre le dossier 'input_documents' : copiez-collez dedans vos PDF, scans, Word, SMS (.xml), WhatsApp (.txt), Google Chat/Teams/Messenger (.json/.vtt), e-mails (.mbox/.eml) ou vocaux.",
        ).pack(side="left", padx=(0, 8))

        self._make_button(
            btn_row1,
            text="2. Ajouter un carnet (.csv) — recommandé",
            command=self._import_csv_dialog,
            variant="success",
            tooltip="Ajoute un ou plusieurs fichiers .csv (depuis n'importe quel dossier de votre PC). Répétez l'opération autant de fois que nécessaire : tous vos carnets sont cumulés et fusionnés.",
        ).pack(side="left", padx=(0, 8))

        self._make_button(
            btn_row1,
            text="Voir mes carnets",
            command=lambda: self._open_workspace_folder("input_contacts_dir"),
            variant="secondary",
            tooltip="Ouvre le dossier 'input_contacts' où sont regroupés tous vos fichiers .csv ajoutés.",
        ).pack(side="left", padx=(0, 8))

        self._make_button(
            btn_row1,
            text="Comment exporter ?",
            command=self._show_export_guide_popup,
            variant="secondary",
            tooltip="Affiche la marche à suivre pour exporter vos contacts CSV, SMS, WhatsApp, Teams, Google Chat, Messenger/Instagram, Signal ou e-mails.",
        ).pack(side="right")

        status_files_row = tk.Frame(card_files, bg=self.COLORS["card"])
        status_files_row.pack(fill="x", pady=(8, 0))

        self.docs_summary_var = tk.StringVar(value="Documents sources déposés : 0 fichier.")
        self.csv_summary_var = tk.StringVar(value="Carnets (.csv) chargés : aucun.")

        info_col = tk.Frame(status_files_row, bg=self.COLORS["card"])
        info_col.pack(side="left", fill="x", expand=True)
        tk.Label(
            info_col,
            textvariable=self.docs_summary_var,
            bg=self.COLORS["card"],
            fg=self.COLORS["text"],
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            info_col,
            textvariable=self.csv_summary_var,
            bg=self.COLORS["card"],
            fg=self.COLORS["primary"],
            font=("Segoe UI", 8, "bold"),
            wraplength=660,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        self._make_button(
            status_files_row,
            text="Actualiser",
            command=self._refresh_workspace_counters,
            variant="secondary",
            tooltip="Met à jour le nombre de documents et de carnets CSV détectés dans le dossier actif.",
        ).pack(side="right")

        card_out = self._make_card(
            parent,
            title="Étape 1C — Récupérer vos fichiers anonymisés (pour IA ou pour un avocat)",
        )
        btn_row2 = tk.Frame(card_out, bg=self.COLORS["card"])
        btn_row2.pack(fill="x", pady=(6, 0))

        self._make_button(
            btn_row2,
            text="Résultats .txt (pour IA)",
            command=lambda: self._open_workspace_folder("results_dir"),
            variant="secondary",
            tooltip="Ouvre le dossier 'anonymized_results' contenant les lots .txt optimisés pour une IA.",
        ).pack(side="left", padx=(0, 8))

        self._make_button(
            btn_row2,
            text="Pack Avocat (.docx + Bordereau + ZIP)",
            command=self._export_lawyer_pack,
            variant="success",
            tooltip="Génère un recueil chronologique Word (.docx), un bordereau CSV de pièces numérotées et une archive ZIP prêts à transmettre à un avocat.",
        ).pack(side="left", padx=(0, 8))

        self._make_button(
            btn_row2,
            text="Règles manuelles",
            command=lambda: self._open_workspace_file("manual_contacts_file"),
            variant="secondary",
            tooltip="Ouvre le fichier 'manual_contacts.txt' contenant les règles spécifiques à ce dossier.",
        ).pack(side="left")

        self._make_button(
            btn_row2,
            text="Étape 2 : Lancer ->",
            command=lambda: self._show_page("run"),
            variant="primary",
            tooltip="Passe à l'étape 2 pour démarrer l'extraction et l'anonymisation.",
        ).pack(side="right")
    def _build_page_run(self) -> None:
        """Page 2 : lancement du pipeline avec bouton Arrêter et journal moderne."""
        parent = self.pages["run"]

        card_ctrl = self._make_card(
            parent,
            title="Choisir l'action à lancer",
            subtitle=(
                "• 1er passage complet : lit tous vos documents (PDF, scans OCR, Word, SMS, chats, e-mails, audios) et anonymise tout.\n"
                "• 2e passage rapide : ré-applique vos corrections en quelques secondes sans relire les PDF ni les audios.\n"
                "• Mettre à jour les contacts : relit tous vos carnets CSV et pré-scanne les interlocuteurs de vos chats et e-mails."
            ),
        )

        ctrl_row = tk.Frame(card_ctrl, bg=self.COLORS["card"])
        ctrl_row.pack(fill="x", pady=(0, 10))

        self.btn_full = self._make_button(
            ctrl_row,
            text="1er passage : Extraire et anonymiser tout",
            command=lambda: self._start_job("full"),
            variant="primary",
            tooltip="Lit tous vos documents sources et génère les lots anonymisés classés par date.",
        )
        self.btn_full.pack(side="left", padx=(0, 8))

        self.btn_anon_only = self._make_button(
            ctrl_row,
            text="2e passage rapide : Ré-anonymiser",
            command=lambda: self._start_job("anonymize_only"),
            variant="success",
            tooltip="Ré-applique instantanément les règles de masquage sur les textes déjà extraits.",
        )
        self.btn_anon_only.pack(side="left", padx=(0, 8))

        self.btn_contacts = self._make_button(
            ctrl_row,
            text="Mettre à jour les contacts",
            command=lambda: self._start_job("contacts"),
            variant="secondary",
            tooltip="Traite tous les exports CSV importés, pré-scanne vos chats/e-mails et unifie tous les contacts.",
        )
        self.btn_contacts.pack(side="left", padx=(0, 8))

        self.btn_stop = self._make_button(
            ctrl_row,
            text="Arrêter",
            command=self._stop_current_job,
            variant="danger",
            tooltip="Interrompt immédiatement le traitement en cours.",
        )
        self.btn_stop.configure(state="disabled")
        self.btn_stop.pack(side="right")

        self.progress = ttk.Progressbar(card_ctrl, mode="indeterminate")
        self.progress.pack(fill="x")

        log_card = tk.Frame(
            parent,
            bg=self.COLORS["card"],
            highlightbackground=self.COLORS["border"],
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        log_card.pack(fill="both", expand=True)

        tk.Label(
            log_card,
            text="Suivi en direct du traitement :",
            bg=self.COLORS["card"],
            fg=self.COLORS["text"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        self.log_text = tk.Text(
            log_card,
            height=15,
            wrap="word",
            font=("Consolas", 9),
            bg=self.COLORS["log_bg"],
            fg=self.COLORS["log_fg"],
            insertbackground="#ffffff",
            relief="flat",
            padx=10,
            pady=8,
            state="disabled",
        )
        self.log_text.pack(fill="both", expand=True)

    def _build_page_audit(self) -> None:
        """Page 3 : validation visuelle avec personnalisation de l'alias proposé."""
        parent = self.pages["audit"]

        card_info = self._make_card(
            parent,
            title="Contrôle rapide des mots détectés après anonymisation",
            subtitle=(
                "1) Cliquez sur une ligne : si c'est une personne ou un organisme à cacher, ajustez le code si besoin puis cliquez sur « Masquer ce nom ».\n"
                "2) Si c'est un mot courant (ex. « Tribunal », « Orthophoniste »), cliquez sur « Ignorer ce mot ».\n"
                "3) Une fois la liste vérifiée, cliquez sur « Appliquer mes corrections (2e passage rapide) »."
            ),
        )

        top_info = tk.Frame(card_info, bg=self.COLORS["card"])
        top_info.pack(fill="x")
        self.audit_count_var = tk.StringVar(value="0 élément(s) à vérifier.")
        tk.Label(
            top_info,
            textvariable=self.audit_count_var,
            bg=self.COLORS["card"],
            fg=self.COLORS["text"],
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        self._make_button(
            top_info,
            text="Actualiser la liste",
            command=self._refresh_audit_list,
            variant="secondary",
            tooltip="Recharge la liste des noms potentiels détectés lors du dernier passage.",
        ).pack(side="right")

        table_card = tk.Frame(
            parent,
            bg=self.COLORS["card"],
            highlightbackground=self.COLORS["border"],
            highlightthickness=1,
            padx=10,
            pady=10,
        )
        table_card.pack(fill="both", expand=True, pady=(0, 10))

        cols = ("candidate", "alias")
        self.audit_tree = ttk.Treeview(
            table_card,
            columns=cols,
            show="headings",
            selectmode="browse",
            style="Modern.Treeview",
            height=10,
        )
        self.audit_tree.heading("candidate", text="Mot ou nom repéré dans vos documents")
        self.audit_tree.heading("alias", text="Code qui le remplacera")
        self.audit_tree.column("candidate", width=410)
        self.audit_tree.column("alias", width=330)
        self.audit_tree.pack(fill="both", expand=True)
        self.audit_tree.bind("<<TreeviewSelect>>", self._on_audit_row_selected)
        Tooltip(
            self.audit_tree,
            "Cliquez sur une ligne pour pré-remplir son code de remplacement ci-dessous.",
        )

        edit_row = tk.Frame(parent, bg=self.COLORS["bg"])
        edit_row.pack(fill="x", pady=(0, 8))
        tk.Label(
            edit_row,
            text="Code de remplacement pour la ligne choisie :",
            bg=self.COLORS["bg"],
            fg=self.COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 8))
        self.audit_alias_edit_var = tk.StringVar()
        entry_alias = tk.Entry(
            edit_row,
            textvariable=self.audit_alias_edit_var,
            width=30,
            relief="solid",
            bd=1,
            font=("Segoe UI", 9),
        )
        entry_alias.pack(side="left", ipady=3)
        Tooltip(
            entry_alias,
            "Vous pouvez personnaliser l'alias proposé avant de cliquer sur « Masquer ce nom » (ex. Cabinet_Avocat).",
        )

        act_row = tk.Frame(parent, bg=self.COLORS["bg"])
        act_row.pack(fill="x")

        self._make_button(
            act_row,
            text="Masquer ce nom (personne / organisme)",
            command=self._approve_selected_audit,
            variant="primary",
            tooltip="Ajoute ce nom dans 'manual_contacts.txt' avec le code indiqué ci-dessus.",
        ).pack(side="left", padx=(0, 8))

        self._make_button(
            act_row,
            text="Ignorer ce mot (faux positif)",
            command=self._exclude_selected_audit,
            variant="secondary",
            tooltip="Ajoute ce mot dans le dictionnaire des mots courants exclus ('data/mots_exclus.txt').",
        ).pack(side="left")

        self._make_button(
            act_row,
            text="Appliquer mes corrections (2e passage rapide)",
            command=lambda: self._start_job("anonymize_only"),
            variant="success",
            tooltip="Relance immédiatement le nettoyage rapide des fichiers avec les nouveaux noms ajoutés.",
        ).pack(side="right")
    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _refresh_workspaces(self, select_ini: Optional[str] = None) -> None:
        self.workspaces = self.controller.list_workspaces()
        self.combo_ws["values"] = [lbl for lbl, _ in self.workspaces]
        if not self.workspaces:
            return
        target_idx: int = next(
            (i for i, (_, p) in enumerate(self.workspaces) if select_ini and os.path.abspath(p) == os.path.abspath(select_ini)),
            0,
        )
        self.combo_ws.current(target_idx)
        lbl, selected_ini = self.workspaces[target_idx]
        self.current_ini_var.set(selected_ini)
        self.active_ws_badge_var.set(f"Dossier : {lbl}")
        self._refresh_audit_list()
        self._refresh_workspace_counters()

    def _on_workspace_selected(self, _event: object = None) -> None:
        idx: int = self.combo_ws.current()
        if 0 <= idx < len(self.workspaces):
            lbl, p_ini = self.workspaces[idx]
            self.current_ini_var.set(p_ini)
            self.active_ws_badge_var.set(f"Dossier : {lbl}")
            self._refresh_audit_list()
            self._refresh_workspace_counters()
            self.status_var.set(f"Dossier actif : {lbl}")

    def _create_new_workspace(self) -> None:
        raw_name: str = self.new_ws_name_var.get().strip()
        if not raw_name:
            messagebox.showwarning("Nom requis", "Veuillez saisir un nom de dossier (ex. Dossier_Enfant).")
            return
        try:
            ini_path: str = self.controller.create_workspace(raw_name)
            self.new_ws_name_var.set("")
            self._refresh_workspaces(select_ini=ini_path)
            self.status_var.set(f"Dossier prêt : {os.path.dirname(ini_path)}")
            messagebox.showinfo("Dossier créé", "Votre nouvel espace est prêt !")
        except OSError as exc:
            messagebox.showerror("Erreur", str(exc))

    def _open_path_in_os(self, target_path: str) -> None:
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
        if ini_path:
            paths = self.controller.resolve_workspace_paths(ini_path)
            os.makedirs(paths[key], exist_ok=True)
            self._open_path_in_os(paths[key])

    def _open_workspace_file(self, key: str) -> None:
        ini_path: str = self.current_ini_var.get()
        if ini_path:
            self._open_path_in_os(self.controller.resolve_workspace_paths(ini_path)[key])

    def _export_lawyer_pack(self) -> None:
        """Génère le recueil Word + Bordereau CSV + ZIP et ouvre le dossier généré."""
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        paths = self.controller.resolve_workspace_paths(ini_path)
        res_dir: str = paths["results_dir"]
        if not os.path.isdir(res_dir) or not any(
            fn.lower().endswith(".txt") for _, _, files in os.walk(res_dir) for fn in files
        ):
            messagebox.showinfo(
                "Aucun résultat à exporter",
                "Lancez d'abord l'anonymisation (Étape 2) avant de générer le Pack Avocat.",
            )
            return
        from doc_anonymizer.dossier_exporter import LawyerDossierExporter

        ws_dir: str = os.path.dirname(os.path.abspath(ini_path))
        export_dir: str = os.path.join(ws_dir, "pack_avocat")
        count, out_folder = LawyerDossierExporter(res_dir, export_dir).export_lawyer_pack()
        self.status_var.set(f"Pack Avocat généré ({count} pièce(s)) : {out_folder}")
        messagebox.showinfo(
            "Pack Avocat prêt",
            f"{count} pièce(s) numérotée(s) et classée(s) chronologiquement !\n\n"
            f"Fichiers créés dans :\n{out_folder}\n"
            f"• Recueil_Chronologique_Avocat.docx\n"
            f"• Bordereau_des_Pieces.csv\n"
            f"• Pack_Avocat_Complet.zip",
        )
        self._open_path_in_os(out_folder)

    def _refresh_workspace_counters(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            self.docs_summary_var.set("Documents sources déposés : 0 fichier.")
            self.csv_summary_var.set("Carnets (.csv) chargés : aucun.")
            return
        paths = self.controller.resolve_workspace_paths(ini_path)
        doc_count: int = sum(
            sum(1 for fn in files if not fn.startswith("."))
            for _, _, files in os.walk(paths["sources_dir"])
        ) if os.path.isdir(paths["sources_dir"]) else 0
        self.docs_summary_var.set(f"Documents sources déposés dans ce dossier : {doc_count} fichier(s).")
        c_dir: str = paths["input_contacts_dir"]
        csvs: List[str] = sorted(fn for fn in os.listdir(c_dir) if fn.lower().endswith(".csv")) if os.path.isdir(c_dir) else []
        if not csvs:
            self.csv_summary_var.set("Carnets (.csv) chargés : aucun (vous pouvez en ajouter un ou plusieurs).")
        else:
            prev: str = ", ".join(csvs[:5]) + (f" (+{len(csvs) - 5} autre(s))" if len(csvs) > 5 else "")
            self.csv_summary_var.set(f"Carnets (.csv) chargés ({len(csvs)}) : {prev}")
    def _import_csv_dialog(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        csv_files = filedialog.askopenfilenames(
            title="Ajouter un ou plusieurs carnets de contacts (.csv)",
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")],
        )
        if not csv_files:
            return
        try:
            for csv_file in csv_files:
                dest = self.controller.import_contacts_csv(ini_path, str(csv_file))
                self._append_log(f"[CONTACTS] Carnet ajouté : {dest}")
            self._refresh_workspace_counters()
            self._start_job("contacts")
        except OSError as exc:
            messagebox.showerror("Erreur d'import", str(exc))

    def _set_buttons_state(self, enabled: bool) -> None:
        st: str = "normal" if enabled else "disabled"
        self.btn_full.configure(state=st)
        self.btn_anon_only.configure(state=st)
        self.btn_contacts.configure(state=st)
        self.btn_stop.configure(state="disabled" if enabled else "normal")

    def _stop_current_job(self) -> None:
        if self.current_proc is not None and self.current_proc.poll() is None:
            try:
                self.current_proc.terminate()
                self._append_log("[ARRÊT] Interruption demandée par l'utilisateur.")
                self.status_var.set("Traitement interrompu.")
            except OSError:
                pass

    def _start_job(self, mode: str) -> None:
        if self.is_running:
            return
        ini_path: str = self.current_ini_var.get()
        if not ini_path or not os.path.isfile(ini_path):
            messagebox.showwarning("Configuration manquante", "Aucun dossier sélectionné.")
            return
        self.is_running = True
        self._set_buttons_state(False)
        self.progress.start(12)
        self._show_page("run")
        self.status_var.set("Traitement en cours, veuillez patienter...")
        cmd = self.controller.build_cli_command(ini_path, mode)
        self._append_log(f"\n>>> Lancement : {' '.join(cmd)}")

        def _worker() -> None:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.Popen(
                cmd, cwd=ROOT_DIR, env=env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            )
            self.current_proc = proc
            if proc.stdout:
                for raw_ln in proc.stdout:
                    ln = raw_ln.rstrip("\r\n")
                    if ln:
                        self.after(0, self._append_log, ln)
            ret = proc.wait()
            self.current_proc = None
            self.after(0, self._on_job_finished, ret, mode)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_job_finished(self, return_code: int, mode: str) -> None:
        self.progress.stop()
        self.is_running = False
        self._set_buttons_state(True)
        self._refresh_audit_list()
        self._refresh_workspace_counters()
        if return_code == 0:
            self.status_var.set("Traitement terminé avec succès.")
            self._append_log("[OK] Traitement terminé.")
            if mode in {"full", "anonymize_only"}:
                cands = self.controller.load_audit_candidates(self.current_ini_var.get())
                if cands:
                    self._show_page("audit")
                    messagebox.showinfo("Vérification recommandée", f"{len(cands)} nom(s) potentiel(s) à vérifier dans l'étape 3.")
                else:
                    messagebox.showinfo("Terminé", "Tout est propre ! Aucun nom résiduel détecté.")
        else:
            self.status_var.set(f"Traitement arrêté ou terminé avec avertissement (code {return_code}).")
            self._append_log(f"[INFO] Fin du processus (code : {return_code})")

    def _refresh_audit_list(self) -> None:
        for item in self.audit_tree.get_children():
            self.audit_tree.delete(item)
        self.audit_alias_edit_var.set("")
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            self.audit_count_var.set("0 élément(s) à vérifier.")
            return
        candidates = self.controller.load_audit_candidates(ini_path)
        for cand, alias in candidates:
            self.audit_tree.insert("", "end", values=(cand, alias))
        self.audit_count_var.set(f"{len(candidates)} élément(s) à vérifier dans ce dossier.")

    def _on_audit_row_selected(self, _event: object = None) -> None:
        sel = self.audit_tree.selection()
        if sel:
            vals = tuple(self.audit_tree.item(next(iter(sel)), "values"))
            if len(vals) >= 2:
                _, alias_val = vals[:2]
                self.audit_alias_edit_var.set(str(alias_val))

    def _approve_selected_audit(self) -> None:
        sel = self.audit_tree.selection()
        if not sel:
            messagebox.showinfo("Sélection requise", "Cliquez d'abord sur une ligne du tableau.")
            return
        vals = tuple(self.audit_tree.item(next(iter(sel)), "values"))
        if len(vals) >= 2:
            cand_raw, alias_raw = vals[:2]
            cand_txt = str(cand_raw).strip()
            alias_txt = self.audit_alias_edit_var.get().strip() or str(alias_raw).strip()
            self.controller.approve_audit_mask(self.current_ini_var.get(), cand_txt, alias_txt)
            self._refresh_audit_list()
            self.status_var.set(f"Ajouté aux noms à masquer : {cand_txt} -> {alias_txt}")

    def _exclude_selected_audit(self) -> None:
        sel = self.audit_tree.selection()
        if not sel:
            messagebox.showinfo("Sélection requise", "Cliquez d'abord sur une ligne du tableau.")
            return
        vals = tuple(self.audit_tree.item(next(iter(sel)), "values"))
        if vals:
            cand_txt = str(next(iter(vals))).strip()
            self.controller.exclude_audit_false_positive(self.current_ini_var.get(), cand_txt)
            self._refresh_audit_list()
            self.status_var.set(f"Mot courant ignoré : {cand_txt}")


def main() -> None:
    app = AnonymizerGuiApp()
    app.mainloop()


if __name__ == "__main__":
    main()
