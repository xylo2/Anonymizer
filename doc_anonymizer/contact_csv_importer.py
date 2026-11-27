import csv
import json
import os
import re
import shutil
from typing import Any, Dict, List, Set

_NAME_PARTICLES: Set[str] = {
    "de", "du", "des", "d", "le", "la", "les", "van", "von", "ben", "el", "al", "dos", "da", "di"
}


def normalize_phone_identifier(raw_phone: str) -> str:
    """Normalise un numéro de téléphone (supprime '* ', espaces, tirets et +33 -> 0)."""
    cleaned: str = re.sub(r"[\s\u00a0\u202f.\-()]+", "", raw_phone.lstrip("* ").strip())
    if cleaned.startswith("00") and len(cleaned) > 4:
        cleaned = "+" + cleaned[2:]
    if cleaned.startswith("+33") and len(cleaned) == 12 and cleaned[1:].isdigit():
        cleaned = "0" + cleaned[3:]
    return cleaned


def _format_surname_initials(last_name: str) -> str:
    """Formate les initiales d'un nom de famille en gérant particules et apostrophes."""
    clean_ln: str = re.sub(r"[\s\u00a0\u202f]+", " ", last_name).strip()
    if not clean_ln:
        return ""
    parts: List[str] = [p for p in re.split(r"[\s\-]+", clean_ln) if p]
    initials: List[str] = []
    for part in parts:
        m_apos = re.match(r"^([A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ])(['\u2019])([A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ])", part)
        if m_apos:
            initials.append(f"{m_apos.group(1).upper()}{m_apos.group(2)}{m_apos.group(3).upper()}.")
        else:
            initials.append(f"{part[:1].upper()}.")
    return " ".join(initials)


def build_person_initial_alias(first_name: str, last_name: str, fallback: str = "") -> str:
    """Construit un alias anonymisé 'Prénom N.' en gérant particules et noms composés."""
    fn: str = re.sub(r"[\s\u00a0\u202f]+", " ", first_name).strip()
    ln: str = re.sub(r"[\s\u00a0\u202f]+", " ", last_name).strip()
    if fn and ln:
        return f"{fn} {_format_surname_initials(ln)}"
    tokens: List[str] = [t for t in re.split(r"[\s\u00a0\u202f]+", fallback.strip()) if t]
    if len(tokens) >= 2:
        split_idx: int = len(tokens) - 1
        while split_idx > 1 and tokens[split_idx - 1].lower().rstrip("'\u2019") in _NAME_PARTICLES:
            split_idx -= 1
        return f"{' '.join(tokens[:split_idx])} {_format_surname_initials(' '.join(tokens[split_idx:]))}"
    return fallback.strip()
