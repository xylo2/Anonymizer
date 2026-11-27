# -*- coding: utf-8 -*-
"""
Interface graphique principale d'AnonVault — Pièces protégées.

License: GNU GPL v3
"""
import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer import gui_widgets as _gw
from doc_anonymizer.gui_audit_export_mixin import GuiAuditExportMixin
from doc_anonymizer.gui_controller import AnonymizerGuiController
from doc_anonymizer.gui_dialogs import ExportGuideDialog
from doc_anonymizer.gui_navigation_mixin import GuiNavigationMixin
from doc_anonymizer.gui_pages import GuiPagesMixin
from doc_anonymizer.gui_runner_mixin import GuiRunnerMixin
from doc_anonymizer.gui_startup_error import (
    run_with_optional_error_dialog as _run_with_optional_error_dialog,
    show_startup_error_dialog as _show_startup_error_dialog,
)
from doc_anonymizer.gui_tables_mixin import GuiTablesMixin
from doc_anonymizer.gui_widgets import (
    HAS_CTK,
    UI_COLORS,
    configure_ttk_styles,
    ctk,
    load_saved_ui_font_scale,
    set_screen_reader_mode,
    set_ui_font_scale,
)
from doc_anonymizer.workspace_settings_dialog import WorkspaceSettingsDialog

_ENV_SR: str = os.environ.get("ANONYMIZER_SCREEN_READER", "").strip().lower()
if "--screen-reader" in sys.argv or _ENV_SR in {"1", "true", "yes"}:
    set_screen_reader_mode(True)

