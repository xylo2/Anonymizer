# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, Optional, Set, Tuple
from doc_anonymizer.gui_dialogs import BeforeAfterPreviewDialog
from doc_anonymizer.text_utils import DocumentTextUtils


class GuiAuditExportMixin:
    """Mixin gérant la relecture des noms résiduels, les requêtes IA, le Pack Avocat et la désanonymisation."""

    controller: Any
    current_ini_var: tk.StringVar
    status_var: tk.StringVar
    workflow_mode: str

    def _update_export_mode_visibility(self) -> None:
        self.frame_export_ia.pack_forget()  # type: ignore[attr-defined]
        self.frame_export_lawyer.pack_forget()  # type: ignore[attr-defined]
        (self.frame_export_lawyer if self.workflow_mode == "lawyer" else self.frame_export_ia).pack(fill="both", expand=True)  # type: ignore[attr-defined]

    def _on_prompt_selected(self, _event: object = None) -> None:
        choice: str = self.prompt_choice_var.get()  # type: ignore[attr-defined]
        idx: int = next((i for i, (lbl, _) in enumerate(self.controller.AI_PROMPT_TEMPLATES) if lbl == choice), 0)
        if 0 <= idx < len(self.controller.AI_PROMPT_TEMPLATES):
            _, body = self.controller.AI_PROMPT_TEMPLATES[idx]
            self.txt_prompt_preview.delete("1.0", "end")  # type: ignore[attr-defined]
            self.txt_prompt_preview.insert("1.0", body)  # type: ignore[attr-defined]

    def _copy_selected_prompt(self) -> None:
        txt: str = self.txt_prompt_preview.get("1.0", "end-1c").strip()  # type: ignore[attr-defined]
        if txt:
            self.clipboard_clear()  # type: ignore[attr-defined]
            self.clipboard_append(txt)  # type: ignore[attr-defined]
            self.status_var.set("Requête IA copiée dans le presse-papiers !")
            messagebox.showinfo("Copié", "La requête IA a été copiée.")

    def _load_audit_counts_map(self, ini_path: str) -> Dict[str, int]:
        paths = self.controller.resolve_workspace_paths(ini_path)
        state_file: str = os.path.join(paths["results_dir"], ".anonymization_state.json")
        if not os.path.isfile(state_file):
            return {}
        try:
            with open(state_file, "r", encoding="utf-8") as f_st:
                payload = json.load(f_st)
            raw_counts = payload.get("compteur_paires", {}) if isinstance(payload, dict) else {}
            if isinstance(raw_counts, dict):
                normalized_map: Dict[str, int] = {}
                for k, v in raw_counts.items():
                    norm_k: str = DocumentTextUtils.normalize_word(str(k))
                    if norm_k:
                        normalized_map[norm_k] = normalized_map.get(norm_k, 0) + int(v)
                return normalized_map
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        return {}

    def _refresh_audit_list(self, keep_index: int = 0) -> None:
        for item in self.audit_tree.get_children():  # type: ignore[attr-defined]
            self.audit_tree.delete(item)  # type: ignore[attr-defined]
        self.audit_alias_edit_var.set("")  # type: ignore[attr-defined]
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        candidates = self.controller.load_audit_candidates(ini_path)
        counts_map: Dict[str, int] = self._load_audit_counts_map(ini_path)
        for cand, alias in candidates:
            occ: int = counts_map.get(DocumentTextUtils.normalize_word(cand), 1)
            self.audit_tree.insert("", "end", values=(f"{occ}x", cand, alias))  # type: ignore[attr-defined]
        self.audit_count_var.set(f"{len(candidates)} élément(s) à vérifier (raccourcis : Entrée = Aperçu, M = Masquer, I = Ignorer).")  # type: ignore[attr-defined]
        children = self.audit_tree.get_children()  # type: ignore[attr-defined]
        if children:
            next_iid = children[min(max(0, keep_index), len(children) - 1)]
            self.audit_tree.selection_set(next_iid)  # type: ignore[attr-defined]
            self.audit_tree.focus(next_iid)  # type: ignore[attr-defined]
            self._on_audit_row_selected()
    def _get_selected_audit_pair(self) -> Optional[Tuple[str, str, int]]:
        sel = self.audit_tree.selection()  # type: ignore[attr-defined]
        if not sel:
            return None
        iid: str = next(iter(sel))
        row_idx: int = list(self.audit_tree.get_children()).index(iid)  # type: ignore[attr-defined]
        vals = tuple(self.audit_tree.item(iid, "values"))  # type: ignore[attr-defined]
        if len(vals) >= 3:
            _, cand_txt, alias_txt = vals
            return str(cand_txt).strip(), str(alias_txt).strip(), row_idx
        if len(vals) == 2:
            cand_txt, alias_txt = vals
            return str(cand_txt).strip(), str(alias_txt).strip(), row_idx
        return None

    def _on_audit_row_selected(self, _event: object = None) -> None:
        pair = self._get_selected_audit_pair()
        if pair is not None:
            _, alias_txt, _ = pair
            self.audit_alias_edit_var.set(alias_txt)  # type: ignore[attr-defined]

    def _open_before_after_preview(self) -> None:
        pair = self._get_selected_audit_pair()
        if pair is None:
            messagebox.showinfo("Sélection requise", "Cliquez d'abord sur une ligne du tableau.")
            return
        cand_txt, default_alias, _ = pair
        alias_txt: str = self.audit_alias_edit_var.get().strip() or default_alias  # type: ignore[attr-defined]
        occs = self.controller.load_audit_occurrences(self.current_ini_var.get(), cand_txt)
        BeforeAfterPreviewDialog(self, cand_txt, alias_txt, occs, on_approve=self._approve_selected_audit, on_exclude=self._exclude_selected_audit)  # type: ignore[arg-type]

    def _approve_selected_audit(self) -> None:
        pair = self._get_selected_audit_pair()
        if pair is not None:
            cand_txt, default_alias, row_idx = pair
            alias_txt: str = self.audit_alias_edit_var.get().strip() or default_alias  # type: ignore[attr-defined]
            self.controller.approve_audit_mask(self.current_ini_var.get(), cand_txt, alias_txt)
            self._refresh_audit_list(keep_index=row_idx)
            self.status_var.set(f"Règle ajoutée : « {cand_txt} » -> « {alias_txt} ».")

    def _exclude_selected_audit(self) -> None:
        pair = self._get_selected_audit_pair()
        if pair is not None:
            cand_txt, _, row_idx = pair
            self.controller.exclude_audit_false_positive(self.current_ini_var.get(), cand_txt)
            self._refresh_audit_list(keep_index=row_idx)
            self.status_var.set(f"Faux positif ignoré : « {cand_txt} ».")

    def _apply_audit_and_go_export(self) -> None:
        self._start_job("anonymize_only", go_export_after=True)  # type: ignore[attr-defined]

    def _export_lawyer_pack(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        paths = self.controller.resolve_workspace_paths(ini_path)
        selected_set: Optional[Set[str]] = None
        if self.lawyer_filter_mode_var.get() == "ai_list":  # type: ignore[attr-defined]
            raw_list: str = self.txt_ai_pieces_list.get("1.0", "end-1c").strip()  # type: ignore[attr-defined]
            selected_set = self.controller.resolve_ai_selected_extracted_files(ini_path, raw_list)
            if not selected_set:
                messagebox.showwarning("Aucune pièce reconnue", "Aucun chemin valide trouvé dans la liste collée.")
                return
        from doc_anonymizer.dossier_exporter import LawyerDossierExporter
        exporter = LawyerDossierExporter(results_dir=paths["results_dir"], export_dir=os.path.join(os.path.dirname(os.path.abspath(ini_path)), "pack_avocat"), transcriptions_dir=paths["transcriptions_dir"], sources_dir=paths["sources_dir"], mapping_file=paths["mapping_file"], selected_extracted_files=selected_set)
        count, out_folder = exporter.export_lawyer_pack()
        if count == 0:
            messagebox.showinfo("Aucune pièce extraite", "Lancez d'abord l'étape 5 avant de générer le Pack Avocat.")
            return
        messagebox.showinfo("Pack Avocat Nominatif prêt", f"{count} pièce(s) numérotée(s) et classée(s) chronologiquement !\nDossier :\n{out_folder}")
        self._open_path_in_os(out_folder)  # type: ignore[attr-defined]
    def _sync_archived_deanon_files(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path:
            return
        archived: list[str] = self.controller.list_archived_ai_files(ini_path)
        for p in archived:
            if p not in self.deanon_files:  # type: ignore[attr-defined]
                self.deanon_files.append(p)  # type: ignore[attr-defined]
        if self.deanon_files and not self.deanon_proposals:  # type: ignore[attr-defined]
            self._run_deanon_analysis()

    def _select_deanon_files(self) -> None:
        from tkinter import filedialog

        if not self.current_ini_var.get():
            messagebox.showwarning("Dossier requis", "Ouvrez d'abord un dossier à l'étape 0.")
            return
        picked = filedialog.askopenfilenames(
            title="Sélectionner les documents retournés par l'IA",
            filetypes=[
                ("Documents pris en charge", "*.txt *.md *.doc *.docx *.odt *.rtf *.html *.csv"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not picked:
            return
        for p in picked:
            norm_p: str = os.path.normpath(p)
            if norm_p not in self.deanon_files:  # type: ignore[attr-defined]
                self.deanon_files.append(norm_p)  # type: ignore[attr-defined]
        self._run_deanon_analysis()

    def _clear_deanon_files(self) -> None:
        self.deanon_files = []  # type: ignore[attr-defined]
        self.deanon_proposals = []  # type: ignore[attr-defined]
        self.deanon_files_var.set("Aucun document IA sélectionné pour le moment.")  # type: ignore[attr-defined]
        self.deanon_edit_val_var.set("")  # type: ignore[attr-defined]
        self._render_deanon_tree()

    def _run_deanon_analysis(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path or not self.deanon_files:  # type: ignore[attr-defined]
            return
        try:
            proposals, _, archived_paths = self.controller.analyze_ai_files_for_deanonymization(ini_path, self.deanon_files)  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("Erreur d'analyse", f"Impossible d'analyser les fichiers :\n{exc}")
            return
        self.deanon_files = archived_paths  # type: ignore[attr-defined]
        self.deanon_proposals = proposals  # type: ignore[attr-defined]
        names_preview: str = ", ".join(os.path.basename(p) for p in self.deanon_files[:4])  # type: ignore[attr-defined]
        extra: str = f" (+{len(self.deanon_files) - 4})" if len(self.deanon_files) > 4 else ""  # type: ignore[attr-defined]
        self.deanon_files_var.set(f"{len(self.deanon_files)} fichier(s) archivé(s) dans retour_ia_brut/ : {names_preview}{extra}")  # type: ignore[attr-defined]
        self._render_deanon_tree()
        self.status_var.set(f"Analyse terminée : {len(proposals)} terme(s) anonymisé(s) détecté(s).")

    def _render_deanon_tree(self) -> None:
        if not hasattr(self, "deanon_tree"):
            return
        for iid in self.deanon_tree.get_children():  # type: ignore[attr-defined]
            self.deanon_tree.delete(iid)  # type: ignore[attr-defined]
        for idx, item in enumerate(self.deanon_proposals):  # type: ignore[attr-defined]
            is_on: bool = bool(item.get("apply")) and bool(str(item.get("proposed") or "").strip())
            mark: str = "✓ Oui" if is_on else "✕ Non"
            tag: str = "kept" if is_on else "ignored"
            self.deanon_tree.insert(  # type: ignore[attr-defined]
                "",
                "end",
                iid=str(idx),
                values=(mark, item.get("token", ""), item.get("proposed", ""), item.get("status", ""), item.get("count", 1), item.get("context", "")),
                tags=(tag,),
            )

    def _on_deanon_row_selected(self, _event: object = None) -> None:
        sel = self.deanon_tree.selection()  # type: ignore[attr-defined]
        if not sel:
            return
        idx_s: str = next(iter(sel))
        if idx_s.isdigit() and 0 <= int(idx_s) < len(self.deanon_proposals):  # type: ignore[attr-defined]
            item = self.deanon_proposals[int(idx_s)]  # type: ignore[attr-defined]
            self.deanon_edit_val_var.set(str(item.get("proposed") or ""))  # type: ignore[attr-defined]
            alts: list[str] = [str(a) for a in item.get("alternatives", []) if str(a).strip()]
            if hasattr(self, "combo_deanon_alts"):
                if alts:
                    header_lbl: str = f"Choix probables ({len(alts)})..."
                    self.combo_deanon_alts.configure(values=[header_lbl] + alts)  # type: ignore[attr-defined]
                    self.deanon_alt_var.set(header_lbl)  # type: ignore[attr-defined]
                else:
                    self.combo_deanon_alts.configure(values=["Aucun choix probable"])  # type: ignore[attr-defined]
                    self.deanon_alt_var.set("Aucun choix probable")  # type: ignore[attr-defined]

    def _on_deanon_alt_picked(self) -> None:
        picked: str = self.deanon_alt_var.get().strip()  # type: ignore[attr-defined]
        if picked and not picked.startswith(("Choix probables", "Aucun choix")):
            self.deanon_edit_val_var.set(picked)  # type: ignore[attr-defined]
            self._apply_deanon_row_edit()

    def _apply_deanon_row_edit(self) -> None:
        sel = self.deanon_tree.selection()  # type: ignore[attr-defined]
        if not sel:
            messagebox.showinfo("Sélection requise", "Sélectionnez d'abord une ligne dans le tableau.")
            return
        idx: int = int(next(iter(sel)))
        new_val: str = self.deanon_edit_val_var.get().strip()  # type: ignore[attr-defined]
        if 0 <= idx < len(self.deanon_proposals):  # type: ignore[attr-defined]
            self.deanon_proposals[idx]["proposed"] = new_val  # type: ignore[attr-defined]
            self.deanon_proposals[idx]["apply"] = bool(new_val)  # type: ignore[attr-defined]
            if new_val:
                self.deanon_proposals[idx]["status"] = "Validé manuellement"  # type: ignore[attr-defined]
            self._render_deanon_tree()
            self.deanon_tree.selection_set(str(idx))  # type: ignore[attr-defined]

    def _toggle_deanon_row_apply(self) -> None:
        sel = self.deanon_tree.selection()  # type: ignore[attr-defined]
        if not sel:
            return
        idx: int = int(next(iter(sel)))
        if 0 <= idx < len(self.deanon_proposals):  # type: ignore[attr-defined]
            cur: bool = bool(self.deanon_proposals[idx].get("apply"))  # type: ignore[attr-defined]
            self.deanon_proposals[idx]["apply"] = not cur  # type: ignore[attr-defined]
            self._render_deanon_tree()
            self.deanon_tree.selection_set(str(idx))  # type: ignore[attr-defined]

    def _export_deanonymized_files(self) -> None:
        ini_path: str = self.current_ini_var.get()
        if not ini_path or not self.deanon_files:  # type: ignore[attr-defined]
            messagebox.showwarning("Aucun fichier", "Ajoutez d'abord au moins un document retourné par l'IA.")
            return
        try:
            exported, out_dir = self.controller.export_deanonymized_ai_files(ini_path, self.deanon_files, self.deanon_proposals)  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("Erreur d'export", f"Impossible de générer les documents :\n{exc}")
            return
        messagebox.showinfo("Documents nominatifs générés", f"{len(exported)} fichier(s) créé(s) avec le suffixe _nominatif dans :\n{out_dir}")
        self._open_path_in_os(out_dir)  # type: ignore[attr-defined]
