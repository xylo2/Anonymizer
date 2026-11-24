# Commandes pip à exécuter : Aucune dépendance externe requise

import ctypes
import os
import re
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, List


class GuiRunnerMixin:
    """Glisser-déposer, dépôt de pièces, exécution des traitements et suivi."""

    PROGRESS_LINE_RE = re.compile(r"^\[(\d+)/(\d+)\]\s*Extrait\s*:\s*(.+)$")

    controller: Any
    current_ini_var: tk.StringVar
    status_var: tk.StringVar
    workflow_mode: str
    is_running: bool
    current_proc: Any
    log_visible: bool

    def _enable_windows_drag_and_drop(self) -> None:
        """Active le glisser-déposer de fichiers/dossiers sans erreur 64 bits."""
        if hasattr(self, "links_listbox"):
            try:
                self.links_listbox.drop_target_register("DND_Files")  # type: ignore[attr-defined]
                self.links_listbox.dnd_bind("<<Drop>>", self._on_tkdnd_drop)  # type: ignore[attr-defined]
                return
            except Exception:
                pass
        if os.name != "nt":
            return
        try:
            self.update_idletasks()  # type: ignore[attr-defined]
            hwnd: int = int(self.winfo_id())  # type: ignore[attr-defined]
            shell32 = ctypes.windll.shell32
            user32 = ctypes.windll.user32
            shell32.DragAcceptFiles(ctypes.c_void_p(hwnd), True)
            WNDPROC = ctypes.WINFUNCTYPE(
                ctypes.c_longlong, ctypes.c_void_p, ctypes.c_uint,
                ctypes.c_void_p, ctypes.c_void_p,
            )
            set_win_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
            set_win_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            set_win_long.restype = ctypes.c_void_p
            call_win_proc = user32.CallWindowProcW
            call_win_proc.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                ctypes.c_void_p, ctypes.c_void_p,
            ]
            call_win_proc.restype = ctypes.c_longlong
            old_proc = set_win_long(ctypes.c_void_p(hwnd), -4, None)
            set_win_long(ctypes.c_void_p(hwnd), -4, old_proc)

            def _wnd_proc(h: Any, msg: int, w_param: Any, l_param: Any) -> int:
                if msg == 0x0233 and w_param:
                    count: int = shell32.DragQueryFileW(w_param, 0xFFFFFFFF, None, 0)
                    dropped: List[str] = []
                    for idx in range(count):
                        ln: int = shell32.DragQueryFileW(w_param, idx, None, 0) + 1
                        buf = ctypes.create_unicode_buffer(ln)
                        shell32.DragQueryFileW(w_param, idx, buf, ln)
                        if buf.value:
                            dropped.append(buf.value)
                    shell32.DragFinish(w_param)
                    if dropped and hasattr(self, "after"):
                        self.after(0, self._handle_dropped_paths, dropped)  # type: ignore[attr-defined]
                    return 0
                return int(call_win_proc(old_proc, h, msg, w_param, l_param))

            self._win_dnd_proc_ref = WNDPROC(_wnd_proc)
            set_win_long(ctypes.c_void_p(hwnd), -4, self._win_dnd_proc_ref)
        except Exception:
            pass

    def _on_tkdnd_drop(self, event: Any) -> None:
        raw: str = str(getattr(event, "data", "") or "").strip()
        if raw:
            paths = list(self.tk.splitlist(raw))  # type: ignore[attr-defined]
            if paths:
                self._ingest_selected_paths(paths)

    def _handle_dropped_paths(self, dropped: List[str]) -> None:
        if dropped:
            self._ingest_selected_paths(dropped)

    @staticmethod
    def _open_path_in_os(target_path: str) -> None:
        if not target_path or not os.path.exists(target_path):
            return
        if os.name == "nt":
            os.startfile(target_path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", target_path])

    def _open_workspace_folder(self, key: str) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path or not os.path.isfile(ini_path):
            messagebox.showwarning("Dossier requis", "Veuillez d'abord ouvrir ou créer un dossier.")
            return
        folder: str = self.controller.resolve_workspace_paths(ini_path)[key]
        os.makedirs(folder, exist_ok=True)
        self._open_path_in_os(folder)

    def _open_selected_linked_source(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path or not hasattr(self, "links_listbox"):
            return
        sel = self.links_listbox.curselection()  # type: ignore[attr-defined]
        if not sel:
            return
        idx: int = int(next(iter(sel)))
        links = self.controller.list_linked_sources(ini_path)
        if 0 <= idx < len(links):
            target_p: str = links[idx]["path"]
            folder_to_open: str = target_p if os.path.isdir(target_p) else os.path.dirname(target_p)
            self._open_path_in_os(folder_to_open)
    def _set_docs_busy(self, active: bool, message: str = "") -> None:
        if not hasattr(self, "docs_busy_frame"):
            return
        if active:
            self.docs_busy_var.set(message or "Analyse des emplacements sélectionnés en cours...")  # type: ignore[attr-defined]
            self.docs_busy_frame.pack(fill="x", pady=(0, 6))  # type: ignore[attr-defined]
            self.docs_busy_bar.start(12)  # type: ignore[attr-defined]
            self.status_var.set(self.docs_busy_var.get())  # type: ignore[attr-defined]
        else:
            self.docs_busy_bar.stop()  # type: ignore[attr-defined]
            self.docs_busy_frame.pack_forget()  # type: ignore[attr-defined]

    def _run_docs_task(self, message: str, worker_fn: Any, on_done_fn: Any) -> None:
        if getattr(self, "_sync_docs_tasks", False):
            res = worker_fn()
            on_done_fn(res)
            return
        self._set_docs_busy(True, message)

        def _bg() -> None:
            res = worker_fn()
            if not getattr(self, "_closing", False) and hasattr(self, "after"):
                def _ui() -> None:
                    self._set_docs_busy(False)
                    on_done_fn(res)
                self.after(0, _ui)  # type: ignore[attr-defined]

        threading.Thread(target=_bg, daemon=True).start()

    def _ingest_selected_paths(self, chosen: List[str]) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path or not chosen:
            return
        external_items: List[str] = []
        for p in chosen:
            is_ext, lbl = self.controller.inspect_storage_location(ini_path, p)
            if is_ext:
                external_items.append(f"• {os.path.basename(p) or p} ({lbl})")
        copy_ext: bool = False
        if external_items:
            preview_ext: str = "\n".join(external_items[:5])
            copy_ext = messagebox.askyesno(
                "Support externe détecté (clé USB / disque externe)",
                f"Les éléments suivants sont sur un support externe :\n{preview_ext}\n\n"
                "Voulez-vous les COPIER dans le dossier interne de l'affaire (recommandé si vous débranchez le support) ?\n\n"
                "• Oui = Copier dans le dossier de l'affaire\n"
                "• Non = Garder uniquement un lien (lecture seule, aucune copie)",
            )

        def _work() -> Any:
            return self.controller.register_or_copy_sources(ini_path, chosen, copy_external=copy_ext)

        def _done(res: Any) -> None:
            added_links, copied_local = res
            self._refresh_workspace_counters()
            self.status_var.set(f"{added_links} référence(s) ajoutée(s) en lecture seule, {copied_local} copie(s) effectuée(s).")

        self._run_docs_task("Indexation et classement automatique des pièces en cours...", _work, _done)

    def _link_external_files(self) -> None:
        if self.current_ini_var.get():
            files = filedialog.askopenfilenames(title="Référencer des fichiers (lecture seule, sans copie)")
            if files:
                self._ingest_selected_paths(list(files))

    def _link_external_folder(self) -> None:
        if self.current_ini_var.get():
            folder = filedialog.askdirectory(title="Référencer un dossier entier (lecture seule, sans copie)")
            if folder:
                self._ingest_selected_paths([folder])

    def _remove_selected_linked_source(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path or not hasattr(self, "links_listbox"):
            return
        sel = self.links_listbox.curselection()  # type: ignore[attr-defined]
        if not sel:
            return
        idx: int = int(next(iter(sel)))
        links = self.controller.list_linked_sources(ini_path)
        if 0 <= idx < len(links):
            self.controller.remove_linked_source(ini_path, links[idx]["path"])
            self._refresh_workspace_counters()
            self.status_var.set("Référence supprimée (les fichiers d'origine n'ont pas été touchés).")

    def _advance_from_documents(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return

        def _work() -> Any:
            moved_c, moved_s = self.controller.auto_organize_dropped_files(ini_path)
            dups = self.controller.load_duplicate_file_items(ini_path)
            return moved_c, moved_s, dups

        def _done(res: Any) -> None:
            moved_contacts, moved_sms, dups = res
            self._refresh_workspace_counters()
            if moved_contacts or moved_sms:
                self.status_var.set(f"Classement automatique : {moved_contacts} carnet(s), {moved_sms} export(s) SMS.")
            if dups:
                self.duplicate_filter_items = dups  # type: ignore[attr-defined]
                self._show_page("duplicates")  # type: ignore[attr-defined]
            else:
                self._show_page("setup")  # type: ignore[attr-defined]

        self._run_docs_task("Vérification des doublons et classement automatique en cours...", _work, _done)
    def _open_sms_exports_folder(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if ini_path:
            sms_dir: str = os.path.join(self.controller.resolve_workspace_paths(ini_path)["sources_dir"], "sms_exports")
            os.makedirs(sms_dir, exist_ok=True)
            self._open_path_in_os(sms_dir)

    def _open_chat_exports_folder(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if ini_path:
            chat_dir: str = os.path.join(self.controller.resolve_workspace_paths(ini_path)["sources_dir"], "chat_exports")
            os.makedirs(chat_dir, exist_ok=True)
            self._open_path_in_os(chat_dir)

    def _toggle_log_panel(self) -> None:
        self.log_visible = not self.log_visible
        self.log_text.pack(fill="both", expand=True, pady=(0, 8)) if self.log_visible else self.log_text.pack_forget()  # type: ignore[attr-defined]

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
            self.dash_zip_var.set(f"ATTENTION : {len(zips)} archive(s) .zip détectée(s) ({', '.join(os.path.basename(z) for z in zips[:3])}). Décompressez-les pour que leur contenu soit traité.")  # type: ignore[attr-defined]
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
        self._start_job("extract_only" if self.workflow_mode == "lawyer" else "full_with_contacts", go_export_after=(self.workflow_mode == "lawyer"))  # type: ignore[attr-defined]

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
        if hasattr(self, "links_listbox"):
            self.links_listbox.delete(0, "end")  # type: ignore[attr-defined]
            for it in self.controller.list_linked_sources(ini_path):
                status_tag: str = "OK" if os.path.exists(it["path"]) else "DÉCONNECTÉ"
                self.links_listbox.insert("end", f"[{status_tag} • {it['storage']}] {it['path']}")  # type: ignore[attr-defined]

        c_files: List[str] = sorted(fn for fn in os.listdir(c_dir) if not fn.startswith(".") and fn.lower().endswith((".csv", ".vcf"))) if os.path.isdir(c_dir) else []
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
            self.lbl_zip_warning.pack(anchor="w", fill="x", pady=(8, 0))  # type: ignore[attr-defined]
        else:
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
                proc = subprocess.Popen(cmd, cwd=self.controller.root_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=creation_flags)
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
