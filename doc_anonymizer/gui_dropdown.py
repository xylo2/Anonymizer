# Commandes pip à exécuter : Aucune dépendance externe requise

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, List, Optional, Tuple
from doc_anonymizer import gui_widgets as _gw
from doc_anonymizer.gui_widgets import (
    UI_COLORS,
    make_widget_keyboard_accessible,
    register_scalable_font,
    scaled_size,
)


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
        self._box_h: int = max(36, int(round(36 * _gw.UI_FONT_SCALE)))
        parent_bg: str = UI_COLORS["card"]
        try:
            parent_bg = str(parent.cget("bg"))
        except tk.TclError:
            pass
        self._parent_bg: str = parent_bg
        super().__init__(
            parent, width=width, height=self._box_h, bg=parent_bg,
            highlightthickness=0, bd=0, cursor="hand2",
        )
        self.variable: tk.StringVar = variable
        self._values: List[str] = list(values) if values else []
        self._command: Optional[Callable[[str], Any]] = command
        self._popup: Optional[tk.Toplevel] = None
        self._hovered: bool = False
        self._bg_photo: Any = None
        self._text_id: int = self.create_text(
            12, self._box_h // 2, text=self.variable.get(), anchor="w",
            fill=UI_COLORS["text"], font=("Segoe UI", scaled_size(10)),
        )
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
        target_h: int = max(36, int(round(36 * _gw.UI_FONT_SCALE)))
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
        row_h: int = max(32, int(round(32 * _gw.UI_FONT_SCALE)))
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
            item_lbl = tk.Label(
                inner, text=val,
                bg="#eff6ff" if is_cur else "#ffffff",
                fg="#1d4ed8" if is_cur else UI_COLORS["text"],
                font=("Segoe UI", scaled_size(10), "bold" if is_cur else "normal"),
                anchor="w", padx=12, pady=5, cursor="hand2",
            )
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
    if _gw.SCREEN_READER_MODE:
        cb_tk = ttk.Combobox(
            parent, textvariable=variable, values=values, state="readonly",
            width=max(16, width // 8), font=("Segoe UI", scaled_size(10)),
        )
        if command is not None:
            cb_tk.bind("<<ComboboxSelected>>", lambda _e: command(variable.get()))
        register_scalable_font(cb_tk, "Segoe UI", 10, "normal")
        make_widget_keyboard_accessible(cb_tk)
        return cb_tk
    cb = CleanDropdown(parent, variable, values, width=width, command=command)
    register_scalable_font(cb, "Segoe UI", 10, "normal")
    return cb
