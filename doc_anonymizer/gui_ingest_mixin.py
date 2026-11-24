# Commandes pip à exécuter : Aucune dépendance externe requise

import ctypes
import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, List, Optional, Tuple


class GuiIngestMixin:
    """Glisser-déposer Windows/TkDnD, référencement et pré-tri silencieux."""

    controller: Any
    current_ini_var: tk.StringVar
    status_var: tk.StringVar

    def _enable_windows_drag_and_drop(self) -> None:
        """Active le glisser-déposer de fichiers/dossiers sans erreur 64 bits."""
        if hasattr(self, "links_tree"):
            try:
                self.links_tree.drop_target_register("DND_Files")  # type: ignore[attr-defined]
                self.links_tree.dnd_bind("<<Drop>>", self._on_tkdnd_drop)  # type: ignore[attr-defined]
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
            set_win_long = getattr(
                user32, "SetWindowLongPtrW", user32.SetWindowLongW
            )
            set_win_long.argtypes = [
                ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p
            ]
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
                    count: int = shell32.DragQueryFileW(
                        w_param, 0xFFFFFFFF, None, 0
                    )
                    dropped: List[str] = []
                    for idx in range(count):
                        ln: int = (
                            shell32.DragQueryFileW(w_param, idx, None, 0) + 1
                        )
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
            messagebox.showwarning(
                "Dossier requis", "Veuillez d'abord ouvrir ou créer un dossier."
            )
            return
        folder: str = self.controller.resolve_workspace_paths(ini_path)[key]
        os.makedirs(folder, exist_ok=True)
        self._open_path_in_os(folder)
    def _get_selected_linked_index(self) -> Optional[int]:
        if not hasattr(self, "links_tree"):
            return None
        sel = self.links_tree.selection()  # type: ignore[attr-defined]
        if not sel:
            return None
        iid: str = str(next(iter(sel)))
        return int(iid) if iid.isdigit() else None

    def _open_selected_linked_source(self) -> None:
        ini_path: str = self.current_ini_var.get()
        idx: Optional[int] = self._get_selected_linked_index()
        if not ini_path or idx is None:
            return
        links = self.controller.list_linked_sources(ini_path)
        if 0 <= idx < len(links):
            target_p: str = links[idx]["path"]
            folder_to_open: str = (
                target_p
                if os.path.isdir(target_p)
                else os.path.dirname(target_p)
            )
            self._open_path_in_os(folder_to_open)

    def _set_docs_busy(self, active: bool, message: str = "") -> None:
        if not hasattr(self, "docs_busy_frame"):
            return
        if active:
            self.docs_busy_var.set(message or "Analyse en cours...")  # type: ignore[attr-defined]
            self.docs_busy_frame.pack(fill="x", pady=(0, 6))  # type: ignore[attr-defined]
            self.docs_busy_bar.start(12)  # type: ignore[attr-defined]
            self.status_var.set(self.docs_busy_var.get())
        else:
            self.docs_busy_bar.stop()  # type: ignore[attr-defined]
            self.docs_busy_frame.pack_forget()  # type: ignore[attr-defined]

    def _run_docs_task(
        self, message: str, worker_fn: Any, on_done_fn: Any
    ) -> None:
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

    def _run_step1_scan_worker(self, ini_path: str) -> Tuple[int, int, List[Any]]:
        lock = getattr(self, "_prewarm_lock", None)
        if lock is None:
            lock = threading.Lock()
            self._prewarm_lock = lock
        with lock:
            moved_c, moved_s = self.controller.auto_organize_dropped_files(
                ini_path
            )
            dups = self.controller.load_duplicate_file_items(ini_path)
            self._prewarm_cache_result = (ini_path, moved_c, moved_s, dups)
            return moved_c, moved_s, dups

    def _trigger_silent_prewarm(self) -> None:
        """Pré-analyse silencieusement contacts, SMS, chats et doublons."""
        ini_path: str = self.current_ini_var.get()
        if not ini_path or getattr(self, "_closing", False):
            return
        if getattr(self, "_sync_docs_tasks", False):
            self._run_step1_scan_worker(ini_path)
            return
        in_flight: Optional[threading.Thread] = getattr(
            self, "_prewarm_thread", None
        )
        if in_flight is not None and in_flight.is_alive():
            self._prewarm_dirty = True
            return
        self._prewarm_dirty = False

        def _bg_prewarm() -> None:
            while not getattr(self, "_closing", False):
                self._prewarm_dirty = False
                cur_ini: str = self.current_ini_var.get()
                if not cur_ini:
                    break
                self._run_step1_scan_worker(cur_ini)
                if not getattr(self, "_prewarm_dirty", False):
                    break
            if not getattr(self, "_closing", False) and hasattr(self, "after"):
                self.after(0, self._refresh_workspace_counters)  # type: ignore[attr-defined]

        t = threading.Thread(target=_bg_prewarm, daemon=True)
        self._prewarm_thread = t
        t.start()
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
                "Voulez-vous les COPIER dans le dossier interne de l'affaire "
                "(recommandé si vous débranchez le support) ?\n\n"
                "• Oui = Copier dans le dossier de l'affaire\n"
                "• Non = Garder uniquement un lien (lecture seule, aucune copie)",
            )

        def _work() -> Any:
            return self.controller.register_or_copy_sources(
                ini_path, chosen, copy_external=copy_ext
            )

        def _done(res: Any) -> None:
            added_links, copied_local = res
            self._refresh_workspace_counters()  # type: ignore[attr-defined]
            self.status_var.set(
                f"{added_links} référence(s) ajoutée(s) en lecture seule, "
                f"{copied_local} copie(s) effectuée(s)."
            )
            self._trigger_silent_prewarm()

        self._run_docs_task(
            "Ajout des références en cours...", _work, _done
        )

    def _link_external_files(self) -> None:
        if self.current_ini_var.get():
            files = filedialog.askopenfilenames(
                title="Référencer des fichiers (lecture seule, sans copie)"
            )
            if files:
                self._ingest_selected_paths(list(files))

    def _link_external_folder(self) -> None:
        if self.current_ini_var.get():
            folder = filedialog.askdirectory(
                title="Référencer un dossier entier (lecture seule, sans copie)"
            )
            if folder:
                self._ingest_selected_paths([folder])

    def _remove_selected_linked_source(self) -> None:
        ini_path: str = self.current_ini_var.get()
        idx: Optional[int] = self._get_selected_linked_index()
        if not ini_path or idx is None:
            return
        links = self.controller.list_linked_sources(ini_path)
        if 0 <= idx < len(links):
            self.controller.remove_linked_source(ini_path, links[idx]["path"])
            self._refresh_workspace_counters()  # type: ignore[attr-defined]
            self.status_var.set(
                "Référence supprimée (les fichiers d'origine n'ont pas été touchés)."
            )
            self._trigger_silent_prewarm()

    def _advance_from_documents(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return

        def _work() -> Any:
            return self._run_step1_scan_worker(ini_path)

        def _done(res: Any) -> None:
            moved_contacts, moved_sms, dups = res
            self._refresh_workspace_counters()  # type: ignore[attr-defined]
            if moved_contacts or moved_sms:
                self.status_var.set(
                    f"Classement automatique : {moved_contacts} carnet(s), "
                    f"{moved_sms} export(s) SMS."
                )
            if dups:
                self.duplicate_filter_items = dups  # type: ignore[attr-defined]
                self._show_page("duplicates")  # type: ignore[attr-defined]
            else:
                self._show_page("setup")  # type: ignore[attr-defined]

        in_flight: Optional[threading.Thread] = getattr(
            self, "_prewarm_thread", None
        )
        if in_flight is not None and in_flight.is_alive():
            self._run_docs_task(
                "Finalisation de la vérification déjà démarrée...",
                _work,
                _done,
            )
        else:
            _done(_work())
