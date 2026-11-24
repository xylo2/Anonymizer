# Commandes pip à exécuter : pip install python-docx striprtf odfpy

import os
import re
from typing import Any, Dict, List, Set, Tuple
from doc_anonymizer.deanon_catalog_loader import DeanonCatalogLoader
from doc_anonymizer.deanon_file_io import DeanonFileIO


class DocumentDeanonymizer:
    """
    Analyse les retours IA bruts, suggère les correspondances nominatives probables
    et applique les remplacements sécurisés par sentinelles.
    """

    GENERIC_TOKEN_RE = re.compile(
        r"\b(?:EMAIL|TEL|Contact_Mail|Contact_Tel|AUTRE|PERSONNAGE)_[A-Za-z0-9_]+\b"
        r"|\[JOUR_MOIS_MASQUES\]/(?:19|20)\d{2}"
        r"|\[(?:LIEU|ADRESSE|ETABLISSEMENT|DATE|DATE_TITRE|IBAN|BIC|ID_FISCAL|ID_FT|ID_CAF|ID_CNI_PERMIS|REF_BANCAIRE_TX|ID_REUNION|PLAQUE_IMMAT|CODE_ACCES|REF_ADMIN|NUM_SECU|MRZ_IDENTITE)_\d+\]"
        r"|\[[A-Z_]+_MASQU[A-Z_]*\]"
    )
    TITLE_INITIAL_RE = re.compile(
        r"\b(?:Dr\.?|Docteur|Pr\.?|Professeur|Mme\.?|Madame|Mlle\.?|Mademoiselle|M\.|Mr\.?|Monsieur)\s+"
        r"(?:[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç]+(?:-[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç]+)?\s+)?"
        r"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]\.(?:\s*[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]\.)*"
    )
    INITIAL_PAIR_RE = re.compile(
        r"\b([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç]+(?:-[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç]+)?)"
        r"\s+([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]\.(?:\s*[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]\.)*)"
    )
    DOC_REF_RE = re.compile(
        r"(?:(?:extracted_texts|transcriptions)[\\/][^\s`\"'<>|;*?\r\n]+?\.(?:txt|pdf|docx?|odt|rtf|xlsx?|pptx?|mp3|wav|m4a|jpg|jpeg|png)"
        r"|[A-Za-zÀ-ÿ0-9_.\-()]+?\.(?:txt|pdf|docx?|odt|rtf|xlsx?|pptx?|mp3|wav|m4a|jpg|jpeg|png))",
        re.IGNORECASE,
    )
    TITLE_PREFIXES: Tuple[str, ...] = (
        "dr.", "dr", "docteur", "pr.", "pr", "professeur",
        "mme.", "mme", "madame", "mlle.", "mlle", "mademoiselle",
        "m.", "mr.", "mr", "monsieur",
    )

    def __init__(self, paths: Dict[str, str]) -> None:
        self.paths: Dict[str, str] = paths
        self.catalog: DeanonCatalogLoader = DeanonCatalogLoader(paths)
        self.catalog.load_all()
        self.alias_to_candidates = self.catalog.alias_to_candidates
        self.token_to_candidates = self.catalog.token_to_candidates
        self.doc_ref_to_candidates = self.catalog.doc_ref_to_candidates
        self.known_dates = self.catalog.known_dates
        self.known_locations = self.catalog.known_locations
        self.known_children_first_names = self.catalog.known_children_first_names
        self.all_known_people = self.catalog.all_known_people
        self.all_known_surnames = self.catalog.all_known_surnames

    @staticmethod
    def archive_input_file(source_path: str, archive_dir: str) -> str:
        return DeanonFileIO.archive_input_file(source_path, archive_dir)

    @staticmethod
    def read_document_text(file_path: str) -> str:
        return DeanonFileIO.read_document_text(file_path)

    @staticmethod
    def _extract_snippet(text: str, pos: int, length: int, radius: int = 45) -> str:
        start: int = max(0, pos - radius)
        end: int = min(len(text), pos + length + radius)
        snippet: str = text[start:end].replace("\n", " ").strip()
        return f"...{snippet}..." if (start > 0 or end < len(text)) else snippet

    def _find_probable_choices(self, token: str, existing: List[str]) -> List[str]:
        choices: List[str] = list(dict.fromkeys(existing))
        seen_low: Set[str] = {c.lower() for c in choices}

        def _add(val: str) -> None:
            clean_v: str = val.strip()
            if clean_v and clean_v.lower() not in seen_low and clean_v.lower() != token.lower():
                seen_low.add(clean_v.lower())
                choices.append(clean_v)

        if token == "[DATE_MASQUEE]" or token.startswith("[JOUR_MOIS_MASQUES]/"):
            for d_val in self.known_dates:
                _add(d_val)
            return choices[:25]
        if token in {"[LIEU_MASQUE]", "[ADRESSE_MASQUEE]", "[ETABLISSEMENT_LIEU_MASQUE]"}:
            for loc_val in self.known_locations:
                _add(loc_val)
            return choices[:25]

        raw_tokens: List[str] = [t for t in token.strip().split() if t]
        if not raw_tokens:
            return choices
        title_prefix: str = ""
        first_tok: str = next(iter(raw_tokens))
        if first_tok.lower() in self.TITLE_PREFIXES:
            title_prefix = first_tok
            raw_tokens = raw_tokens[1:]
        if not raw_tokens:
            return choices

        last_tok: str = raw_tokens[-1]
        last_initial: str = last_tok.rstrip(".").upper() if re.fullmatch(r"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]\.", last_tok) else ""
        first_given: str = next(iter(raw_tokens)).lower() if len(raw_tokens) >= 2 else ""

        for person in sorted(self.all_known_people):
            p_parts: List[str] = [p for p in person.split() if p]
            if not p_parts:
                continue
            p_first: str = next(iter(p_parts)).lower()
            p_last: str = p_parts[-1]
            same_first: bool = bool(first_given) and p_first == first_given
            same_init: bool = bool(last_initial) and p_last.upper().startswith(last_initial)
            if (same_first and same_init) or same_first or (not first_given and same_init):
                _add(f"{title_prefix} {person}".strip() if title_prefix else person)
                if not first_given and same_init:
                    _add(f"{title_prefix} {p_last}".strip() if title_prefix else p_last)

        if not first_given and last_initial:
            for sur in sorted(self.all_known_surnames):
                if sur.upper().startswith(last_initial):
                    _add(f"{title_prefix} {sur}".strip() if title_prefix else sur)
        if first_given:
            for person in sorted(self.all_known_people):
                if first_given in person.lower():
                    _add(f"{title_prefix} {person}".strip() if title_prefix else person)
        return choices[:25]
    @staticmethod
    def _looks_like_anonymized_doc_ref(ref_str: str) -> bool:
        low: str = ref_str.lower()
        if low.startswith(("extracted_texts/", "extracted_texts\\", "transcriptions/", "transcriptions\\")):
            return True
        if any(tag in ref_str for tag in ("_MASQU", "EMAIL_", "TEL_", "Contact_")):
            return True
        return bool(re.search(r"(?:^|[_\-\s])[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]\.(?=[_\-\s.])", ref_str))

    def analyze_text(self, text: str) -> List[Dict[str, Any]]:
        found: Dict[str, Dict[str, Any]] = {}

        def _record(
            token: str,
            pos: int,
            cands: List[Tuple[str, str]],
            status_hint: str,
            search_people: bool = True,
        ) -> None:
            if token in found:
                found[token]["count"] = int(found[token]["count"]) + 1
                return
            first_pair = next(iter(cands), ("", ""))
            best_val, source_lbl = first_pair if first_pair else ("", status_hint)
            raw_alts: List[str] = [c for c, _ in cands]
            all_choices: List[str] = self._find_probable_choices(token, raw_alts) if search_people else list(dict.fromkeys(raw_alts))
            if len(cands) > 1:
                status: str = f"Ambigu ({len(cands)} correspondances)"
            elif best_val:
                status = f"Proposé ({source_lbl})"
            elif all_choices:
                status = f"{len(all_choices)} choix probable(s)"
            else:
                status = "À compléter manuellement"
            found[token] = {
                "token": token,
                "proposed": best_val,
                "alternatives": all_choices,
                "status": status,
                "count": 1,
                "context": self._extract_snippet(text, pos, len(token)),
                "apply": bool(best_val),
            }

        for m in self.DOC_REF_RE.finditer(text):
            doc_tok: str = m.group(0).strip()
            norm_doc: str = doc_tok.lower()
            unix_doc: str = norm_doc.replace("\\", "/")
            doc_cands = self.doc_ref_to_candidates.get(norm_doc) or self.doc_ref_to_candidates.get(unix_doc) or []
            if doc_cands or self._looks_like_anonymized_doc_ref(doc_tok):
                _record(doc_tok, m.start(), doc_cands, "Référence document", search_people=False)

        for alias, cands in sorted(self.alias_to_candidates.items(), key=lambda x: -len(x[0])):
            pat = re.compile(rf"(?<![A-Za-zÀ-ÿ0-9]){re.escape(alias)}(?![A-Za-zÀ-ÿ0-9])")
            for m in pat.finditer(text):
                _record(m.group(0), m.start(), cands, "Correspondance connue")

        for first_n, full_n in sorted(self.known_children_first_names.items(), key=lambda x: -len(x[0])):
            pat_child = re.compile(rf"\b{re.escape(first_n)}(?=\s*\((?:\d+\s*ans|classe|frère|cad|aîné))")
            for m in pat_child.finditer(text):
                _record(m.group(0), m.start(), [(full_n, "Famille / Fratrie")], "Famille / Fratrie")

        for m in self.GENERIC_TOKEN_RE.finditer(text):
            tok: str = m.group(0)
            if tok not in found:
                is_loc_generic: bool = tok in {"[ADRESSE_MASQUEE]", "[ETABLISSEMENT_LIEU_MASQUE]"}
                cands_tok = [] if is_loc_generic else self.token_to_candidates.get(tok, [])
                _record(tok, m.start(), cands_tok, "Masque générique", search_people=not tok.startswith("["))

        for rx_pattern, hint in ((self.TITLE_INITIAL_RE, "Titre + Initiale"), (self.INITIAL_PAIR_RE, "Initiale non référencée")):
            for m in rx_pattern.finditer(text):
                tok = m.group(0).strip()
                if tok not in found and not any(tok in k for k in found):
                    _record(tok, m.start(), self.token_to_candidates.get(tok, []), hint)

        return sorted(found.values(), key=lambda it: (-int(it["count"]), str(it["token"]).lower()))

    @staticmethod
    def apply_replacements_to_text(text: str, proposals: List[Dict[str, Any]]) -> str:
        active: List[Tuple[str, str]] = [
            (str(it["token"]), str(it["proposed"]).strip())
            for it in proposals
            if it.get("apply") and str(it.get("token") or "").strip() and str(it.get("proposed") or "").strip()
        ]
        active.sort(key=lambda pair: -len(pair[0]))
        result: str = text
        slot_values: List[str] = []
        for tok, real_val in active:
            slot_marker: str = f"\x00DEANON_SLOT_{len(slot_values)}\x00"
            if tok.startswith("[") and tok.endswith("]"):
                if tok in result:
                    slot_values.append(real_val)
                    result = result.replace(tok, slot_marker)
            else:
                pat = re.compile(rf"(?<![A-Za-zÀ-ÿ0-9]){re.escape(tok)}(?![A-Za-zÀ-ÿ0-9])")
                new_res, n_sub = pat.subn(lambda _m, s=slot_marker: s, result)
                if n_sub > 0:
                    slot_values.append(real_val)
                    result = new_res
        for idx, real_val in enumerate(slot_values):
            result = result.replace(f"\x00DEANON_SLOT_{idx}\x00", real_val)
        return result

    @classmethod
    def export_deanonymized_file(
        cls, source_path: str, out_dir: str, proposals: List[Dict[str, Any]]
    ) -> str:
        return DeanonFileIO.export_deanonymized_file(
            source_path, out_dir, proposals, cls.apply_replacements_to_text
        )
