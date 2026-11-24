# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Any, List
from doc_anonymizer.gui_ingest_mixin import GuiIngestMixin


class GuiRunnerMixin(GuiIngestMixin):
    """Exécution des traitements en arrière-plan, suivi de progression et compteurs."""

    PROGRESS_LINE_RE = re.compile(r"^\[(\d+)/(\d+)\]\s*Extrait\s*:\s*(.+)$")

    controller: Any
    current_ini_var: tk.StringVar
    status_var: tk.StringVar
    workflow_mode: str
    is_running: bool
    current_proc: Any
    log_visible: bool

    def _open_sms_exports_folder(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if ini_path:
            sms_dir: str = os.path.join(
                self.controller.resolve_workspace_paths(ini_path)["sources_dir"],
                "sms_exports",
            )
            os.makedirs(sms_dir, exist_ok=True)
            self._open_path_in_os(sms_dir)

    def _open_chat_exports_folder(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if ini_path:
            chat_dir: str = os.path.join(
                self.controller.resolve_workspace_paths(ini_path)["sources_dir"],
                "chat_exports",
            )
            os.makedirs(chat_dir, exist_ok=True)
            self._open_path_in_os(chat_dir)

    def _toggle_log_panel(self) -> None:
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log_text.pack(fill="both", expand=True, pady=(0, 8))  # type: ignore[attr-defined]
        else:
            self.log_text.pack_forget()  # type: ignore[attr-defined]

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")  # type: ignore[attr-defined]
        self.log_text.insert("end", line + "\n")  # type: ignore[attr-defined]
        self.log_text.see("end")  # type: ignore[attr-defined]
        self.log_text.configure(state="disabled")  # type: ignore[attr-defined]
        m = self.PROGRESS_LINE_RE.match(line.strip())
        if m and hasattr(self, "progress"):
            cur_i, tot_i, fname = int(m.group(1)), max(1, int(m.group(2))), m.group(3).strip()
            pct: float = min(100.0, (cur_i / tot_i) * 100.0)
            self.progress.stop()  # type: ignore[attr-defined]
            self.progress.configure(mode="determinate", maximum=100.0, value=pct)  # type: ignore[attr-defined]
            if hasattr(self, "run_progress_label_var"):
                self.run_progress_label_var.set(f"{int(round(pct))} % ({cur_i}/{tot_i}) — {fname}")  # type: ignore[attr-defined]
    def _refresh_dashboard_cards(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        stats = self.controller.load_dashboard_stats(ini_path)
        docs_val: int = int(stats.get("documents_traites", stats.get("documents_extraits", 0)))
        self.stat_vars["docs"].set(str(docs_val))  # type: ignore[attr-defined]
        self.stat_vars["names"].set(str(stats.get("noms_masques", 0)))  # type: ignore[attr-defined]
        self.stat_vars["coords"].set(str(stats.get("coordonnees_masquees", 0)))  # type: ignore[attr-defined]
        self.stat_vars["ids"].set(str(stats.get("identifiants_masques", 0)))  # type: ignore[attr-defined]
        self.stat_vars["locs"].set(str(stats.get("lieux_dates_masques", 0)))  # type: ignore[attr-defined]
        zips = self.controller.detect_zip_files(ini_path)
        if zips:
            self.dash_zip_var.set(  # type: ignore[attr-defined]
                f"ATTENTION : {len(zips)} archive(s) .zip détectée(s) "
                f"({', '.join(os.path.basename(z) for z in zips[:3])}). "
                "Décompressez-les pour que leur contenu soit traité."
            )
            self.lbl_dash_zip.pack(anchor="w", fill="x", pady=(0, 6))  # type: ignore[attr-defined]
        else:
            self.lbl_dash_zip.pack_forget()  # type: ignore[attr-defined]
        if self.workflow_mode == "lawyer":
            self.btn_main_run.configure(text="Lancer l'extraction et le classement nominatif")  # type: ignore[attr-defined]
            self.btn_fast_reanon.pack_forget()  # type: ignore[attr-defined]
            self.btn_after_run_next.configure(text="Étape suivante : Pack Avocat Nominatif ->")  # type: ignore[attr-defined]
        else:
            self.btn_main_run.configure(text="Lancer l'extraction et l'anonymisation")  # type: ignore[attr-defined]
            self.btn_fast_reanon.pack(side="left", padx=(0, 8))  # type: ignore[attr-defined]
            self.btn_after_run_next.configure(text="Étape suivante : Vérifier les noms ->")  # type: ignore[attr-defined]

    def _start_primary_workflow_job(self) -> None:
        self._start_job(
            "extract_only" if self.workflow_mode == "lawyer" else "full_with_contacts",
            go_export_after=(self.workflow_mode == "lawyer"),
        )

    def _go_to_step_after_run(self) -> None:
        self._show_page("export" if self.workflow_mode == "lawyer" else "audit")  # type: ignore[attr-defined]

    def _refresh_workspace_counters(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        paths = self.controller.resolve_workspace_paths(ini_path)
        src_dir: str = paths["sources_dir"]
        sms_dir: str = os.path.abspath(os.path.join(src_dir, "sms_exports"))
        chat_dir: str = os.path.abspath(os.path.join(src_dir, "chat_exports"))
        c_dir: str = paths["input_contacts_dir"]

        raw_docs_count = sms_count = chats_count = 0
        if os.path.isdir(src_dir):
            for root_p, _, files in os.walk(src_dir):
                visible_cnt: int = sum(1 for fn in files if not fn.startswith("."))
                abs_r: str = os.path.abspath(root_p)
                if abs_r.startswith(sms_dir):
                    sms_count += visible_cnt
                elif abs_r.startswith(chat_dir):
                    chats_count += visible_cnt
                else:
                    raw_docs_count += visible_cnt

        linked_files, missing_links = self.controller.expand_linked_files(ini_path)
        linked_count: int = len(linked_files)
        if hasattr(self, "links_tree"):
            for iid in self.links_tree.get_children():  # type: ignore[attr-defined]
                self.links_tree.delete(iid)  # type: ignore[attr-defined]
            self.links_tree.tag_configure("ok", background="#ecfdf5", foreground="#065f46")  # type: ignore[attr-defined]
            self.links_tree.tag_configure("missing", background="#fef2f2", foreground="#991b1b")  # type: ignore[attr-defined]
            for idx, it in enumerate(self.controller.list_linked_sources(ini_path)):
                full_p: str = str(it.get("path") or "")
                exists: bool = os.path.exists(full_p)
                status_tag: str = "✓ Actif" if exists else "✕ Déconnecté"
                base_n: str = os.path.basename(full_p.rstrip("\\/")) or full_p
                self.links_tree.insert(  # type: ignore[attr-defined]
                    "",
                    "end",
                    iid=str(idx),
                    values=(status_tag, str(it.get("storage") or "Local"), base_n, full_p),
                    tags=("ok" if exists else "missing",),
                )
        c_files: List[str] = (
            sorted(fn for fn in os.listdir(c_dir) if not fn.startswith(".") and fn.lower().endswith((".csv", ".vcf")))
            if os.path.isdir(c_dir) else []
        )
        contacts_count: int = len(c_files)
        total_count: int = raw_docs_count + sms_count + chats_count + contacts_count + linked_count
        missing_note: str = f" • {len(missing_links)} support(s) débranché(s)" if missing_links else ""
        self.docs_summary_var.set(  # type: ignore[attr-defined]
            f"Pièces de l'affaire : {total_count} fichier(s) ({raw_docs_count} interne(s), {linked_count} référencé(s), "
            f"{contacts_count} carnet(s), {sms_count} SMS, {chats_count} chat(s){missing_note})."
        )

        zips = self.controller.detect_zip_files(ini_path)
        if zips:
            self.zip_warning_var.set(  # type: ignore[attr-defined]
                f"ATTENTION — ARCHIVE .ZIP DÉTECTÉE : {', '.join(os.path.basename(z) for z in zips[:4])}.\n"
                "Par sécurité, les archives .zip ne sont jamais décompressées automatiquement. "
                "Veuillez faire un clic droit -> Extraire tout avant de continuer."
            )
            self.lbl_dash_zip_warn = getattr(self, "lbl_zip_warning", None)
            if self.lbl_dash_zip_warn is not None:
                self.lbl_dash_zip_warn.pack(anchor="w", fill="x", pady=(8, 0))
        elif hasattr(self, "lbl_zip_warning"):
            self.lbl_zip_warning.pack_forget()  # type: ignore[attr-defined]

    def _set_buttons_state(self, enabled: bool) -> None:
        from doc_anonymizer.gui_widgets import set_button_enabled_style

        set_button_enabled_style(self.btn_main_run, enabled, active_variant="primary")  # type: ignore[attr-defined]
        set_button_enabled_style(self.btn_fast_reanon, enabled, active_variant="secondary")  # type: ignore[attr-defined]
        set_button_enabled_style(self.btn_stop, not enabled, active_variant="danger")  # type: ignore[attr-defined]

    def _stop_current_job(self) -> None:
        if self.current_proc and self.current_proc.poll() is None:
            self.current_proc.terminate()
            self.status_var.set("Arrêt demandé par l'utilisateur...")

    def _start_job(self, mode: str, go_export_after: bool = False) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            messagebox.showwarning("Dossier requis", "Veuillez d'abord ouvrir ou créer un dossier à l'étape 0.")
            return
        if self.is_running:
            return
        self.controller.auto_organize_dropped_files(ini_path)
        self.is_running = True
        self._set_buttons_state(False)
        self.progress.configure(mode="indeterminate", value=0)  # type: ignore[attr-defined]
        self.progress.start()  # type: ignore[attr-defined]
        if hasattr(self, "run_progress_label_var"):
            self.run_progress_label_var.set("Analyse et extraction en cours...")  # type: ignore[attr-defined]
        self._show_page("run")  # type: ignore[attr-defined]
        self.status_var.set("Traitement en cours, veuillez patienter...")
        cmds: List[List[str]] = [self.controller.build_cli_command(ini_path, mode)]

        def _safe_ui_call(fn: Any, *args: Any) -> None:
            if not getattr(self, "_closing", False):
                try:
                    self.after(0, fn, *args)  # type: ignore[attr-defined]
                except tk.TclError:
                    pass

        def _worker() -> None:
            env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
            creation_flags: int = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            ret: int = 0
            for cmd in cmds:
                if getattr(self, "_closing", False):
                    break
                _safe_ui_call(self._append_log, f"\n>>> Lancement : {' '.join(cmd)}")
                proc = subprocess.Popen(
                    cmd, cwd=self.controller.root_dir, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=creation_flags,
                )
                self.current_proc = proc
                if proc.stdout:
                    for raw_ln in proc.stdout:
                        if getattr(self, "_closing", False):
                            break
                        if raw_ln.strip():
                            _safe_ui_call(self._append_log, raw_ln.rstrip("\r\n"))
                ret = proc.wait()
                self.current_proc = None
                if ret != 0 or getattr(self, "_closing", False):
                    break
            _safe_ui_call(self._on_job_finished, ret, mode, go_export_after)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_job_finished(self, return_code: int, mode: str, go_export_after: bool = False) -> None:
        if getattr(self, "_closing", False):
            return
        self.progress.stop()  # type: ignore[attr-defined]
        self.progress.configure(mode="determinate", value=100.0 if return_code == 0 else 0.0)  # type: ignore[attr-defined]
        if hasattr(self, "run_progress_label_var"):
            self.run_progress_label_var.set("100 % — Traitement terminé." if return_code == 0 else "Traitement interrompu.")  # type: ignore[attr-defined]
        self.is_running = False
        self._set_buttons_state(True)
        self._refresh_audit_list()  # type: ignore[attr-defined]
        self._refresh_dashboard_cards()
        if return_code == 0:
            self.status_var.set("Traitement terminé avec succès.")
            if go_export_after or mode == "extract_only":
                self._show_page("export")  # type: ignore[attr-defined]
            elif mode in {"full", "full_with_contacts", "anonymize_only", "reset_anonymize_only"}:
                cands = self.controller.load_audit_candidates(self.current_ini_var.get())
                self._show_page("audit" if cands else "export")  # type: ignore[attr-defined]
        else:
            self.status_var.set(f"Le traitement s'est arrêté (code {return_code}).")
