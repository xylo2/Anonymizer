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
        """Met à jour dynamiquement le texte des onglets (compteurs)."""
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
def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h: str = hex_color.lstrip("#")
    if len(h) != 6:
        return (255, 255, 255)
    return (int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _render_rounded_dropdown_image(
    master: tk.Misc, width: int, height: int,
    border_hex: str, btn_bg_hex: str, card_bg_hex: str = "#ffffff",
) -> Any:
    """Génère une tk.PhotoImage PPM pure Python à coins arrondis antialiasés."""
    w: int = max(40, width)
    h: int = max(20, height)
    bg_rgb = _hex_to_rgb(card_bg_hex)
    bd_rgb = _hex_to_rgb(border_hex)
    btn_rgb = _hex_to_rgb(btn_bg_hex)
    in_rgb = (255, 255, 255)
    rad: float = 8.0
    bw: float = 1.2
    btn_start_x: float = float(w - 36)
    cx: float = (w - 1.0) / 2.0
    cy: float = (h - 1.0) / 2.0
    hx: float = cx - rad
    hy: float = cy - rad
    subs: Tuple[float, ...] = (-0.375, -0.125, 0.125, 0.375)
    buf = bytearray(w * h * 3)
    idx: int = 0
    for y in range(h):
        for x in range(w):
            r_acc = g_acc = b_acc = 0
            for sy in subs:
                dy: float = max(0.0, abs((y + sy) - cy) - hy)
                for sx in subs:
                    px: float = x + sx
                    dx: float = max(0.0, abs(px - cx) - hx)
                    dist: float = (dx * dx + dy * dy) ** 0.5 - rad
                    if dist > 0.0:
                        c = bg_rgb
                    elif dist > -bw:
                        c = bd_rgb
                    elif px >= btn_start_x:
                        c = btn_rgb
                    else:
                        c = in_rgb
                    r_acc += c[0]
                    g_acc += c[1]
                    b_acc += c[2]
            buf[idx] = r_acc >> 4
            buf[idx + 1] = g_acc >> 4
            buf[idx + 2] = b_acc >> 4
            idx += 3
    ppm_header: bytes = f"P6\n{w} {h}\n255\n".encode("ascii")
    try:
        return tk.PhotoImage(master=master, data=ppm_header + bytes(buf), format="PPM")
    except tk.TclError:
        return None
class CleanDropdown(tk.Canvas):
    """Sélecteur déroulant à coins arrondis antialiasés et zoom dynamique."""

    def __init__(
        self, parent: tk.Misc, variable: tk.StringVar, values: List[str],
        width: int = 260, command: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self._box_w: int = width
        self._box_h: int = max(36, int(round(36 * UI_FONT_SCALE)))
        parent_bg: str = UI_COLORS["card"]
        try:
            parent_bg = str(parent.cget("bg"))
        except tk.TclError:
            pass
        self._parent_bg: str = parent_bg
        super().__init__(parent, width=width, height=self._box_h, bg=parent_bg, highlightthickness=0, bd=0, cursor="hand2")
        self.variable: tk.StringVar = variable
        self._values: List[str] = list(values) if values else []
        self._command: Optional[Callable[[str], Any]] = command
        self._popup: Optional[tk.Toplevel] = None
        self._hovered: bool = False
        self._bg_photo: Any = None
        self._text_id: int = self.create_text(12, self._box_h // 2, text=self.variable.get(), anchor="w", fill=UI_COLORS["text"], font=("Segoe UI", scaled_size(10)))
        self.variable.trace_add("write", lambda *_a: self._sync_text())
        self._redraw_skin()
        self.bind("<Configure>", lambda _e: self._redraw_skin())
        self.bind("<Button-1>", lambda _e: self._toggle_menu())
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self.bind("<FocusIn>", lambda _e: self._redraw_skin())
        self.bind("<FocusOut>", lambda _e: self._redraw_skin())
        make_widget_keyboard_accessible(self, command=self._toggle_menu)
        self.bind("<Down>", lambda _e: (self._open_menu(), "break"))

    def _sync_text(self) -> None:
        try:
            self.itemconfigure(self._text_id, text=self.variable.get())
        except tk.TclError:
            pass

    def _set_hover(self, state: bool) -> None:
        self._hovered = state
        self._redraw_skin()

    def _redraw_skin(self) -> None:
        target_h: int = max(36, int(round(36 * UI_FONT_SCALE)))
        if int(self.cget("height")) != target_h:
            self._box_h = target_h
            super().configure(height=target_h)
        cur_w: int = max(self._box_w, self.winfo_width() if self.winfo_width() > 10 else self._box_w)
        cur_h: int = target_h
        active: bool = self._popup is not None or self.focus_displayof() is self
        border_c: str = UI_COLORS["primary"] if active else UI_COLORS["border_strong"]
        btn_c: str = "#e2e8f0" if self._hovered else "#f1f5f9"
        photo = _render_rounded_dropdown_image(self, cur_w, cur_h, border_c, btn_c, self._parent_bg)
        self.delete("skin")
        if photo is not None:
            self._bg_photo = photo
            self.create_image(0, 0, image=photo, anchor="nw", tags="skin")
        else:
            self.create_rectangle(1, 1, cur_w - 2, cur_h - 2, fill="#ffffff", outline=border_c, tags="skin")
        self.create_text(cur_w - 18, cur_h // 2, text="▾", fill="#334155", font=("Segoe UI", scaled_size(11), "bold"), tags="skin")
        self.coords(self._text_id, 12, cur_h // 2)
        self.itemconfigure(self._text_id, font=("Segoe UI", scaled_size(10)))
        self.tag_raise(self._text_id)
    def _close_menu(self) -> None:
        if self._popup is not None:
            try:
                self._popup.grab_release()
                self._popup.destroy()
            except tk.TclError:
                pass
            self._popup = None
            self._redraw_skin()

    def _toggle_menu(self) -> None:
        if self._popup is not None:
            self._close_menu()
        else:
            self._open_menu()

    def _open_menu(self) -> None:
        if not self._values:
            return
        self._close_menu()
        self.update_idletasks()
        row_h: int = max(32, int(round(32 * UI_FONT_SCALE)))
        box_w: int = max(120, self.winfo_width())
        box_h: int = min(len(self._values), 10) * row_h + 2
        popup = tk.Toplevel(self)
        popup.wm_overrideredirect(True)
        popup.wm_geometry(f"{box_w}x{box_h}+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height() + 2}")
        popup.configure(bg=UI_COLORS["border_strong"], padx=1, pady=1)
        inner = tk.Frame(popup, bg="#ffffff")
        inner.pack(fill="both", expand=True)
        cur_val: str = self.variable.get()
        for val in self._values:
            is_cur: bool = val == cur_val
            item_lbl = tk.Label(inner, text=val, bg="#eff6ff" if is_cur else "#ffffff", fg="#1d4ed8" if is_cur else UI_COLORS["text"], font=("Segoe UI", scaled_size(10), "bold" if is_cur else "normal"), anchor="w", padx=12, pady=5, cursor="hand2")
            item_lbl.pack(fill="x")
            item_lbl.bind("<Enter>", lambda _e, lbl=item_lbl: lbl.configure(bg="#eff6ff", fg="#1d4ed8"))
            item_lbl.bind("<Leave>", lambda _e, lbl=item_lbl, sel=is_cur: lbl.configure(bg="#eff6ff" if sel else "#ffffff", fg="#1d4ed8" if sel else UI_COLORS["text"]))
            item_lbl.bind("<Button-1>", lambda _e, v=val: self._choose(v))
        self._popup = popup
        self._redraw_skin()
        popup.bind("<Escape>", lambda _e: self._close_menu())
        popup.bind("<Button-1>", lambda e: self._close_menu() if e.widget is popup else None)
        popup.focus_set()
        popup.grab_set()

    def _choose(self, value: str) -> None:
        self._close_menu()
        self.variable.set(value)
        if self._command is not None:
            self._command(value)

    def configure(self, **kwargs: Any) -> Any:  # type: ignore[override]
        if "font" in kwargs:
            kwargs.pop("font")
            self._redraw_skin()
        if "values" in kwargs:
            self._values = list(kwargs.pop("values") or [])
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if kwargs:
            return super().configure(**kwargs)
        return None

    def set(self, val: str) -> None:
        self.variable.set(val)

    def get(self) -> str:
        return self.variable.get()


def make_modern_dropdown(
    parent: tk.Misc, variable: tk.StringVar, values: List[str],
    width: int = 260, command: Optional[Callable[[str], Any]] = None,
) -> Any:
    if SCREEN_READER_MODE:
        cb_tk = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=max(16, width // 8), font=("Segoe UI", scaled_size(10)))
        if command is not None:
            cb_tk.bind("<<ComboboxSelected>>", lambda _e: command(variable.get()))
        register_scalable_font(cb_tk, "Segoe UI", 10, "normal")
        make_widget_keyboard_accessible(cb_tk)
        return cb_tk
    cb = CleanDropdown(parent, variable, values, width=width, command=command)
    register_scalable_font(cb, "Segoe UI", 10, "normal")
    return cb
