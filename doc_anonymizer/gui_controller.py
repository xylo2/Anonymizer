# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Set, Tuple


class AnonymizerGuiController:
    """
    Contrôleur métier indépendant de l'interface graphique pour gérer les
    dossiers isolés, l'audit Avant/Après, le tableau de bord et la passerelle
    entre le mode IA (anonymisé) et le mode Avocat (nominatif).
    """

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
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned
    def list_workspaces(self) -> List[Tuple[str, str]]:
        """Retourne uniquement les espaces de travail isolés créés dans dossiers/."""
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
        for sub in (
            "input_documents",
            "input_contacts",
            "output_contacts",
            "extracted_texts",
            "anonymized_results",
            "audits",
        ):
            os.makedirs(os.path.join(ws_dir, sub), exist_ok=True)

        manual_file: str = os.path.join(ws_dir, "output_contacts", "manual_contacts.txt")
        if not os.path.exists(manual_file):
            with open(manual_file, "w", encoding="utf-8") as f_man:
                f_man.write("# Règles manuelles spécifiques à ce dossier (Identifiant = Alias)\n")

        shared_first_names: str = os.path.join(self.shared_data_dir, "prenoms.txt")
        shared_excluded: str = os.path.join(self.shared_data_dir, "mots_exclus.txt")
        shared_collisions: str = os.path.join(self.shared_data_dir, "collisions_noms.txt")
        shared_cities: str = os.path.join(self.shared_data_dir, "villes.txt")

        ini_path: str = os.path.join(ws_dir, "config.ini")
        if not os.path.exists(ini_path):
            ini_content: str = (
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = input_documents\n"
                "transcriptions_dir = extracted_texts\n"
                "results_dir = anonymized_results\n"
                "input_contacts_dir = input_contacts\n"
                "contacts_file = output_contacts/contacts.txt\n"
                "discovered_emails_file = output_contacts/discovered_email_contacts.txt\n"
                "discovered_chats_file = output_contacts/discovered_chat_contacts.txt\n"
                "manual_contacts_file = output_contacts/manual_contacts.txt\n"
                "audit_report_file = audits/residual_names_audit.txt\n"
                "audit_copy_file = audits/residual_names_copy.txt\n"
                "\n[files]\n"
                f"first_names_file = {shared_first_names}\n"
                f"excluded_words_file = {shared_excluded}\n"
                f"surname_collisions_file = {shared_collisions}\n"
                f"masked_locations_file = {shared_cities}\n"
            )
            with open(ini_path, "w", encoding="utf-8") as f_ini:
                f_ini.write(ini_content)
        return ini_path

    @staticmethod
    def resolve_workspace_paths(ini_path: str) -> Dict[str, str]:
        ws_root: str = os.path.dirname(os.path.abspath(ini_path))
        return {
            "workspace_root": ws_root,
            "ini_path": os.path.abspath(ini_path),
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
        """Retourne la liste triée des archives .zip présentes dans input_documents/."""
        paths: Dict[str, str] = self.resolve_workspace_paths(ini_path)
        src_dir: str = paths["sources_dir"]
        if not os.path.isdir(src_dir):
            return []
        found: List[str] = []
        for root_p, _, files in os.walk(src_dir):
            for fn in sorted(files):
                if fn.lower().endswith(".zip") and not fn.startswith("."):
                    found.append(os.path.join(root_p, fn))
        return found

    def load_dashboard_stats(self, ini_path: str) -> Dict[str, Any]:
        """Lit les statistiques d'anonymisation/extraction depuis .anonymization_state.json."""
        default_stats: Dict[str, Any] = {
            "documents_traites": 0,
            "documents_extraits": 0,
            "noms_masques": 0,
            "coordonnees_masquees": 0,
            "identifiants_masques": 0,
            "lieux_dates_masques": 0,
            "zip_ignores": self.detect_zip_files(ini_path),
        }
        paths: Dict[str, str] = self.resolve_workspace_paths(ini_path)
        state_path: str = paths["state_file"]
        if not os.path.isfile(state_path):
            return default_stats
        try:
            with open(state_path, "r", encoding="utf-8") as f_in:
                payload = json.load(f_in)
            st = payload.get("stats_anonymisation")
            if isinstance(st, dict):
                default_stats.update(st)
        except Exception:
            pass
        return default_stats

    def load_audit_occurrences(
        self, ini_path: str, candidate: str, context_lines: int = 4
    ) -> List[Dict[str, str]]:
        """
        Retourne toutes les occurrences d'un candidat d'audit avec leur extrait brut
        et leur extrait anonymisé côte à côte pour la fenêtre Avant/Après.
        """
        from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
        from doc_anonymizer.config_manager import PipelineConfig

        paths: Dict[str, str] = self.resolve_workspace_paths(ini_path)
        state_path: str = paths["state_file"]
        target_files: List[str] = []
        if os.path.isfile(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f_in:
                    st = json.load(f_in)
                files_map = st.get("fichiers_par_nom", {})
                if isinstance(files_map, dict):
                    for k_name, flist in files_map.items():
                        if k_name.strip().lower() == candidate.strip().lower() and isinstance(flist, list):
                            target_files = [str(p) for p in flist if os.path.isfile(str(p))]
                            break
            except Exception:
                pass

        if not target_files and os.path.isdir(paths["transcriptions_dir"]):
            for root_p, _, files in os.walk(paths["transcriptions_dir"]):
                for fn in sorted(files):
                    if fn.lower().endswith(".txt"):
                        target_files.append(os.path.join(root_p, fn))

        cfg = PipelineConfig(ini_path)
        runner = DocumentAnonymizationRunner(cfg)
        runner.initialize()

        tokens: List[str] = [re.escape(t) for t in candidate.strip().split() if t]
        if len(tokens) == 2:
            pat = re.compile(
                rf"\b(?:{tokens[0]}\s+{tokens[1]}|{tokens[1]}\s+{tokens[0]})\b",
                re.IGNORECASE,
            )
        else:
            pat = re.compile(rf"\b{re.escape(candidate.strip())}\b", re.IGNORECASE)

        occurrences: List[Dict[str, str]] = []
        for fpath in target_files:
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f_txt:
                    lines: List[str] = f_txt.read().splitlines()
            except OSError:
                continue
            for idx, ln in enumerate(lines):
                if pat.search(ln):
                    start_i: int = max(0, idx - context_lines)
                    end_i: int = min(len(lines), idx + context_lines + 1)
                    raw_excerpt: str = "\n".join(lines[start_i:end_i])
                    anon_excerpt: str = runner.anonymize_text(raw_excerpt)
                    occurrences.append({
                        "file_label": os.path.basename(fpath),
                        "file_path": fpath,
                        "line_num": str(idx + 1),
                        "raw_excerpt": raw_excerpt,
                        "anon_excerpt": anon_excerpt,
                    })
                    if len(occurrences) >= 25:
                        return occurrences
        return occurrences
    def resolve_ai_selected_extracted_files(
        self, ini_path: str, ai_response_text: str
    ) -> Set[str]:
        """
        Extrait les chemins anonymisés mentionnés dans la réponse de l'IA et les résout
        en chemins de transcriptions brutes nominatives (extracted_texts/*.txt).
        """
        from doc_anonymizer.config_manager import PipelineConfig
        from tools.copy_unmasked_transcriptions import UnmaskedTranscriptionCopier

        paths: Dict[str, str] = self.resolve_workspace_paths(ini_path)
        raw_targets: List[str] = []
        for m_bt in re.findall(r"`([^`\r\n]+?\.txt)`", ai_response_text or "", re.IGNORECASE):
            raw_targets.append(m_bt.strip())
        for m_hdr in re.findall(
            r"#\s*SOURCE TRANSCRIPTION\s*:\s*(.+?\.txt)",
            ai_response_text or "",
            re.IGNORECASE,
        ):
            raw_targets.append(m_hdr.strip())
        for line in (ai_response_text or "").splitlines():
            cleaned: str = re.sub(r"^[\-\*\•\d\.\)\s]+", "", line.strip()).strip("`\"' ")
            if cleaned.lower().endswith(".txt") and ("/" in cleaned or "\\" in cleaned):
                raw_targets.append(cleaned)

        unique_targets: List[str] = list(dict.fromkeys(raw_targets))
        if not unique_targets:
            return set()

        cfg = PipelineConfig(ini_path)
        copier = UnmaskedTranscriptionCopier(config=cfg, mapping_file=paths["mapping_file"])
        json_lookup = copier._load_json_mapping()
        resolved: Set[str] = set()
        for tgt in unique_targets:
            norm_k: str = os.path.normpath(tgt).lower()
            src_p: Optional[str] = json_lookup.get(norm_k) or json_lookup.get(os.path.basename(norm_k))
            if not src_p or not os.path.exists(src_p):
                src_p = copier._resolve_via_fallback(tgt)
            if src_p and os.path.exists(src_p):
                resolved.add(os.path.normpath(src_p))
        return resolved

    def import_contacts_csv(self, ini_path: str, csv_source_path: str) -> str:
        """Copie un fichier CSV de contacts dans le dossier input_contacts du profil."""
        if not csv_source_path or not os.path.isfile(csv_source_path):
            raise FileNotFoundError("Fichier CSV introuvable.")
        paths: Dict[str, str] = self.resolve_workspace_paths(ini_path)
        os.makedirs(paths["input_contacts_dir"], exist_ok=True)
        dest_path: str = os.path.join(
            paths["input_contacts_dir"], os.path.basename(csv_source_path)
        )
        if os.path.abspath(csv_source_path) != os.path.abspath(dest_path):
            shutil.copy2(csv_source_path, dest_path)
        return dest_path

    def load_audit_candidates(self, ini_path: str) -> List[Tuple[str, str]]:
        """Lit audits/residual_names_copy.txt et retourne [(Nom_Détecté, Alias_Suggéré), ...]."""
        paths: Dict[str, str] = self.resolve_workspace_paths(ini_path)
        audit_copy: str = paths["audit_copy_file"]
        candidates: List[Tuple[str, str]] = []
        if not os.path.isfile(audit_copy):
            return candidates
        with open(audit_copy, "r", encoding="utf-8", errors="ignore") as f_in:
            for raw_line in f_in:
                line: str = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                left, right = line.split("=", 1)
                cand: str = left.strip()
                alias: str = right.strip()
                if cand and alias:
                    candidates.append((cand, alias))
        return candidates

    def _remove_line_from_audit(self, audit_copy_path: str, target_left: str) -> None:
        if not os.path.isfile(audit_copy_path):
            return
        kept_lines: List[str] = []
        with open(audit_copy_path, "r", encoding="utf-8", errors="ignore") as f_in:
            for raw_line in f_in:
                stripped: str = raw_line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    left_part, _ = stripped.split("=", 1)
                    if left_part.strip().lower() == target_left.strip().lower():
                        continue
                kept_lines.append(raw_line)
        with open(audit_copy_path, "w", encoding="utf-8") as f_out:
            f_out.writelines(kept_lines)

    def approve_audit_mask(self, ini_path: str, candidate: str, alias: str) -> None:
        paths: Dict[str, str] = self.resolve_workspace_paths(ini_path)
        manual_path: str = paths["manual_contacts_file"]
        os.makedirs(os.path.dirname(manual_path), exist_ok=True)
        existing_keys: set[str] = set()
        if os.path.isfile(manual_path):
            with open(manual_path, "r", encoding="utf-8", errors="ignore") as f_in:
                for ln in f_in:
                    if "=" in ln and not ln.strip().startswith("#"):
                        k, _ = ln.split("=", 1)
                        existing_keys.add(k.strip().lower())
        if candidate.strip().lower() not in existing_keys:
            with open(manual_path, "a", encoding="utf-8") as f_out:
                f_out.write(f"\n{candidate.strip()} = {alias.strip()}\n")
        self._remove_line_from_audit(paths["audit_copy_file"], candidate)

    def exclude_audit_false_positive(self, ini_path: str, candidate: str) -> None:
        paths: Dict[str, str] = self.resolve_workspace_paths(ini_path)
        excl_path: str = os.path.join(self.shared_data_dir, "mots_exclus.txt")
        os.makedirs(os.path.dirname(excl_path), exist_ok=True)
        existing_words: set[str] = set()
        if os.path.isfile(excl_path):
            with open(excl_path, "r", encoding="utf-8", errors="ignore") as f_in:
                for ln in f_in:
                    w: str = ln.strip().lower()
                    if w and not w.startswith("#"):
                        existing_words.add(w)
        tokens: List[str] = [
            t.strip().lower()
            for t in re.split(r"[\s'\-]+", candidate.strip())
            if len(t.strip()) >= 3
        ]
        new_tokens: List[str] = [t for t in tokens if t not in existing_words]
        if new_tokens:
            with open(excl_path, "a", encoding="utf-8") as f_out:
                for tok in new_tokens:
                    f_out.write(f"\n{tok}")
        self._remove_line_from_audit(paths["audit_copy_file"], candidate)

    def build_cli_command(self, ini_path: str, mode: str) -> List[str]:
        if mode == "contacts":
            script: str = os.path.join(self.project_root, "run_contacts.py")
            return [sys.executable, script, "--config", ini_path]
        script = os.path.join(self.project_root, "run_documents.py")
        if mode == "extract_only":
            return [sys.executable, script, "--config", ini_path, "--extract-only"]
        if mode == "anonymize_only":
            return [sys.executable, script, "--config", ini_path, "--anonymize-only", "--reset-results"]
        if mode == "full_reset":
            return [sys.executable, script, "--config", ini_path, "--reset-results"]
        return [sys.executable, script, "--config", ini_path]
