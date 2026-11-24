# Commandes pip à exécuter : pip install customtkinter>=5.2.2

import json
import os
import sys
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import customtkinter as ctk  # type: ignore[import-untyped]
    HAS_CTK: bool = True
except ImportError:
    ctk = None
    HAS_CTK = False

UI_COLORS: Dict[str, str] = {
    "bg": "#eef2f6",
    "sidebar": "#0f172a",
    "sidebar_hover": "#1e293b",
    "sidebar_active": "#2563eb",
    "card": "#ffffff",
    "card_alt": "#f8fafc",
    "border": "#cbd5e1",
    "border_strong": "#94a3b8",
    "text": "#0f172a",
    "muted": "#475569",
    "primary": "#2563eb",
    "primary_hover": "#1d4ed8",
    "success": "#059669",
    "success_hover": "#047857",
    "danger": "#dc2626",
    "danger_hover": "#b91c1c",
    "danger_soft_bg": "#fef2f2",
    "danger_soft_hover": "#fee2e2",
    "danger_soft_border": "#fca5a5",
    "danger_soft_fg": "#b91c1c",
    "secondary_bg": "#f1f5f9",
    "secondary_hover": "#e2e8f0",
    "tab_rail": "#e2e8f0",
    "tab_active_bg": "#1e293b",
    "tab_active_fg": "#ffffff",
    "tab_inactive_fg": "#334155",
    "warning_bg": "#fef3c7",
    "warning_fg": "#92400e",
    "log_bg": "#0b1120",
    "log_fg": "#e2e8f0",
}
BUTTON_STYLES: Dict[str, Tuple[str, str, str, int, str]] = {
    "primary": (
        UI_COLORS["primary"], UI_COLORS["primary_hover"],
        "#ffffff", 0, UI_COLORS["primary"],
    ),
    "success": (
        UI_COLORS["success"], UI_COLORS["success_hover"],
        "#ffffff", 0, UI_COLORS["success"],
    ),
    "danger": (
        UI_COLORS["danger"], UI_COLORS["danger_hover"],
        "#ffffff", 0, UI_COLORS["danger"],
    ),
    "danger_soft": (
        UI_COLORS["danger_soft_bg"], UI_COLORS["danger_soft_hover"],
        UI_COLORS["danger_soft_fg"], 1, UI_COLORS["danger_soft_border"],
    ),
    "ghost": (
        "#ffffff", "#f1f5f9",
        UI_COLORS["muted"], 1, UI_COLORS["border"],
    ),
    "secondary": (
        UI_COLORS["secondary_bg"], UI_COLORS["secondary_hover"],
        UI_COLORS["text"], 1, UI_COLORS["border"],
    ),
}

UI_FONT_SCALE: float = 1.0
_ENV_SR: str = os.environ.get("ANONYMIZER_SCREEN_READER", "").strip().lower()
SCREEN_READER_MODE: bool = "--screen-reader" in sys.argv or _ENV_SR in {"1", "true", "yes"}
_SCALED_WIDGETS: List[Tuple[Any, str, int, str]] = []
_REGISTERED_TOOLTIPS: List[Any] = []
_ACTIVE_TTK_STYLE: Optional[ttk.Style] = None


def set_screen_reader_mode(enabled: bool) -> bool:
    global SCREEN_READER_MODE
    SCREEN_READER_MODE = bool(enabled)
    return SCREEN_READER_MODE


def scaled_size(base_pt: int) -> int:
    return max(8, int(round(base_pt * UI_FONT_SCALE)))


def register_scalable_font(
    widget: Any, family: str, base_pt: int, weight: str = "normal"
) -> Tuple[str, int, str]:
    _SCALED_WIDGETS.append((widget, family, base_pt, weight))
    return (family, scaled_size(base_pt), weight)
def load_saved_ui_font_scale(prefs_path: str) -> float:
    """Restaure le facteur de zoom texte sauvegardé (0.85 à 1.50)."""
    global UI_FONT_SCALE
    if prefs_path and os.path.isfile(prefs_path):
        try:
            with open(prefs_path, "r", encoding="utf-8") as f_in:
                payload = json.load(f_in)
            if isinstance(payload, dict) and "font_scale" in payload:
                val: float = float(payload["font_scale"])
                UI_FONT_SCALE = max(0.85, min(1.5, round(val, 2)))
                return UI_FONT_SCALE
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    return UI_FONT_SCALE


