# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Set, Tuple


class AnonymizerGuiController:
    """Contrôleur métier indépendant de l'interface graphique."""

    AI_PROMPT_TEMPLATES: List[Tuple[str, str]] = [
        (
            "1. Bilan médico-social (MDPH / suivi enfant)",
            "Tu es un assistant spécialisé en droit médico-social et accompagnement du handicap. "
            "Analyse ces pièces anonymisées pour rédiger une synthèse chronologique claire du parcours "
            "médical, paramédical et scolaire (difficultés constatées, bilans, préconisations, besoins). "
            "À la fin de ton analyse, liste impérativement les chemins exacts des fichiers pertinents "
            "(# SOURCE TRANSCRIPTION : ...) à retenir pour le dossier officiel.",
        ),
        (
            "2. Prud'hommes — Paiement d'heures supplémentaires",
            "Tu es un assistant en droit du travail français. Analyse ces pièces anonymisées pour relever "
            "tous les éléments prouvant l'accomplissement d'heures supplémentaires non rémunérées "
            "(horaires, plannings, courriels/messages tardifs, charge de travail, demandes de la hiérarchie). "
            "Dresse un tableau chronologique des faits et, à la fin, liste impérativement les chemins exacts "
            "des fichiers pertinents (# SOURCE TRANSCRIPTION : ...) à transmettre à mon avocat.",
        ),
        (
            "3. Dossier judiciaire — Harcèlement moral ou sexuel",
            "Tu es un assistant juridique spécialisé dans la protection contre le harcèlement. "
            "Analyse ces pièces anonymisées pour identifier les agissements répétés, propos déplacés, "
            "mises à l'écart, sanctions injustifiées et leur impact sur la santé. Classe les faits par date "
            "et, à la fin, liste impérativement les chemins exacts des fichiers pertinents "
            "(# SOURCE TRANSCRIPTION : ...) pour constituer le dossier judiciaire.",
        ),
        (
            "4. Reconnaissance de maladie professionnelle",
            "Tu es un assistant spécialisé en droit de la Sécurité sociale. Analyse ces pièces anonymisées "
            "pour établir le lien entre les conditions de travail / expositions professionnelles et la "
            "pathologie diagnostiquée (certificats médicaux, arrêts, fiches de poste, alertes). "
            "À la fin, liste impérativement les chemins exacts des fichiers pertinents "
            "(# SOURCE TRANSCRIPTION : ...) à joindre au dossier.",
        ),
        (
            "5. Reconnaissance d'accident du travail",
            "Tu es un assistant spécialisé en accidents du travail. Analyse ces pièces anonymisées pour "
            "reconstituer précisément le fait accidentel soudain survenu par le fait ou à l'occasion du travail "
            "(date, heure, lieu, circonstances, témoins, premiers soins et certificats initiaux). "
            "À la fin, liste impérativement les chemins exacts des fichiers pertinents "
            "(# SOURCE TRANSCRIPTION : ...) à retenir pour le dossier.",
        ),
        (
            "6. Prud'hommes — Faute grave de l'employeur / Prise d'acte",
            "Tu es un assistant en droit du travail français. Analyse ces pièces anonymisées pour relever "
            "tous les manquements graves de l'employeur rendant impossible la poursuite du contrat de travail "
            "(non-paiement de salaire, atteinte à la sécurité, modification unilatérale, humiliations). "
            "Classe les preuves par date et, à la fin, liste impérativement les chemins exacts des fichiers "
            "pertinents (# SOURCE TRANSCRIPTION : ...) à remettre à mon avocat.",
        ),
    ]

    def __init__(self, project_root: str) -> None:
        self.project_root: str = os.path.abspath(project_root)
        self.workspaces_dir: str = os.path.join(self.project_root, "dossiers")
        self.shared_data_dir: str = os.path.join(self.project_root, "data")

    @staticmethod
    def sanitize_workspace_name(raw_name: str) -> str:
        cleaned: str = re.sub(r"[^A-Za-zÀ-ÿ0-9_\-]+", "_", (raw_name or "").strip())
        return re.sub(r"_+", "_", cleaned).strip("_")

    def list_workspaces(self) -> List[Tuple[str, str]]:
        found: List[Tuple[str, str]] = []
        if os.path.isdir(self.workspaces_dir):
            for entry in sorted(os.listdir(self.workspaces_dir)):
                sub_dir: str = os.path.join(self.workspaces_dir, entry)
                sub_ini: str = os.path.join(sub_dir, "config.ini")
                if os.path.isdir(sub_dir) and os.path.isfile(sub_ini):
                    found.append((entry, sub_ini))
        return found
    def create_workspace(self, raw_name: str) -> str:
        safe_name: str = self.sanitize_workspace_name(raw_name)
        if not safe_name:
            raise ValueError("Le nom du dossier ne peut pas être vide.")
        ws_dir: str = os.path.join(self.workspaces_dir, safe_name)
        for sub in ("input_documents", "input_contacts", "output_contacts", "extracted_texts", "anonymized_results", "audits"):
            os.makedirs(os.path.join(ws_dir, sub), exist_ok=True)
        manual_file: str = os.path.join(ws_dir, "output_contacts", "manual_contacts.txt")
        if not os.path.exists(manual_file):
            with open(manual_file, "w", encoding="utf-8") as f_man:
                f_man.write("# Règles manuelles spécifiques à ce dossier (Identifiant = Alias)\n")
        ini_path: str = os.path.join(ws_dir, "config.ini")
        if not os.path.exists(ini_path):
            ini_content: str = (
                "[paths]\nroot_dir = .\nsources_dir = input_documents\ntranscriptions_dir = extracted_texts\n"
                "results_dir = anonymized_results\ninput_contacts_dir = input_contacts\n"
                "contacts_file = output_contacts/contacts.txt\ndiscovered_contacts_file = output_contacts/discovered_email_contacts.txt\n"
                "discovered_chats_file = output_contacts/discovered_chat_contacts.txt\nmanual_contacts_file = output_contacts/manual_contacts.txt\n"
                "audit_report_file = audits/residual_names_audit.txt\naudit_copy_file = audits/residual_names_copy.txt\n"
                "\n[files]\ncsv_directory = input_contacts\n"
                f"first_names_file = {os.path.join(self.shared_data_dir, 'prenoms.txt')}\n"
                f"excluded_words_file = {os.path.join(self.shared_data_dir, 'mots_exclus.txt')}\n"
                f"surname_collisions_file = {os.path.join(self.shared_data_dir, 'collisions_noms.txt')}\n"
                f"locations_file = {os.path.join(self.shared_data_dir, 'villes_masquees.txt')}\n"
            )
            with open(ini_path, "w", encoding="utf-8") as f_ini:
                f_ini.write(ini_content)
        return ini_path

    @staticmethod
    def resolve_workspace_paths(ini_path: str) -> Dict[str, str]:
        ws_root: str = os.path.dirname(os.path.abspath(ini_path))
        return {
            "workspace_root": ws_root, "ini_path": os.path.abspath(ini_path),
            "sources_dir": os.path.join(ws_root, "input_documents"),
            "transcriptions_dir": os.path.join(ws_root, "extracted_texts"),
            "input_contacts_dir": os.path.join(ws_root, "input_contacts"),
            "results_dir": os.path.join(ws_root, "anonymized_results"),
            "manual_contacts_file": os.path.join(ws_root, "output_contacts", "manual_contacts.txt"),
            "audit_copy_file": os.path.join(ws_root, "audits", "residual_names_copy.txt"),
            "audit_report_file": os.path.join(ws_root, "audits", "residual_names_audit.txt"),
            "state_file": os.path.join(ws_root, "anonymized_results", ".anonymization_state.json"),
            "mapping_file": os.path.join(ws_root, "audits", "source_files_mapping.json"),
        }

    def detect_zip_files(self, ini_path: str) -> List[str]:
        src_dir: str = self.resolve_workspace_paths(ini_path)["sources_dir"]
        if not os.path.isdir(src_dir):
            return []
        return [os.path.join(r, fn) for r, _, fs in os.walk(src_dir) for fn in sorted(fs) if fn.lower().endswith(".zip") and not fn.startswith(".")]

    def load_dashboard_stats(self, ini_path: str) -> Dict[str, Any]:
        default_stats: Dict[str, Any] = {
            "documents_traites": 0, "documents_extraits": 0, "noms_masques": 0,
            "coordonnees_masquees": 0, "identifiants_masques": 0, "lieux_dates_masques": 0,
            "zip_ignores": self.detect_zip_files(ini_path),
        }
        state_path: str = self.resolve_workspace_paths(ini_path)["state_file"]
        if os.path.isfile(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f_in:
                    st = json.load(f_in).get("stats_anonymisation")
                if isinstance(st, dict):
                    default_stats.update(st)
            except Exception:
                pass
        return default_stats
    def load_audit_occurrences(self, ini_path: str, candidate: str, context_lines: int = 4) -> List[Dict[str, str]]:
        from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
        from doc_anonymizer.config_manager import PipelineConfig

        paths: Dict[str, str] = self.resolve_workspace_paths(ini_path)
        target_files: List[str] = []
        if os.path.isfile(paths["state_file"]):
            try:
                with open(paths["state_file"], "r", encoding="utf-8") as f_in:
                    files_map = json.load(f_in).get("fichiers_par_nom", {})
                if isinstance(files_map, dict):
                    for k_name, flist in files_map.items():
                        if k_name.strip().lower() == candidate.strip().lower() and isinstance(flist, list):
                            target_files = [str(p) for p in flist if os.path.isfile(str(p))]
                            break
            except Exception:
                pass
        if not target_files and os.path.isdir(paths["transcriptions_dir"]):
            target_files = [os.path.join(r, fn) for r, _, fs in os.walk(paths["transcriptions_dir"]) for fn in sorted(fs) if fn.lower().endswith(".txt")]

        runner = DocumentAnonymizationRunner(PipelineConfig(ini_path))
        runner.initialize()
        tokens: List[str] = [re.escape(t) for t in candidate.strip().split() if t]
        pat = re.compile(rf"\b(?:{tokens[0]}\s+{tokens[1]}|{tokens[1]}\s+{tokens[0]})\b", re.IGNORECASE) if len(tokens) == 2 else re.compile(rf"\b{re.escape(candidate.strip())}\b", re.IGNORECASE)
        occurrences: List[Dict[str, str]] = []
        for fpath in target_files:
            try:
                lines: List[str] = open(fpath, "r", encoding="utf-8", errors="ignore").read().splitlines()
            except OSError:
                continue
            for idx, ln in enumerate(lines):
                if pat.search(ln):
                    raw_ex: str = "\n".join(lines[max(0, idx - context_lines) : min(len(lines), idx + context_lines + 1)])
                    occurrences.append({"file_label": os.path.basename(fpath), "file_path": fpath, "line_num": str(idx + 1), "raw_excerpt": raw_ex, "anon_excerpt": runner.anonymize_text(raw_ex)})
                    if len(occurrences) >= 25:
                        return occurrences
        return occurrences

    def resolve_ai_selected_extracted_files(self, ini_path: str, ai_response_text: str) -> Set[str]:
        from doc_anonymizer.config_manager import PipelineConfig
        from tools.copy_unmasked_transcriptions import UnmaskedTranscriptionCopier

        paths: Dict[str, str] = self.resolve_workspace_paths(ini_path)
        raw_targets: List[str] = re.findall(r"`([^`\r\n]+?\.txt)`", ai_response_text or "", re.IGNORECASE)
        raw_targets.extend(re.findall(r"#\s*SOURCE TRANSCRIPTION\s*:\s*(.+?\.txt)", ai_response_text or "", re.IGNORECASE))
        for line in (ai_response_text or "").splitlines():
            cleaned: str = re.sub(r"^[\-\*\•\d\.\)\s]+", "", line.strip()).strip("`\"' ")
            if cleaned.lower().endswith(".txt") and ("/" in cleaned or "\\" in cleaned):
                raw_targets.append(cleaned)
        unique_targets: List[str] = list(dict.fromkeys(t.strip() for t in raw_targets if t.strip()))
        if not unique_targets:
            return set()
        copier = UnmaskedTranscriptionCopier(config=PipelineConfig(ini_path), mapping_file=paths["mapping_file"])
        json_lookup = copier._load_json_mapping()
        resolved: Set[str] = set()
        for tgt in unique_targets:
            norm_k: str = os.path.normpath(tgt).lower()
            src_p: Optional[str] = json_lookup.get(norm_k) or json_lookup.get(os.path.basename(norm_k)) or copier._resolve_via_fallback(tgt)
            if src_p and os.path.exists(src_p):
                resolved.add(os.path.normpath(src_p))
        return resolved

    def import_contacts_csv(self, ini_path: str, csv_source_path: str) -> str:
        if not csv_source_path or not os.path.isfile(csv_source_path):
            raise FileNotFoundError("Fichier CSV introuvable.")
        paths: Dict[str, str] = self.resolve_workspace_paths(ini_path)
        os.makedirs(paths["input_contacts_dir"], exist_ok=True)
        dest_path: str = os.path.join(paths["input_contacts_dir"], os.path.basename(csv_source_path))
        if os.path.abspath(csv_source_path) != os.path.abspath(dest_path):
            shutil.copy2(csv_source_path, dest_path)
        return dest_path

    def load_audit_candidates(self, ini_path: str) -> List[Tuple[str, str]]:
        audit_copy: str = self.resolve_workspace_paths(ini_path)["audit_copy_file"]
        candidates: List[Tuple[str, str]] = []
        if os.path.isfile(audit_copy):
            for raw_line in open(audit_copy, "r", encoding="utf-8", errors="ignore"):
                line: str = raw_line.strip()
                if line and not line.startswith("#") and "=" in line:
                    left, right = line.split("=", 1)
                    if left.strip() and right.strip():
                        candidates.append((left.strip(), right.strip()))
        return candidates

    def _remove_line_from_audit(self, audit_copy_path: str, target_left: str) -> None:
        if not os.path.isfile(audit_copy_path):
            return
        kept: List[str] = [ln for ln in open(audit_copy_path, "r", encoding="utf-8", errors="ignore") if not (ln.strip() and not ln.strip().startswith("#") and "=" in ln and ln.split("=", 1)[0].strip().lower() == target_left.strip().lower())]
        with open(audit_copy_path, "w", encoding="utf-8") as f_out:
            f_out.writelines(kept)

    def approve_audit_mask(self, ini_path: str, candidate: str, alias: str) -> None:
        paths: Dict[str, str] = self.resolve_workspace_paths(ini_path)
        manual_path: str = paths["manual_contacts_file"]
        os.makedirs(os.path.dirname(manual_path), exist_ok=True)
        existing = {ln.split("=", 1)[0].strip().lower() for ln in open(manual_path, "r", encoding="utf-8", errors="ignore") if "=" in ln and not ln.strip().startswith("#")} if os.path.isfile(manual_path) else set()
        if candidate.strip().lower() not in existing:
            with open(manual_path, "a", encoding="utf-8") as f_out:
                f_out.write(f"\n{candidate.strip()} = {alias.strip()}\n")
        self._remove_line_from_audit(paths["audit_copy_file"], candidate)

    def exclude_audit_false_positive(self, ini_path: str, candidate: str) -> None:
        paths: Dict[str, str] = self.resolve_workspace_paths(ini_path)
        excl_path: str = os.path.join(self.shared_data_dir, "mots_exclus.txt")
        os.makedirs(os.path.dirname(excl_path), exist_ok=True)
        existing = {ln.strip().lower() for ln in open(excl_path, "r", encoding="utf-8", errors="ignore") if ln.strip() and not ln.strip().startswith("#")} if os.path.isfile(excl_path) else set()
        new_tokens = [t.strip().lower() for t in re.split(r"[\s'\-]+", candidate.strip()) if len(t.strip()) >= 3 and t.strip().lower() not in existing]
        if new_tokens:
            with open(excl_path, "a", encoding="utf-8") as f_out:
                for tok in new_tokens:
                    f_out.write(f"\n{tok}")
        self._remove_line_from_audit(paths["audit_copy_file"], candidate)

    def build_cli_command(self, ini_path: str, mode: str) -> List[str]:
        if mode == "contacts":
            return [sys.executable, os.path.join(self.project_root, "run_contacts.py"), "--config", ini_path]
        script = os.path.join(self.project_root, "run_documents.py")
        flags = {"extract_only": ["--extract-only"], "anonymize_only": ["--anonymize-only", "--reset-results"], "full_reset": ["--reset-results"]}.get(mode, [])
        return [sys.executable, script, "--config", ini_path, *flags]