class ContactCatalogImporter:
    """Gère l'importation et l'indexation des carnets (.csv / .vcf) et la liste blanche contacts."""

    CONTACT_HEADER_HINTS: Set[str] = {
        "first name", "given name", "prénom", "prenom",
        "last name", "family name", "nom de famille", "nom",
        "e-mail 1 - value", "email", "mail", "phone 1 - value", "téléphone", "telephone",
    }

    def __init__(self, paths: Dict[str, str], ini_path: str) -> None:
        self.paths: Dict[str, str] = paths
        self.ini_path: str = ini_path

    @classmethod
    def is_contact_catalog_file(cls, file_path: str) -> bool:
        """Détecte si un fichier .vcf ou .csv est un carnet de contacts exploitable."""
        low: str = file_path.lower()
        if not os.path.isfile(file_path):
            return False
        if low.endswith(".vcf"):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f_v:
                    return "BEGIN:VCARD" in f_v.read(2048).upper()
            except OSError:
                return False
        if not low.endswith(".csv"):
            return False
        try:
            with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f_c:
                first_ln: str = next(iter(f_c.read(4096).splitlines()), "")
            delim: str = ";" if first_ln.count(";") > first_ln.count(",") else ","
            headers = {h.strip().lower() for h in first_ln.split(delim) if h.strip()}
            return bool(headers & cls.CONTACT_HEADER_HINTS)
        except OSError:
            return False

    @staticmethod
    def _is_phone_or_email_col(col_name: str) -> bool:
        low: str = (col_name or "").strip().lower()
        if not low or any(ex in low for ex in ("type", "label", "étiquette", "etiquette", "note", "address", "adresse")):
            return False
        return any(tag in low for tag in ("phone", "tél", "telephone", "mail", "e-mail", "courriel"))

    @staticmethod
    def _unique_dest_path(dest_dir: str, filename: str) -> str:
        candidate: str = os.path.join(dest_dir, filename)
        if not os.path.exists(candidate):
            return candidate
        stem, ext = os.path.splitext(filename)
        idx: int = 2
        while os.path.exists(os.path.join(dest_dir, f"{stem}_{idx}{ext}")):
            idx += 1
        return os.path.join(dest_dir, f"{stem}_{idx}{ext}")
    def parse_file_to_mapping(self, source_file: str, mapping_data: Dict[str, Any]) -> None:
        if source_file.lower().endswith(".csv"):
            with open(source_file, "r", encoding="utf-8-sig", newline="") as f_csv:
                sample: str = f_csv.read(4096)
                f_csv.seek(0)
                first_ln: str = next(iter(sample.splitlines()), "")
                delim: str = ";" if first_ln.count(";") > first_ln.count(",") else ","
                for row in csv.DictReader(f_csv, delimiter=delim):
                    fn: str = (row.get("First Name") or row.get("Given Name") or row.get("Prénom") or "").strip()
                    ln: str = (row.get("Last Name") or row.get("Family Name") or row.get("Nom de famille") or row.get("Nom") or "").strip()
                    full_name: str = f"{fn} {ln}".strip() or (row.get("Name") or row.get("Nom complet") or "").strip()
                    if not full_name:
                        continue
                    alias: str = build_person_initial_alias(fn, ln, fallback=full_name)
                    mapping_data[full_name] = {"alias": alias, "real_name": full_name}
                    for col, val in row.items():
                        raw_v: str = (val or "").strip()
                        if raw_v and self._is_phone_or_email_col(col):
                            for sub in raw_v.split(":::"):
                                clean_sub: str = sub.lstrip("* ").strip()
                                if clean_sub:
                                    norm_v: str = normalize_phone_identifier(clean_sub) if "@" not in clean_sub else clean_sub.lower()
                                    if norm_v:
                                        mapping_data[norm_v] = {"alias": alias, "real_name": full_name}
        elif source_file.lower().endswith(".vcf"):
            from google_contacts_parser.config_manager import ContactsConfig
            from google_contacts_parser.vcard_reader import VCardContactsReader

            for ident, full_name in VCardContactsReader(ContactsConfig(self.ini_path)).parse_file(source_file):
                alias = build_person_initial_alias("", "", fallback=full_name)
                mapping_data[full_name] = {"alias": alias, "real_name": full_name}
                clean_id: str = ident.lstrip("* ").strip()
                norm_v = normalize_phone_identifier(clean_id) if "@" not in clean_id else clean_id.lower()
                if norm_v:
                    mapping_data[norm_v] = {"alias": alias, "real_name": full_name}

    def _compute_contact_activity_counts(self) -> Dict[str, int]:
        """Agrège les volumes d'échanges SMS et Chats depuis les caches du dossier."""
        ws_root: str = self.paths.get("workspace_root") or os.path.dirname(self.paths["contacts_dir"])
        audits_dir: str = os.path.join(ws_root, "audits")
        counts: Dict[str, int] = {}
        sms_cache: str = os.path.join(audits_dir, ".sms_numbers_cache.json")
        if os.path.isfile(sms_cache):
            try:
                with open(sms_cache, "r", encoding="utf-8") as f_s:
                    stats = json.load(f_s).get("stats", {})
                if isinstance(stats, dict):
                    for num, info in stats.items():
                        if isinstance(info, dict):
                            k: str = normalize_phone_identifier(str(num)).lower()
                            counts[k] = counts.get(k, 0) + int(info.get("count", 0))
            except (OSError, json.JSONDecodeError):
                pass
        chat_cache: str = os.path.join(audits_dir, ".chats_filter_cache.json")
        if os.path.isfile(chat_cache):
            try:
                with open(chat_cache, "r", encoding="utf-8") as f_c:
                    metas = json.load(f_c).get("metas", [])
                if isinstance(metas, list):
                    for m in metas:
                        if isinstance(m, dict):
                            cnt: int = int(m.get("count", 0))
                            for p in m.get("participants", []):
                                pk: str = str(p).strip().lower()
                                if pk:
                                    counts[pk] = counts.get(pk, 0) + cnt
            except (OSError, json.JSONDecodeError):
                pass
        return counts
    def import_contact_file(self, source_file: str, move_source: bool = False) -> str:
        os.makedirs(self.paths["input_contacts_dir"], exist_ok=True)
        os.makedirs(self.paths["contacts_dir"], exist_ok=True)
        dest_dir: str = self.paths["input_contacts_dir"]
        dest_path: str = source_file if os.path.abspath(os.path.dirname(source_file)) == os.path.abspath(dest_dir) else self._unique_dest_path(dest_dir, os.path.basename(source_file))
        if dest_path != source_file:
            (shutil.move if move_source else shutil.copy2)(source_file, dest_path)

        prev_states: Dict[str, bool] = {str(it["display_name"]).lower(): bool(it["selected"]) for it in self.load_filter_items()}
        mapping_data: Dict[str, Any] = {}
        if os.path.isfile(self.paths["mapping_file"]):
            try:
                with open(self.paths["mapping_file"], "r", encoding="utf-8") as f_m:
                    loaded = json.load(f_m)
                if isinstance(loaded, dict):
                    mapping_data = loaded
            except (OSError, json.JSONDecodeError):
                pass
        self.parse_file_to_mapping(dest_path, mapping_data)
        with open(self.paths["mapping_file"], "w", encoding="utf-8") as f_out:
            json.dump(mapping_data, f_out, ensure_ascii=False, indent=2)

        merged_contacts: Dict[str, str] = {}
        if os.path.isfile(self.paths["contacts_file"]):
            try:
                with open(self.paths["contacts_file"], "r", encoding="utf-8", errors="ignore") as f_old:
                    for raw_ln in f_old:
                        ln: str = raw_ln.strip()
                        if ln and not ln.startswith("#") and "=" in ln:
                            lk, rv = [x.strip() for x in ln.split("=", 1)]
                            if lk and rv:
                                merged_contacts[lk] = rv
            except OSError:
                pass
        for ident, info in mapping_data.items():
            if isinstance(info, dict) and info.get("alias"):
                merged_contacts[ident] = str(info["alias"]).strip()
        with open(self.paths["contacts_file"], "w", encoding="utf-8") as f_ct:
            for ident, alias_val in sorted(merged_contacts.items(), key=lambda x: next(iter(x)).lower()):
                f_ct.write(f"{ident} = {alias_val}\n")

        updated_items = self.load_filter_items()
        for it in updated_items:
            it["selected"] = prev_states.get(str(it["display_name"]).lower(), True)
        self.save_filter_selection(updated_items)
        return dest_path
    def load_filter_items(self) -> List[Dict[str, Any]]:
        mapping_path, contacts_txt = self.paths["mapping_file"], self.paths["contacts_file"]
        wl_path: str = os.path.join(self.paths["contacts_dir"], "whitelist_contacts.json")
        if not os.path.isfile(mapping_path) and os.path.isdir(self.paths["input_contacts_dir"]):
            c_files = sorted(os.path.join(self.paths["input_contacts_dir"], fn) for fn in os.listdir(self.paths["input_contacts_dir"]) if fn.lower().endswith((".csv", ".vcf")))
            if c_files:
                rebuilt: Dict[str, Any] = {}
                for cf in c_files:
                    self.parse_file_to_mapping(cf, rebuilt)
                os.makedirs(self.paths["contacts_dir"], exist_ok=True)
                with open(mapping_path, "w", encoding="utf-8") as f_m:
                    json.dump(rebuilt, f_m, ensure_ascii=False, indent=2)

        wl_set: Set[str] = set()
        has_wl_file: bool = os.path.isfile(wl_path)
        if has_wl_file:
            try:
                with open(wl_path, "r", encoding="utf-8") as f_w:
                    raw_wl = json.load(f_w)
                if isinstance(raw_wl, list):
                    wl_set = {normalize_phone_identifier(str(x)).lower() for x in raw_wl if str(x).strip()}
            except (OSError, json.JSONDecodeError):
                pass

        grouped: Dict[str, Dict[str, Any]] = {}
        if os.path.isfile(mapping_path):
            try:
                with open(mapping_path, "r", encoding="utf-8") as f_m:
                    mapping_data = json.load(f_m)
                if isinstance(mapping_data, dict):
                    for raw_ident, info in mapping_data.items():
                        if not isinstance(info, dict):
                            continue
                        alias: str = str(info.get("alias") or "").strip()
                        real_name: str = str(info.get("real_name") or info.get("name") or alias).strip()
                        ident_str: str = str(raw_ident).lstrip("* ").strip()
                        if alias or real_name:
                            entry = grouped.setdefault(f"{real_name}|{alias}", {"display_name": real_name or alias, "alias": alias, "identifiers": []})
                            if ident_str and ident_str.lower() != real_name.lower() and ident_str not in entry["identifiers"]:
                                entry["identifiers"].append(ident_str)
            except (OSError, json.JSONDecodeError):
                pass

        if not grouped and os.path.isfile(contacts_txt):
            with open(contacts_txt, "r", encoding="utf-8", errors="ignore") as f_c:
                for raw_ln in f_c:
                    ln: str = raw_ln.strip()
                    if ln and not ln.startswith("#") and "=" in ln:
                        left, right = [x.lstrip("* ").strip() for x in ln.split("=", 1)]
                        if left and right:
                            is_coord: bool = ("@" in left) or any(ch.isdigit() for ch in left)
                            disp: str = right if is_coord else left
                            entry = grouped.setdefault(disp, {"display_name": disp, "alias": right, "identifiers": []})
                            if is_coord and left not in entry["identifiers"]:
                                entry["identifiers"].append(left)

        activity = self._compute_contact_activity_counts()
        items: List[Dict[str, Any]] = []
        for entry in sorted(grouped.values(), key=lambda x: str(x["display_name"]).lower()):
            idents: List[str] = list(entry["identifiers"])
            disp_low: str = str(entry["display_name"]).lower()
            msg_cnt: int = activity.get(disp_low, 0) + sum(activity.get(normalize_phone_identifier(id_v).lower(), 0) for id_v in idents)
            selected: bool = True if not has_wl_file else (any(normalize_phone_identifier(id_val).lower() in wl_set for id_val in idents) or disp_low in wl_set)
            items.append({**entry, "count": msg_cnt, "selected": selected})
        return items

    def sync_selected_extraction_file(self, kept_identifiers: List[str]) -> None:
        alias_lookup: Dict[str, str] = {}
        if os.path.isfile(self.paths["mapping_file"]):
            try:
                with open(self.paths["mapping_file"], "r", encoding="utf-8") as f_m:
                    m_data = json.load(f_m)
                if isinstance(m_data, dict):
                    for k, v in m_data.items():
                        if isinstance(v, dict) and v.get("alias"):
                            alias_lookup[normalize_phone_identifier(str(k)).lower()] = str(v["alias"]).strip()
            except (OSError, json.JSONDecodeError):
                pass
        lines: List[str] = []
        for ident in kept_identifiers:
            clean_id: str = normalize_phone_identifier(ident.strip())
            if clean_id and ("@" in clean_id or any(ch.isdigit() for ch in clean_id)):
                lines.append(f"{clean_id} = {alias_lookup.get(clean_id.lower(), 'Contact_SMS')}\n")
        with open(self.paths["selected_extraction_contacts_file"], "w", encoding="utf-8") as f_sel:
            f_sel.writelines(lines)

    def save_filter_selection(self, items: List[Dict[str, Any]]) -> int:
        os.makedirs(self.paths["contacts_dir"], exist_ok=True)
        wl_path: str = os.path.join(self.paths["contacts_dir"], "whitelist_contacts.json")
        kept_entries: List[str] = []
        kept_contacts: int = 0
        for item in items:
            if item.get("selected"):
                kept_contacts += 1
                for ident in item.get("identifiers", []):
                    val: str = str(ident).lstrip("* ").strip()
                    if val and val not in kept_entries:
                        kept_entries.append(val)
                d_name: str = str(item.get("display_name") or "").strip()
                if d_name and d_name not in kept_entries:
                    kept_entries.append(d_name)
        with open(wl_path, "w", encoding="utf-8") as f_w:
            json.dump(kept_entries, f_w, ensure_ascii=False, indent=2)
        self.sync_selected_extraction_file(kept_entries)
        return kept_contacts
