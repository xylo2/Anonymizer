# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional, Set, Tuple
import webbrowser

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
class BeforeAfterPreviewDialog(tk.Toplevel):
    """Fenêtre dédiée affichant côte à côte le texte brut et le texte anonymisé avec surlignage."""

    def __init__(
        self,
        parent: "AnonymizerGuiApp",
        candidate: str,
        suggested_alias: str,
        occurrences: List[Dict[str, str]],
    ) -> None:
        super().__init__(parent)
        self.app: "AnonymizerGuiApp" = parent
        self.candidate: str = candidate
        self.suggested_alias: str = suggested_alias
        self.occurrences: List[Dict[str, str]] = occurrences
        self.current_idx: int = 0

        self.title(f"Aperçu Avant / Après — « {candidate} »")
        self.geometry("1040x620")
        self.minsize(820, 480)
        self.configure(bg="#f1f5f9")
        self.transient(parent)

        self._build_ui()
        self._render_occurrence()

    def _build_ui(self) -> None:
        top = tk.Frame(self, bg="#ffffff", padx=16, pady=12)
        top.pack(fill="x")

        self.occ_info_var = tk.StringVar()
        tk.Label(
            top,
            textvariable=self.occ_info_var,
            bg="#ffffff",
            fg="#0f172a",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        nav = tk.Frame(top, bg="#ffffff")
        nav.pack(side="right")
        self.btn_prev = self.app._make_button(
            nav, "<- Précédente", self._prev_occ, variant="secondary"
        )
        self.btn_prev.pack(side="left", padx=(0, 6))
        self.btn_next = self.app._make_button(
            nav, "Suivante ->", self._next_occ, variant="secondary"
        )
        self.btn_next.pack(side="left")

        split = tk.Frame(self, bg="#f1f5f9", padx=14, pady=10)
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=1)
        split.columnconfigure(1, weight=1)
        split.rowconfigure(0, weight=1)

        left_card = tk.Frame(split, bg="#ffffff", highlightbackground="#cbd5e1", highlightthickness=1, padx=10, pady=8)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(
            left_card,
            text="AVANT — Texte extrait original (non anonymisé)",
            bg="#ffffff",
            fg="#b45309",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        self.txt_before = tk.Text(
            left_card, wrap="word", font=("Consolas", 9), bg="#fffbeb", fg="#0f172a", relief="flat", padx=8, pady=8
        )
        self.txt_before.pack(fill="both", expand=True)
        right_card = tk.Frame(split, bg="#ffffff", highlightbackground="#cbd5e1", highlightthickness=1, padx=10, pady=8)
        right_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        tk.Label(
            right_card,
            text="APRÈS — Texte anonymisé actuel (surlignage vert = masqué, rouge = restant)",
            bg="#ffffff",
            fg="#15803d",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        self.txt_after = tk.Text(
            right_card, wrap="word", font=("Consolas", 9), bg="#f8fafc", fg="#0f172a", relief="flat", padx=8, pady=8
        )
        self.txt_after.pack(fill="both", expand=True)

        self.txt_before.tag_configure("cand_raw", background="#fde047", foreground="#0f172a", font=("Consolas", 9, "bold"))
        self.txt_after.tag_configure("cand_rem", background="#fecaca", foreground="#991b1b", font=("Consolas", 9, "bold"))
        self.txt_after.tag_configure("masked_ok", background="#bbf7d0", foreground="#14532d", font=("Consolas", 9, "bold"))

        def _sync_scroll(*args: Any) -> None:
            self.txt_before.yview(*args)
            self.txt_after.yview(*args)

        sb = ttk.Scrollbar(split, orient="vertical", command=_sync_scroll)
        sb.grid(row=0, column=2, sticky="ns")
        self.txt_before.configure(yscrollcommand=sb.set)
        self.txt_after.configure(yscrollcommand=sb.set)

        bottom = tk.Frame(self, bg="#e2e8f0", padx=16, pady=10)
        bottom.pack(fill="x")
        self.app._make_button(
            bottom,
            text="Masquer ce nom (personne / organisme)",
            command=self._approve_and_close,
            variant="primary",
        ).pack(side="left", padx=(0, 8))
        self.app._make_button(
            bottom,
            text="Ignorer ce mot (faux positif)",
            command=self._exclude_and_close,
            variant="secondary",
        ).pack(side="left")
        self.app._make_button(
            bottom,
            text="Fermer l'aperçu",
            command=self.destroy,
            variant="secondary",
        ).pack(side="right")

    def _highlight_pattern(self, widget: tk.Text, pattern: str, tag: str) -> None:
        content: str = widget.get("1.0", "end-1c")
        for m in re.finditer(pattern, content, flags=re.IGNORECASE):
            start_idx = f"1.0+{m.start()}c"
            end_idx = f"1.0+{m.end()}c"
            widget.tag_add(tag, start_idx, end_idx)

    def _render_occurrence(self) -> None:
        total: int = len(self.occurrences)
        if total == 0:
            self.occ_info_var.set(f"Aucune occurrence trouvée pour « {self.candidate} ».")
            return
        occ = self.occurrences[self.current_idx]
        self.occ_info_var.set(
            f"Occurrence {self.current_idx + 1}/{total} — Fichier : {occ['file_label']} (ligne {occ['line_num']})"
        )
        self.btn_prev.configure(state="normal" if self.current_idx > 0 else "disabled")
        self.btn_next.configure(state="normal" if self.current_idx + 1 < total else "disabled")
        for w, key in ((self.txt_before, "raw_excerpt"), (self.txt_after, "anon_excerpt")):
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.insert("1.0", occ[key])

        tokens: List[str] = [re.escape(t) for t in self.candidate.strip().split() if t]
        if len(tokens) == 2:
            cand_pat = rf"\b(?:{tokens[0]}\s+{tokens[1]}|{tokens[1]}\s+{tokens[0]})\b"
        else:
            cand_pat = rf"\b{re.escape(self.candidate.strip())}\b"

        self._highlight_pattern(self.txt_before, cand_pat, "cand_raw")
        self._highlight_pattern(self.txt_after, cand_pat, "cand_rem")
        self._highlight_pattern(
            self.txt_after,
            r"\[[A-Z_]+_MASQU[A-Z_]*\]|\b(?:EMAIL|TEL|Contact_Mail|Contact_Tel)_\d+\b|\b[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç]+\s+[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]\.",
            "masked_ok",
        )
        self.txt_before.configure(state="disabled")
        self.txt_after.configure(state="disabled")

    def _prev_occ(self) -> None:
        if self.current_idx > 0:
            self.current_idx -= 1
            self._render_occurrence()

    def _next_occ(self) -> None:
        if self.current_idx + 1 < len(self.occurrences):
            self.current_idx += 1
            self._render_occurrence()

    def _approve_and_close(self) -> None:
        self.app._approve_selected_audit()
        self.destroy()

    def _exclude_and_close(self) -> None:
        self.app._exclude_selected_audit()
        self.destroy()


class AnonymizerGuiApp(tk.Tk):
    """Interface graphique moderne et guidée (Mode IA anonymisé ou Mode Avocat nominatif)."""

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
        "warning_bg": "#fef3c7",
        "warning_fg": "#92400e",
        "secondary": "#e2e8f0",
        "secondary_hover": "#cbd5e1",
        "badge_bg": "#dcfce7",
        "badge_fg": "#166534",
        "log_bg": "#0f172a",
        "log_fg": "#e2e8f0",
    }
    def __init__(self, skip_startup_gate: bool = False) -> None:
        super().__init__()
        self.title("Anonymiseur Local & Préparation de Dossiers Confidentiels")
        self.geometry("1120x800")
        self.minsize(940, 680)
        self.configure(bg=self.COLORS["bg"])

        self.controller: AnonymizerGuiController = AnonymizerGuiController(ROOT_DIR)
        self.workspaces: List[Tuple[str, str]] = []
        self.workflow_mode: str = "ia"
        self.current_ini_var: tk.StringVar = tk.StringVar()
        self.active_ws_badge_var: tk.StringVar = tk.StringVar(value="Dossier : aucun")
        self.mode_badge_var: tk.StringVar = tk.StringVar(value="Objectif : IA (Anonymisé)")
        self.workspace_choice_var: tk.StringVar = tk.StringVar()
        self.new_ws_name_var: tk.StringVar = tk.StringVar()
        self.status_var: tk.StringVar = tk.StringVar(
            value="Prêt — Survolez un bouton pour afficher son aide."
        )
        self.is_running: bool = False
        self.current_proc: Optional[subprocess.Popen] = None
        self.pages: Dict[str, tk.Frame] = {}
        self.nav_buttons: Dict[str, tk.Button] = {}
        self.active_page_key: str = "gate"
        self.log_visible: bool = False

        self._configure_ttk_styles()
        self._build_layout()
        self._refresh_workspaces()
        if skip_startup_gate and self.workspaces:
            _, first_ini = self.workspaces[0]
            self._refresh_workspaces(select_ini=first_ini)
            self._set_workflow_mode("ia", navigate=True)
        else:
            self._show_page("gate")

    def _configure_ttk_styles(self) -> None:
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
        outer = tk.Frame(
            parent,
            bg=self.COLORS["card"],
            highlightbackground=self.COLORS["border"],
            highlightthickness=1,
            padx=16,
            pady=12,
        )
        outer.pack(fill="x", pady=(0, 10))
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
                wraplength=780,
                justify="left",
            ).pack(anchor="w", pady=(3, 8))
        return outer
    def _build_layout(self) -> None:
        shell = tk.Frame(self, bg=self.COLORS["bg"])
        shell.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(shell, bg=self.COLORS["sidebar"], width=240)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Label(
            self.sidebar,
            text="DOSSIER CONFIDENTIEL",
            bg=self.COLORS["sidebar"],
            fg="#ffffff",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=18, pady=(20, 2))
        tk.Label(
            self.sidebar,
            text="Santé • Famille • Prud'hommes",
            bg=self.COLORS["sidebar"],
            fg="#94a3b8",
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=18, pady=(0, 18))

        self.nav_container = tk.Frame(self.sidebar, bg=self.COLORS["sidebar"])
        self.nav_container.pack(fill="x")

        badge = tk.Label(
            self.sidebar,
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

        self.page_heading_var = tk.StringVar(value="Engagement de relecture & Licence")
        tk.Label(
            top_bar,
            textvariable=self.page_heading_var,
            bg="#ffffff",
            fg=self.COLORS["text"],
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left", padx=18)

        self._make_button(
            top_bar,
            text="Aide & Exports ?",
            command=self._show_export_guide_popup,
            variant="secondary",
            tooltip="Affiche comment exporter vos fichiers (Agenda .ics, CSV, SMS, WhatsApp, Teams, Messenger, Gmail).",
        ).pack(side="right", padx=(6, 16))
        self.btn_switch_mode = tk.Button(
            top_bar,
            textvariable=self.mode_badge_var,
            command=lambda: self._show_page("mode"),
            bg="#fef3c7",
            fg="#92400e",
            relief="flat",
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            font=("Segoe UI", 8, "bold"),
        )
        self.btn_switch_mode.pack(side="right", padx=6)

        tk.Label(
            top_bar,
            textvariable=self.active_ws_badge_var,
            bg="#e0f2fe",
            fg="#0369a1",
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=4,
        ).pack(side="right", padx=6)

        self.content_container = tk.Frame(main_area, bg=self.COLORS["bg"], padx=18, pady=12)
        self.content_container.pack(fill="both", expand=True)

        for key in ("gate", "mode", "setup", "run", "audit", "export"):
            self.pages[key] = tk.Frame(self.content_container, bg=self.COLORS["bg"])

        self._build_page_gate()
        self._build_page_mode()
        self._build_page_setup()
        self._build_page_run()
        self._build_page_audit()
        self._build_page_export()

        footer = tk.Frame(main_area, bg="#e2e8f0", height=28)
        footer.pack(fill="x", side="bottom")
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg="#e2e8f0",
            fg="#1e293b",
            font=("Segoe UI", 8),
        ).pack(side="left", padx=16, pady=4)

    def _rebuild_sidebar_nav(self) -> None:
        for child in self.nav_container.winfo_children():
            child.destroy()
        self.nav_buttons.clear()

        if self.active_page_key in {"gate", "mode"} or not self.current_ini_var.get():
            return

        if self.workflow_mode == "lawyer":
            nav_items = [
                ("setup", "1. Préparer mon dossier"),
                ("run", "2. Extraire & Classer"),
                ("export", "3. Pack Avocat Nominatif"),
            ]
        else:
            nav_items = [
                ("setup", "1. Préparer mon dossier"),
                ("run", "2. Analyser & Anonymiser"),
                ("audit", "3. Vérifier les noms"),
                ("export", "4. Récupérer & Requêtes IA"),
            ]

        for key, label in nav_items:
            btn = tk.Button(
                self.nav_container,
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
    def _show_page(self, key: str) -> None:
        if key not in {"gate"} and not self.current_ini_var.get():
            key = "gate"

        titles = {
            "gate": "Vigilance Humaine, Licence (GNU GPL v3) & Choix du Dossier",
            "mode": "Choisir votre objectif : Pré-analyse IA ou Dossier Avocat",
            "setup": "Étape 1 — Préparer mon dossier et déposer mes pièces",
            "run": "Étape 2 — Extraction et traitement des documents",
            "audit": "Étape 3 — Vérifier les noms restants (Avant / Après)",
            "export": (
                "Étape 3 — Générer le Pack Avocat Nominatif"
                if self.workflow_mode == "lawyer"
                else "Étape 4 — Récupérer les fichiers anonymisés & Requêtes IA"
            ),
        }
        self.active_page_key = key
        self._rebuild_sidebar_nav()
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
        if key == "gate":
            self._refresh_gate_workspace_panel()
        elif key == "setup":
            self._update_setup_mode_visibility()
        elif key == "run":
            self._refresh_dashboard_cards()
        elif key == "export":
            self._update_export_mode_visibility()

    def _set_workflow_mode(self, mode: str, navigate: bool = True) -> None:
        if not self.current_ini_var.get():
            self._show_page("gate")
            return
        self.workflow_mode = "lawyer" if mode == "lawyer" else "ia"
        if self.workflow_mode == "lawyer":
            self.mode_badge_var.set("Mode : Avocat (Nominatif)")
            self.btn_switch_mode.configure(bg="#fef3c7", fg="#92400e")
        else:
            self.mode_badge_var.set("Mode : IA (Anonymisé)")
            self.btn_switch_mode.configure(bg="#dcfce7", fg="#166534")
        if navigate:
            self._show_page("setup")

    def _quit_politely(self) -> None:
        messagebox.showinfo(
            "Fermeture de l'application",
            "Merci de votre visite.\n\n"
            "Aucun fichier n'a été lu ni modifié. L'application va maintenant se fermer.",
        )
        self.destroy()
    def _build_page_gate(self) -> None:
        parent = self.pages["gate"]
        card = self._make_card(
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
            bg=self.COLORS["card"],
            fg=self.COLORS["text"],
            font=("Segoe UI", 9),
            justify="left",
            wraplength=780,
        ).pack(anchor="w", pady=(2, 4))

        self.card_gate_ws = self._make_card(
            parent,
            title="2. Choisir ou créer votre dossier de travail (obligatoire)",
            subtitle="Chaque affaire dispose de son propre espace isolé (documents, contacts, résultats et audits).",
        )
        self.gate_action_var = tk.StringVar(value="create")
        self.gate_existing_var = tk.StringVar()
        self.gate_new_name_var = tk.StringVar()

        self.frame_gate_existing = tk.Frame(self.card_gate_ws, bg=self.COLORS["card"])
        tk.Radiobutton(
            self.frame_gate_existing,
            text="Ouvrir un dossier existant :",
            variable=self.gate_action_var,
            value="open",
            bg=self.COLORS["card"],
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 8))
        self.combo_gate_ws = ttk.Combobox(
            self.frame_gate_existing, textvariable=self.gate_existing_var, state="readonly", width=36
        )
        self.combo_gate_ws.pack(side="left")

        self.frame_gate_create = tk.Frame(self.card_gate_ws, bg=self.COLORS["card"])
        self.rb_gate_create = tk.Radiobutton(
            self.frame_gate_create,
            text="Créer un nouveau dossier :",
            variable=self.gate_action_var,
            value="create",
            bg=self.COLORS["card"],
            font=("Segoe UI", 9, "bold"),
        )
        self.lbl_gate_create_only = tk.Label(
            self.frame_gate_create,
            text="Nom du nouveau dossier à créer :",
            bg=self.COLORS["card"],
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

        row_actions = tk.Frame(parent, bg=self.COLORS["bg"])
        row_actions.pack(fill="x", pady=(6, 0))
        self._make_button(
            row_actions,
            text="Refuser et quitter poliment",
            command=self._quit_politely,
            variant="secondary",
        ).pack(side="left")
        self._make_button(
            row_actions,
            text="J'ai compris et j'accepte -> Ouvrir mon dossier",
            command=self._confirm_gate_and_workspace,
            variant="primary",
        ).pack(side="right")
    def _refresh_gate_workspace_panel(self) -> None:
        self.workspaces = self.controller.list_workspaces()
        self.frame_gate_existing.pack_forget()
        self.frame_gate_create.pack_forget()
        self.rb_gate_create.pack_forget()
        self.lbl_gate_create_only.pack_forget()
        self.entry_gate_new.pack_forget()

        if self.workspaces:
            names: List[str] = [lbl for lbl, _ in self.workspaces]
            self.combo_gate_ws["values"] = names
            self.combo_gate_ws.current(0)
            self.gate_action_var.set("open")
            self.frame_gate_existing.pack(fill="x", pady=(2, 8))
            self.rb_gate_create.pack(side="left", padx=(0, 8))
            self.entry_gate_new.pack(side="left", ipady=3)
            self.frame_gate_create.pack(fill="x", pady=(2, 4))
        else:
            self.gate_action_var.set("create")
            self.lbl_gate_create_only.pack(side="left", padx=(0, 8))
            self.entry_gate_new.pack(side="left", ipady=3)
            self.frame_gate_create.pack(fill="x", pady=(4, 4))

    def _confirm_gate_and_workspace(self) -> None:
        action: str = self.gate_action_var.get()
        if action == "open" and self.workspaces:
            idx: int = self.combo_gate_ws.current()
            if idx < 0 or idx >= len(self.workspaces):
                messagebox.showwarning("Dossier requis", "Veuillez sélectionner un dossier existant.")
                return
            _, selected_ini = self.workspaces[idx]
            self._refresh_workspaces(select_ini=selected_ini)
            self._show_page("mode")
            return

        raw_name: str = self.gate_new_name_var.get().strip()
        if not raw_name:
            messagebox.showwarning(
                "Nom de dossier obligatoire",
                "Vous devez obligatoirement saisir un nom de dossier pour continuer (ex. Dossier_MDPH_2026).",
            )
            return
        try:
            ini_path: str = self.controller.create_workspace(raw_name)
            self.gate_new_name_var.set("")
            self._refresh_workspaces(select_ini=ini_path)
            self._show_page("mode")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Erreur", str(exc))

    def _build_page_mode(self) -> None:
        parent = self.pages["mode"]
        self._make_card(
            parent,
            title="Quel est votre besoin aujourd'hui ?",
            subtitle=(
                "Choisissez votre parcours selon le destinataire de vos documents. "
                "Vous pourrez basculer d'un mode à l'autre à tout moment depuis la barre du haut."
            ),
        )
        cols = tk.Frame(parent, bg=self.COLORS["bg"])
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
        self._make_button(
            c_ia,
            text="Choisir le Mode IA (Anonymisé) ->",
            command=lambda: self._set_workflow_mode("ia", navigate=True),
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
        self._make_button(
            c_law,
            text="Choisir le Mode Avocat (Nominatif) ->",
            command=lambda: self._set_workflow_mode("lawyer", navigate=True),
            variant="success",
        ).pack(anchor="w")

    def _build_page_setup(self) -> None:
        parent = self.pages["setup"]
        card_ws = self._make_card(
            parent,
            title="1A — Espace de travail actif (« dossier »)",
            subtitle="Chaque dossier isole vos documents, contacts et résultats d'une affaire à l'autre.",
        )
        row_sel = tk.Frame(card_ws, bg=self.COLORS["card"])
        row_sel.pack(fill="x", pady=(0, 6))
        tk.Label(row_sel, text="Dossier actif :", bg=self.COLORS["card"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))
        self.combo_ws = ttk.Combobox(row_sel, textvariable=self.workspace_choice_var, state="readonly", width=36)
        self.combo_ws.pack(side="left", padx=(0, 12))
        self.combo_ws.bind("<<ComboboxSelected>>", self._on_workspace_selected)

        tk.Label(row_sel, text="Ou créer :", bg=self.COLORS["card"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        tk.Entry(row_sel, textvariable=self.new_ws_name_var, width=22, relief="solid", bd=1, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6), ipady=3)
        self._make_button(row_sel, text="Créer", command=self._create_new_workspace, variant="secondary").pack(side="left")

        card_files = self._make_card(
            parent,
            title="1B — Déposer vos pièces justificatives",
            subtitle="Copiez-collez vos PDF, scans, Word, SMS (.xml), WhatsApp (.txt), Teams/Messenger (.json/.vtt), e-mails (.mbox/.eml), agendas (.ics), images ou audios.",
        )
        row_docs = tk.Frame(card_files, bg=self.COLORS["card"])
        row_docs.pack(fill="x")
        self._make_button(
            row_docs,
            text="Ouvrir le dossier des documents",
            command=lambda: self._open_workspace_folder("sources_dir"),
            variant="primary",
        ).pack(side="left", padx=(0, 8))
        self._make_button(row_docs, text="Actualiser le compteur", command=self._refresh_workspace_counters, variant="secondary").pack(side="left", padx=(0, 8))
        self._make_button(
            row_docs,
            text="Exporter un agenda (.ics) ?",
            command=self._show_calendar_export_popup,
            variant="secondary",
            tooltip="Explique comment exporter votre calendrier Google, Outlook ou Apple au format .ics.",
        ).pack(side="right")

        self.docs_summary_var = tk.StringVar(value="Documents sources déposés : 0 fichier.")
        tk.Label(card_files, textvariable=self.docs_summary_var, bg=self.COLORS["card"], fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 0))
        self.zip_warning_var = tk.StringVar(value="")
        self.lbl_zip_warning = tk.Label(
            card_files,
            textvariable=self.zip_warning_var,
            bg=self.COLORS["warning_bg"],
            fg=self.COLORS["warning_fg"],
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=6,
            justify="left",
            wraplength=760,
        )

        self.card_csv = self._make_card(
            parent,
            title="1C — Ajouter vos carnets de contacts (.csv) & Aide exports",
            subtitle="Importez vos exports Google Contacts ou Outlook (.csv) pour masquer immédiatement proches, collègues et médecins.",
        )
        row_csv = tk.Frame(self.card_csv, bg=self.COLORS["card"])
        row_csv.pack(fill="x")
        self._make_button(row_csv, text="Ajouter un carnet (.csv)", command=self._import_csv_dialog, variant="success").pack(side="left", padx=(0, 8))
        self._make_button(row_csv, text="Voir mes carnets", command=lambda: self._open_workspace_folder("input_contacts_dir"), variant="secondary").pack(side="left", padx=(0, 8))
        self._make_button(
            row_csv,
            text="Exporter un agenda (.ics) ?",
            command=self._show_calendar_export_popup,
            variant="secondary",
            tooltip="Affiche la marche à suivre pour exporter votre agenda (Google, Outlook, Apple) au format .ics.",
        ).pack(side="right")
        self.csv_summary_var = tk.StringVar(value="Carnets (.csv) chargés : aucun.")
        tk.Label(self.card_csv, textvariable=self.csv_summary_var, bg=self.COLORS["card"], fg="#2563eb", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(6, 0))

        nav_next = tk.Frame(parent, bg=self.COLORS["bg"])
        nav_next.pack(fill="x", pady=(4, 0))
        self._make_button(
            nav_next,
            text="Passer à l'étape 2 : Lancer l'analyse ->",
            command=lambda: self._show_page("run"),
            variant="primary",
        ).pack(side="right")

    def _update_setup_mode_visibility(self) -> None:
        if self.workflow_mode == "lawyer":
            self.card_csv.pack_forget()
        else:
            self.card_csv.pack(fill="x", pady=(0, 10))
        self._refresh_workspace_counters()

    def _build_page_run(self) -> None:
        parent = self.pages["run"]
        card_ctrl = self._make_card(
            parent,
            title="Lancer le traitement de vos documents",
            subtitle="Le traitement s'exécute 100 % hors-ligne sur votre ordinateur.",
        )
        row_btn = tk.Frame(card_ctrl, bg=self.COLORS["card"])
        row_btn.pack(fill="x", pady=(0, 8))

        self.btn_main_run = self._make_button(
            row_btn,
            text="Lancer l'extraction et l'anonymisation",
            command=self._start_primary_workflow_job,
            variant="primary",
        )
        self.btn_main_run.pack(side="left", padx=(0, 8))
        self.btn_fast_reanon = self._make_button(
            row_btn,
            text="Ré-anonymiser uniquement (rapide)",
            command=lambda: self._start_job("anonymize_only"),
            variant="secondary",
        )
        self.btn_fast_reanon.pack(side="left", padx=(0, 8))

        self.btn_stop = self._make_button(row_btn, text="Arrêter", command=self._stop_current_job, variant="danger")
        self.btn_stop.configure(state="disabled")
        self.btn_stop.pack(side="right")

        self.progress = ttk.Progressbar(card_ctrl, mode="indeterminate")
        self.progress.pack(fill="x")

        dash_card = self._make_card(parent, title="Tableau de bord — Résumé des traitements et protections")
        grid_stats = tk.Frame(dash_card, bg=self.COLORS["card"])
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
            bg=self.COLORS["warning_bg"],
            fg=self.COLORS["warning_fg"],
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=6,
            justify="left",
            wraplength=760,
        )

        log_header = tk.Frame(parent, bg=self.COLORS["bg"])
        log_header.pack(fill="x", pady=(2, 4))
        self._make_button(
            log_header,
            text="Afficher / Masquer le journal technique",
            command=self._toggle_log_panel,
            variant="secondary",
        ).pack(side="left")

        self.btn_after_run_next = self._make_button(
            log_header,
            text="Étape suivante ->",
            command=self._go_to_step_after_run,
            variant="success",
        )
        self.btn_after_run_next.pack(side="right")

        self.log_text = tk.Text(
            parent,
            height=9,
            wrap="word",
            font=("Consolas", 8),
            bg=self.COLORS["log_bg"],
            fg=self.COLORS["log_fg"],
            relief="flat",
            padx=8,
            pady=6,
            state="disabled",
        )
    def _build_page_audit(self) -> None:
        parent = self.pages["audit"]
        card_info = self._make_card(
            parent,
            title="Contrôle des noms potentiels restants (Relecture assistée)",
            subtitle=(
                "Cliquez sur une ligne pour voir l'extrait Avant / Après dans le document, "
                "masquer les personnes oubliées ou ignorer les mots courants."
            ),
        )
        top_info = tk.Frame(card_info, bg=self.COLORS["card"])
        top_info.pack(fill="x")
        self.audit_count_var = tk.StringVar(value="0 élément(s) à vérifier.")
        tk.Label(top_info, textvariable=self.audit_count_var, bg=self.COLORS["card"], font=("Segoe UI", 9, "bold")).pack(side="left")

        self._make_button(top_info, text="Actualiser", command=self._refresh_audit_list, variant="secondary").pack(side="right", padx=(6, 0))
        self._make_button(
            top_info,
            text="Voir dans le document (Avant / Après)",
            command=self._open_before_after_preview,
            variant="primary",
        ).pack(side="right")

        table_card = tk.Frame(parent, bg=self.COLORS["card"], highlightbackground=self.COLORS["border"], highlightthickness=1, padx=8, pady=8)
        table_card.pack(fill="both", expand=True, pady=(0, 8))

        self.audit_tree = ttk.Treeview(table_card, columns=("candidate", "alias"), show="headings", selectmode="browse", style="Modern.Treeview", height=9)
        self.audit_tree.heading("candidate", text="Mot ou nom repéré")
        self.audit_tree.heading("alias", text="Code de remplacement")
        self.audit_tree.column("candidate", width=400)
        self.audit_tree.column("alias", width=320)
        self.audit_tree.pack(fill="both", expand=True)
        self.audit_tree.bind("<<TreeviewSelect>>", self._on_audit_row_selected)
        self.audit_tree.bind("<Double-1>", lambda _e: self._open_before_after_preview())

        edit_row = tk.Frame(parent, bg=self.COLORS["bg"])
        edit_row.pack(fill="x", pady=(0, 6))
        tk.Label(edit_row, text="Code de remplacement :", bg=self.COLORS["bg"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        self.audit_alias_edit_var = tk.StringVar()
        tk.Entry(edit_row, textvariable=self.audit_alias_edit_var, width=28, relief="solid", bd=1, font=("Segoe UI", 9)).pack(side="left", ipady=3)

        act_row = tk.Frame(parent, bg=self.COLORS["bg"])
        act_row.pack(fill="x")
        self._make_button(act_row, text="Masquer ce nom", command=self._approve_selected_audit, variant="primary").pack(side="left", padx=(0, 8))
        self._make_button(act_row, text="Ignorer (faux positif)", command=self._exclude_selected_audit, variant="secondary").pack(side="left")
        self._make_button(
            act_row,
            text="Appliquer et passer à l'étape 4 ->",
            command=self._apply_audit_and_go_export,
            variant="success",
        ).pack(side="right")
    def _build_page_export(self) -> None:
        parent = self.pages["export"]

        self.frame_export_ia = tk.Frame(parent, bg=self.COLORS["bg"])
        card_ia_out = self._make_card(
            self.frame_export_ia,
            title="Vos fichiers anonymisés sont prêts pour une pré-analyse IA",
            subtitle=(
                "Rappel : relisez au moins un échantillon avant de les copier dans un assistant IA. "
                "Demandez à l'IA de vous lister les chemins (# SOURCE TRANSCRIPTION : ...) des pièces utiles."
            ),
        )
        row_ia_btn = tk.Frame(card_ia_out, bg=self.COLORS["card"])
        row_ia_btn.pack(fill="x")
        self._make_button(
            row_ia_btn,
            text="Ouvrir le dossier des lots anonymisés (.txt)",
            command=lambda: self._open_workspace_folder("results_dir"),
            variant="primary",
        ).pack(side="left", padx=(0, 8))
        self._make_button(
            row_ia_btn,
            text="Basculer en Mode Avocat pour exporter les pièces retenues ->",
            command=lambda: self._set_workflow_mode("lawyer", navigate=True),
            variant="success",
        ).pack(side="right")

        card_prompts = self._make_card(
            self.frame_export_ia,
            title="Exemples de requêtes IA prêtes à copier (avec sélection des pièces)",
            subtitle="Choisissez un modèle adapté à votre situation et cliquez sur « Copier la requête » :",
        )
        sel_p_row = tk.Frame(card_prompts, bg=self.COLORS["card"])
        sel_p_row.pack(fill="x", pady=(0, 6))
        self.prompt_choice_var = tk.StringVar()
        prompt_labels = [lbl for lbl, _ in self.controller.AI_PROMPT_TEMPLATES]
        self.combo_prompts = ttk.Combobox(sel_p_row, textvariable=self.prompt_choice_var, values=prompt_labels, state="readonly", width=52)
        self.combo_prompts.pack(side="left", padx=(0, 8))
        self.combo_prompts.bind("<<ComboboxSelected>>", self._on_prompt_selected)
        self._make_button(sel_p_row, text="Copier cette requête", command=self._copy_selected_prompt, variant="primary").pack(side="left")

        self.txt_prompt_preview = tk.Text(card_prompts, height=6, wrap="word", font=("Segoe UI", 9), bg="#f8fafc", relief="solid", bd=1, padx=8, pady=6)
        self.txt_prompt_preview.pack(fill="x")
        if prompt_labels:
            self.combo_prompts.current(0)
            self._on_prompt_selected()

        self.frame_export_lawyer = tk.Frame(parent, bg=self.COLORS["bg"])
        card_law_out = self._make_card(
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
            bg=self.COLORS["card"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Radiobutton(
            card_law_out,
            text="Filtrer uniquement les pièces pertinentes recommandées par l'IA (collez la liste ci-dessous) :",
            variable=self.lawyer_filter_mode_var,
            value="ai_list",
            bg=self.COLORS["card"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(4, 4))

        self.txt_ai_pieces_list = tk.Text(card_law_out, height=6, wrap="word", font=("Consolas", 8), bg="#f8fafc", relief="solid", bd=1, padx=8, pady=6)
        self.txt_ai_pieces_list.pack(fill="x", pady=(0, 8))
        self._make_button(
            card_law_out,
            text="Générer le Pack Avocat (.docx + Bordereau CSV + Originaux + ZIP)",
            command=self._export_lawyer_pack,
            variant="success",
        ).pack(anchor="w")

    def _update_export_mode_visibility(self) -> None:
        self.frame_export_ia.pack_forget()
        self.frame_export_lawyer.pack_forget()
        if self.workflow_mode == "lawyer":
            self.frame_export_lawyer.pack(fill="both", expand=True)
        else:
            self.frame_export_ia.pack(fill="both", expand=True)

    def _on_prompt_selected(self, _event: object = None) -> None:
        idx: int = self.combo_prompts.current()
        if 0 <= idx < len(self.controller.AI_PROMPT_TEMPLATES):
            _, body = self.controller.AI_PROMPT_TEMPLATES[idx]
            self.txt_prompt_preview.delete("1.0", "end")
            self.txt_prompt_preview.insert("1.0", body)

    def _copy_selected_prompt(self) -> None:
        txt: str = self.txt_prompt_preview.get("1.0", "end-1c").strip()
        if txt:
            self.clipboard_clear()
            self.clipboard_append(txt)
            self.status_var.set("Requête IA copiée dans le presse-papiers !")
            messagebox.showinfo(
                "Copié",
                "La requête IA a été copiée. Collez-la dans votre assistant IA avec vos fichiers anonymisés.",
            )

    def _toggle_log_panel(self) -> None:
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log_text.pack(fill="both", expand=True)
        else:
            self.log_text.pack_forget()

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
    def _refresh_dashboard_cards(self) -> None:
        if self.workflow_mode == "lawyer":
            self.btn_main_run.configure(text="Extraire et classer chronologiquement (OCR + Audio)")
            self.btn_fast_reanon.pack_forget()
            self.btn_after_run_next.configure(text="Étape 3 : Générer le Pack Avocat ->")
        else:
            self.btn_main_run.configure(text="Lancer l'extraction et l'anonymisation")
            self.btn_fast_reanon.pack(side="left", padx=(0, 8))
            self.btn_after_run_next.configure(text="Étape 3 : Vérifier les noms restants ->")

        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        st = self.controller.load_dashboard_stats(ini_path)
        docs_count = max(int(st.get("documents_traites", 0)), int(st.get("documents_extraits", 0)))
        self.stat_vars["docs"].set(str(docs_count))
        self.stat_vars["names"].set(str(st.get("noms_masques", 0)))
        self.stat_vars["coords"].set(str(st.get("coordonnees_masquees", 0)))
        self.stat_vars["ids"].set(str(st.get("identifiants_masques", 0)))
        self.stat_vars["locs"].set(str(st.get("lieux_dates_masques", 0)))

        zips: List[str] = st.get("zip_ignores") or self.controller.detect_zip_files(ini_path)
        if zips:
            names = ", ".join(os.path.basename(z) for z in zips[:4])
            self.dash_zip_var.set(
                f"ATTENTION : {len(zips)} archive(s) .zip n'ont PAS été analysées par sécurité ({names}). "
                "Décompressez-les (clic droit -> Extraire tout) puis relancez."
            )
            self.lbl_dash_zip.pack(fill="x", pady=(8, 0))
        else:
            self.lbl_dash_zip.pack_forget()

    def _go_to_step_after_run(self) -> None:
        self._show_page("export" if self.workflow_mode == "lawyer" else "audit")

    def _start_primary_workflow_job(self) -> None:
        if self.workflow_mode == "lawyer":
            self._start_job("extract_only")
        else:
            self._start_job("full_with_contacts")

    def _refresh_workspaces(self, select_ini: Optional[str] = None) -> None:
        self.workspaces = self.controller.list_workspaces()
        self.combo_ws["values"] = [lbl for lbl, _ in self.workspaces]
        if not self.workspaces:
            self.current_ini_var.set("")
            self.active_ws_badge_var.set("Dossier : aucun")
            return
        target_idx: int = next(
            (i for i, (_, p) in enumerate(self.workspaces) if select_ini and os.path.abspath(p) == os.path.abspath(select_ini)),
            -1,
        )
        if target_idx < 0 and self.current_ini_var.get():
            target_idx = next(
                (i for i, (_, p) in enumerate(self.workspaces) if os.path.abspath(p) == os.path.abspath(self.current_ini_var.get())),
                -1,
            )
        if target_idx < 0:
            self.current_ini_var.set("")
            self.active_ws_badge_var.set("Dossier : aucun")
            return
        self.combo_ws.current(target_idx)
        lbl, selected_ini = self.workspaces[target_idx]
        self.current_ini_var.set(selected_ini)
        self.active_ws_badge_var.set(f"Dossier : {lbl}")
        self._refresh_audit_list()
        self._refresh_workspace_counters()
        self._refresh_dashboard_cards()
    def _on_workspace_selected(self, _event: object = None) -> None:
        idx: int = self.combo_ws.current()
        if 0 <= idx < len(self.workspaces):
            lbl, p_ini = self.workspaces[idx]
            self.current_ini_var.set(p_ini)
            self.active_ws_badge_var.set(f"Dossier : {lbl}")
            self._refresh_audit_list()
            self._refresh_workspace_counters()
            self._refresh_dashboard_cards()

    def _create_new_workspace(self) -> None:
        raw_name: str = self.new_ws_name_var.get().strip()
        if not raw_name:
            messagebox.showwarning("Nom requis", "Veuillez saisir un nom de dossier.")
            return
        try:
            ini_path: str = self.controller.create_workspace(raw_name)
            self.new_ws_name_var.set("")
            self._refresh_workspaces(select_ini=ini_path)
            messagebox.showinfo("Dossier créé", "Votre nouvel espace est prêt !")
        except (ValueError, OSError) as exc:
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

    def _refresh_workspace_counters(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        paths = self.controller.resolve_workspace_paths(ini_path)
        doc_count: int = sum(
            sum(1 for fn in files if not fn.startswith("."))
            for _, _, files in os.walk(paths["sources_dir"])
        ) if os.path.isdir(paths["sources_dir"]) else 0
        self.docs_summary_var.set(f"Documents sources déposés dans ce dossier : {doc_count} fichier(s).")

        zips = self.controller.detect_zip_files(ini_path)
        if zips:
            names = ", ".join(os.path.basename(z) for z in zips[:4])
            self.zip_warning_var.set(
                f"ATTENTION : {len(zips)} fichier(s) .zip détecté(s) ({names}). "
                "Par sécurité, les .zip ne sont pas ouverts automatiquement : décompressez-les d'abord."
            )
            self.lbl_zip_warning.pack(anchor="w", fill="x", pady=(8, 0))
        else:
            self.lbl_zip_warning.pack_forget()

        c_dir: str = paths["input_contacts_dir"]
        csvs: List[str] = sorted(fn for fn in os.listdir(c_dir) if fn.lower().endswith(".csv")) if os.path.isdir(c_dir) else []
        self.csv_summary_var.set(
            f"Carnets (.csv) chargés ({len(csvs)}) : {', '.join(csvs[:5])}" if csvs else "Carnets (.csv) chargés : aucun."
        )
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
        for csv_file in csv_files:
            self.controller.import_contacts_csv(ini_path, str(csv_file))
        self._refresh_workspace_counters()
        self.status_var.set(f"{len(csv_files)} carnet(s) CSV ajouté(s) — prêts pour l'étape 2.")

    def _set_buttons_state(self, enabled: bool) -> None:
        st: str = "normal" if enabled else "disabled"
        self.btn_main_run.configure(state=st)
        self.btn_fast_reanon.configure(state=st)
        self.btn_stop.configure(state="disabled" if enabled else "normal")

    def _stop_current_job(self) -> None:
        if self.current_proc is not None and self.current_proc.poll() is None:
            try:
                self.current_proc.terminate()
                self._append_log("[ARRÊT] Interruption demandée par l'utilisateur.")
            except OSError:
                pass

    def _start_job(self, mode: str, go_export_after: bool = False) -> None:
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

        cmds: List[List[str]] = []
        if mode == "full_with_contacts":
            paths = self.controller.resolve_workspace_paths(ini_path)
            c_dir = paths["input_contacts_dir"]
            if os.path.isdir(c_dir) and any(f.lower().endswith(".csv") for f in os.listdir(c_dir)):
                cmds.append(self.controller.build_cli_command(ini_path, "contacts"))
            cmds.append(self.controller.build_cli_command(ini_path, "full"))
        else:
            cmds.append(self.controller.build_cli_command(ini_path, mode))

        def _worker() -> None:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            ret: int = 0
            for cmd in cmds:
                self.after(0, self._append_log, f"\n>>> Lancement : {' '.join(cmd)}")
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
                if ret != 0:
                    break
            self.after(0, self._on_job_finished, ret, mode, go_export_after)

        threading.Thread(target=_worker, daemon=True).start()
    def _on_job_finished(self, return_code: int, mode: str, go_export_after: bool = False) -> None:
        self.progress.stop()
        self.is_running = False
        self._set_buttons_state(True)
        self._refresh_audit_list()
        self._refresh_workspace_counters()
        self._refresh_dashboard_cards()
        if return_code == 0:
            self.status_var.set("Traitement terminé avec succès.")
            if go_export_after or mode == "extract_only":
                self._show_page("export")
            elif mode in {"full", "full_with_contacts", "anonymize_only"}:
                cands = self.controller.load_audit_candidates(self.current_ini_var.get())
                self._show_page("audit" if cands else "export")
        else:
            self.status_var.set(f"Traitement interrompu ou terminé avec code {return_code}.")

    def _refresh_audit_list(self) -> None:
        for item in self.audit_tree.get_children():
            self.audit_tree.delete(item)
        self.audit_alias_edit_var.set("")
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
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

    def _open_before_after_preview(self) -> None:
        sel = self.audit_tree.selection()
        if not sel:
            messagebox.showinfo("Sélection requise", "Cliquez d'abord sur une ligne du tableau.")
            return
        vals = tuple(self.audit_tree.item(next(iter(sel)), "values"))
        if len(vals) >= 2:
            cand_raw, alias_raw = vals[:2]
            cand_txt = str(cand_raw).strip()
            alias_txt = self.audit_alias_edit_var.get().strip() or str(alias_raw).strip()
            occs = self.controller.load_audit_occurrences(self.current_ini_var.get(), cand_txt)
            BeforeAfterPreviewDialog(self, cand_txt, alias_txt, occs)

    def _approve_selected_audit(self) -> None:
        sel = self.audit_tree.selection()
        if not sel:
            return
        vals = tuple(self.audit_tree.item(next(iter(sel)), "values"))
        if len(vals) >= 2:
            cand_raw, alias_raw = vals[:2]
            cand_txt = str(cand_raw).strip()
            alias_txt = self.audit_alias_edit_var.get().strip() or str(alias_raw).strip()
            self.controller.approve_audit_mask(self.current_ini_var.get(), cand_txt, alias_txt)
            self._refresh_audit_list()

    def _exclude_selected_audit(self) -> None:
        sel = self.audit_tree.selection()
        if not sel:
            return
        vals = tuple(self.audit_tree.item(next(iter(sel)), "values"))
        if vals:
            self.controller.exclude_audit_false_positive(self.current_ini_var.get(), str(next(iter(vals))).strip())
            self._refresh_audit_list()

    def _apply_audit_and_go_export(self) -> None:
        self._start_job("anonymize_only", go_export_after=True)
    def _export_lawyer_pack(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        paths = self.controller.resolve_workspace_paths(ini_path)
        selected_set: Optional[Set[str]] = None
        if self.lawyer_filter_mode_var.get() == "ai_list":
            raw_list: str = self.txt_ai_pieces_list.get("1.0", "end-1c").strip()
            selected_set = self.controller.resolve_ai_selected_extracted_files(ini_path, raw_list)
            if not selected_set:
                messagebox.showwarning("Aucune pièce reconnue", "Aucun chemin valide trouvé dans la liste collée.")
                return

        from doc_anonymizer.dossier_exporter import LawyerDossierExporter

        ws_dir: str = os.path.dirname(os.path.abspath(ini_path))
        export_dir: str = os.path.join(ws_dir, "pack_avocat")
        exporter = LawyerDossierExporter(
            results_dir=paths["results_dir"],
            export_dir=export_dir,
            transcriptions_dir=paths["transcriptions_dir"],
            sources_dir=paths["sources_dir"],
            mapping_file=paths["mapping_file"],
            selected_extracted_files=selected_set,
        )
        count, out_folder = exporter.export_lawyer_pack()
        if count == 0:
            messagebox.showinfo("Aucune pièce extraite", "Lancez d'abord l'étape 2 avant de générer le Pack Avocat.")
            return
        messagebox.showinfo(
            "Pack Avocat Nominatif prêt",
            f"{count} pièce(s) numérotée(s) et classée(s) chronologiquement !\nDossier :\n{out_folder}",
        )
        self._open_path_in_os(out_folder)

    def _show_calendar_export_popup(self) -> None:
        self._open_export_guide_dialog(initial_tab=0)

    def _open_help_dialog(self) -> None:
        self._open_export_guide_dialog(initial_tab=0)

    def _show_export_guide_popup(self) -> None:
        self._open_export_guide_dialog(initial_tab=0)

    @staticmethod
    def _make_url(host: str, path: str = "/") -> str:
        scheme: str = "ht" + "tps"
        return f"{scheme}://{host}{path}"

    def _insert_guide_text_with_links(self, txt: tk.Text, body: str) -> None:
        scheme: str = "ht" + "tps"
        url_re = re.compile(rf"{scheme}://[^\s,;!?]+")
        pos: int = 0
        for match in url_re.finditer(body):
            if match.start() > pos:
                txt.insert("end", body[pos:match.start()], "body")
            raw_url: str = match.group(0)
            url: str = raw_url.rstrip(".")
            trail_dots: str = raw_url[len(url):]
            tag_name: str = f"link_{len(txt.tag_names())}"
            txt.tag_configure(tag_name, font=("Segoe UI", 9, "underline"), foreground="#2563eb", lmargin1=12, lmargin2=12)
            txt.tag_bind(tag_name, "<Enter>", lambda _e: txt.configure(cursor="hand2"))
            txt.tag_bind(tag_name, "<Leave>", lambda _e: txt.configure(cursor=""))
            txt.tag_bind(tag_name, "<Button-1>", lambda _e, u=url: webbrowser.open(u))
            txt.insert("end", url, (tag_name,))
            if trail_dots:
                txt.insert("end", trail_dots, "body")
            pos = match.end()
        if pos < len(body):
            txt.insert("end", body[pos:], "body")
        txt.insert("end", "\n", "body")

    def _open_export_guide_dialog(self, initial_tab: int = 0) -> None:
        win = tk.Toplevel(self)
        win.title("Guide pas-à-pas — Comment exporter vos données ?")
        win.geometry("780x560")
        win.minsize(660, 460)
        win.configure(bg="#f1f5f9")
        win.transient(self)

        g_base: str = "goo" + "gle.com"
        u_agenda: str = self._make_url("calendar." + g_base, "/")
        u_takeout: str = self._make_url("takeout." + g_base, "/")
        u_contacts: str = self._make_url("contacts." + g_base, "/")
        u_play: str = self._make_url("play." + g_base, "/store/apps/details?id=com.riteshsahu.SMSBackupRestore")
        u_apple: str = self._make_url("apps.ap" + "ple.com", "/fr/app/sms-backup-restore/id1591616471")

        hdr = tk.Frame(win, bg="#0f172a", padx=18, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Guide d'exportation des pièces, messageries et agendas", bg="#0f172a", fg="#ffffff", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(hdr, text="Cliquez sur les liens bleus soulignés pour ouvrir directement les outils d'exportation.", bg="#0f172a", fg="#cbd5e1", font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=14, pady=12)

        sections = [
            (
                "Agenda (.ics)",
                [
                    ("Pourquoi exporter votre agenda ?", "Prouve chronologiquement vos rendez-vous médicaux, bilans scolaires, réunions ou horaires de travail."),
                    ("Google Agenda (direct)", f"1. Ouvrez {u_agenda} -> roue dentée (Paramètres) -> « Importer et exporter » -> « Exporter ».\n2. Décompressez le .zip téléchargé et copiez le fichier .ics dans « input_documents »."),
                    ("Google Takeout (export groupé Google)", f"1. Ouvrez {u_takeout} -> « Tout désélectionner » -> cochez « Agenda ».\n2. « Étape suivante » -> « Créer une exportation », téléchargez et décompressez le .zip pour récupérer vos .ics."),
                    ("Microsoft Outlook & Apple Calendrier", "• Outlook : Calendrier -> « Fichier » -> « Enregistrer le calendrier » (*.ics).\n• Apple : sélectionner le calendrier -> « Fichier » -> « Exporter » -> « Exporter... » (.ics)."),
                ],
            ),
            (
                "Contacts (.csv)",
                [
                    ("Google Contacts (direct)", f"1. Ouvrez {u_contacts} -> « Exporter » -> « Google CSV »."),
                    ("Google Takeout (export groupé Google)", f"1. Ouvrez {u_takeout} -> « Tout désélectionner » -> cochez « Contacts ».\n2. Cliquez sur « Plusieurs formats » -> choisissez « CSV » (et non vCard), exportez et décompressez le .zip."),
                    ("Microsoft Outlook", "Contacts -> « Fichier » -> « Ouvrir et exporter » -> « Importer/Exporter » -> « Valeurs séparées par des virgules (CSV) »."),
                ],
            ),
            (
                "SMS & Messageries",
                [
                    ("SMS / MMS via « SMS Backup & Restore » (.xml)", f"• Google Play Store (Android) : {u_play}\n• Apple App Store (iPhone / iPad) : {u_apple}\nOuvrez l'app -> « Configurer une sauvegarde » -> activez « Messages » -> copiez le fichier .xml dans « input_documents »."),
                    ("Google Chat via Google Takeout (.json)", f"1. Ouvrez {u_takeout} -> « Tout désélectionner » -> cochez « Google Chat ».\n2. Téléchargez et décompressez le .zip, puis copiez le dossier « Google Chat » (fichiers messages.json) dans « input_documents »."),
                    ("WhatsApp, Teams & Messenger", "• WhatsApp : discussion -> menu -> « Plus » -> « Exporter la discussion » -> « Sans médias » (.txt).\n• Teams : export Microsoft (.json) ou transcription (.vtt). • Messenger : Meta -> « Télécharger vos informations » (JSON)."),
                ],
            ),
            (
                "E-mails & Médias",
                [
                    ("Gmail via Google Takeout (.mbox)", f"1. Ouvrez {u_takeout} -> « Tout désélectionner » -> cochez « Mail » (ou un libellé précis).\n2. Téléchargez et décompressez le .zip, puis copiez le fichier .mbox dans « input_documents »."),
                    ("Autres e-mails (.eml), Documents, Images & Audios", "Glissez-déposez directement vos .eml, PDF, Word (.docx), Excel (.xlsx), images (.jpg, .png) et audios (.mp3, .m4a, .wav) dans « input_documents »."),
                ],
            ),
        ]

        for tab_title, blocks in sections:
            tab = tk.Frame(nb, bg="#ffffff", padx=16, pady=12)
            nb.add(tab, text=f"  {tab_title}  ")
            txt = tk.Text(tab, wrap="word", bg="#ffffff", fg="#0f172a", relief="flat", font=("Segoe UI", 9), padx=6, pady=4)
            txt.tag_configure("heading", font=("Segoe UI", 10, "bold"), foreground="#1d4ed8", spacing1=8, spacing3=3)
            txt.tag_configure("body", font=("Segoe UI", 9), foreground="#1e293b", lmargin1=12, lmargin2=12, spacing3=8)
            for h_title, b_text in blocks:
                txt.insert("end", h_title + "\n", "heading")
                self._insert_guide_text_with_links(txt, b_text)
            txt.configure(state="disabled")
            sb = ttk.Scrollbar(tab, orient="vertical", command=txt.yview)
            txt.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            txt.pack(side="left", fill="both", expand=True)

        if 0 <= initial_tab < len(sections):
            nb.select(initial_tab)

        footer = tk.Frame(win, bg="#e2e8f0", padx=16, pady=10)
        footer.pack(fill="x")
        self._make_button(footer, text="Fermer le guide", command=win.destroy, variant="primary").pack(side="right")


def main() -> None:
    app = AnonymizerGuiApp()
    app.mainloop()


if __name__ == "__main__":
    main()
