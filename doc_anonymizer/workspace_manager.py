import configparser
import hashlib
import json
import os
import re
import shutil
from typing import Dict, List, Tuple
from doc_anonymizer import config_manager as _cfg_mod
from doc_anonymizer.chat_filter_manager import ChatFilterManager
from doc_anonymizer.contact_csv_importer import ContactCatalogImporter
from doc_anonymizer.duplicate_files_manager import DuplicateFilesManager
from doc_anonymizer.linked_sources_manager import LinkedSourcesManager
from doc_anonymizer.sms_filter_manager import SmsFilterManager

DEFAULT_WORKSPACES_BASE_DIR: str = getattr(
    _cfg_mod, "DEFAULT_WORKSPACES_BASE_DIR", "dossiers"
)


class WorkspaceManager:
    """
    Gère l'isolation des espaces de travail (dossiers/<nom>/), la résolution des
    chemins INI, le tri automatique avec cache et la détection des archives ZIP.
    """

    def __init__(self, root_dir: str) -> None:
        self.root_dir: str = os.path.abspath(root_dir)
        self.workspaces_base_dir: str = os.path.join(
            self.root_dir, DEFAULT_WORKSPACES_BASE_DIR
        )
        self._last_ws_state_file: str = os.path.join(
            self.workspaces_base_dir, ".last_workspace.json"
        )

    def get_last_opened_workspace(self) -> str:
        """Retourne le chemin absolu du dernier config.ini ouvert s'il existe."""
        if not os.path.isfile(self._last_ws_state_file):
            return ""
        try:
            with open(self._last_ws_state_file, "r", encoding="utf-8") as f_in:
                payload = json.load(f_in)
            if isinstance(payload, dict):
                ini_p: str = str(payload.get("last_ini_path") or "").strip()
                if ini_p and os.path.isfile(ini_p):
                    return os.path.abspath(ini_p)
        except (OSError, json.JSONDecodeError):
            pass
        return ""

    def save_last_opened_workspace(self, ini_path: str) -> None:
        """Mémorise le dernier dossier ouvert pour le proposer au démarrage."""
        if not ini_path:
            return
        abs_ini: str = os.path.abspath(ini_path)
        if not os.path.isfile(abs_ini):
            return
        try:
            os.makedirs(self.workspaces_base_dir, exist_ok=True)
            with open(self._last_ws_state_file, "w", encoding="utf-8") as f_out:
                json.dump(
                    {
                        "last_ini_path": abs_ini,
                        "workspace_name": os.path.basename(
                            os.path.dirname(abs_ini)
                        ),
                    },
                    f_out,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError:
            pass
    def list_workspaces(self) -> List[Tuple[str, str]]:
        results: List[Tuple[str, str]] = []
        if not os.path.isdir(self.workspaces_base_dir):
            return results
        for entry in sorted(os.listdir(self.workspaces_base_dir)):
            ws_dir: str = os.path.join(self.workspaces_base_dir, entry)
            ini_path: str = os.path.join(ws_dir, "config.ini")
            if os.path.isdir(ws_dir) and os.path.isfile(ini_path):
                results.append((entry, os.path.abspath(ini_path)))
        return results

    def create_workspace(self, workspace_name: str) -> str:
        clean_name: str = re.sub(
            r'[<>:"/\\|?*]+', "_", workspace_name.strip()
        ).strip(". ")
        if not clean_name:
            raise ValueError("Veuillez saisir un nom de dossier valide.")
        ws_dir: str = os.path.abspath(
            os.path.join(self.workspaces_base_dir, clean_name)
        )
        ini_path: str = os.path.join(ws_dir, "config.ini")
        if os.path.exists(ini_path):
            raise ValueError(f"Le dossier « {clean_name} » existe déjà.")
        for sub in (
            "input_documents", "input_contacts", "contacts",
            "transcriptions", "results", "audits",
        ):
            os.makedirs(os.path.join(ws_dir, sub), exist_ok=True)
        for rel_file in (
            "contacts/contacts.txt",
            "contacts/contacts_manuels.txt",
            "contacts/mots_exclus_dossier.txt",
            "audits/residual_names_copy.txt",
        ):
            full_f: str = os.path.join(ws_dir, rel_file)
            if not os.path.exists(full_f):
                open(full_f, "w", encoding="utf-8").close()
        shared_data: str = os.path.join(self.root_dir, "data")
        ws_locations: str = os.path.join(ws_dir, "contacts", "villes_masquees.txt")
        default_locations: str = os.path.join(shared_data, "villes_masquees.txt")
        if os.path.isfile(default_locations):
            shutil.copy2(default_locations, ws_locations)
        elif not os.path.exists(ws_locations):
            open(ws_locations, "w", encoding="utf-8").close()

        cfg = configparser.ConfigParser()
        cfg["paths"] = {
            "root_dir": ws_dir,
            "sources_dir": os.path.join(ws_dir, "input_documents"),
            "input_contacts_dir": os.path.join(ws_dir, "input_contacts"),
            "contacts_dir": os.path.join(ws_dir, "contacts"),
            "transcriptions_dir": os.path.join(ws_dir, "transcriptions"),
            "results_dir": os.path.join(ws_dir, "results"),
            "contacts_file": os.path.join(ws_dir, "contacts", "contacts.txt"),
            "selected_extraction_contacts_file": os.path.join(
                ws_dir, "contacts", "selected_extraction_contacts.txt"
            ),
            "surnames_contacts_file": os.path.join(
                ws_dir, "contacts", "contact_surnames.txt"
            ),
            "mapping_file": os.path.join(ws_dir, "contacts", "mapping.json"),
            "manual_contacts_file": os.path.join(
                ws_dir, "contacts", "contacts_manuels.txt"
            ),
            "discovered_contacts_file": os.path.join(
                ws_dir, "contacts", "discovered_email_contacts.txt"
            ),
            "discovered_chats_file": os.path.join(
                ws_dir, "contacts", "discovered_chat_contacts.txt"
            ),
            "all_sms_numbers_file": os.path.join(
                ws_dir, "audits", "all_sms_numbers.txt"
            ),
            "all_emails_file": os.path.join(
                ws_dir, "audits", "all_found_emails.txt"
            ),
            "audit_report_file": os.path.join(
                ws_dir, "audits", "residual_names_audit.txt"
            ),
            "audit_copy_file": os.path.join(
                ws_dir, "audits", "residual_names_copy.txt"
            ),
            "extraction_report_file": os.path.join(
                ws_dir, "audits", "extraction_report.txt"
            ),
        }
        cfg["files"] = {
            "csv_directory": os.path.join(ws_dir, "input_contacts"),
            "first_names_file": os.path.join(shared_data, "prenoms.txt"),
            "locations_file": ws_locations,
            "surname_collisions_file": os.path.join(
                shared_data, "collisions_noms.txt"
            ),
            "excluded_words_file": os.path.join(
                ws_dir, "contacts", "mots_exclus_dossier.txt"
            ),
            "inverted_output_file": os.path.join(ws_dir, "contacts", "contacts.txt"),
        }
        cfg["extraction"] = {
            "enable_ocr": "true",
            "enable_audio": "true",
            "ignored_dirs": (
                "extracted_texts, anonymized_results, output_contacts, audits, "
                "pack_avocat, retour_ia_brut, retour_ia_nominatif, "
                "data, docs, venv, .venv, .git, __pycache__, common, tools, tests"
            ),
        }
        with open(ini_path, "w", encoding="utf-8") as f_ini:
            cfg.write(f_ini)
        self.save_last_opened_workspace(ini_path)
        return ini_path
    @classmethod
    def _ensure_contacts_ini_keys(cls, abs_ini: str, ws_dir: str, cfg: configparser.ConfigParser) -> None:
        """Garantit que csv_directory et les sorties contacts pointent vers le dossier isolé."""
        if not os.path.isfile(abs_ini):
            return
        in_contacts: str = os.path.join(ws_dir, "input_contacts")
        contacts_dir: str = os.path.join(ws_dir, "contacts")
        inter_dir: str = os.path.join(contacts_dir, ".intermediates")
        dirty: bool = False
        if not cfg.has_section("files"):
            cfg.add_section("files")
            dirty = True
        cur_csv: str = cfg.get("files", "csv_directory", fallback="").strip()
        if not cur_csv or not os.path.isabs(cur_csv):
            cfg.set("files", "csv_directory", in_contacts)
            dirty = True
        expected_files: Dict[str, str] = {
            "output_file": os.path.join(inter_dir, "indexed_contacts.txt"),
            "anonymized_output_file": os.path.join(inter_dir, "anonymized_contacts.txt"),
            "surnames_output_file": os.path.join(inter_dir, "contact_surnames.txt"),
            "deduplicated_output_file": os.path.join(inter_dir, "deduplicated_contacts.txt"),
            "suggested_first_names_file": os.path.join(inter_dir, "suggested_first_names.txt"),
            "inverted_output_file": os.path.join(contacts_dir, "contacts.txt"),
            "manual_contacts_file": os.path.join(contacts_dir, "contacts_manuels.txt"),
            "discovered_contacts_file": os.path.join(contacts_dir, "discovered_email_contacts.txt"),
        }
        for key, target_p in expected_files.items():
            cur_v: str = cfg.get("files", key, fallback="").strip()
            if not cur_v or not os.path.isabs(cur_v):
                cfg.set("files", key, target_p)
                dirty = True
        if dirty:
            try:
                with open(abs_ini, "w", encoding="utf-8") as f_out:
                    cfg.write(f_out)
            except OSError:
                pass

    @classmethod
    def resolve_workspace_paths(cls, ini_path: str) -> Dict[str, str]:
        abs_ini: str = os.path.abspath(ini_path)
        ws_dir: str = os.path.dirname(abs_ini)
        cfg = configparser.ConfigParser()
        cfg.read(abs_ini, encoding="utf-8")
        cls._ensure_contacts_ini_keys(abs_ini, ws_dir, cfg)

        def _get(key: str, default_rel: str) -> str:
            raw: str = ""
            for sec in ("paths", "files", "PATHS", "FILES"):
                if cfg.has_option(sec, key):
                    raw = cfg.get(sec, key).strip()
                    break
            val: str = raw or default_rel
            return val if os.path.isabs(val) else os.path.abspath(os.path.join(ws_dir, val))

        return {
            "workspace_root": ws_dir,
            "workspace_dir": ws_dir,
            "sources_dir": _get("sources_dir", "input_documents"),
            "input_contacts_dir": _get("input_contacts_dir", "input_contacts"),
            "contacts_dir": _get("contacts_dir", "contacts"),
            "transcriptions_dir": _get("transcriptions_dir", "transcriptions"),
            "results_dir": _get("results_dir", "results"),
            "contacts_file": _get("contacts_file", os.path.join("contacts", "contacts.txt")),
            "selected_extraction_contacts_file": _get("selected_extraction_contacts_file", os.path.join("contacts", "selected_extraction_contacts.txt")),
            "mapping_file": _get("mapping_file", os.path.join("contacts", "mapping.json")),
            "manual_contacts_file": _get("manual_contacts_file", os.path.join("contacts", "contacts_manuels.txt")),
            "locations_file": _get("locations_file", os.path.join("contacts", "villes_masquees.txt")),
            "audit_copy_file": _get("audit_copy_file", os.path.join("audits", "residual_names_copy.txt")),
            "excluded_words_file": _get("excluded_words_file", os.path.join("contacts", "mots_exclus_dossier.txt")),
            "audit_report_file": _get("audit_report_file", os.path.join("audits", "residual_names_audit.txt")),
        }

    def detect_zip_files(self, ini_path: str) -> List[str]:
        paths = self.resolve_workspace_paths(ini_path)
        src_dir: str = paths["sources_dir"]
        zips: List[str] = []
        if os.path.isdir(src_dir):
            for root_p, _, files in os.walk(src_dir):
                for fn in sorted(files):
                    if fn.lower().endswith(".zip") and not fn.startswith("."):
                        zips.append(os.path.join(root_p, fn))
        linked_files, _ = LinkedSourcesManager(paths["workspace_root"]).expand_linked_files(set())
        for fp in linked_files:
            if fp.lower().endswith(".zip") and fp not in zips:
                zips.append(fp)
        return zips

    @staticmethod
    def compute_sources_signature(paths: Dict[str, str]) -> str:
        """Calcule une empreinte rapide des pièces, liens et carnets."""
        digest = hashlib.sha256()
        for tag, folder in (("S", paths["sources_dir"]), ("C", paths.get("contacts_dir", ""))):
            if not folder or not os.path.isdir(folder):
                continue
            for root_p, dirs, files in os.walk(folder):
                dirs.sort()
                for fn in sorted(files):
                    if fn.startswith("."):
                        continue
                    fp: str = os.path.join(root_p, fn)
                    try:
                        st = os.stat(fp)
                        digest.update(f"{tag}|{fp}|{st.st_size}|{st.st_mtime_ns}\n".encode("utf-8"))
                    except OSError:
                        continue
        links_file: str = os.path.join(paths["workspace_root"], "linked_sources.json")
        if os.path.isfile(links_file):
            try:
                st_l = os.stat(links_file)
                digest.update(f"L|{st_l.st_size}|{st_l.st_mtime_ns}\n".encode("utf-8"))
            except OSError:
                pass
        linked_files, _ = LinkedSourcesManager(paths["workspace_root"]).expand_linked_files(set())
        for fp in sorted(linked_files):
            try:
                st = os.stat(fp)
                digest.update(f"R|{fp}|{st.st_size}|{st.st_mtime_ns}\n".encode("utf-8"))
            except OSError:
                continue
        return digest.hexdigest()

    def auto_organize_dropped_files(self, ini_path: str, force: bool = False) -> Tuple[int, int]:
        paths = self.resolve_workspace_paths(ini_path)
        cache_path: str = os.path.join(paths["workspace_root"], "audits", ".step1_scan_cache.json")
        sig_before: str = self.compute_sources_signature(paths)
        if not force and os.path.isfile(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f_c:
                    cached = json.load(f_c)
                if isinstance(cached, dict) and cached.get("signature") == sig_before:
                    return 0, 0
            except (OSError, json.JSONDecodeError):
                pass

        src_dir: str = paths["sources_dir"]
        sms_dir: str = os.path.abspath(os.path.join(src_dir, "sms_exports"))
        chat_dir: str = os.path.abspath(os.path.join(src_dir, "chat_exports"))
        importer = ContactCatalogImporter(paths, ini_path)
        sms_mgr = SmsFilterManager(paths, importer)
        chat_mgr = ChatFilterManager(paths, importer)
        moved_contacts = moved_sms = 0

        if os.path.isdir(src_dir):
            for root, _, files in os.walk(src_dir):
                abs_r: str = os.path.abspath(root)
                if abs_r.startswith(sms_dir) or abs_r.startswith(chat_dir):
                    continue
                for fn in sorted(files):
                    full_p: str = os.path.join(root, fn)
                    try:
                        if ContactCatalogImporter.is_contact_catalog_file(full_p):
                            importer.import_contact_file(full_p, move_source=True)
                            moved_contacts += 1
                        elif SmsFilterManager.is_sms_backup_xml(full_p):
                            sms_mgr.import_export_file(full_p, move=True)
                            moved_sms += 1
                    except OSError:
                        continue
            chat_mgr.organize_chat_exports(move=True)

        linked_files, _ = LinkedSourcesManager(paths["workspace_root"]).expand_linked_files(set())
        for full_p in linked_files:
            try:
                if ContactCatalogImporter.is_contact_catalog_file(full_p):
                    importer.import_contact_file(full_p, move_source=False)
                    moved_contacts += 1
            except OSError:
                continue

        DuplicateFilesManager(paths).find_duplicate_items()
        sig_after: str = self.compute_sources_signature(paths)
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f_out:
                json.dump({"signature": sig_after, "moved_contacts": moved_contacts, "moved_sms": moved_sms}, f_out, ensure_ascii=False)
        except OSError:
            pass
        return moved_contacts, moved_sms
