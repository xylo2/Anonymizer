# Commandes pip à exécuter : Aucune dépendance externe requise

import tkinter as tk
from tkinter import ttk
from typing import Any


def inject_tree_column_toolbar(tree: ttk.Treeview, mgr: Any) -> None:
    """Injecte la barre d'outils de gestion des colonnes au-dessus du tableau."""
    parent = tree.master
    if parent is None or getattr(parent, "_has_col_toolbar", False):
        return
    setattr(parent, "_has_col_toolbar", True)
    bar = tk.Frame(parent, bg="#f8fafc", padx=6, pady=3)
    slaves = parent.pack_slaves()
    if slaves:
        bar.pack(side="top", fill="x", before=next(iter(slaves)))
    else:
        bar.pack(side="top", fill="x")
    tk.Label(
        bar,
        text="Glissez les en-têtes pour réordonner • Double-clic pour ajuster",
        bg="#f8fafc",
        fg="#64748b",
        font=("Segoe UI", 8),
    ).pack(side="left")
    btn_reset = tk.Button(
        bar,
        text="Réinitialiser colonnes",
        relief="flat",
        bd=0,
        bg="#e2e8f0",
        fg="#0f172a",
        padx=8,
        pady=2,
        cursor="hand2",
        font=("Segoe UI", 8),
        command=mgr.reset_to_default,
    )
    btn_reset.pack(side="right")
    btn_cols = tk.Button(
        bar,
        text="Colonnes ▾",
        relief="flat",
        bd=0,
        bg="#e2e8f0",
        fg="#0f172a",
        padx=8,
        pady=2,
        cursor="hand2",
        font=("Segoe UI", 8, "bold"),
    )
    btn_cols.configure(
        command=lambda b=btn_cols: mgr.open_columns_menu(
            b.winfo_rootx(), b.winfo_rooty() + b.winfo_height()
        )
    )
    btn_cols.pack(side="right", padx=(0, 6))
    setattr(tree, "_col_reset_btn", btn_reset)
    setattr(tree, "_col_menu_btn", btn_cols)
