# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
import shutil
import sys
from typing import Dict, List, Optional, Tuple


class AnonymizerGuiController:
    """
    Contrôleur métier indépendant de l'interface graphique (Tkinter ou Web locale)
    pour gérer les dossiers/profils isolés, l'import de contacts et la validation
    interactive de l'audit des noms résiduels.
    """

    def __init__(self, project_root: str) -> None:
        """Initialise le contrôleur à partir de la racine du dépôt."""
        self.project_root: str = os.path.abspath(project_root)
        self.workspaces_dir: str = os.path.join(self.project_root, "dossiers")
        self.shared_data_dir: str = os.path.join(self.project_root, "data")

    @staticmethod
    def sanitize_workspace_name(raw_name: str) -> str:
        """Normalise un nom de dossier/profil (ex. 'Dossier Salarié Jean' -> 'Dossier_Salarie_Jean')."""
        cleaned: str = re.sub(r"[^A-Za-zÀ-ÿ0-9_\-]+", "_", (raw_name or "").strip())
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned

    def list_workspaces(self) -> List[Tuple[str, str]]:
        """
        Retourne la liste des profils disponibles sous forme (Libellé, Chemin_config.ini) :
        1) Le dossier principal à la racine s'il possède un config.ini
        2) Chaque sous-dossier de 'dossiers/' possédant un config.ini
        """
        found: List[Tuple[str, str]] = []
        root_ini: str = os.path.join(self.project_root, "config.ini")
        if os.path.isfile(root_ini):
            found.append(("Dossier principal (racine)", root_ini))

        if os.path.isdir(self.workspaces_dir):
            for entry in sorted(os.listdir(self.workspaces_dir)):
                sub_dir: str = os.path.join(self.workspaces_dir, entry)
                sub_ini: str = os.path.join(sub_dir, "config.ini")
                if os.path.isdir(sub_dir) and os.path.isfile(sub_ini):
                    found.append((entry, sub_ini))
        return found

    def create_workspace(self, raw_name: str) -> str:
        """Crée un nouvel espace isolé dans 'dossiers/<nom>/' et retourne le chemin de son config.ini."""
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
        """Résout les principaux dossiers et fichiers à partir d'un fichier config.ini."""
        ws_root: str = os.path.dirname(os.path.abspath(ini_path))
        return {
            "workspace_root": ws_root,
            "ini_path": os.path.abspath(ini_path),
            "sources_dir": os.path.join(ws_root, "input_documents"),
            "input_contacts_dir": os.path.join(ws_root, "input_contacts"),
            "results_dir": os.path.join(ws_root, "anonymized_results"),
            "manual_contacts_file": os.path.join(ws_root, "output_contacts", "manual_contacts.txt"),
            "audit_copy_file": os.path.join(ws_root, "audits", "residual_names_copy.txt"),
            "audit_report_file": os.path.join(ws_root, "audits", "residual_names_audit.txt"),
        }

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
        """Lit audits/residual_names_copy.txt et retourne la liste [(Nom_Détecté, Alias_Suggéré), ...]."""
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
        """Retire une entrée déjà traitée du fichier audits/residual_names_copy.txt."""
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
        """Ajoute 'candidate = alias' dans manual_contacts.txt et le retire de l'audit."""
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
        """Ajoute les mots d'un faux positif dans data/mots_exclus.txt et le retire de l'audit."""
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
        """Construit la ligne de commande Python correspondant à l'action demandée."""
        if mode == "contacts":
            script: str = os.path.join(self.project_root, "run_contacts.py")
            return [sys.executable, script, "--config", ini_path]
        script = os.path.join(self.project_root, "run_documents.py")
        if mode == "anonymize_only":
            return [sys.executable, script, "--config", ini_path, "--anonymize-only", "--reset-results"]
        if mode == "full_reset":
            return [sys.executable, script, "--config", ini_path, "--reset-results"]
        return [sys.executable, script, "--config", ini_path]
