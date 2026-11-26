# Commandes pip à exécuter : pip install customtkinter>=5.2.2

import tkinter as tk
from typing import Any, Dict, List, Tuple
from doc_anonymizer import gui_widgets as _gw
from doc_anonymizer.gui_widgets import (
    HAS_CTK,
    UI_COLORS,
    ctk,
    make_widget_keyboard_accessible,
    register_scalable_font,
    scaled_size,
)


class GuiSidebarMixin:
    """Construit la barre de navigation latérale et ses étapes dynamiques."""

    current_ini_var: tk.StringVar
    workflow_mode: str
    active_page_key: str
    nav_buttons: Dict[str, Any]
    nav_container: tk.Frame

    def _rebuild_sidebar_nav(self) -> None:
        use_ctk: bool = bool(
            HAS_CTK and ctk is not None and not _gw.SCREEN_READER_MODE
        )
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
            act_cmd = (lambda k=key: self._show_page(k)) if enabled else None  # type: ignore[attr-defined]
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