def save_ui_font_scale(prefs_path: str, scale: float) -> None:
    """Enregistre le facteur de zoom texte pour les prochaines ouvertures."""
    if not prefs_path:
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(prefs_path)), exist_ok=True)
        existing: Dict[str, Any] = {}
        if os.path.isfile(prefs_path):
            try:
                with open(prefs_path, "r", encoding="utf-8") as f_in:
                    loaded = json.load(f_in)
                if isinstance(loaded, dict):
                    existing = loaded
            except (OSError, json.JSONDecodeError):
                pass
        existing["font_scale"] = max(0.85, min(1.5, round(float(scale), 2)))
        with open(prefs_path, "w", encoding="utf-8") as f_out:
            json.dump(existing, f_out, ensure_ascii=False, indent=2)
    except OSError:
        pass


def set_ui_font_scale(new_scale: float, prefs_path: str = "") -> float:
    global UI_FONT_SCALE
    UI_FONT_SCALE = max(0.85, min(1.5, round(new_scale, 2)))
    alive: List[Tuple[Any, str, int, str]] = []
    for widget, family, base_pt, weight in _SCALED_WIDGETS:
        try:
            if widget.winfo_exists():
                widget.configure(font=(family, scaled_size(base_pt), weight))
                alive.append((widget, family, base_pt, weight))
        except tk.TclError:
            pass
    _SCALED_WIDGETS[:] = alive
    if _ACTIVE_TTK_STYLE is not None:
        try:
            rh: int = max(26, int(round(30 * UI_FONT_SCALE)))
            _ACTIVE_TTK_STYLE.configure(
                "Modern.Treeview", rowheight=rh, font=("Segoe UI", scaled_size(9))
            )
            _ACTIVE_TTK_STYLE.configure(
                "Modern.Treeview.Heading", font=("Segoe UI", scaled_size(9), "bold")
            )
        except tk.TclError:
            pass
    if prefs_path:
        save_ui_font_scale(prefs_path, UI_FONT_SCALE)
    return UI_FONT_SCALE
class AccessibleTooltip:
    """Infobulle accessible au survol souris ou à la prise de focus clavier."""

    def __init__(self, widget: Any, text: str) -> None:
        self.widget: Any = widget
        self.text: str = text
        self.tip_window: Optional[tk.Toplevel] = None
        _REGISTERED_TOOLTIPS.append(self)
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<FocusIn>", self.show, add="+")
        widget.bind("<FocusOut>", self.hide, add="+")

    def show(self, _event: object = None) -> None:
        if self.tip_window is not None or not self.text:
            return
        try:
            x: int = self.widget.winfo_rootx() + 12
            y: int = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            lbl = tk.Label(
                tw, text=self.text, bg="#0f172a", fg="#ffffff",
                font=("Segoe UI", scaled_size(9)), padx=10, pady=5,
                wraplength=340, justify="left",
            )
            lbl.pack()
            self.tip_window = tw
        except tk.TclError:
            self.tip_window = None

    def hide(self, _event: object = None) -> None:
        if self.tip_window is not None:
            try:
                self.tip_window.destroy()
            except tk.TclError:
                pass
            self.tip_window = None


class CleanSegmentedTabs(tk.Frame):
    """Sélecteur d'onglets sobre avec compteurs dynamiques."""

    def __init__(
        self, parent: Any, options: List[Tuple[str, str]],
        variable: tk.StringVar, command: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent, bg=UI_COLORS["tab_rail"], padx=3, pady=3)
        self.variable: tk.StringVar = variable
        self.command: Optional[Callable[[str], None]] = command
        self._buttons: Dict[str, Any] = {}
        use_ctk: bool = bool(HAS_CTK and ctk is not None and not SCREEN_READER_MODE)
        for label, value in options:
            if use_ctk:
                btn = ctk.CTkButton(
                    self, text=label, height=32, corner_radius=7,
                    font=("Segoe UI", scaled_size(10), "bold"),
                    command=lambda v=value: self._select(v),
                )
            else:
                btn = tk.Button(
                    self, text=label, relief="flat", bd=0, padx=10, pady=4,
                    cursor="hand2", font=("Segoe UI", scaled_size(9), "bold"),
                    command=lambda v=value: self._select(v),
                )
            pt_sz: int = 10 if use_ctk else 9
            register_scalable_font(btn, "Segoe UI", pt_sz, "bold")
            btn.pack(side="left", padx=2)
            self._buttons[value] = btn
        self._refresh()
    def set_option_labels(self, labels_by_value: Dict[str, str]) -> None:
        for val, new_lbl in labels_by_value.items():
            btn = self._buttons.get(val)
            if btn is not None:
                try:
                    btn.configure(text=new_lbl)
                except tk.TclError:
                    pass

    def _select(self, value: str) -> None:
        self.variable.set(value)
        self._refresh()
        if self.command is not None:
            self.command(value)

    def _refresh(self) -> None:
        cur: str = self.variable.get()
        for val, btn in self._buttons.items():
            active: bool = val == cur
            if HAS_CTK and ctk is not None and isinstance(btn, ctk.CTkButton):
                btn.configure(
                    fg_color=UI_COLORS["tab_active_bg"] if active else "transparent",
                    hover_color=UI_COLORS["tab_active_bg"] if active else "#cbd5e1",
                    text_color=UI_COLORS["tab_active_fg"] if active else UI_COLORS["tab_inactive_fg"],
                )
            else:
                btn.configure(
                    bg=UI_COLORS["tab_active_bg"] if active else UI_COLORS["tab_rail"],
                    fg=UI_COLORS["tab_active_fg"] if active else UI_COLORS["tab_inactive_fg"],
                )


