# Commandes pip à exécuter : pip install customtkinter>=5.2.2

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict
from doc_anonymizer.gui_widgets import (
    UI_COLORS,
    make_card,
    make_modern_dropdown,
    make_modern_entry,
    make_styled_button,
)


class GuiDeanonPageMixin:
    """Écran de désanonymisation des documents retournés par l'IA."""

    pages: Dict[str, Any]

    def _build_page_deanonymize(self) -> None:
        parent = self.pages["deanon"]
        top = make_card(
            parent,
            title="Désanonymiser les documents retournés par l'IA",
            subtitle="Importez le fichier IA (.txt, .md, .docx, .odt, .rtf) pour restituer les vraies identités.",
            accent_color="#2563eb",
        )
        bar = tk.Frame(top, bg=UI_COLORS["card"])
        bar.pack(fill="x")
        make_styled_button(
            bar, text="Ajouter un document IA...",
            command=self._select_deanon_files, variant="primary",  # type: ignore[attr-defined]
        ).pack(side="left", padx=(0, 8))
        make_styled_button(
            bar, text="Vider la liste",
            command=self._clear_deanon_files, variant="secondary",  # type: ignore[attr-defined]
        ).pack(side="left")

        self.deanon_files_var = tk.StringVar(
            value="Aucun document IA sélectionné pour le moment."
        )
        tk.Label(
            top, textvariable=self.deanon_files_var,
            bg=UI_COLORS["card"], fg="#1d4ed8", font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", pady=(8, 0))

        table_card = tk.Frame(
            parent, bg=UI_COLORS["card"],
            highlightbackground=UI_COLORS["border"],
            highlightthickness=1, padx=4, pady=4,
        )
        table_card.pack(fill="both", expand=True, pady=(0, 8))
        cols = ("apply", "token", "proposed", "status", "count", "context")
        self.deanon_tree = ttk.Treeview(
            table_card, columns=cols, show="headings",
            selectmode="browse", style="Modern.Treeview", height=6,
        )
        self.deanon_tree.tag_configure("kept", background="#ecfdf5", foreground="#065f46")
        self.deanon_tree.tag_configure("ignored", background="#fef2f2", foreground="#991b1b")
        headers = (
            ("apply", "ACTIF", 75), ("token", "TERME ANONYME", 170),
            ("proposed", "REMPLACEMENT", 190), ("status", "STATUT", 150),
            ("count", "OCC.", 60), ("context", "EXTRAIT", 220),
        )
        for col_id, lbl, w in headers:
            self.deanon_tree.heading(col_id, text=lbl)
            self.deanon_tree.column(col_id, width=w, anchor="center" if col_id in ("apply", "count") else "w")
        sb = ttk.Scrollbar(table_card, orient="vertical", command=self.deanon_tree.yview)
        self.deanon_tree.configure(yscrollcommand=sb.set)
        self.deanon_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.deanon_tree.bind("<<TreeviewSelect>>", self._on_deanon_row_selected)  # type: ignore[attr-defined]
        self.deanon_tree.bind("<Double-1>", lambda _e: self._toggle_deanon_row_apply())  # type: ignore[attr-defined]

        edit_card = make_card(parent, title="Ajuster la correspondance sélectionnée")
        edit_row = tk.Frame(edit_card, bg=UI_COLORS["card"])
        edit_row.pack(fill="x")
        self.deanon_edit_val_var = tk.StringVar()
        make_modern_entry(edit_row, self.deanon_edit_val_var, width=210).pack(side="left", padx=(0, 8))
        self.deanon_alt_var = tk.StringVar(value="Aucun choix probable")
        self.combo_deanon_alts = make_modern_dropdown(
            edit_row, self.deanon_alt_var, ["Aucun choix probable"],
            width=210, command=lambda _v: self._on_deanon_alt_picked(),  # type: ignore[attr-defined]
        )
        self.combo_deanon_alts.pack(side="left", padx=(0, 8))
        make_styled_button(
            edit_row, text="Appliquer",
            command=self._apply_deanon_row_edit, variant="secondary",  # type: ignore[attr-defined]
        ).pack(side="left", padx=(0, 8))
        make_styled_button(
            edit_row, text="Activer / Désactiver",
            command=self._toggle_deanon_row_apply, variant="secondary",  # type: ignore[attr-defined]
        ).pack(side="left")

        nav_row = tk.Frame(parent, bg=UI_COLORS["bg"])
        nav_row.pack(fill="x", pady=(2, 0))
        make_styled_button(
            nav_row, text="<- Retour",
            command=lambda: self._show_page("export"), variant="secondary",  # type: ignore[attr-defined]
        ).pack(side="left")
        make_styled_button(
            nav_row, text="Générer les fichiers _nominatif ->",
            command=self._export_deanonymized_files, variant="success",  # type: ignore[attr-defined]
        ).pack(side="right")
