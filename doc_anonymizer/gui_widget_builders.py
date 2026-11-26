# Commandes pip à exécuter : pip install customtkinter>=5.2.2

import tkinter as tk
from typing import Any, Optional
from doc_anonymizer import gui_widgets as _gw
from doc_anonymizer.gui_entry_widget import LabeledModernEntry


def build_modern_entry(
    parent: tk.Misc,
    textvariable: Optional[tk.StringVar] = None,
    width: int = 240,
    placeholder: str = "",
) -> Any:
    """Crée un champ de saisie moderne avec libellé, aide au survol et bouton d'effacement."""
    return LabeledModernEntry(
        parent=parent,
        textvariable=textvariable,
        width=width,
        placeholder=placeholder,
        colors=_gw.UI_COLORS,
        scaled_fn=_gw.scaled_size,
        reg_font_fn=_gw.register_scalable_font,
        kbd_fn=_gw.make_widget_keyboard_accessible,
        tooltip_cls=_gw.AccessibleTooltip,
    )


def make_card(
    parent: tk.Misc, title: str = "", subtitle: str = "", accent_color: str = ""
) -> tk.Frame:
    if _gw.HAS_CTK and _gw.ctk is not None and not _gw.SCREEN_READER_MODE:
        outer = _gw.ctk.CTkFrame(
            parent, fg_color=_gw.UI_COLORS["card"], border_width=1,
            border_color=_gw.UI_COLORS["border"], corner_radius=12,
        )
        outer.pack(fill="x", pady=(0, 10))
        if accent_color:
            bar = _gw.ctk.CTkFrame(outer, fg_color=accent_color, width=5, corner_radius=3)
            bar.pack(side="left", fill="y", padx=(4, 0), pady=6)
        body = tk.Frame(outer, bg=_gw.UI_COLORS["card"], padx=16, pady=12)
        body.pack(side="left", fill="both", expand=True)
    else:
        outer_tk = tk.Frame(
            parent, bg=_gw.UI_COLORS["card"],
            highlightbackground=_gw.UI_COLORS["border"], highlightthickness=1,
        )
        outer_tk.pack(fill="x", pady=(0, 10))
        if accent_color:
            tk.Frame(outer_tk, bg=accent_color, width=5).pack(side="left", fill="y")
        body = tk.Frame(outer_tk, bg=_gw.UI_COLORS["card"], padx=16, pady=12)
        body.pack(side="left", fill="both", expand=True)
    if title:
        lbl_t = tk.Label(
            body, text=title, bg=_gw.UI_COLORS["card"], fg=_gw.UI_COLORS["text"],
            font=("Segoe UI", _gw.scaled_size(11), "bold"),
            justify="left", anchor="w", wraplength=780,
        )
        lbl_t.pack(anchor="w")
        _gw.register_scalable_font(lbl_t, "Segoe UI", 11, "bold")
    if subtitle:
        lbl_s = tk.Label(
            body, text=subtitle, bg=_gw.UI_COLORS["card"], fg=_gw.UI_COLORS["muted"],
            font=("Segoe UI", _gw.scaled_size(9)),
            justify="left", anchor="w", wraplength=780,
        )
        lbl_s.pack(anchor="w", pady=(2, 8))
        _gw.register_scalable_font(lbl_s, "Segoe UI", 9, "normal")
    return body
