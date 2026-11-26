# Commandes pip à exécuter : Aucune dépendance externe requise

import tkinter as tk
from tkinter import ttk
from typing import Any


class ScrollablePageContainer(tk.Frame):
    """Conteneur principal avec barres de défilement horizontale et verticale sur toute la zone de page."""

    def __init__(self, parent: tk.Misc, bg_color: str, pad_x: int = 22, pad_y: int = 16) -> None:
        super().__init__(parent, bg=bg_color)
        self._bg: str = bg_color
        self.canvas = tk.Canvas(
            self, bg=bg_color, highlightthickness=0, bd=0,
        )
        self.v_scroll = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.h_scroll = ttk.Scrollbar(
            self, orient="horizontal", command=self.canvas.xview
        )
        self.canvas.configure(
            yscrollcommand=self.v_scroll.set,
            xscrollcommand=self.h_scroll.set,
        )
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        self.inner = tk.Frame(self.canvas, bg=bg_color, padx=pad_x, pady=pad_y)
        self._win_id: int = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw"
        )
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_wheel)
        self.inner.bind("<Shift-MouseWheel>", self._on_shift_wheel)

    def _sync_scroll_region(self) -> None:
        self.update_idletasks()
        cw: int = self.canvas.winfo_width()
        ch: int = self.canvas.winfo_height()
        req_w: int = self.inner.winfo_reqwidth()
        req_h: int = self.inner.winfo_reqheight()
        target_w: int = max(cw, req_w) if cw > 1 else req_w
        target_h: int = max(ch, req_h) if ch > 1 else req_h
        self.canvas.itemconfigure(self._win_id, width=target_w, height=target_h)
        self.canvas.configure(scrollregion=(0, 0, target_w, target_h))

    def _on_inner_configure(self, _event: Any = None) -> None:
        self._sync_scroll_region()

    def _on_canvas_configure(self, _event: Any = None) -> None:
        self._sync_scroll_region()

    def _on_shift_wheel(self, event: Any) -> str:
        delta: int = -1 if getattr(event, "delta", 0) > 0 else 1
        self.canvas.xview_scroll(delta * 3, "units")
        return "break"

    def reset_scroll(self) -> None:
        self._sync_scroll_region()
        self.canvas.xview_moveto(0.0)
        self.canvas.yview_moveto(0.0)
