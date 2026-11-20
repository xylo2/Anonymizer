# Commandes pip à exécuter : Aucune dépendance externe requise

import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional


UI_COLORS: Dict[str, str] = {
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


def configure_ttk_styles(root: tk.Misc) -> None:
    """Configure les styles ttk modernes partagés par l'application."""
    style = ttk.Style(root)
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


def make_styled_button(
    parent: tk.Widget,
    text: str,
    command: object,
    variant: str = "primary",
    tooltip: str = "",
) -> tk.Button:
    """Construit un bouton plat harmonisé avec effet au survol et infobulle."""
    bg_map = {
        "primary": (UI_COLORS["primary"], UI_COLORS["primary_hover"], "#ffffff"),
        "success": (UI_COLORS["success"], UI_COLORS["success_hover"], "#ffffff"),
        "danger": ("#dc2626", "#b91c1c", "#ffffff"),
        "secondary": (UI_COLORS["secondary"], UI_COLORS["secondary_hover"], "#0f172a"),
    }
    bg, hover_bg, fg = bg_map.get(variant, bg_map["primary"])
    btn = tk.Button(
        parent,
        text=text,
        command=command,  # type: ignore[arg-type]
        bg=bg,
        fg=fg,
        disabledforeground="#64748b",
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


def make_card(parent: tk.Widget, title: str, subtitle: str = "") -> tk.Frame:
    """Construit une carte blanche encadrée avec titre et sous-titre."""
    outer = tk.Frame(
        parent,
        bg=UI_COLORS["card"],
        highlightbackground=UI_COLORS["border"],
        highlightthickness=1,
        padx=16,
        pady=12,
    )
    outer.pack(fill="x", pady=(0, 10))
    tk.Label(
        outer,
        text=title,
        bg=UI_COLORS["card"],
        fg=UI_COLORS["text"],
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w")
    if subtitle:
        tk.Label(
            outer,
            text=subtitle,
            bg=UI_COLORS["card"],
            fg=UI_COLORS["muted"],
            font=("Segoe UI", 9),
            wraplength=780,
            justify="left",
        ).pack(anchor="w", pady=(3, 8))
    return outer
