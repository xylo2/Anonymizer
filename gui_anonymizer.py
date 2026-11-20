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
    """Interface graphique guidée pour préparer et anonymiser des dossiers confidentiels."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Anonymiseur de Documents Confidentiels (100 % Local & Hors-Ligne)")
        self.geometry("960x720")
        self.minsize(860, 620)

        self.controller: AnonymizerGuiController = AnonymizerGuiController(ROOT_DIR)
        self.workspaces: List[Tuple[str, str]] = []
        self.current_ini_var: tk.StringVar = tk.StringVar()
        self.workspace_choice_var: tk.StringVar = tk.StringVar()
        self.new_ws_name_var: tk.StringVar = tk.StringVar()
        self.status_var: tk.StringVar = tk.StringVar(value="Prêt — Suivez les étapes 1 à 3.")
        self.is_running: bool = False

        self._build_ui()
        self._refresh_workspaces()

    def _build_ui(self) -> None:
        """Construit l'en-tête et les 4 onglets guidés de l'interface."""
        header = ttk.Frame(self, padding=(14, 10))
        header.pack(fill="x")

        top_bar = ttk.Frame(header)
        top_bar.pack(fill="x")
        ttk.Label(
            top_bar,
            text="Anonymiseur Local de Documents (Santé, Garde d'enfant, Prud'hommes)",
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left")
        ttk.Button(
            top_bar,
            text="? Mode d'emploi",
            command=lambda: self.notebook.select(self.tab_help),
        ).pack(side="right")

        ttk.Label(
            header,
            text="Sécurité garantie : tout fonctionne sur votre ordinateur sans Internet. Vos fichiers originaux ne sont jamais modifiés.",
            foreground="#1f4e79",
        ).pack(anchor="w", pady=(3, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(4, 6))

        self.tab_help = ttk.Frame(self.notebook, padding=14)
        self.tab_setup = ttk.Frame(self.notebook, padding=14)
        self.tab_run = ttk.Frame(self.notebook, padding=14)
        self.tab_audit = ttk.Frame(self.notebook, padding=14)

        self.notebook.add(self.tab_help, text="0. Mode d'emploi")
        self.notebook.add(self.tab_setup, text="1. Dossier & Documents")
        self.notebook.add(self.tab_run, text="2. Lancer l'anonymisation")
        self.notebook.add(self.tab_audit, text="3. Vérifier les noms restants")

        self._build_tab_help()
        self._build_tab_setup()
        self._build_tab_run()
        self._build_tab_audit()

        footer = ttk.Frame(self, padding=(14, 6))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var, foreground="#1f4e79").pack(side="left")

    def _build_tab_help(self) -> None:
        """Onglet 0 : guide pas-à-pas intégré en langage simple."""
        guide_box = tk.Text(
            self.tab_help,
            wrap="word",
            font=("Segoe UI", 10),
            bg="#f8fafc",
            relief="flat",
            padx=14,
            pady=12,
        )
        guide_box.pack(fill="both", expand=True, pady=(0, 10))

        guide_text: str = (
            "BIENVENUE — À QUOI SERT CE LOGICIEL ?\n"
            "Cet outil prépare vos documents confidentiels (comptes rendus médicaux, bilans orthophoniques, "
            "attestations scolaires, échanges avec l'autre parent, SMS, e-mails, courriers employeur) "
            "en remplaçant automatiquement les noms, adresses, téléphones et numéros sensibles par des codes neutres "
            "(ex. « Camille D. », « Dr M. », « [ADRESSE_MASQUEE] », « [NUM_SECU_MASQUE] »).\n"
            "Vous pouvez ensuite transmettre ces fichiers anonymisés à une association, un avocat ou un outil d'aide à la lecture "
            "sans révéler votre identité ni celle de votre enfant.\n\n"
            "COMMENT FAIRE EN 3 ÉTAPES SIMPLES :\n\n"
            "ÉTAPE 1 — Préparer votre dossier (Onglet « 1. Dossier & Documents »)\n"
            "  • Créez un dossier portant un nom simple (ex. « Dossier_Enfant » ou « Dossier_Salarie »).\n"
            "  • Cliquez sur « Ouvrir le dossier où déposer mes documents » et copiez-collez vos fichiers dedans "
            "(PDF, photos/scans, Word, exports SMS, WhatsApp, e-mails, enregistrements vocaux).\n"
            "  • Facultatif : importez votre carnet d'adresses (.csv) pour que vos proches soient reconnus immédiatement.\n\n"
            "ÉTAPE 2 — Lancer le nettoyage automatique (Onglet « 2. Lancer l'anonymisation »)\n"
            "  • Cliquez sur le bouton « 1er passage : Extraire et anonymiser tout ».\n"
            "  • Patientez pendant la barre de progression (le logiciel lit les PDF, les scans et les vocaux tout seul).\n\n"
            "ÉTAPE 3 — Contrôle rapide et récupération (Onglet « 3. Vérifier les noms restants »)\n"
            "  • Le logiciel vous montre les quelques mots douteux qu'il n'était pas sûr de masquer.\n"
            "  • Pour chacun : cliquez sur « Masquer ce nom » s'il s'agit d'une personne, ou « Ignorer » si c'est un mot normal.\n"
            "  • Cliquez sur « Appliquer mes corrections », puis récupérez vos fichiers prêts dans « anonymized_results » !"
        )
        guide_box.insert("1.0", guide_text)
        guide_box.configure(state="disabled")

        nav_row = ttk.Frame(self.tab_help)
        nav_row.pack(fill="x")
        ttk.Button(
            nav_row,
            text="Commencer à l'étape 1 : Préparer mon dossier ->",
            command=lambda: self.notebook.select(self.tab_setup),
        ).pack(side="right")
    def _build_tab_setup(self) -> None:
        """Onglet 1 : choix ou création d'un dossier isolé et dépôt des fichiers."""
        ttk.Label(
            self.tab_setup,
            text="Ici, vous choisissez votre espace de travail et vous déposez les pièces du dossier à protéger.",
            foreground="#333333",
            wraplength=880,
        ).pack(anchor="w", pady=(0, 8))

        grp_ws = ttk.LabelFrame(
            self.tab_setup, text="1. Choisir ou créer un espace dédié (chaque dossier reste séparé)", padding=10
        )
        grp_ws.pack(fill="x", pady=(0, 10))

        row_sel = ttk.Frame(grp_ws)
        row_sel.pack(fill="x", pady=(0, 6))
        ttk.Label(row_sel, text="Dossier actuellement ouvert :").pack(side="left", padx=(0, 8))
        self.combo_ws = ttk.Combobox(
            row_sel, textvariable=self.workspace_choice_var, state="readonly", width=44
        )
        self.combo_ws.pack(side="left", padx=(0, 8))
        self.combo_ws.bind("<<ComboboxSelected>>", self._on_workspace_selected)

        row_new = ttk.Frame(grp_ws)
        row_new.pack(fill="x")
        ttk.Label(row_new, text="Ou créer un nouveau dossier (ex. Sante_Enfant) :").pack(
            side="left", padx=(0, 8)
        )
        ttk.Entry(row_new, textvariable=self.new_ws_name_var, width=26).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(row_new, text="Créer ce dossier", command=self._create_new_workspace).pack(
            side="left"
        )

        grp_files = ttk.LabelFrame(
            self.tab_setup, text="2. Déposer vos pièces justificatives et vos contacts", padding=10
        )
        grp_files.pack(fill="x", pady=(0, 10))

        ttk.Label(
            grp_files,
            text="Formats acceptés : PDF, scans, Word (.docx/.odt), tableaux, e-mails (.mbox/.eml), SMS (.xml), WhatsApp/Teams, vocaux (.mp3/.m4a/.wav).",
            wraplength=860,
            foreground="#444444",
        ).pack(anchor="w", pady=(0, 8))

        btn_row1 = ttk.Frame(grp_files)
        btn_row1.pack(fill="x")
        ttk.Button(
            btn_row1,
            text="Ouvrir le dossier où déposer mes documents",
            command=lambda: self._open_workspace_folder("sources_dir"),
        ).pack(side="left", padx=(0, 10))
        ttk.Button(
            btn_row1,
            text="Importer un carnet de contacts (.csv) (facultatif)",
            command=self._import_csv_dialog,
        ).pack(side="left")

        grp_out = ttk.LabelFrame(
            self.tab_setup, text="3. Récupérer vos fichiers anonymisés (une fois le traitement terminé)", padding=10
        )
        grp_out.pack(fill="x")
        ttk.Button(
            grp_out,
            text="Ouvrir le dossier des résultats anonymisés",
            command=lambda: self._open_workspace_folder("results_dir"),
        ).pack(side="left", padx=(0, 10))
        ttk.Button(
            grp_out,
            text="Voir ma liste de noms masqués (manual_contacts.txt)",
            command=lambda: self._open_workspace_file("manual_contacts_file"),
        ).pack(side="left")
        ttk.Button(
            grp_out,
            text="Étape suivante : Lancer ->",
            command=lambda: self.notebook.select(self.tab_run),
        ).pack(side="right")
    def _build_tab_run(self) -> None:
        """Onglet 2 : lancement du pipeline avec explications simples de chaque action."""
        help_box = ttk.LabelFrame(
            self.tab_run, text="Quel bouton choisir ?", padding=10
        )
        help_box.pack(fill="x", pady=(0, 10))
        ttk.Label(
            help_box,
            text=(
                "• « 1er passage : Extraire et anonymiser tout » : à utiliser la première fois ou quand vous ajoutez de nouveaux documents.\n"
                "• « 2e passage rapide : Ré-anonymiser uniquement » : à utiliser après avoir ajouté un nom à masquer (dure quelques secondes).\n"
                "• « Mettre à jour les contacts » : relit votre carnet CSV et repère les contacts dans vos chats/e-mails."
            ),
            wraplength=880,
            justify="left",
        ).pack(anchor="w")

        ctrl_row = ttk.Frame(self.tab_run)
        ctrl_row.pack(fill="x", pady=(0, 10))

        self.btn_full = ttk.Button(
            ctrl_row,
            text="1er passage : Extraire et anonymiser tout",
            command=lambda: self._start_job("full"),
        )
        self.btn_full.pack(side="left", padx=(0, 8))

        self.btn_anon_only = ttk.Button(
            ctrl_row,
            text="2e passage rapide : Ré-anonymiser uniquement",
            command=lambda: self._start_job("anonymize_only"),
        )
        self.btn_anon_only.pack(side="left", padx=(0, 8))

        self.btn_contacts = ttk.Button(
            ctrl_row,
            text="Mettre à jour les contacts",
            command=lambda: self._start_job("contacts"),
        )
        self.btn_contacts.pack(side="left")

        self.progress = ttk.Progressbar(self.tab_run, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 8))

        ttk.Label(
            self.tab_run,
            text="Suivi détaillé du traitement en cours :",
            foreground="#444444",
        ).pack(anchor="w", pady=(0, 4))

        self.log_text = tk.Text(
            self.tab_run, height=18, wrap="word", font=("Consolas", 9), state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)

    def _build_tab_audit(self) -> None:
        """Onglet 3 : validation visuelle de audits/residual_names_copy.txt."""
        help_audit = ttk.LabelFrame(
            self.tab_audit, text="Comment vérifier cette liste ?", padding=10
        )
        help_audit.pack(fill="x", pady=(0, 8))
        ttk.Label(
            help_audit,
            text=(
                "Après chaque passage, le logiciel liste ci-dessous les mots avec majuscule qui pourraient encore être des noms de personnes.\n"
                "1) Cliquez sur une ligne : si c'est une personne ou un organisme à cacher, cliquez sur « Masquer ce nom ».\n"
                "2) Si c'est un mot normal (ex. « Tribunal », « Orthophoniste »), cliquez sur « Ignorer ce mot ».\n"
                "3) Quand vous avez fini, cliquez sur « Appliquer mes corrections » en bas à droite."
            ),
            wraplength=880,
            justify="left",
        ).pack(anchor="w")

        top_info = ttk.Frame(self.tab_audit)
        top_info.pack(fill="x", pady=(0, 6))
        self.audit_count_var = tk.StringVar(value="0 élément(s) à vérifier.")
        ttk.Label(top_info, textvariable=self.audit_count_var, font=("Segoe UI", 9, "bold")).pack(
            side="left"
        )
        ttk.Button(top_info, text="Actualiser la liste", command=self._refresh_audit_list).pack(
            side="right"
        )

        cols = ("candidate", "alias")
        self.audit_tree = ttk.Treeview(
            self.tab_audit, columns=cols, show="headings", selectmode="browse", height=13
        )
        self.audit_tree.heading("candidate", text="Mot ou nom repéré dans vos documents")
        self.audit_tree.heading("alias", text="Code qui le remplacera")
        self.audit_tree.column("candidate", width=420)
        self.audit_tree.column("alias", width=340)
        self.audit_tree.pack(fill="both", expand=True, pady=(0, 10))

        act_row = ttk.Frame(self.tab_audit)
        act_row.pack(fill="x")
        ttk.Button(
            act_row,
            text="Masquer ce nom (c'est une personne)",
            command=self._approve_selected_audit,
        ).pack(side="left", padx=(0, 10))
        ttk.Button(
            act_row,
            text="Ignorer ce mot (faux positif)",
            command=self._exclude_selected_audit,
        ).pack(side="left", padx=(0, 10))
        ttk.Button(
            act_row,
            text="Appliquer mes corrections (2e passage rapide)",
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
            messagebox.showwarning("Nom requis", "Veuillez saisir un nom de dossier (ex. Dossier_Enfant).")
            return
        try:
            ini_path: str = self.controller.create_workspace(raw_name)
            self.new_ws_name_var.set("")
            self._refresh_workspaces(select_ini=ini_path)
            self.status_var.set(f"Dossier prêt : {os.path.dirname(ini_path)}")
            messagebox.showinfo(
                "Dossier créé",
                "Votre nouvel espace est prêt !\n\n"
                "Cliquez maintenant sur « Ouvrir le dossier où déposer mes documents » pour y glisser vos fichiers.",
            )
        except OSError as exc:
            messagebox.showerror("Erreur", str(exc))

    def _open_path_in_os(self, target_path: str) -> None:
        """Ouvre un dossier ou un fichier dans le gestionnaire natif du système."""
        if not os.path.exists(target_path):
            messagebox.showinfo("Information", f"Aucun fichier généré pour le moment :\n{target_path}")
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
            self._append_log(f"[CONTACTS] Carnet importé : {dest}")
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
            messagebox.showwarning("Configuration manquante", "Aucun dossier sélectionné.")
            return

        self.is_running = True
        self._set_buttons_state(False)
        self.progress.start(12)
        self.notebook.select(self.tab_run)
        self.status_var.set("Traitement en cours, veuillez patienter...")

        cmd: List[str] = self.controller.build_cli_command(ini_path, mode)
        self._append_log(f"\n>>> Lancement : {' '.join(cmd)}")

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
            self.after(0, self._on_job_finished, ret, mode)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_job_finished(self, return_code: int, mode: str) -> None:
        """Réactive l'interface et actualise l'audit une fois le traitement terminé."""
        self.progress.stop()
        self.is_running = False
        self._set_buttons_state(True)
        self._refresh_audit_list()
        if return_code == 0:
            self.status_var.set("Traitement terminé avec succès.")
            self._append_log("[OK] Traitement terminé.")
            if mode in {"full", "anonymize_only"}:
                cands = self.controller.load_audit_candidates(self.current_ini_var.get())
                if cands:
                    self.notebook.select(self.tab_audit)
                    messagebox.showinfo(
                        "Vérification recommandée",
                        f"Le traitement est terminé !\n\n"
                        f"{len(cands)} nom(s) potentiel(s) sont affichés dans l'onglet 3 pour contrôle rapide.",
                    )
                else:
                    messagebox.showinfo(
                        "Terminé — 0 nom résiduel",
                        "Tout est propre ! Aucun nom résiduel n'a été détecté.\n"
                        "Vous pouvez ouvrir le dossier des résultats anonymisés dans l'onglet 1.",
                    )
        else:
            self.status_var.set(f"Traitement terminé avec avertissement (code {return_code}).")
            self._append_log(f"[ATTENTION] Code retour : {return_code}")

    def _refresh_audit_list(self) -> None:
        """Recharge les candidats de residual_names_copy.txt dans le tableau."""
        for item in self.audit_tree.get_children():
            self.audit_tree.delete(item)
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            self.audit_count_var.set("0 élément(s) à vérifier.")
            return
        candidates: List[Tuple[str, str]] = self.controller.load_audit_candidates(ini_path)
        for cand, alias in candidates:
            self.audit_tree.insert("", "end", values=(cand, alias))
        self.audit_count_var.set(f"{len(candidates)} élément(s) à vérifier dans ce dossier.")

    def _approve_selected_audit(self) -> None:
        """Enregistre la ligne sélectionnée dans manual_contacts.txt."""
        sel = self.audit_tree.selection()
        if not sel:
            messagebox.showinfo("Sélection requise", "Cliquez d'abord sur une ligne du tableau.")
            return
        vals = self.audit_tree.item(next(iter(sel)), "values")
        if len(vals) < 2:
            return
        cand_txt, alias_txt = str(vals), str(vals)
        ini_path: str = self.current_ini_var.get()
        self.controller.approve_audit_mask(ini_path, cand_txt, alias_txt)
        self._refresh_audit_list()
        self.status_var.set(f"Ajouté aux noms à masquer : {cand_txt} -> {alias_txt}")

    def _exclude_selected_audit(self) -> None:
        """Ajoute les mots de la ligne sélectionnée dans data/mots_exclus.txt."""
        sel = self.audit_tree.selection()
        if not sel:
            messagebox.showinfo("Sélection requise", "Cliquez d'abord sur une ligne du tableau.")
            return
        vals = self.audit_tree.item(next(iter(sel)), "values")
        if not vals:
            return
        cand_txt: str = str(vals)
        ini_path: str = self.current_ini_var.get()
        self.controller.exclude_audit_false_positive(ini_path, cand_txt)
        self._refresh_audit_list()
        self.status_var.set(f"Mot courant ignoré : {cand_txt}")


def main() -> None:
    """Point d'entrée de l'interface graphique."""
    app = AnonymizerGuiApp()
    app.mainloop()


if __name__ == "__main__":
    main()
