# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional, Set, Tuple

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.gui_controller import AnonymizerGuiController
from doc_anonymizer.gui_dialogs import BeforeAfterPreviewDialog, ExportGuideDialog
from doc_anonymizer.gui_pages import GuiPagesMixin
from doc_anonymizer.gui_widgets import UI_COLORS, configure_ttk_styles, make_styled_button


class AnonymizerGuiApp(GuiPagesMixin, tk.Tk):
    """Interface graphique légère orchestrant les écrans, dialogues et traitements locaux."""

    def __init__(self, skip_startup_gate: bool = False) -> None:
        super().__init__()
        self.title("Anonymiseur Local & Préparation de Dossiers Confidentiels")
        self.geometry("1120x800")
        self.minsize(940, 680)
        self.configure(bg=UI_COLORS["bg"])

        self.controller: AnonymizerGuiController = AnonymizerGuiController(ROOT_DIR)
        self.workspaces: List[Tuple[str, str]] = []
        self.workflow_mode: str = "ia"
        self.current_ini_var: tk.StringVar = tk.StringVar()
        self.active_ws_badge_var: tk.StringVar = tk.StringVar(value="Dossier : aucun")
        self.mode_badge_var: tk.StringVar = tk.StringVar(value="Objectif : IA (Anonymisé)")
        self.workspace_choice_var: tk.StringVar = tk.StringVar()
        self.new_ws_name_var: tk.StringVar = tk.StringVar()
        self.status_var: tk.StringVar = tk.StringVar(
            value="Prêt — Survolez un bouton pour afficher son aide."
        )
        self.is_running: bool = False
        self.current_proc: Optional[subprocess.Popen] = None
        self.pages: Dict[str, tk.Frame] = {}
        self.nav_buttons: Dict[str, tk.Button] = {}
        self.active_page_key: str = "gate"
        self.log_visible: bool = False

        configure_ttk_styles(self)
        self._build_layout()
        self._refresh_workspaces()
        if skip_startup_gate and self.workspaces:
            _, first_ini = self.workspaces
            self._refresh_workspaces(select_ini=first_ini)
            self._set_workflow_mode("ia", navigate=True)
        else:
            self._show_page("gate")

    def _build_layout(self) -> None:
        shell = tk.Frame(self, bg=UI_COLORS["bg"])
        shell.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(shell, bg=UI_COLORS["sidebar"], width=240)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text="DOSSIER CONFIDENTIEL", bg=UI_COLORS["sidebar"], fg="#ffffff", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=18, pady=(20, 2))
        tk.Label(self.sidebar, text="Santé • Famille • Prud'hommes", bg=UI_COLORS["sidebar"], fg="#94a3b8", font=("Segoe UI", 8)).pack(anchor="w", padx=18, pady=(0, 18))

        self.nav_container = tk.Frame(self.sidebar, bg=UI_COLORS["sidebar"])
        self.nav_container.pack(fill="x")

        tk.Label(
            self.sidebar,
            text="100 % LOCAL & HORS-LIGNE\nVos fichiers restent sur ce PC",
            bg="#1e293b",
            fg="#86efac",
            font=("Segoe UI", 8),
            justify="left",
            padx=12,
            pady=10,
        ).pack(side="bottom", fill="x", padx=12, pady=14)
        main_area = tk.Frame(shell, bg=UI_COLORS["bg"])
        main_area.pack(side="left", fill="both", expand=True)

        top_bar = tk.Frame(main_area, bg="#ffffff", height=54)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        self.page_heading_var = tk.StringVar(value="Engagement de relecture & Licence")
        tk.Label(top_bar, textvariable=self.page_heading_var, bg="#ffffff", fg=UI_COLORS["text"], font=("Segoe UI", 11, "bold")).pack(side="left", padx=18)

        make_styled_button(
            top_bar,
            text="Aide & Exports ?",
            command=self._show_export_guide_popup,
            variant="secondary",
            tooltip="Affiche comment exporter vos fichiers (Agenda .ics, CSV, SMS, WhatsApp, Teams, Messenger, Gmail).",
        ).pack(side="right", padx=(6, 16))

        self.btn_switch_mode = tk.Button(
            top_bar,
            textvariable=self.mode_badge_var,
            command=lambda: self._show_page("mode"),
            bg="#fef3c7",
            fg="#92400e",
            relief="flat",
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            font=("Segoe UI", 8, "bold"),
        )
        self.btn_switch_mode.pack(side="right", padx=6)

        tk.Label(top_bar, textvariable=self.active_ws_badge_var, bg="#e0f2fe", fg="#0369a1", font=("Segoe UI", 8, "bold"), padx=10, pady=4).pack(side="right", padx=6)

        self.content_container = tk.Frame(main_area, bg=UI_COLORS["bg"], padx=18, pady=12)
        self.content_container.pack(fill="both", expand=True)

        for key in ("gate", "mode", "setup", "run", "audit", "export"):
            self.pages[key] = tk.Frame(self.content_container, bg=UI_COLORS["bg"])

        self._build_page_gate()
        self._build_page_mode()
        self._build_page_setup()
        self._build_page_run()
        self._build_page_audit()
        self._build_page_export()

        footer = tk.Frame(main_area, bg="#e2e8f0", height=28)
        footer.pack(fill="x", side="bottom")
        tk.Label(footer, textvariable=self.status_var, bg="#e2e8f0", fg="#1e293b", font=("Segoe UI", 8)).pack(side="left", padx=16, pady=4)

    def _rebuild_sidebar_nav(self) -> None:
        for child in self.nav_container.winfo_children():
            child.destroy()
        self.nav_buttons.clear()
        if self.active_page_key in {"gate", "mode"} or not self.current_ini_var.get():
            return
        nav_items = (
            [("setup", "1. Préparer mon dossier"), ("run", "2. Extraire & Classer"), ("export", "3. Pack Avocat Nominatif")]
            if self.workflow_mode == "lawyer"
            else [("setup", "1. Préparer mon dossier"), ("run", "2. Analyser & Anonymiser"), ("audit", "3. Vérifier les noms"), ("export", "4. Récupérer & Requêtes IA")]
        )
        for key, label in nav_items:
            btn = tk.Button(
                self.nav_container, text=f"  {label}", anchor="w", bg=UI_COLORS["sidebar"], fg="#e2e8f0",
                activebackground=UI_COLORS["sidebar_hover"], activeforeground="#ffffff", relief="flat", bd=0,
                padx=14, pady=11, cursor="hand2", font=("Segoe UI", 9, "bold"), command=lambda k=key: self._show_page(k),
            )
            btn.pack(fill="x", padx=10, pady=3)
            self.nav_buttons[key] = btn
    def _show_page(self, key: str) -> None:
        if key != "gate" and not self.current_ini_var.get():
            key = "gate"
        titles = {
            "gate": "Vigilance Humaine, Licence (GNU GPL v3) & Choix du Dossier",
            "mode": "Choisir votre objectif : Pré-analyse IA ou Dossier Avocat",
            "setup": "Étape 1 — Préparer mon dossier et déposer mes pièces",
            "run": "Étape 2 — Extraction et traitement des documents",
            "audit": "Étape 3 — Vérifier les noms restants (Avant / Après)",
            "export": "Étape 3 — Générer le Pack Avocat Nominatif" if self.workflow_mode == "lawyer" else "Étape 4 — Récupérer les fichiers anonymisés & Requêtes IA",
        }
        self.active_page_key = key
        self._rebuild_sidebar_nav()
        self.page_heading_var.set(titles.get(key, ""))
        for k, frame in self.pages.items():
            frame.pack(fill="both", expand=True) if k == key else frame.pack_forget()
        for k, btn in self.nav_buttons.items():
            btn.configure(bg=UI_COLORS["sidebar_active"] if k == key else UI_COLORS["sidebar"], fg="#ffffff")
        if key == "gate":
            self._refresh_gate_workspace_panel()
        elif key == "setup":
            self._update_setup_mode_visibility()
        elif key == "run":
            self._refresh_dashboard_cards()
        elif key == "export":
            self._update_export_mode_visibility()

    def _set_workflow_mode(self, mode: str, navigate: bool = True) -> None:
        if not self.current_ini_var.get():
            self._show_page("gate")
            return
        self.workflow_mode = "lawyer" if mode == "lawyer" else "ia"
        if self.workflow_mode == "lawyer":
            self.mode_badge_var.set("Mode : Avocat (Nominatif)")
            self.btn_switch_mode.configure(bg="#fef3c7", fg="#92400e")
        else:
            self.mode_badge_var.set("Mode : IA (Anonymisé)")
            self.btn_switch_mode.configure(bg="#dcfce7", fg="#166534")
        if navigate:
            self._show_page("setup")

    def _quit_politely(self) -> None:
        messagebox.showinfo("Fermeture de l'application", "Merci de votre visite.\n\nAucun fichier n'a été lu ni modifié. L'application va maintenant se fermer.")
        self.destroy()

    def _refresh_gate_workspace_panel(self) -> None:
        self.workspaces = self.controller.list_workspaces()
        for w in (self.frame_gate_existing, self.frame_gate_create, self.rb_gate_create, self.lbl_gate_create_only, self.entry_gate_new):
            w.pack_forget()
        if self.workspaces:
            self.combo_gate_ws["values"] = [lbl for lbl, _ in self.workspaces]
            self.combo_gate_ws.current(0)
            self.gate_action_var.set("open")
            self.frame_gate_existing.pack(fill="x", pady=(2, 8))
            self.rb_gate_create.pack(side="left", padx=(0, 8))
            self.entry_gate_new.pack(side="left", ipady=3)
            self.frame_gate_create.pack(fill="x", pady=(2, 4))
        else:
            self.gate_action_var.set("create")
            self.lbl_gate_create_only.pack(side="left", padx=(0, 8))
            self.entry_gate_new.pack(side="left", ipady=3)
            self.frame_gate_create.pack(fill="x", pady=(4, 4))

    def _confirm_gate_and_workspace(self) -> None:
        if self.gate_action_var.get() == "open" and self.workspaces:
            idx: int = self.combo_gate_ws.current()
            if idx < 0 or idx >= len(self.workspaces):
                messagebox.showwarning("Dossier requis", "Veuillez sélectionner un dossier existant.")
                return
            _, selected_ini = self.workspaces[idx]
            self._refresh_workspaces(select_ini=selected_ini)
            self._show_page("mode")
            return
        raw_name: str = self.gate_new_name_var.get().strip()
        if not raw_name:
            messagebox.showwarning("Nom de dossier obligatoire", "Vous devez obligatoirement saisir un nom de dossier pour continuer.")
            return
        try:
            ini_path: str = self.controller.create_workspace(raw_name)
            self.gate_new_name_var.set("")
            self._refresh_workspaces(select_ini=ini_path)
            self._show_page("mode")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Erreur", str(exc))

    def _update_setup_mode_visibility(self) -> None:
        self.card_csv.pack_forget() if self.workflow_mode == "lawyer" else self.card_csv.pack(fill="x", pady=(0, 10))
        self._refresh_workspace_counters()

    def _update_export_mode_visibility(self) -> None:
        self.frame_export_ia.pack_forget()
        self.frame_export_lawyer.pack_forget()
        (self.frame_export_lawyer if self.workflow_mode == "lawyer" else self.frame_export_ia).pack(fill="both", expand=True)

    def _on_prompt_selected(self, _event: object = None) -> None:
        idx: int = self.combo_prompts.current()
        if 0 <= idx < len(self.controller.AI_PROMPT_TEMPLATES):
            _, body = self.controller.AI_PROMPT_TEMPLATES[idx]
            self.txt_prompt_preview.delete("1.0", "end")
            self.txt_prompt_preview.insert("1.0", body)

    def _copy_selected_prompt(self) -> None:
        txt: str = self.txt_prompt_preview.get("1.0", "end-1c").strip()
        if txt:
            self.clipboard_clear()
            self.clipboard_append(txt)
            self.status_var.set("Requête IA copiée dans le presse-papiers !")
            messagebox.showinfo("Copié", "La requête IA a été copiée. Collez-la dans votre assistant IA avec vos fichiers anonymisés.")
    def _toggle_log_panel(self) -> None:
        self.log_visible = not self.log_visible
        self.log_text.pack(fill="both", expand=True) if self.log_visible else self.log_text.pack_forget()

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _refresh_dashboard_cards(self) -> None:
        if self.workflow_mode == "lawyer":
            self.btn_main_run.configure(text="Extraire et classer chronologiquement (OCR + Audio)")
            self.btn_fast_reanon.pack_forget()
            self.btn_after_run_next.configure(text="Étape 3 : Générer le Pack Avocat ->")
        else:
            self.btn_main_run.configure(text="Lancer l'extraction et l'anonymisation")
            self.btn_fast_reanon.pack(side="left", padx=(0, 8))
            self.btn_after_run_next.configure(text="Étape 3 : Vérifier les noms restants ->")
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        st = self.controller.load_dashboard_stats(ini_path)
        self.stat_vars["docs"].set(str(max(int(st.get("documents_traites", 0)), int(st.get("documents_extraits", 0)))))
        self.stat_vars["names"].set(str(st.get("noms_masques", 0)))
        self.stat_vars["coords"].set(str(st.get("coordonnees_masquees", 0)))
        self.stat_vars["ids"].set(str(st.get("identifiants_masques", 0)))
        self.stat_vars["locs"].set(str(st.get("lieux_dates_masques", 0)))
        zips: List[str] = st.get("zip_ignores") or self.controller.detect_zip_files(ini_path)
        if zips:
            self.dash_zip_var.set(f"ATTENTION : {len(zips)} archive(s) .zip ignorée(s) par sécurité ({', '.join(os.path.basename(z) for z in zips[:4])}). Décompressez-les puis relancez.")
            self.lbl_dash_zip.pack(fill="x", pady=(8, 0))
        else:
            self.lbl_dash_zip.pack_forget()

    def _go_to_step_after_run(self) -> None:
        self._show_page("export" if self.workflow_mode == "lawyer" else "audit")

    def _start_primary_workflow_job(self) -> None:
        self._start_job("extract_only" if self.workflow_mode == "lawyer" else "full_with_contacts")

    def _refresh_workspaces(self, select_ini: Optional[str] = None) -> None:
        self.workspaces = self.controller.list_workspaces()
        self.combo_ws["values"] = [lbl for lbl, _ in self.workspaces]
        if not self.workspaces:
            self.current_ini_var.set("")
            self.active_ws_badge_var.set("Dossier : aucun")
            return
        target_ref: str = select_ini or self.current_ini_var.get()
        target_idx: int = next((i for i, (_, p) in enumerate(self.workspaces) if target_ref and os.path.abspath(p) == os.path.abspath(target_ref)), -1)
        if target_idx < 0:
            self.current_ini_var.set("")
            self.active_ws_badge_var.set("Dossier : aucun")
            return
        self.combo_ws.current(target_idx)
        lbl, selected_ini = self.workspaces[target_idx]
        self.current_ini_var.set(selected_ini)
        self.active_ws_badge_var.set(f"Dossier : {lbl}")
        self._refresh_audit_list()
        self._refresh_workspace_counters()
        self._refresh_dashboard_cards()
    def _on_workspace_selected(self, _event: object = None) -> None:
        idx: int = self.combo_ws.current()
        if 0 <= idx < len(self.workspaces):
            lbl, p_ini = self.workspaces[idx]
            self.current_ini_var.set(p_ini)
            self.active_ws_badge_var.set(f"Dossier : {lbl}")
            self._refresh_audit_list()
            self._refresh_workspace_counters()
            self._refresh_dashboard_cards()

    def _create_new_workspace(self) -> None:
        raw_name: str = self.new_ws_name_var.get().strip()
        if not raw_name:
            messagebox.showwarning("Nom requis", "Veuillez saisir un nom de dossier.")
            return
        try:
            ini_path: str = self.controller.create_workspace(raw_name)
            self.new_ws_name_var.set("")
            self._refresh_workspaces(select_ini=ini_path)
            messagebox.showinfo("Dossier créé", "Votre nouvel espace est prêt !")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Erreur", str(exc))

    def _open_path_in_os(self, target_path: str) -> None:
        if not os.path.exists(target_path):
            messagebox.showinfo("Information", f"Aucun fichier généré pour le moment :\n{target_path}")
            return
        if os.name == "nt":
            os.startfile(target_path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", target_path])

    def _open_workspace_folder(self, key: str) -> None:
        if self.current_ini_var.get():
            paths = self.controller.resolve_workspace_paths(self.current_ini_var.get())
            os.makedirs(paths[key], exist_ok=True)
            self._open_path_in_os(paths[key])

    def _refresh_workspace_counters(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        paths = self.controller.resolve_workspace_paths(ini_path)
        doc_count: int = sum(sum(1 for fn in files if not fn.startswith(".")) for _, _, files in os.walk(paths["sources_dir"])) if os.path.isdir(paths["sources_dir"]) else 0
        self.docs_summary_var.set(f"Documents sources déposés dans ce dossier : {doc_count} fichier(s).")
        zips = self.controller.detect_zip_files(ini_path)
        if zips:
            self.zip_warning_var.set(f"ATTENTION : {len(zips)} fichier(s) .zip détecté(s) ({', '.join(os.path.basename(z) for z in zips[:4])}). Décompressez-les d'abord.")
            self.lbl_zip_warning.pack(anchor="w", fill="x", pady=(8, 0))
        else:
            self.lbl_zip_warning.pack_forget()
        c_dir: str = paths["input_contacts_dir"]
        csvs: List[str] = sorted(fn for fn in os.listdir(c_dir) if fn.lower().endswith(".csv")) if os.path.isdir(c_dir) else []
        self.csv_summary_var.set(f"Carnets (.csv) chargés ({len(csvs)}) : {', '.join(csvs[:5])}" if csvs else "Carnets (.csv) chargés : aucun.")

    def _import_csv_dialog(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        csv_files = filedialog.askopenfilenames(title="Ajouter un ou plusieurs carnets (.csv)", filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")])
        if csv_files:
            for csv_file in csv_files:
                self.controller.import_contacts_csv(ini_path, str(csv_file))
            self._refresh_workspace_counters()
            self.status_var.set(f"{len(csv_files)} carnet(s) CSV ajouté(s) — prêts pour l'étape 2.")
    def _set_buttons_state(self, enabled: bool) -> None:
        st: str = "normal" if enabled else "disabled"
        self.btn_main_run.configure(state=st)
        self.btn_fast_reanon.configure(state=st)
        self.btn_stop.configure(state="disabled" if enabled else "normal")

    def _stop_current_job(self) -> None:
        if self.current_proc is not None and self.current_proc.poll() is None:
            try:
                self.current_proc.terminate()
                self._append_log("[ARRÊT] Interruption demandée par l'utilisateur.")
            except OSError:
                pass

    def _start_job(self, mode: str, go_export_after: bool = False) -> None:
        if self.is_running:
            return
        ini_path: str = self.current_ini_var.get()
        if not ini_path or not os.path.isfile(ini_path):
            messagebox.showwarning("Configuration manquante", "Aucun dossier sélectionné.")
            return
        self.is_running = True
        self._set_buttons_state(False)
        self.progress.start(12)
        self._show_page("run")
        self.status_var.set("Traitement en cours, veuillez patienter...")
        cmds: List[List[str]] = []
        if mode == "full_with_contacts":
            c_dir = self.controller.resolve_workspace_paths(ini_path)["input_contacts_dir"]
            if os.path.isdir(c_dir) and any(f.lower().endswith(".csv") for f in os.listdir(c_dir)):
                cmds.append(self.controller.build_cli_command(ini_path, "contacts"))
            cmds.append(self.controller.build_cli_command(ini_path, "full"))
        else:
            cmds.append(self.controller.build_cli_command(ini_path, mode))

        def _worker() -> None:
            env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
            ret: int = 0
            for cmd in cmds:
                self.after(0, self._append_log, f"\n>>> Lancement : {' '.join(cmd)}")
                proc = subprocess.Popen(cmd, cwd=ROOT_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
                self.current_proc = proc
                if proc.stdout:
                    for raw_ln in proc.stdout:
                        if raw_ln.strip():
                            self.after(0, self._append_log, raw_ln.rstrip("\r\n"))
                ret = proc.wait()
                self.current_proc = None
                if ret != 0:
                    break
            self.after(0, self._on_job_finished, ret, mode, go_export_after)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_job_finished(self, return_code: int, mode: str, go_export_after: bool = False) -> None:
        self.progress.stop()
        self.is_running = False
        self._set_buttons_state(True)
        self._refresh_audit_list()
        self._refresh_workspace_counters()
        self._refresh_dashboard_cards()
        if return_code == 0:
            self.status_var.set("Traitement terminé avec succès.")
            if go_export_after or mode == "extract_only":
                self._show_page("export")
            elif mode in {"full", "full_with_contacts", "anonymize_only"}:
                cands = self.controller.load_audit_candidates(self.current_ini_var.get())
                self._show_page("audit" if cands else "export")
        else:
            self.status_var.set(f"Traitement interrompu ou terminé avec code {return_code}.")

    def _refresh_audit_list(self) -> None:
        for item in self.audit_tree.get_children():
            self.audit_tree.delete(item)
        self.audit_alias_edit_var.set("")
        if not self.current_ini_var.get():
            return
        candidates = self.controller.load_audit_candidates(self.current_ini_var.get())
        for cand, alias in candidates:
            self.audit_tree.insert("", "end", values=(cand, alias))
        self.audit_count_var.set(f"{len(candidates)} élément(s) à vérifier dans ce dossier.")

    def _on_audit_row_selected(self, _event: object = None) -> None:
        sel = self.audit_tree.selection()
        if sel:
            vals = tuple(self.audit_tree.item(next(iter(sel)), "values"))
            if len(vals) >= 2:
                self.audit_alias_edit_var.set(str(vals))

    def _open_before_after_preview(self) -> None:
        sel = self.audit_tree.selection()
        if not sel:
            messagebox.showinfo("Sélection requise", "Cliquez d'abord sur une ligne du tableau.")
            return
        vals = tuple(self.audit_tree.item(next(iter(sel)), "values"))
        if len(vals) >= 2:
            cand_txt = str(vals).strip()
            alias_txt = self.audit_alias_edit_var.get().strip() or str(vals).strip()
            occs = self.controller.load_audit_occurrences(self.current_ini_var.get(), cand_txt)
            BeforeAfterPreviewDialog(self, cand_txt, alias_txt, occs, on_approve=self._approve_selected_audit, on_exclude=self._exclude_selected_audit)

    def _approve_selected_audit(self) -> None:
        sel = self.audit_tree.selection()
        if sel:
            vals = tuple(self.audit_tree.item(next(iter(sel)), "values"))
            if len(vals) >= 2:
                cand_txt = str(vals).strip()
                alias_txt = self.audit_alias_edit_var.get().strip() or str(vals).strip()
                self.controller.approve_audit_mask(self.current_ini_var.get(), cand_txt, alias_txt)
                self._refresh_audit_list()

    def _exclude_selected_audit(self) -> None:
        sel = self.audit_tree.selection()
        if sel:
            vals = tuple(self.audit_tree.item(next(iter(sel)), "values"))
            if vals:
                self.controller.exclude_audit_false_positive(self.current_ini_var.get(), str(next(iter(vals))).strip())
                self._refresh_audit_list()

    def _apply_audit_and_go_export(self) -> None:
        self._start_job("anonymize_only", go_export_after=True)

    def _export_lawyer_pack(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        paths = self.controller.resolve_workspace_paths(ini_path)
        selected_set: Optional[Set[str]] = None
        if self.lawyer_filter_mode_var.get() == "ai_list":
            raw_list: str = self.txt_ai_pieces_list.get("1.0", "end-1c").strip()
            selected_set = self.controller.resolve_ai_selected_extracted_files(ini_path, raw_list)
            if not selected_set:
                messagebox.showwarning("Aucune pièce reconnue", "Aucun chemin valide trouvé dans la liste collée.")
                return
        from doc_anonymizer.dossier_exporter import LawyerDossierExporter
        exporter = LawyerDossierExporter(
            results_dir=paths["results_dir"],
            export_dir=os.path.join(os.path.dirname(os.path.abspath(ini_path)), "pack_avocat"),
            transcriptions_dir=paths["transcriptions_dir"],
            sources_dir=paths["sources_dir"],
            mapping_file=paths["mapping_file"],
            selected_extracted_files=selected_set,
        )
        count, out_folder = exporter.export_lawyer_pack()
        if count == 0:
            messagebox.showinfo("Aucune pièce extraite", "Lancez d'abord l'étape 2 avant de générer le Pack Avocat.")
            return
        messagebox.showinfo("Pack Avocat Nominatif prêt", f"{count} pièce(s) numérotée(s) et classée(s) chronologiquement !\nDossier :\n{out_folder}")
        self._open_path_in_os(out_folder)

    def _show_calendar_export_popup(self) -> None:
        ExportGuideDialog(self, initial_tab=0)

    def _open_help_dialog(self) -> None:
        ExportGuideDialog(self, initial_tab=0)

    def _show_export_guide_popup(self) -> None:
        ExportGuideDialog(self, initial_tab=0)


def main() -> None:
    app = AnonymizerGuiApp()
    app.mainloop()


if __name__ == "__main__":
    main()
