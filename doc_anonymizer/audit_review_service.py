# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import re
from typing import Any, Dict, List, Set, Tuple


class AuditReviewService:
    """
    Gère le tableau de bord d'audit, la recherche d'occurrences Avant/Après,
    la validation ou l'exclusion des candidats et la résolution des pièces sélectionnées par l'IA.
    """

    @staticmethod
    def load_dashboard_stats(paths: Dict[str, str]) -> Dict[str, Any]:
        state_file: str = os.path.join(paths["results_dir"], ".anonymization_state.json")
        if os.path.isfile(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f_st:
                    payload = json.load(f_st)
                if isinstance(payload, dict) and isinstance(payload.get("stats_anonymisation"), dict):
                    return dict(payload["stats_anonymisation"])
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    @staticmethod
    def load_audit_candidates(paths: Dict[str, str]) -> List[Tuple[str, str]]:
        copy_file: str = paths["audit_copy_file"]
        if not os.path.isfile(copy_file):
            return []
        candidates: List[Tuple[str, str]] = []
        try:
            with open(copy_file, "r", encoding="utf-8", errors="ignore") as f_in:
                for raw_ln in f_in:
                    ln: str = raw_ln.strip()
                    if not ln or ln.startswith("#") or "=" not in ln:
                        continue
                    left, right = [x.strip() for x in ln.split("=", 1)]
                    if left:
                        candidates.append((left, right))
        except OSError:
            pass
        return candidates

    @staticmethod
    def load_audit_occurrences(paths: Dict[str, str], candidate: str) -> List[Dict[str, str]]:
        trans_dir: str = paths["transcriptions_dir"]
        results_dir: str = paths["results_dir"]
        if not candidate or not os.path.isdir(trans_dir):
            return []
        pattern = re.compile(rf"\b{re.escape(candidate.strip())}\b", re.IGNORECASE)
        anon_chunks: List[str] = []
        if os.path.isdir(results_dir):
            for rp, _, fs in os.walk(results_dir):
                for fn in sorted(fs):
                    if fn.endswith(".txt"):
                        try:
                            with open(os.path.join(rp, fn), "r", encoding="utf-8", errors="ignore") as f_a:
                                anon_chunks.append(f_a.read())
                        except OSError:
                            pass
        anon_full: str = "\n".join(anon_chunks)
        occurrences: List[Dict[str, str]] = []
        for rp, _, fs in os.walk(trans_dir):
            for fn in sorted(fs):
                if not fn.endswith(".txt"):
                    continue
                full_p: str = os.path.join(rp, fn)
                try:
                    with open(full_p, "r", encoding="utf-8", errors="ignore") as f_t:
                        lines: List[str] = f_t.read().splitlines()
                except OSError:
                    continue
                for idx, line in enumerate(lines):
                    if pattern.search(line):
                        start: int = max(0, idx - 2)
                        end: int = min(len(lines), idx + 3)
                        raw_excerpt: str = "\n".join(lines[start:end])
                        occurrences.append({
                            "file_label": os.path.relpath(full_p, trans_dir),
                            "line_num": str(idx + 1),
                            "raw_excerpt": raw_excerpt,
                            "anon_excerpt": anon_full if anon_full else raw_excerpt,
                        })
                        if len(occurrences) >= 25:
                            return occurrences
        return occurrences
    @staticmethod
    def remove_candidate_from_audit_files(paths: Dict[str, str], candidate: str) -> None:
        target_low: str = candidate.strip().lower()
        for key in ("audit_copy_file", "audit_report_file"):
            fpath: str = paths.get(key, "")
            if not fpath or not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f_in:
                    lines: List[str] = f_in.readlines()
                kept: List[str] = [
                    ln for ln in lines
                    if not (
                        "=" in ln
                        and not ln.lstrip().startswith("#")
                        and ln.split("=", 1)[0].strip().lower() == target_low
                    )
                ]
                with open(fpath, "w", encoding="utf-8") as f_out:
                    f_out.writelines(kept)
            except OSError:
                pass

    @classmethod
    def approve_audit_mask(cls, paths: Dict[str, str], candidate: str, alias: str) -> None:
        clean_cand: str = candidate.strip()
        if not clean_cand:
            return
        tokens: List[str] = [t for t in clean_cand.split() if t]
        first_tok: str = next(iter(tokens), clean_cand)
        final_alias: str = alias.strip() or (f"{first_tok} {tokens[-1][:1].upper()}." if len(tokens) >= 2 else f"{clean_cand[:1].upper()}.")
        os.makedirs(os.path.dirname(paths["manual_contacts_file"]), exist_ok=True)
        with open(paths["manual_contacts_file"], "a", encoding="utf-8") as f_man:
            f_man.write(f"{clean_cand} = {final_alias}\n")
        cls.remove_candidate_from_audit_files(paths, clean_cand)

    @classmethod
    def exclude_audit_false_positive(cls, paths: Dict[str, str], candidate: str) -> None:
        clean_cand: str = candidate.strip()
        if not clean_cand:
            return
        os.makedirs(os.path.dirname(paths["excluded_words_file"]), exist_ok=True)
        with open(paths["excluded_words_file"], "a", encoding="utf-8") as f_ex:
            for tok in clean_cand.split():
                if len(tok) >= 2:
                    f_ex.write(f"{tok.lower()}\n")
        cls.remove_candidate_from_audit_files(paths, clean_cand)

    @staticmethod
    def resolve_ai_selected_extracted_files(paths: Dict[str, str], raw_ai_text: str) -> Set[str]:
        ws_root: str = paths["workspace_root"]
        trans_dir: str = paths["transcriptions_dir"]
        mapping_lookup: Dict[str, str] = {}
        for map_path in (
            paths["mapping_file"],
            os.path.join(os.path.dirname(paths["audit_report_file"]), "source_files_mapping.json"),
        ):
            if not os.path.isfile(map_path):
                continue
            try:
                with open(map_path, "r", encoding="utf-8") as f_m:
                    payload = json.load(f_m)
                files_map = payload.get("files", payload) if isinstance(payload, dict) else {}
                if isinstance(files_map, dict):
                    for k, meta in files_map.items():
                        if isinstance(meta, dict) and meta.get("extracted_file"):
                            mapping_lookup[str(k).strip().replace("\\", "/").lower()] = str(meta["extracted_file"])
            except (OSError, json.JSONDecodeError):
                pass
        resolved: Set[str] = set()
        for raw_ln in (raw_ai_text or "").splitlines():
            m = re.search(r"([^\s`\"':#]+\.txt)\b", raw_ln.strip(), re.IGNORECASE)
            if not m:
                continue
            rel_candidate: str = m.group(1).replace("\\", "/").lstrip("./")
            rel_low: str = rel_candidate.lower()
            mapped: str = mapping_lookup.get(rel_low, "")
            if not mapped:
                mapped = next((ext_p for k_low, ext_p in mapping_lookup.items() if k_low.endswith(rel_low)), "")
            if mapped and os.path.isfile(mapped):
                resolved.add(os.path.normpath(mapped))
                continue
            trimmed_rel: str = re.sub(r"^extracted_texts/", "", rel_candidate, flags=re.IGNORECASE)
            for base, rel_opt in ((ws_root, rel_candidate), (trans_dir, rel_candidate), (trans_dir, trimmed_rel)):
                cand_p: str = os.path.normpath(os.path.join(base, rel_opt))
                if os.path.isfile(cand_p):
                    resolved.add(cand_p)
                    break
        return resolved
