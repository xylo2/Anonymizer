# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import re
import shutil
from typing import Any, Dict, List, Set, Tuple
import xml.etree.ElementTree as ET
from doc_anonymizer.contact_csv_importer import ContactCatalogImporter, normalize_phone_identifier
from doc_anonymizer.duplicate_files_manager import DuplicateFilesManager
from doc_anonymizer.text_utils import DocumentTextUtils


class SmsFilterManager:
    """Gère la détection des sauvegardes SMS (.xml), le cache et le filtrage des numéros."""

    def __init__(self, paths: Dict[str, str], importer: ContactCatalogImporter) -> None:
        self.paths: Dict[str, str] = paths
        self.importer: ContactCatalogImporter = importer

    @staticmethod
    def _canonical_phone(raw_phone: str) -> str:
        """Normalise un numéro SMS au format canonique FR 0XXXXXXXXX ou +CCXXXX."""
        norm: str = normalize_phone_identifier(raw_phone)
        if not norm:
            return ""
        any_p: str = DocumentTextUtils.normalize_any_phone(norm)
        return any_p if any_p else norm

    @staticmethod
    def is_short_number(phone: str) -> bool:
        """Indique si un identifiant SMS est un numéro court (4-7 chiffres) ou automate."""
        clean: str = (phone or "").strip()
        if not clean or "@" in clean:
            return False
        if any(ch.isalpha() for ch in clean):
            return True
        digits: str = re.sub(r"\D", "", clean)
        if not digits:
            return False
        return len(digits) < 9 if clean.startswith("+") else len(digits) < 8

    @staticmethod
    def is_sms_backup_xml(xml_path: str) -> bool:
        """Vérifie si un fichier .xml est un export SMS/MMS (SMS Backup & Restore)."""
        if not xml_path or not os.path.isfile(xml_path) or not xml_path.lower().endswith(".xml"):
            return False
        try:
            with open(xml_path, "r", encoding="utf-8", errors="ignore") as f_in:
                head: str = f_in.read(2048).lower()
            return any(tag in head for tag in ("<smses", "<sms ", "<mms "))
        except OSError:
            return False
    def known_phone_names_map(self) -> Dict[str, str]:
        known: Dict[str, str] = {}
        for item in self.importer.load_filter_items():
            label: str = str(item.get("display_name") or item.get("alias") or "").strip()
            for ident in item.get("identifiers", []):
                norm: str = self._canonical_phone(str(ident))
                if norm and "@" not in norm and label:
                    known[norm] = label
        return known

    def list_export_files(self) -> List[str]:
        src_dir: str = self.paths["sources_dir"]
        if not os.path.isdir(src_dir):
            return []
        ignored_dups: Set[str] = DuplicateFilesManager(self.paths).load_ignored_paths()
        found: List[str] = []
        for root, _, files in os.walk(src_dir):
            for fn in sorted(files):
                full_p: str = os.path.normpath(os.path.join(root, fn))
                if os.path.normcase(full_p) in ignored_dups:
                    continue
                if fn.lower().endswith(".xml") and self.is_sms_backup_xml(full_p):
                    found.append(full_p)
        return found

    def import_export_file(self, source_xml_path: str, move: bool = False) -> str:
        dest_dir: str = os.path.join(self.paths["sources_dir"], "sms_exports")
        os.makedirs(dest_dir, exist_ok=True)
        if os.path.abspath(os.path.dirname(source_xml_path)) == os.path.abspath(dest_dir):
            return source_xml_path
        dest_path: str = ContactCatalogImporter._unique_dest_path(
            dest_dir, os.path.basename(source_xml_path)
        )
        if move:
            shutil.move(source_xml_path, dest_path)
        else:
            shutil.copy2(source_xml_path, dest_path)
        return dest_path

    @staticmethod
    def _stat_sort_key(pair: Tuple[str, Dict[str, Any]]) -> Tuple[int, str]:
        phone_key, info_dict = pair
        return (-int(info_dict.get("count", 0)), phone_key)
    def _get_cache_file_path(self) -> str:
        ws_root: str = self.paths.get("workspace_root") or os.path.dirname(self.paths["contacts_dir"])
        return os.path.join(ws_root, "audits", ".sms_numbers_cache.json")

    def _scan_xml_files_cached(self, xml_files: List[str]) -> Dict[str, Dict[str, Any]]:
        """Lit les statistiques par numéro depuis le cache disque si les XML n'ont pas changé."""
        sig: List[List[Any]] = []
        for xp in sorted(xml_files):
            try:
                st = os.stat(xp)
                sig.append([os.path.abspath(xp), int(st.st_size), int(st.st_mtime_ns)])
            except OSError:
                continue

        cache_path: str = self._get_cache_file_path()
        if sig and os.path.isfile(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f_c:
                    cached = json.load(f_c)
                if isinstance(cached, dict) and cached.get("signature") == sig and isinstance(cached.get("stats"), dict):
                    return dict(cached["stats"])
            except (OSError, json.JSONDecodeError):
                pass

        stats: Dict[str, Dict[str, Any]] = {}
        for xml_path in xml_files:
            try:
                for _, elem in ET.iterparse(xml_path, events=("end",)):
                    if elem.tag in ("sms", "mms"):
                        raw_addr: str = str(elem.attrib.get("address") or "").strip()
                        c_name: str = str(elem.attrib.get("contact_name") or "").strip()
                        for part in DocumentTextUtils.split_sms_addresses(raw_addr):
                            norm_num: str = self._canonical_phone(part)
                            if norm_num and (any(ch.isdigit() for ch in norm_num) or any(ch.isalpha() for ch in norm_num)):
                                entry = stats.setdefault(norm_num, {"phone": norm_num, "name": "", "count": 0})
                                entry["count"] = int(entry["count"]) + 1
                                if not entry["name"] and c_name and c_name != "(Unknown)":
                                    entry["name"] = c_name
                    elem.clear()
            except (OSError, ET.ParseError):
                continue

        if sig:
            try:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                DocumentTextUtils.atomic_write_text(
                    cache_path,
                    json.dumps({"signature": sig, "stats": stats}, ensure_ascii=False),
                )
            except OSError:
                pass
        return stats

    def load_number_filter_items(self) -> List[Dict[str, Any]]:
        wl_file: str = os.path.join(self.paths["contacts_dir"], "whitelist_contacts.json")
        existing_wl: Set[str] = set()
        if os.path.isfile(wl_file):
            try:
                with open(wl_file, "r", encoding="utf-8") as f_wl:
                    data = json.load(f_wl)
                if isinstance(data, list):
                    existing_wl = {self._canonical_phone(str(x)) for x in data if str(x).strip()}
            except (OSError, json.JSONDecodeError):
                pass
        known_names: Dict[str, str] = self.known_phone_names_map()
        stats = self._scan_xml_files_cached(self.list_export_files())

        items: List[Dict[str, Any]] = []
        for norm_num, info in sorted(stats.items(), key=self._stat_sort_key):
            short_flag: bool = self.is_short_number(norm_num)
            is_kept: bool = (norm_num in existing_wl) if existing_wl else (norm_num in known_names and not short_flag)
            resolved_name: str = known_names.get(norm_num) or str(info.get("name") or "")
            default_lbl: str = "[Numéro court / Automate]" if short_flag else "Correspondant SMS non enregistré"
            disp_name: str = f"[Numéro court] {resolved_name}" if (short_flag and resolved_name) else (resolved_name or default_lbl)
            items.append({
                "phone": norm_num,
                "display_name": disp_name,
                "count": int(info.get("count", 0)),
                "is_short": short_flag,
                "selected": is_kept,
            })
        return items

    def save_number_filter_selection(self, items: List[Dict[str, Any]]) -> int:
        os.makedirs(self.paths["contacts_dir"], exist_ok=True)
        wl_file: str = os.path.join(self.paths["contacts_dir"], "whitelist_contacts.json")
        current_entries: List[str] = []
        if os.path.isfile(wl_file):
            try:
                with open(wl_file, "r", encoding="utf-8") as f_wl:
                    data = json.load(f_wl)
                if isinstance(data, list):
                    current_entries = [str(x).strip() for x in data if str(x).strip()]
            except (OSError, json.JSONDecodeError):
                current_entries = []
        managed_phones: Set[str] = {self._canonical_phone(str(it.get("phone") or "")) for it in items}
        kept_phones: List[str] = [self._canonical_phone(str(it.get("phone") or "")) for it in items if it.get("selected") and str(it.get("phone") or "").strip()]
        preserved: List[str] = [val for val in current_entries if self._canonical_phone(val) not in managed_phones]
        merged: List[str] = list(dict.fromkeys(preserved + kept_phones))
        with open(wl_file, "w", encoding="utf-8") as f_out:
            json.dump(merged, f_out, ensure_ascii=False, indent=2)
        self.importer.sync_selected_extraction_file(merged)
        return len(kept_phones)
