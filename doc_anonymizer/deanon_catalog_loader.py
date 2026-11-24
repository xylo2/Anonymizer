# Commandes pip à exécuter : Aucune dépendance externe requise

from collections import Counter
import configparser
import json
import os
import re
from typing import Dict, List, Set, Tuple
from doc_anonymizer.deanon_vault import DeanonVaultManager


class DeanonCatalogLoader:
    """
    Charge et consolide toutes les sources de correspondances pour la désanonymisation :
    coffre de réversibilité (deanon_vault.json), carnets de contacts, références de
    documents (source_files_mapping.json), dates et localités masquées.
    """

    def __init__(self, paths: Dict[str, str]) -> None:
        self.paths: Dict[str, str] = paths
        self._raw_alias_votes: Dict[str, Counter[str]] = {}
        self._alias_sources: Dict[Tuple[str, str], str] = {}
        self.alias_to_candidates: Dict[str, List[Tuple[str, str]]] = {}
        self.token_to_candidates: Dict[str, List[Tuple[str, str]]] = {}
        self.doc_ref_to_candidates: Dict[str, List[Tuple[str, str]]] = {}
        self.known_dates: List[str] = []
        self.known_locations: List[str] = []
        self.known_children_first_names: Dict[str, str] = {}
        self.all_known_people: Set[str] = set()
        self.all_known_surnames: Set[str] = set()

    @staticmethod
    def is_coordinate_value(val: str) -> bool:
        s: str = val.strip()
        if not s or "@" in s:
            return True
        digits: str = re.sub(r"[\s.\-()+]", "", s)
        return len(digits) >= 6 and digits.isdigit()

    @classmethod
    def is_valid_person_alias(cls, alias: str) -> bool:
        clean: str = alias.strip()
        if len(clean) < 4 or cls.is_coordinate_value(clean):
            return False
        if clean.startswith(("EMAIL_", "TEL_", "Contact_", "AUTRE_", "PERSONNAGE_")):
            return True
        tokens: List[str] = [t for t in clean.split() if t]
        if len(tokens) < 2:
            return False
        return any(re.fullmatch(r"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]\.", t) for t in tokens)

    def register_token_candidate(self, key: str, real_val: str, source: str, prepend: bool = False) -> None:
        clean_k: str = key.strip()
        clean_v: str = real_val.strip()
        if not clean_k or not clean_v or clean_k.lower() == clean_v.lower():
            return
        bucket = self.token_to_candidates.setdefault(clean_k, [])
        if any(existing_v.lower() == clean_v.lower() for existing_v, _ in bucket):
            return
        if prepend:
            bucket.insert(0, (clean_v, source))
        else:
            bucket.append((clean_v, source))

    def register_doc_candidate(self, anon_ref: str, real_ref: str, source: str) -> None:
        clean_k: str = anon_ref.strip()
        clean_v: str = real_ref.strip()
        if not clean_k or not clean_v or clean_k.lower() == clean_v.lower():
            return
        bucket = self.doc_ref_to_candidates.setdefault(clean_k.lower(), [])
        if not any(existing_v.lower() == clean_v.lower() for existing_v, _ in bucket):
            bucket.append((clean_v, source))
    def vote_person_candidate(self, alias: str, real_name: str, source: str, weight: int = 1) -> None:
        clean_a: str = alias.strip()
        clean_r: str = re.sub(r"\s*\([^)]*\)\s*$", "", real_name).strip()
        if not self.is_valid_person_alias(clean_a):
            return
        if self.is_coordinate_value(clean_r) or len(clean_r.split()) < 2:
            return
        if clean_a.lower() == clean_r.lower():
            return
        self.all_known_people.add(clean_r)
        parts: List[str] = clean_r.split()
        if len(parts[-1]) >= 2:
            self.all_known_surnames.add(parts[-1])
        votes = self._raw_alias_votes.setdefault(clean_a, Counter())
        votes[clean_r] += weight
        self._alias_sources.setdefault((clean_a, clean_r), source)
        first_n: str = next(iter(parts))
        if len(first_n) >= 3 and first_n[:1].isupper():
            self.known_children_first_names[first_n] = clean_r

    def register_date_candidate(self, raw_date: str, source: str) -> None:
        clean_d: str = raw_date.strip()
        if not clean_d:
            return
        if clean_d not in self.known_dates:
            self.known_dates.append(clean_d)
        self.register_token_candidate("[DATE_MASQUEE]", clean_d, source)
        m_fr = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.]((?:19|20)\d{2})", clean_d)
        m_iso = re.fullmatch(r"((?:19|20)\d{2})[/\-.](\d{1,2})[/\-.](\d{1,2})", clean_d)
        year_str: str = m_fr.group(3) if m_fr else (m_iso.group(1) if m_iso else "")
        if year_str:
            self.register_token_candidate(f"[JOUR_MOIS_MASQUES]/{year_str}", clean_d, source)

    def register_location_candidate(self, raw_loc: str, source: str) -> None:
        clean_l: str = raw_loc.strip()
        if len(clean_l) < 2:
            return
        if not any(existing.lower() == clean_l.lower() for existing in self.known_locations):
            self.known_locations.append(clean_l)
        self.register_token_candidate("[LIEU_MASQUE]", clean_l, source)

    def _load_deanon_vault(self) -> None:
        ws_root: str = self.paths.get("workspace_root", "")
        audit_rep: str = self.paths.get("audit_report_file", "")
        candidates: List[str] = [
            os.path.join(os.path.dirname(audit_rep), "deanon_vault.json") if audit_rep else "",
            os.path.join(ws_root, "audits", "deanon_vault.json") if ws_root else "",
        ]
        for vault_p in candidates:
            if not vault_p or not os.path.isfile(vault_p):
                continue
            vault = DeanonVaultManager(vault_p)
            vault.load()
            for token, cands in vault.get_all_ranked_entries().items():
                if not cands:
                    continue
                is_bracket_or_gen: bool = token.startswith("[") or token.startswith(("EMAIL_", "TEL_", "Contact_"))
                for idx, (orig_val, category) in enumerate(cands):
                    lbl: str = f"Coffre ({category})"
                    if is_bracket_or_gen:
                        self.register_token_candidate(token, orig_val, lbl, prepend=(idx == 0))
                    else:
                        self.vote_person_candidate(token, orig_val, lbl, weight=10 if idx == 0 else 4)
                        self.register_token_candidate(token, orig_val, lbl, prepend=(idx == 0))

    def _load_dates_and_locations(self) -> None:
        ws_root: str = self.paths.get("workspace_root", "")
        ini_path: str = os.path.join(ws_root, "config.ini") if ws_root else ""
        if ini_path and os.path.isfile(ini_path):
            cfg = configparser.ConfigParser()
            try:
                cfg.read(ini_path, encoding="utf-8")
                for d_item in cfg.get("anonymization", "masked_birth_dates", fallback="").split(","):
                    if d_item.strip():
                        self.register_date_candidate(d_item.strip(), "Config dossier")
                for loc_item in cfg.get("anonymizer", "extra_locations", fallback="").split(","):
                    if loc_item.strip():
                        self.register_location_candidate(loc_item.strip(), "Config dossier")
            except Exception:
                pass

        loc_file: str = self.paths.get("locations_file", "") or (
            os.path.join(ws_root, "contacts", "villes_masquees.txt") if ws_root else ""
        )
        if loc_file and os.path.isfile(loc_file):
            try:
                with open(loc_file, "r", encoding="utf-8", errors="ignore") as f_loc:
                    for raw_ln in f_loc:
                        ln: str = raw_ln.strip()
                        if ln and not ln.startswith("#"):
                            self.register_location_candidate(ln, "Villes masquées")
            except OSError:
                pass
    def _load_indexed_identities(self) -> Dict[str, str]:
        coord_to_name: Dict[str, str] = {}
        ws_root: str = self.paths.get("workspace_root", "")
        candidates: List[str] = [
            os.path.join(ws_root, "output_contacts", ".intermediates", "indexed_contacts.txt"),
            os.path.join(ws_root, "contacts", "indexed_contacts.txt"),
        ]
        for idx_p in candidates:
            if not idx_p or not os.path.isfile(idx_p):
                continue
            try:
                with open(idx_p, "r", encoding="utf-8", errors="ignore") as f_i:
                    for raw_ln in f_i:
                        ln: str = raw_ln.strip()
                        if not ln or ln.startswith("#") or "=" not in ln:
                            continue
                        left_c, right_n = [x.strip() for x in ln.split("=", 1)]
                        clean_n: str = re.sub(r"\s*\([^)]*\)\s*$", "", right_n).strip()
                        if left_c and clean_n and not self.is_coordinate_value(clean_n) and len(clean_n.split()) >= 2:
                            coord_to_name[left_c.lower()] = clean_n
                            self.all_known_people.add(clean_n)
            except OSError:
                pass
        return coord_to_name

    def _load_document_references(self) -> None:
        ws_root: str = self.paths.get("workspace_root", "")
        audit_rep: str = self.paths.get("audit_report_file", "")
        candidates: List[str] = [
            os.path.join(os.path.dirname(audit_rep), "source_files_mapping.json") if audit_rep else "",
            os.path.join(ws_root, "audits", "source_files_mapping.json") if ws_root else "",
        ]
        for map_p in candidates:
            if not map_p or not os.path.isfile(map_p):
                continue
            try:
                with open(map_p, "r", encoding="utf-8") as f_m:
                    payload = json.load(f_m)
                files_map = payload.get("files", payload) if isinstance(payload, dict) else {}
                if not isinstance(files_map, dict):
                    continue
                for anon_key, meta in files_map.items():
                    if not isinstance(meta, dict):
                        continue
                    anon_str: str = str(anon_key).strip()
                    ext_file: str = str(meta.get("extracted_file") or "").strip()
                    orig_file: str = str(meta.get("original_source_file") or "").strip()
                    if not anon_str:
                        continue
                    anon_unix: str = anon_str.replace("\\", "/")
                    anon_base: str = os.path.basename(anon_unix)
                    if ext_file:
                        ext_unix: str = ext_file.replace("\\", "/")
                        rel_ext: str = os.path.relpath(ext_file, ws_root).replace("\\", "/") if ws_root else ext_unix
                        chosen_ext: str = rel_ext if (ws_root and not rel_ext.startswith("..")) else ext_unix
                        self.register_doc_candidate(anon_str, chosen_ext, "Transcription extraite")
                        self.register_doc_candidate(anon_unix, chosen_ext, "Transcription extraite")
                        self.register_doc_candidate(anon_base, os.path.basename(ext_unix), "Fichier extrait")
                    if orig_file:
                        orig_unix: str = orig_file.replace("\\", "/")
                        rel_orig: str = os.path.relpath(orig_file, ws_root).replace("\\", "/") if ws_root else orig_unix
                        chosen_orig: str = rel_orig if (ws_root and not rel_orig.startswith("..")) else orig_unix
                        self.register_doc_candidate(anon_str, chosen_orig, "Fichier source original")
                        self.register_doc_candidate(anon_unix, chosen_orig, "Fichier source original")
                        self.register_doc_candidate(anon_base, os.path.basename(orig_unix), "Fichier source original")
            except (OSError, json.JSONDecodeError):
                pass

    def load_all(self) -> None:
        coord_to_name: Dict[str, str] = self._load_indexed_identities()
        self._load_deanon_vault()
        self._load_document_references()
        self._load_dates_and_locations()

        mapping_file: str = self.paths.get("mapping_file", "")
        if mapping_file and os.path.isfile(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f_m:
                    data = json.load(f_m)
                if isinstance(data, dict):
                    for info in data.values():
                        if isinstance(info, dict):
                            alias: str = str(info.get("alias") or "").strip()
                            real_name: str = str(info.get("real_name") or "").strip()
                            if alias and real_name:
                                self.vote_person_candidate(alias, real_name, "Carnet contacts", weight=2)
            except (OSError, json.JSONDecodeError):
                pass

        for key_name, label, w in (("manual_contacts_file", "Règle manuelle", 5), ("contacts_file", "Catalogue contacts", 1)):
            fpath: str = self.paths.get(key_name, "")
            if not fpath or not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f_c:
                    for raw_ln in f_c:
                        ln: str = raw_ln.strip()
                        if not ln or ln.startswith("#") or "=" not in ln:
                            continue
                        left_k, right_v = [x.strip() for x in ln.split("=", 1)]
                        if not left_k or not right_v:
                            continue
                        if right_v == "[DATE_MASQUEE]":
                            self.register_date_candidate(left_k, label)
                        elif right_v in {"[LIEU_MASQUE]", "[ADRESSE_MASQUEE]", "[ETABLISSEMENT_LIEU_MASQUE]"}:
                            self.register_token_candidate(right_v, left_k, label)
                            self.register_location_candidate(left_k, label)
                        elif not right_v.startswith("["):
                            if self.is_coordinate_value(left_k):
                                if right_v.startswith(("EMAIL_", "TEL_", "Contact_")):
                                    self.register_token_candidate(right_v, left_k, label)
                                resolved_real: str = coord_to_name.get(left_k.lower(), "")
                                if resolved_real:
                                    self.vote_person_candidate(right_v, resolved_real, label, weight=w)
                            else:
                                self.vote_person_candidate(right_v, left_k, label, weight=w)
            except OSError:
                pass

        for alias_k, votes in self._raw_alias_votes.items():
            ranked: List[Tuple[str, str]] = [
                (real_n, self._alias_sources.get((alias_k, real_n), "Contacts"))
                for real_n, _ in votes.most_common()
            ]
            if ranked:
                self.alias_to_candidates[alias_k] = ranked
