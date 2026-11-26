# Commandes pip à exécuter : Aucune dépendance externe requise

import tkinter as tk
from typing import Any, Callable, Optional


class LabeledModernEntry(tk.Entry):
    """Champ de saisie encadré avec libellé explicite, texte indicatif visible et bouton effacer."""

    def __init__(
        self,
        parent: tk.Misc,
        textvariable: Optional[tk.StringVar],
        width: int,
        placeholder: str,
        colors: dict[str, str],
        scaled_fn: Callable[[int], int],
        reg_font_fn: Callable[..., Any],
        kbd_fn: Callable[[Any], None],
        tooltip_cls: Any,
    ) -> None:
        eff_ph: str = placeholder.strip() or "Filtrer (nom, numéro, e-mail)..."
        is_search: bool = "recherch" in eff_ph.lower() or "filtrer" in eff_ph.lower()
        self.wrapper = tk.Frame(
            parent, bg="#ffffff",
            highlightbackground=colors["border_strong"],
            highlightthickness=1, padx=8, pady=4,
        )
        if is_search:
            lbl_ico = tk.Label(
                self.wrapper, text="Rechercher :", bg="#ffffff", fg=colors["muted"],
                font=("Segoe UI", scaled_fn(9), "bold"),
            )
            lbl_ico.pack(side="left", padx=(0, 6))
            reg_font_fn(lbl_ico, "Segoe UI", 9, "bold")

        self._var: tk.StringVar = textvariable if textvariable is not None else tk.StringVar()
        super().__init__(
            self.wrapper, textvariable=self._var, width=max(14, width // 8),
            relief="flat", bd=0, bg="#ffffff", fg=colors["text"],
            insertbackground=colors["primary"], font=("Segoe UI", scaled_fn(10)),
        )
        super().pack(side="left", fill="x", expand=True)
        reg_font_fn(self, "Segoe UI", 10, "normal")
        kbd_fn(self)

        self._lbl_ph = tk.Label(
            self, text=eff_ph, bg="#ffffff", fg="#64748b",
            font=("Segoe UI", scaled_fn(9), "italic"), cursor="xterm",
        )
        reg_font_fn(self._lbl_ph, "Segoe UI", 9, "italic")
        self._lbl_ph.bind("<Button-1>", lambda _e: self.focus_set())

        self._btn_clear = tk.Button(
            self.wrapper, text="✕", relief="flat", bd=0,
            bg="#ffffff", fg="#64748b", activebackground="#f1f5f9",
            activeforeground=colors["text"], cursor="hand2", padx=4,
            font=("Segoe UI", scaled_fn(9), "bold"),
            command=lambda: (self._var.set(""), self.focus_set(), self.event_generate("<KeyRelease>")),
        )
        reg_font_fn(self._btn_clear, "Segoe UI", 9, "bold")

        self._var.trace_add("write", self._sync_visual)
        self.bind("<FocusIn>", lambda _e: self._on_focus(True, colors), add="+")
        self.bind("<FocusOut>", lambda _e: self._on_focus(False, colors), add="+")
        self._sync_visual()
        tooltip_cls(
            self,
            "Saisissez un nom, prénom, numéro ou e-mail pour filtrer (Ctrl+F, Échap pour effacer).",
        )

    def _sync_visual(self, *_args: Any) -> None:
        if self._var.get():
            self._lbl_ph.place_forget()
            if not self._btn_clear.winfo_manager():
                self._btn_clear.pack(side="right", padx=(4, 0))
        else:
            self._btn_clear.pack_forget()
            if self.focus_displayof() is not self:
                self._lbl_ph.place(relx=0.0, rely=0.5, anchor="w")
            else:
                self._lbl_ph.place_forget()

    def _on_focus(self, focused: bool, colors: dict[str, str]) -> None:
        self.wrapper.configure(
            highlightbackground=colors["primary"] if focused else colors["border_strong"],
            highlightthickness=2 if focused else 1,
        )
        self._sync_visual()

    def pack(self, **kwargs: Any) -> None:  # type: ignore[override]
        self.wrapper.pack(**kwargs)

    def pack_forget(self) -> None:
        self.wrapper.pack_forget()

    def grid(self, **kwargs: Any) -> None:  # type: ignore[override]
        self.wrapper.grid(**kwargs)

    def grid_forget(self) -> None:
        self.wrapper.grid_forget()
