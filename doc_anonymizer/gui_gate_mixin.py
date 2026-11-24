# Commandes pip à exécuter : pip install customtkinter>=5.2.2

import os
import tkinter as tk
from tkinter import messagebox
from typing import Any, List, Optional, Tuple
from doc_anonymizer import gui_widgets as _gw
from doc_anonymizer.gui_widgets import HAS_CTK, UI_COLORS, ctk


class GuiGateMixin:
    """Gère la sélection, la création et le rafraîchissement des dossiers isolés."""

    controller: Any
    current_ini_var: tk.StringVar
    active_ws_badge_var: tk.StringVar
    workspaces: List[Tuple[str, str]]
    gate_action_var: tk.StringVar
    gate_existing_var: tk.StringVar
    gate_new_name_var: tk.StringVar
    frame_gate_existing: tk.Frame
    frame_gate_create: tk.Frame
    combo_gate_ws: Any

    def _on_gate_segment_changed(self, value: str) -> None:
        low_v: str = value.lower()
        self.gate_action_var.set(
            "open" if "open" in low_v or "existant" in low_v else "create"
        )
        self._sync_gate_action_panels()

    def _sync_gate_action_panels(self) -> None:
        self.frame_gate_existing.pack_forget()
        self.frame_gate_create.pack_forget()
        is_open: bool = self.gate_action_var.get() == "open" and bool(self.workspaces)
        if not is_open:
            self.gate_action_var.set("create")
        btn_open = getattr(self, "btn_tab_open", None)
        btn_create = getattr(self, "btn_tab_create", None)
        if btn_open is not None and btn_create is not None:
            if HAS_CTK and ctk is not None and isinstance(btn_open, ctk.CTkButton):
                btn_open.configure(
                    fg_color=UI_COLORS["tab_active_bg"] if is_open else "transparent",
                    hover_color=UI_COLORS["tab_active_bg"] if is_open else "#cbd5e1",
                    text_color=UI_COLORS["tab_active_fg"] if is_open else UI_COLORS["tab_inactive_fg"],
                )
                btn_create.configure(
                    fg_color=UI_COLORS["tab_active_bg"] if not is_open else "transparent",
                    hover_color=UI_COLORS["tab_active_bg"] if not is_open else "#cbd5e1",
                    text_color=UI_COLORS["tab_active_fg"] if not is_open else UI_COLORS["tab_inactive_fg"],
                )
            else:
                btn_open.configure(
                    bg=UI_COLORS["tab_active_bg"] if is_open else UI_COLORS["tab_rail"],
                    fg=UI_COLORS["tab_active_fg"] if is_open else UI_COLORS["tab_inactive_fg"],
                )
                btn_create.configure(
                    bg=UI_COLORS["tab_active_bg"] if not is_open else UI_COLORS["tab_rail"],
                    fg=UI_COLORS["tab_active_fg"] if not is_open else UI_COLORS["tab_inactive_fg"],
                )
        (self.frame_gate_existing if is_open else self.frame_gate_create).pack(
            fill="x", pady=(8, 4)
        )
    def _refresh_gate_workspace_panel(self) -> None:
        self.workspaces = self.controller.list_workspaces()
        seg_w = getattr(self, "seg_gate_action", None)
        if seg_w is not None:
            (
                seg_w.pack(anchor="w", pady=(0, 6))
                if self.workspaces
                else seg_w.pack_forget()
            )
        if self.workspaces:
            labels = [lbl for lbl, _ in self.workspaces]
            pref_ini: str = (
                self.current_ini_var.get()
                or self.controller.get_last_opened_workspace()
            )
            cur_idx: int = next(
                (
                    i
                    for i, (_, p) in enumerate(self.workspaces)
                    if pref_ini and os.path.abspath(p) == os.path.abspath(pref_ini)
                ),
                0,
            )
            self.combo_gate_ws.configure(values=labels)
            self.combo_gate_ws.set(labels[cur_idx])
            self.gate_existing_var.set(labels[cur_idx])
            self.gate_action_var.set("open")
        else:
            self.gate_action_var.set("create")
        self._sync_gate_action_panels()

    def _confirm_gate_and_workspace(self) -> None:
        if self.gate_action_var.get() == "open" and self.workspaces:
            selected_lbl: str = self.gate_existing_var.get()
            idx: int = next(
                (i for i, (lbl, _) in enumerate(self.workspaces) if lbl == selected_lbl),
                -1,
            )
            if idx < 0:
                messagebox.showwarning(
                    "Dossier requis", "Veuillez sélectionner un dossier existant."
                )
                return
            _, selected_ini = self.workspaces[idx]
            self._refresh_workspaces(select_ini=selected_ini)
            self._show_page("documents")  # type: ignore[attr-defined]
            return
        raw_name: str = self.gate_new_name_var.get().strip()
        if not raw_name:
            messagebox.showwarning(
                "Nom de dossier obligatoire",
                "Vous devez obligatoirement saisir un nom de dossier pour continuer.",
            )
            return
        try:
            ini_path: str = self.controller.create_workspace(raw_name)
            self.gate_new_name_var.set("")
            self._refresh_workspaces(select_ini=ini_path)
            self._show_page("documents")  # type: ignore[attr-defined]
        except (ValueError, OSError) as exc:
            messagebox.showerror("Erreur", str(exc))

    def _refresh_workspaces(self, select_ini: Optional[str] = None) -> None:
        sr_suffix: str = " [Lecteur d'écran]" if _gw.SCREEN_READER_MODE else ""
        base_title: str = "AnonVault — Pièces protégées"
        self.workspaces = self.controller.list_workspaces()
        if not self.workspaces:
            self.current_ini_var.set("")
            self.active_ws_badge_var.set("Dossier : aucun")
            self.title(f"{base_title}{sr_suffix}")  # type: ignore[attr-defined]
            return
        target_ref: str = select_ini or self.current_ini_var.get()
        target_idx: int = next(
            (
                i
                for i, (_, p) in enumerate(self.workspaces)
                if target_ref and os.path.abspath(p) == os.path.abspath(target_ref)
            ),
            -1,
        )
        if target_idx < 0:
            self.current_ini_var.set("")
            self.active_ws_badge_var.set("Dossier : aucun")
            self.title(f"{base_title}{sr_suffix}")  # type: ignore[attr-defined]
            return
        lbl, selected_ini = self.workspaces[target_idx]
        self.current_ini_var.set(selected_ini)
        self.controller.save_last_opened_workspace(selected_ini)
        self.active_ws_badge_var.set(f"Dossier actif : {lbl}")
        self.title(f"{base_title} — Dossier : {lbl}{sr_suffix}")  # type: ignore[attr-defined]
        self._refresh_audit_list()  # type: ignore[attr-defined]
        self._refresh_workspace_counters()  # type: ignore[attr-defined]
        self._refresh_dashboard_cards()  # type: ignore[attr-defined]