_BaseTkWindow: Any = (
    tk.Tk
    if _gw.SCREEN_READER_MODE
    else (ctk.CTk if (HAS_CTK and ctk is not None) else tk.Tk)
)
class AnonymizerGuiApp(
    GuiNavigationMixin,
    GuiPagesMixin,
    GuiTablesMixin,
    GuiRunnerMixin,
    GuiAuditExportMixin,
    _BaseTkWindow,
):
    """Fenêtre principale moderne et accessible (clavier, zoom et lecteur d'écran)."""

    def __init__(self, skip_startup_gate: bool = False) -> None:
        """Initialise la fenêtre principale en plein écran et construit les écrans."""
        super().__init__()
        self.title("AnonVault — Pièces protégées")
        self._apply_window_icon()
        scr_w: int = self.winfo_screenwidth()
        scr_h: int = self.winfo_screenheight()
        win_w: int = min(1180, max(980, scr_w - 60))
        win_h: int = min(820, max(680, scr_h - 80))
        pos_x: int = max(0, (scr_w - win_w) // 2)
        pos_y: int = max(0, (scr_h - win_h) // 2)
        self.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.minsize(960, 660)
        self._maximized_once: bool = False
        if HAS_CTK and ctk is not None and not _gw.SCREEN_READER_MODE:
            self.configure(fg_color=UI_COLORS["bg"])
        else:
            self.configure(bg=UI_COLORS["bg"])
        self.controller: AnonymizerGuiController = AnonymizerGuiController(
            ROOT_DIR
        )
        self._ui_prefs_file: str = os.path.join(
            self.controller.workspaces_base_dir, ".ui_preferences.json"
        )
        load_saved_ui_font_scale(self._ui_prefs_file)
        self.workspaces: List[Tuple[str, str]] = []
        self.workflow_mode: str = "ia"
        self.current_ini_var: tk.StringVar = tk.StringVar()
        self.active_ws_badge_var: tk.StringVar = tk.StringVar(
            value="Dossier : aucun"
        )
        self.mode_badge_var: tk.StringVar = tk.StringVar(
            value="Objectif : IA (Anonymisé)"
        )
        self.new_ws_name_var: tk.StringVar = tk.StringVar()
        self.status_var: tk.StringVar = tk.StringVar(
            value="Prêt — Navigation clavier (Tab / Entrée / Ctrl+F / Alt+Flèches) "
            "& Lecteur d'écran disponibles."
        )
        self.is_running: bool = False
        self._closing: bool = False
        self.current_proc: Optional[subprocess.Popen] = None
        self.pages: Dict[str, Any] = {}
        self.nav_buttons: Dict[str, Any] = {}
        self.active_page_key: str = "gate"
        self.log_visible: bool = False
        self.contact_filter_items: List[Dict[str, Any]] = []
        self.sms_filter_items: List[Dict[str, Any]] = []
        self.chat_filter_items: List[Dict[str, Any]] = []
        self.deanon_files: List[str] = []
        self.deanon_proposals: List[Dict[str, Any]] = []
        self.contact_sort_col: str = "alias"
        self.contact_sort_reverse: bool = False
        self.sms_sort_col: str = "count"
        self.sms_sort_reverse: bool = True
        self.chat_sort_col: str = "count"
        self.chat_sort_reverse: bool = True
        self.relaunch_screen_reader: Optional[bool] = None
        self._last_focus_refresh_ts: float = 0.0
        configure_ttk_styles(self)
        self._bind_global_shortcuts()
        self._build_layout()
        self._bind_gate_return_keys()
        self._refresh_workspaces()
        if skip_startup_gate and self.workspaces:
            _, first_ini = next(iter(self.workspaces))
            self._refresh_workspaces(select_ini=first_ini)
            self._set_workflow_mode("ia", navigate=True)
        else:
            self._show_page("gate")
        self.after(80, self._maximize_main_window)
        self.after(200, self._enable_windows_drag_and_drop)

    def _maximize_main_window(self) -> None:
        """Passe la fenêtre principale en mode maximisé une seule fois au démarrage."""
        if self._closing or getattr(self, "_maximized_once", False):
            return
        self._maximized_once = True
        try:
            self.wm_state("zoomed")
            return
        except tk.TclError:
            pass
        try:
            self.wm_attributes("-zoomed", True)
            return
        except tk.TclError:
            pass
        try:
            screen_w: int = max(960, int(self.winfo_screenwidth()))
            screen_h: int = max(660, int(self.winfo_screenheight()))
            self.geometry(f"{screen_w}x{screen_h}+0+0")
        except tk.TclError:
            pass

    def _bind_global_shortcuts(self) -> None:
        """Associe les raccourcis clavier globaux de l'application."""
        self.protocol("WM_DELETE_WINDOW", self._on_close_requested)
        self.bind("<FocusIn>", self._on_window_focus_in)
        self.bind_all("<Control-f>", self._focus_contact_search)
        self.bind_all("<Control-F>", self._focus_contact_search)
        self.bind_all("<Control-plus>", lambda _e: self._adjust_font_scale(0.1))
        self.bind_all("<Control-equal>", lambda _e: self._adjust_font_scale(0.1))
        self.bind_all("<Control-minus>", lambda _e: self._adjust_font_scale(-0.1))
        self.bind_all("<Control-0>", lambda _e: self._reset_font_scale())
        self.bind_all("<Escape>", self._clear_active_search)
        self.bind_all("<Alt-Left>", lambda _e: self._step_page(-1))
        self.bind_all("<Alt-Right>", lambda _e: self._step_page(1))
    def _bind_gate_return_keys(self) -> None:
        """Permet de valider l'écran d'accueil avec la touche Entrée."""
        for attr_name in (
            "entry_gate_new",
            "ent_gate_new",
            "ent_gate_new_name",
            "combo_gate_ws",
        ):
            widget = getattr(self, attr_name, None)
            if widget is not None:
                widget.bind(
                    "<Return>", lambda _e: self._confirm_gate_and_workspace()
                )

    def _apply_window_icon(self) -> None:
        """Génère si besoin et applique l'icône PNG/ICO de la fenêtre."""
        assets_dir: str = os.path.join(ROOT_DIR, "assets")
        png_path: str = os.path.join(assets_dir, "anonvault_icon.png")
        ico_path: str = os.path.join(assets_dir, "anonvault_icon.ico")
        if not os.path.isfile(png_path) or not os.path.isfile(ico_path):
            try:
                from tools.generate_app_icon import AppIconGenerator

                AppIconGenerator.export_icons(output_dir=assets_dir)
            except Exception:
                pass
        if os.path.isfile(png_path):
            try:
                self._app_icon_photo = tk.PhotoImage(file=png_path)
                self.iconphoto(True, self._app_icon_photo)
            except tk.TclError:
                pass
        if os.name == "nt" and os.path.isfile(ico_path):
            try:
                self.iconbitmap(default=ico_path)
            except tk.TclError:
                pass

    def _clear_active_search(self, _event: object = None) -> None:
        """Efface le champ de recherche actif lors de l'appui sur Échap."""
        mapping = {
            "setup": ("ent_contact_search", self._on_contact_search_typed),
            "sms": ("ent_sms_search", self._on_sms_search_typed),
            "chats": ("ent_chat_search", self._on_chat_search_typed),
        }
        pair = mapping.get(self.active_page_key)
        if pair and hasattr(self, next(iter(pair))):
            ent_name, refresh_cb = pair
            getattr(self, ent_name).delete(0, "end")
            refresh_cb()
    def _step_page(self, delta: int) -> None:
        """Navigue vers l'étape précédente ou suivante via Alt+Flèches."""
        ini_p: str = self.current_ini_var.get()
        if not ini_p:
            return
        if self.active_page_key == "documents" and delta > 0:
            self._advance_from_documents()
            return
        if self.active_page_key == "duplicates":
            self._show_page("setup" if delta > 0 else "documents")
            return
        if self.active_page_key == "setup" and delta < 0:
            self._go_back_from_setup()
            return
        order: List[str] = list(self.nav_buttons.keys())
        if self.active_page_key in order:
            idx: int = order.index(self.active_page_key) + delta
            if 0 <= idx < len(order):
                self._show_page(order[idx])

    def _on_window_focus_in(self, event: Any = None) -> None:
        """Rafraîchit les listes lorsque la fenêtre reprend le focus."""
        if event is not None and event.widget is not self:
            return
        if self._closing or self.is_running or not self.current_ini_var.get():
            return
        now: float = time.monotonic()
        if (now - self._last_focus_refresh_ts) < 1.5:
            return
        self._last_focus_refresh_ts = now
        if self.active_page_key == "documents":
            self._refresh_workspace_counters()
        elif self.active_page_key == "setup":
            self._refresh_workspace_counters()
            self._refresh_contact_filter_list()
        elif self.active_page_key == "sms":
            self.controller.auto_organize_dropped_files(
                self.current_ini_var.get()
            )
            self._refresh_sms_number_list()
        elif self.active_page_key == "chats":
            self.controller.auto_organize_dropped_files(
                self.current_ini_var.get()
            )
            self._refresh_chat_filter_list()

    def _focus_contact_search(self, _event: object = None) -> str:
        """Place le curseur dans la barre de recherche de l'écran actif."""
        targets = {
            "setup": "ent_contact_search",
            "sms": "ent_sms_search",
            "chats": "ent_chat_search",
        }
        attr: str = targets.get(self.active_page_key, "")
        if attr and hasattr(self, attr):
            getattr(self, attr).focus_set()
        return "break"
    def _sync_sidebar_width_for_scale(self, scale: float) -> None:
        """Adapte la largeur du menu latéral au facteur de zoom police."""
        if hasattr(self, "sidebar"):
            try:
                self.sidebar.configure(width=int(round(268 * max(1.0, scale))))
            except tk.TclError:
                pass
        if hasattr(self, "nav_container"):
            self._rebuild_sidebar_nav()

    def _adjust_font_scale(self, delta: float) -> None:
        """Augmente ou réduit la taille globale des polices."""
        new_scale: float = set_ui_font_scale(
            _gw.UI_FONT_SCALE + delta, prefs_path=self._ui_prefs_file
        )
        self._sync_sidebar_width_for_scale(new_scale)
        pct: int = int(round(new_scale * 100))
        self.status_var.set(f"Taille du texte ajustée à {pct} %.")

    def _reset_font_scale(self) -> None:
        """Réinitialise la taille globale des polices à 100 %."""
        new_scale: float = set_ui_font_scale(1.0, prefs_path=self._ui_prefs_file)
        self._sync_sidebar_width_for_scale(new_scale)
        self.status_var.set("Taille du texte réinitialisée à 100 %.")

    def _toggle_screen_reader_mode(self) -> None:
        """Redémarre l'interface en activant ou désactivant le mode lecteur d'écran."""
        target_sr: bool = not _gw.SCREEN_READER_MODE
        self._flush_and_cancel_pending_timers()
        cmd: List[str] = [
            sys.executable,
            os.path.abspath(__file__),
            "--gui-errors",
        ]
        if target_sr:
            cmd.append("--screen-reader")
        env = {
            **os.environ,
            "ANONYMIZER_SCREEN_READER": "1" if target_sr else "0",
        }
        subprocess.Popen(cmd, cwd=ROOT_DIR, env=env)
        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)

    def _on_workspace_settings_saved(self, ini_path: str) -> None:
        """Propose de recalculer les lots après modification des réglages."""
        self.status_var.set(
            "Paramètres du dossier enregistrés dans config.ini."
        )
        paths = self.controller.resolve_workspace_paths(ini_path)
        res_dir: str = paths.get("results_dir", "")
        has_existing_lots: bool = os.path.isdir(res_dir) and any(
            entry.startswith(("batch_", "lot_")) for entry in os.listdir(res_dir)
        )
        if has_existing_lots and messagebox.askyesno(
            "Recalculer les lots anonymisés ?",
            "Les paramètres d'anonymisation ont été mis à jour.\n\n"
            "Voulez-vous recalculer immédiatement tous les lots déjà générés "
            "avec ces nouveaux réglages ?",
        ):
            self._start_job("reset_anonymize_only")
    def _open_workspace_settings_dialog(self) -> None:
        """Ouvre la boîte de dialogue des paramètres du dossier actif."""
        ini_path: str = self.current_ini_var.get()
        if not ini_path or not os.path.isfile(ini_path):
            messagebox.showwarning(
                "Dossier requis", "Ouvrez ou créez d'abord un dossier."
            )
            return
        WorkspaceSettingsDialog(
            self,
            ini_path=ini_path,
            on_saved=lambda: self._on_workspace_settings_saved(ini_path),
        )

    def _show_calendar_export_popup(self) -> None:
        """Affiche l'aide d'export sur l'onglet Agenda."""
        ExportGuideDialog(self, initial_tab=0)

    def _open_help_dialog(self, initial_tab: int = 0) -> None:
        """Affiche la fenêtre d'aide sur l'onglet demandé."""
        ExportGuideDialog(self, initial_tab=initial_tab)

    def _show_export_guide_popup(self) -> None:
        """Affiche le guide pas-à-pas d'export des données."""
        ExportGuideDialog(self, initial_tab=0)

    def _flush_and_cancel_pending_timers(self) -> None:
        """Sauvegarde les sélections en attente et annule les timers Tkinter."""
        for timer_attr, flush_fn in (
            ("_contact_save_after_id", self._persist_contact_filter_now),
            ("_sms_save_after_id", self._persist_sms_filter_now),
            ("_chat_save_after_id", self._persist_chat_filter_now),
        ):
            tid = getattr(self, timer_attr, None)
            if tid is not None:
                try:
                    self.after_cancel(tid)
                except Exception:
                    pass
                setattr(self, timer_attr, None)
                try:
                    flush_fn()
                except Exception:
                    pass
        try:
            for after_id in self.tk.call("after", "info"):
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
        except Exception:
            pass

    def destroy(self) -> None:
        """Nettoie les timers avant de détruire la fenêtre principale."""
        self._closing = True
        self._flush_and_cancel_pending_timers()
        try:
            self.tk.eval("proc ttk::ThemeChanged {} {}")
        except Exception:
            pass
        super().destroy()

    def _on_close_requested(self) -> None:
        """Gère la fermeture propre de la fenêtre et l'arrêt du sous-processus."""
        if self._closing:
            return
        if (
            self.is_running
            and self.current_proc
            and self.current_proc.poll() is None
        ):
            if not messagebox.askyesno(
                "Traitement en cours", "Interrompre et fermer ?"
            ):
                return
        self._closing = True
        if self.current_proc is not None and self.current_proc.poll() is None:
            try:
                self.current_proc.terminate()
                self.current_proc.kill()
            except OSError:
                pass
        self._flush_and_cancel_pending_timers()
        try:
            self.quit()
            self.destroy()
        except Exception:
            pass


def show_startup_error_dialog(exc: BaseException, details: str) -> None:
    """Affiche une boîte de dialogue en cas d'erreur critique au démarrage."""
    _show_startup_error_dialog(exc, details, ROOT_DIR)


def _run_app_loop() -> None:
    """Boucle principale relançant la fenêtre en cas de bascule lecteur d'écran."""
    while True:
        app = AnonymizerGuiApp()
        app.mainloop()
        if app.relaunch_screen_reader is None:
            break
        set_screen_reader_mode(app.relaunch_screen_reader)


def run_with_optional_error_dialog(enable_gui_errors: bool = False) -> int:
    """Exécute l'application avec capture optionnelle des exceptions de démarrage."""
    return _run_with_optional_error_dialog(
        _run_app_loop, ROOT_DIR, enable_gui_errors=enable_gui_errors
    )


def main(argv: Optional[List[str]] = None) -> int:
    """Point d'entrée CLI de l'interface graphique AnonVault."""
    args: List[str] = sys.argv[1:] if argv is None else argv
    if "--screen-reader" in args or _ENV_SR in {"1", "true", "yes"}:
        set_screen_reader_mode(True)
    enable_gui_errors: bool = "--gui-errors" in args or os.environ.get(
        "ANONYMIZER_GUI_ERRORS", ""
    ).strip().lower() in {"1", "true", "yes"}
    return run_with_optional_error_dialog(enable_gui_errors=enable_gui_errors)


if __name__ == "__main__":
    sys.exit(main())