def make_widget_keyboard_accessible(
    widget: Any, command: Optional[Callable[[], Any]] = None
) -> None:
    try:
        widget.configure(takefocus=1)
    except (tk.TclError, ValueError):
        try:
            tk.Widget.configure(widget, takefocus=1)
        except tk.TclError:
            pass
    if command is not None:
        for seq in ("<Return>", "<KP_Enter>", "<space>"):
            widget.bind(seq, lambda _e, cmd=command: (cmd(), "break"), add="+")


def configure_ttk_styles(root: tk.Misc) -> None:
    global _ACTIVE_TTK_STYLE
    style = ttk.Style(root)
    _ACTIVE_TTK_STYLE = style
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    rh: int = max(26, int(round(30 * UI_FONT_SCALE)))
    style.configure(
        "Modern.Treeview", background="#ffffff", fieldbackground="#ffffff",
        foreground=UI_COLORS["text"], rowheight=rh,
        font=("Segoe UI", scaled_size(9)), borderwidth=0,
    )
    style.configure(
        "Modern.Treeview.Heading", background="#e2e8f0",
        foreground=UI_COLORS["text"], font=("Segoe UI", scaled_size(9), "bold"),
        relief="flat", padding=(8, 6),
    )
    style.map(
        "Modern.Treeview",
        background=[("selected", "#dbeafe")],
        foreground=[("selected", "#1e3a8a")],
    )


def make_card(
    parent: tk.Misc, title: str = "", subtitle: str = "", accent_color: str = ""
) -> tk.Frame:
    if HAS_CTK and ctk is not None and not SCREEN_READER_MODE:
        outer = ctk.CTkFrame(
            parent, fg_color=UI_COLORS["card"], border_width=1,
            border_color=UI_COLORS["border"], corner_radius=12,
        )
        outer.pack(fill="x", pady=(0, 10))
        if accent_color:
            bar = ctk.CTkFrame(outer, fg_color=accent_color, width=5, corner_radius=3)
            bar.pack(side="left", fill="y", padx=(4, 0), pady=6)
        body = tk.Frame(outer, bg=UI_COLORS["card"], padx=16, pady=12)
        body.pack(side="left", fill="both", expand=True)
    else:
        outer_tk = tk.Frame(
            parent, bg=UI_COLORS["card"],
            highlightbackground=UI_COLORS["border"], highlightthickness=1,
        )
        outer_tk.pack(fill="x", pady=(0, 10))
        if accent_color:
            tk.Frame(outer_tk, bg=accent_color, width=5).pack(side="left", fill="y")
        body = tk.Frame(outer_tk, bg=UI_COLORS["card"], padx=16, pady=12)
        body.pack(side="left", fill="both", expand=True)
    if title:
        lbl_t = tk.Label(
            body, text=title, bg=UI_COLORS["card"], fg=UI_COLORS["text"],
            font=("Segoe UI", scaled_size(11), "bold"),
            justify="left", anchor="w", wraplength=780,
        )
        lbl_t.pack(anchor="w")
        register_scalable_font(lbl_t, "Segoe UI", 11, "bold")
    if subtitle:
        lbl_s = tk.Label(
            body, text=subtitle, bg=UI_COLORS["card"], fg=UI_COLORS["muted"],
            font=("Segoe UI", scaled_size(9)),
            justify="left", anchor="w", wraplength=780,
        )
        lbl_s.pack(anchor="w", pady=(2, 8))
        register_scalable_font(lbl_s, "Segoe UI", 9, "normal")
    return body


