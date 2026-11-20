# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.gui_controller import AnonymizerGuiController


class AnonymizerGuiApp(tk.Tk):
    """Interface graphique simple pour préparer et anonymiser des dossiers confidentiels."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Anonymiseur de Documents Confidentiels (100 % Local)")
        self.geometry("920x660")
        self.minsize(820, 580)

        self.controller: AnonymizerGuiController = AnonymizerGuiController(ROOT_DIR)
        self.workspaces: List[Tuple[str, str]] = []
        self.current_ini_var: tk.StringVar = tk.StringVar()
        self.workspace_choice_var: tk.StringVar = tk.StringVar()
        self.new_ws_name_var: tk.StringVar = tk.StringVar()
        self.status_var: tk.StringVar = tk.StringVar(value="Prêt.")
        self.is_running: bool = False

        self._build_ui()
        self._refresh_workspaces()

    def _build_ui(self) -> None:
        """Construit les 3 onglets principaux de l'interface."""
        header = ttk.Frame(self, padding=(14, 10))
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Anonymiseur Local de Documents (Santé, Famille, Prud'hommes)",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Traitement 100 % hors-ligne sur votre ordinateur : aucun fichier n'est envoyé sur Internet.",
            foreground="#444444",
        ).pack(anchor="w", pady=(2, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(4, 6))

        self.tab_setup = ttk.Frame(self.notebook, padding=14)
        self.tab_run = ttk.Frame(self.notebook, padding=14)
        self.tab_audit = ttk.Frame(self.notebook, padding=14)

        self.notebook.add(self.tab_setup, text="1. Dossier & Documents")
        self.notebook.add(self.tab_run, text="2. Extraction & Anonymisation")
        self.notebook.add(self.tab_audit, text="3. Vérification des noms restants")

        self._build_tab_setup()
        self._build_tab_run()
        self._build_tab_audit()

        footer = ttk.Frame(self, padding=(14, 6))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var, foreground="#1f4e79").pack(side="left")

    def _build_tab_setup(self) -> None:
        """Onglet 1 : choix ou création d'un dossier isolé et dépôt des fichiers."""
        grp_ws = ttk.LabelFrame(
            self.tab_setup, text="Étape A — Choisir ou créer un dossier isolé", padding=12
        )
        grp_ws.pack(fill="x", pady=(0, 12))

        row_sel = ttk.Frame(grp_ws)
        row_sel.pack(fill="x", pady=(0, 8))
        ttk.Label(row_sel, text="Dossier actif :").pack(side="left", padx=(0, 8))
        self.combo_ws = ttk.Combobox(
            row_sel, textvariable=self.workspace_choice_var, state="readonly", width=45
        )
        self.combo_ws.pack(side="left", padx=(0, 8))
        self.combo_ws.bind("<<ComboboxSelected>>", self._on_workspace_selected)

        row_new = ttk.Frame(grp_ws)
        row_new.pack(fill="x")
        ttk.Label(row_new, text="Nouveau dossier (ex. Garde_Enfant, Dossier_Salarie) :").pack(
            side="left", padx=(0, 8)
        )
        ttk.Entry(row_new, textvariable=self.new_ws_name_var, width=28).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(row_new, text="Créer ce dossier", command=self._create_new_workspace).pack(
            side="left"
        )

        grp_files = ttk.LabelFrame(
            self.tab_setup, text="Étape B — Ajouter les documents et contacts", padding=12
        )
        grp_files.pack(fill="x", pady=(0, 12))

        ttk.Label(
            grp_files,
            text="Déposez vos PDF, scans, e-mails (MBOX), SMS (XML), chats ou audios dans le dossier des sources :",
            wraplength=820,
        ).pack(anchor="w", pady=(0, 8))

        btn_row1 = ttk.Frame(grp_files)
        btn_row1.pack(fill="x", pady=(0, 8))
        ttk.Button(
            btn_row1,
            text="Ouvrir le dossier des documents sources",
            command=lambda: self._open_workspace_folder("sources_dir"),
        ).pack(side="left", padx=(0, 10))
        ttk.Button(
            btn_row1,
            text="Importer un fichier de contacts (.csv)",
            command=self._import_csv_dialog,
        ).pack(side="left")

        grp_out = ttk.LabelFrame(
            self.tab_setup, text="Étape C — Consulter les résultats anonymisés", padding=12
        )
        grp_out.pack(fill="x")
        ttk.Button(
            grp_out,
            text="Ouvrir le dossier des lots anonymisés (anonymized_results)",
            command=lambda: self._open_workspace_folder("results_dir"),
        ).pack(side="left", padx=(0, 10))
        ttk.Button(
            grp_out,
            text="Ouvrir les règles manuelles (manual_contacts.txt)",
            command=lambda: self._open_workspace_file("manual_contacts_file"),
        ).pack(side="left")
    def _build_tab_run(self) -> None:
        """Onglet 2 : lancement du pipeline et journal d'exécution en temps réel."""
        ctrl_row = ttk.Frame(self.tab_run)
        ctrl_row.pack(fill="x", pady=(0, 10))

        self.btn_full = ttk.Button(
            ctrl_row,
            text="Lancer l'extraction et l'anonymisation",
            command=lambda: self._start_job("full"),
        )
        self.btn_full.pack(side="left", padx=(0, 10))

        self.btn_anon_only = ttk.Button(
            ctrl_row,
            text="Ré-anonymiser uniquement (rapide)",
            command=lambda: self._start_job("anonymize_only"),
        )
        self.btn_anon_only.pack(side="left", padx=(0, 10))

        self.btn_contacts = ttk.Button(
            ctrl_row,
            text="Mettre à jour les contacts CSV",
            command=lambda: self._start_job("contacts"),
        )
        self.btn_contacts.pack(side="left")

        self.progress = ttk.Progressbar(self.tab_run, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 10))

        self.log_text = tk.Text(
            self.tab_run, height=22, wrap="word", font=("Consolas", 9), state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)

    def _build_tab_audit(self) -> None:
        """Onglet 3 : validation visuelle de audits/residual_names_copy.txt."""
        top_info = ttk.Frame(self.tab_audit)
        top_info.pack(fill="x", pady=(0, 8))
        ttk.Label(
            top_info,
            text="Noms potentiels détectés après anonymisation. Masquez les vrais noms ou ignorez les faux positifs :",
            wraplength=760,
        ).pack(side="left")
        ttk.Button(top_info, text="Actualiser", command=self._refresh_audit_list).pack(side="right")

        cols = ("candidate", "alias")
        self.audit_tree = ttk.Treeview(
            self.tab_audit, columns=cols, show="headings", selectmode="browse", height=16
        )
        self.audit_tree.heading("candidate", text="Nom détecté dans les textes")
        self.audit_tree.heading("alias", text="Remplacement proposé")
        self.audit_tree.column("candidate", width=380)
        self.audit_tree.column("alias", width=320)
        self.audit_tree.pack(fill="both", expand=True, pady=(0, 10))

        act_row = ttk.Frame(self.tab_audit)
        act_row.pack(fill="x")
        ttk.Button(
            act_row,
            text="Masquer ce nom (ajouter aux règles)",
            command=self._approve_selected_audit,
        ).pack(side="left", padx=(0, 10))
        ttk.Button(
            act_row,
            text="Ignorer (mot courant / faux positif)",
            command=self._exclude_selected_audit,
        ).pack(side="left", padx=(0, 10))
        ttk.Button(
            act_row,
            text="Appliquer les corrections (Ré-anonymiser)",
            command=lambda: self._start_job("anonymize_only"),
        ).pack(side="right")

    def _append_log(self, line: str) -> None:
        """Ajoute une ligne dans la zone de journal."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _refresh_workspaces(self, select_ini: Optional[str] = None) -> None:
        """Recharge la liste des dossiers disponibles."""
        self.workspaces = self.controller.list_workspaces()
        labels: List[str] = [lbl for lbl, _ in self.workspaces]
        self.combo_ws["values"] = labels
        if not self.workspaces:
            return
        target_idx: int = 0
        if select_ini:
            for idx, (_, p_ini) in enumerate(self.workspaces):
                if os.path.abspath(p_ini) == os.path.abspath(select_ini):
                    target_idx = idx
                    break
        self.combo_ws.current(target_idx)
        _, selected_ini = self.workspaces[target_idx]
        self.current_ini_var.set(selected_ini)
        self._refresh_audit_list()

    def _on_workspace_selected(self, _event: object = None) -> None:
        """Met à jour le fichier config.ini actif lors du changement de dossier."""
        idx: int = self.combo_ws.current()
        if 0 <= idx < len(self.workspaces):
            lbl, p_ini = self.workspaces[idx]
            self.current_ini_var.set(p_ini)
            self._refresh_audit_list()
            self.status_var.set(f"Dossier actif : {lbl}")
    def _create_new_workspace(self) -> None:
        """Crée un nouveau profil isolé et le sélectionne."""
        raw_name: str = self.new_ws_name_var.get().strip()
        if not raw_name:
            messagebox.showwarning("Nom requis", "Veuillez saisir un nom de dossier.")
            return
        try:
            ini_path: str = self.controller.create_workspace(raw_name)
            self.new_ws_name_var.set("")
            self._refresh_workspaces(select_ini=ini_path)
            self.status_var.set(f"Dossier créé : {os.path.dirname(ini_path)}")
        except OSError as exc:
            messagebox.showerror("Erreur", str(exc))

    def _open_path_in_os(self, target_path: str) -> None:
        """Ouvre un dossier ou un fichier dans le gestionnaire natif du système."""
        if not os.path.exists(target_path):
            messagebox.showinfo("Information", f"Chemin introuvable :\n{target_path}")
            return
        if os.name == "nt":
            os.startfile(target_path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target_path])
        else:
            subprocess.Popen(["xdg-open", target_path])

    def _open_workspace_folder(self, key: str) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        paths: Dict[str, str] = self.controller.resolve_workspace_paths(ini_path)
        os.makedirs(paths[key], exist_ok=True)
        self._open_path_in_os(paths[key])

    def _open_workspace_file(self, key: str) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        paths: Dict[str, str] = self.controller.resolve_workspace_paths(ini_path)
        self._open_path_in_os(paths[key])

    def _import_csv_dialog(self) -> None:
        """Sélectionne un CSV de contacts, le copie et lance son extraction."""
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        csv_file: str = filedialog.askopenfilename(
            title="Sélectionner un export de contacts CSV",
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")],
        )
        if not csv_file:
            return
        try:
            dest: str = self.controller.import_contacts_csv(ini_path, csv_file)
            self._append_log(f"[CONTACTS] Fichier importé : {dest}")
            self._start_job("contacts")
        except OSError as exc:
            messagebox.showerror("Erreur d'import", str(exc))

    def _set_buttons_state(self, enabled: bool) -> None:
        state_val: str = "normal" if enabled else "disabled"
        self.btn_full.configure(state=state_val)
        self.btn_anon_only.configure(state=state_val)
        self.btn_contacts.configure(state=state_val)

    def _start_job(self, mode: str) -> None:
        """Exécute le script Python correspondant dans un thread secondaire."""
        if self.is_running:
            return
        ini_path: str = self.current_ini_var.get()
        if not ini_path or not os.path.isfile(ini_path):
            messagebox.showwarning("Configuration manquante", "Aucun fichier config.ini sélectionné.")
            return

        self.is_running = True
        self._set_buttons_state(False)
        self.progress.start(12)
        self.notebook.select(self.tab_run)
        self.status_var.set("Traitement en cours...")

        cmd: List[str] = self.controller.build_cli_command(ini_path, mode)
        self._append_log(f"\n>>> Exécution : {' '.join(cmd)}")

        def _worker() -> None:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.Popen(
                cmd,
                cwd=ROOT_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc.stdout:
                for raw_ln in proc.stdout:
                    ln: str = raw_ln.rstrip("\r\n")
                    if ln:
                        self.after(0, self._append_log, ln)
            ret: int = proc.wait()
            self.after(0, self._on_job_finished, ret)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_job_finished(self, return_code: int) -> None:
        """Réactive l'interface et actualise l'audit une fois le traitement terminé."""
        self.progress.stop()
        self.is_running = False
        self._set_buttons_state(True)
        self._refresh_audit_list()
        if return_code == 0:
            self.status_var.set("Traitement terminé avec succès.")
            self._append_log("[OK] Traitement terminé.")
        else:
            self.status_var.set(f"Traitement terminé avec avertissement/erreur (code {return_code}).")
            self._append_log(f"[ATTENTION] Code retour : {return_code}")

    def _refresh_audit_list(self) -> None:
        """Recharge les candidats de residual_names_copy.txt dans le tableau."""
        for item in self.audit_tree.get_children():
            self.audit_tree.delete(item)
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        candidates: List[Tuple[str, str]] = self.controller.load_audit_candidates(ini_path)
        for cand, alias in candidates:
            self.audit_tree.insert("", "end", values=(cand, alias))

    def _approve_selected_audit(self) -> None:
        """Enregistre la ligne sélectionnée dans manual_contacts.txt."""
        sel = self.audit_tree.selection()
        if not sel:
            return
        vals = self.audit_tree.item(next(iter(sel)), "values")
        if len(vals) < 2:
            return
        cand_txt, alias_txt = str(vals[0]), str(vals[1])
        ini_path: str = self.current_ini_var.get()
        self.controller.approve_audit_mask(ini_path, cand_txt, alias_txt)
        self._refresh_audit_list()
        self.status_var.set(f"Règle ajoutée : {cand_txt} = {alias_txt}")

    def _exclude_selected_audit(self) -> None:
        """Ajoute les mots de la ligne sélectionnée dans data/mots_exclus.txt."""
        sel = self.audit_tree.selection()
        if not sel:
            return
        vals = self.audit_tree.item(next(iter(sel)), "values")
        if not vals:
            return
        cand_txt: str = str(vals[0])
        ini_path: str = self.current_ini_var.get()
        self.controller.exclude_audit_false_positive(ini_path, cand_txt)
        self._refresh_audit_list()
        self.status_var.set(f"Ignoré (ajouté aux mots exclus) : {cand_txt}")


def main() -> None:
    """Point d'entrée de l'interface graphique."""
    app = AnonymizerGuiApp()
    app.mainloop()


if __name__ == "__main__":
    main()