def make_styled_button(
    parent: tk.Misc, text: str, command: Callable[[], Any],
    variant: str = "primary", tooltip: str = "",
) -> Any:
    bg_c, hov_c, fg_c, bw, bc = BUTTON_STYLES.get(variant, BUTTON_STYLES["secondary"])
    w_str: str = "bold" if variant in {"primary", "success", "danger"} else "normal"
    if HAS_CTK and ctk is not None and not SCREEN_READER_MODE:
        btn: Any = ctk.CTkButton(
            parent, text=text, command=command, fg_color=bg_c,
            hover_color=hov_c, text_color=fg_c, border_width=bw,
            border_color=bc, corner_radius=8, height=35,
            font=("Segoe UI", scaled_size(10), w_str),
        )
        register_scalable_font(btn, "Segoe UI", 10, w_str)
    else:
        tk_bg: str = UI_COLORS["bg"] if bg_c == "transparent" else bg_c
        btn = tk.Button(
            parent, text=text, command=command, bg=tk_bg, fg=fg_c,
            activebackground=hov_c, activeforeground=fg_c,
            relief="solid" if bw else "flat", bd=bw, padx=14, pady=6,
            cursor="hand2", font=("Segoe UI", scaled_size(9), w_str),
        )
        register_scalable_font(btn, "Segoe UI", 9, w_str)
    make_widget_keyboard_accessible(btn, command=command)
    if tooltip:
        AccessibleTooltip(btn, tooltip)
    return btn


def set_button_enabled_style(
    btn: Any, enabled: bool, active_variant: str = "primary"
) -> None:
    bg_c, hov_c, fg_c, bw, bc = BUTTON_STYLES.get(active_variant, BUTTON_STYLES["primary"])
    if HAS_CTK and ctk is not None and isinstance(btn, ctk.CTkButton):
        btn.configure(
            state="normal" if enabled else "disabled",
            fg_color=bg_c if enabled else "#e2e8f0",
            hover_color=hov_c if enabled else "#e2e8f0",
            text_color=fg_c if enabled else "#94a3b8",
            border_width=bw,
            border_color=bc if enabled else "#cbd5e1",
        )
    else:
        tk_bg: str = UI_COLORS["bg"] if bg_c == "transparent" else bg_c
        btn.configure(
            state="normal" if enabled else "disabled",
            bg=tk_bg if enabled else "#e2e8f0",
            fg=fg_c if enabled else "#94a3b8",
        )


def make_stat_tile(
    parent: tk.Misc, value_var: tk.StringVar, label: str, accent: str, bg_tint: str
) -> tk.Frame:
    tile = tk.Frame(
        parent, bg=bg_tint, highlightbackground=accent,
        highlightthickness=1, padx=12, pady=10,
    )
    lbl_v = tk.Label(
        tile, textvariable=value_var, bg=bg_tint, fg=accent,
        font=("Segoe UI", scaled_size(18), "bold"),
    )
    lbl_v.pack(anchor="w")
    register_scalable_font(lbl_v, "Segoe UI", 18, "bold")
    lbl_t = tk.Label(
        tile, text=label, bg=bg_tint, fg=UI_COLORS["text"],
        font=("Segoe UI", scaled_size(9), "bold"),
    )
    lbl_t.pack(anchor="w", pady=(2, 0))
    register_scalable_font(lbl_t, "Segoe UI", 9, "bold")
    return tile


def make_modern_entry(
    parent: tk.Misc, textvariable: Optional[tk.StringVar] = None,
    width: int = 240, placeholder: str = "",
) -> Any:
    if HAS_CTK and ctk is not None and not SCREEN_READER_MODE:
        kw: Dict[str, Any] = {
            "width": width, "height": 36, "corner_radius": 8,
            "border_width": 1, "border_color": UI_COLORS["border_strong"],
            "fg_color": "#ffffff", "text_color": UI_COLORS["text"],
            "placeholder_text_color": "#64748b", "font": ("Segoe UI", 10),
            "placeholder_text": placeholder,
        }
        if textvariable is not None:
            kw["textvariable"] = textvariable
        ent = ctk.CTkEntry(parent, **kw)
        ent.bind("<FocusIn>", lambda _e: ent.configure(border_color=UI_COLORS["primary"], border_width=2), add="+")
        ent.bind("<FocusOut>", lambda _e: ent.configure(border_color=UI_COLORS["border_strong"], border_width=1), add="+")
    else:
        kw_tk: Dict[str, Any] = {
            "width": max(14, width // 8), "relief": "flat", "bd": 0,
            "highlightthickness": 1, "highlightbackground": UI_COLORS["border_strong"],
            "highlightcolor": UI_COLORS["primary"], "bg": "#ffffff",
            "fg": UI_COLORS["text"], "insertbackground": UI_COLORS["primary"],
            "font": ("Segoe UI", 10),
        }
        if textvariable is not None:
            kw_tk["textvariable"] = textvariable
        ent = tk.Entry(parent, **kw_tk)
    register_scalable_font(ent, "Segoe UI", 10, "normal")
    make_widget_keyboard_accessible(ent)
    return ent


from doc_anonymizer.gui_dropdown import (  # noqa: E402, F401
    CleanDropdown,
    make_modern_dropdown,
)
