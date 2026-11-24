# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import json
import os
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common.core_utils import SharedCoreUtils
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig


class UnmaskedTranscriptionCopier:
    """
    Copie les transcriptions brutes (extracted_texts/*.txt) correspondant à une
    liste de chemins ou noms de fichiers anonymisés vers un dossier dédié.
    """

    BACKTICK_PATH_RE = re.compile(r"`([^`\r\n]+?\.txt)`", re.IGNORECASE)
    HEADER_ANON_RE = re.compile(
        r"^#\s*SOURCE TRANSCRIPTION\s*:\s*(.+?\.txt)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    def __init__(
        self,
        config: PipelineConfig,
        output_dir: str = "transcriptions_non_anonymisees",
        mapping_file: Optional[str] = None,
    ) -> None:
        self.config: PipelineConfig = config
        self.output_dir: str = os.path.abspath(output_dir)
        default_map: str = os.path.join(
            os.path.dirname(self.config.audit_report_file),
            "source_files_mapping.json",
        )
        self.mapping_file: str = os.path.abspath(mapping_file or default_map)
        self._anonymizer: Optional[DocumentAnonymizationRunner] = None

    def _load_json_mapping(self) -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        if not os.path.exists(self.mapping_file):
            return lookup
        try:
            with open(self.mapping_file, "r", encoding="utf-8") as f_in:
                payload: Any = json.load(f_in)
        except Exception:
            return lookup

        entries: Any = payload.get("files", payload) if isinstance(payload, dict) else {}
        if not isinstance(entries, dict):
            return lookup

        for anon_key, meta in entries.items():
            if not isinstance(meta, dict):
                continue
            ext_path: str = str(meta.get("extracted_file") or "").strip()
            if not ext_path:
                continue
            norm_anon: str = os.path.normpath(str(anon_key)).lower()
            lookup[norm_anon] = ext_path
            lookup[os.path.basename(norm_anon)] = ext_path
        return lookup

    def extract_targets_from_list_file(self, list_file_path: str) -> List[str]:
        if not os.path.exists(list_file_path):
            raise FileNotFoundError(f"Fichier liste introuvable : '{list_file_path}'")

        with open(list_file_path, "r", encoding="utf-8", errors="ignore") as f_in:
            content: str = f_in.read()

        raw_items: List[str] = []
        for line in content.splitlines():
            stripped: str = line.strip()
            if not stripped or stripped.startswith("//"):
                continue

            m_header = self.HEADER_ANON_RE.match(stripped)
            if m_header:
                raw_items.append(m_header.group(1).strip())
                continue

            backticks = self.BACKTICK_PATH_RE.findall(stripped)
            if backticks:
                raw_items.extend(bt.strip() for bt in backticks)
                continue

            cleaned: str = re.sub(r"^(?:[\-\*\•]+\s+|\d+[\.\)]\s+)+", "", stripped).strip("`\"' ")
            if cleaned.lower().endswith(".txt"):
                raw_items.append(cleaned)

        return list(dict.fromkeys(raw_items))
    def _get_anonymizer(self) -> DocumentAnonymizationRunner:
        if self._anonymizer is None:
            runner = DocumentAnonymizationRunner(self.config)
            runner.initialize()
            self._anonymizer = runner
        return self._anonymizer

    @staticmethod
    def _canonical_path_key(raw_path: str) -> str:
        norm: str = os.path.normpath(raw_path).lower().replace("\\", "/")
        norm = norm.replace("_", " ").replace("..txt", ".txt")
        return re.sub(r"\s+", " ", norm).strip()

    def _resolve_via_fallback(self, anon_target: str) -> Optional[str]:
        trans_dir: str = self.config.transcriptions_dir
        if not os.path.isdir(trans_dir):
            return None

        norm_target: str = self._canonical_path_key(anon_target)
        target_base: str = norm_target.rsplit("/", 1)[-1]
        target_parts: List[str] = norm_target.split("/")
        suffix_3: str = "/".join(target_parts[-3:]) if len(target_parts) >= 3 else target_base

        anonymizer = self._get_anonymizer()
        candidates: List[str] = []

        for root_p, _, files in os.walk(trans_dir):
            for fname in sorted(files):
                if fname.startswith(".") or not fname.lower().endswith(".txt"):
                    continue
                full_p: str = os.path.normpath(os.path.join(root_p, fname))
                anon_full: str = self._canonical_path_key(anonymizer.anonymize_text(full_p))
                anon_base: str = anon_full.rsplit("/", 1)[-1]
                anon_parts: List[str] = anon_full.split("/")
                anon_suffix_3: str = (
                    "/".join(anon_parts[-3:]) if len(anon_parts) >= 3 else anon_base
                )

                if anon_full == norm_target or anon_suffix_3 == suffix_3:
                    return full_p
                if anon_base == target_base:
                    candidates.append(full_p)

        return next(iter(candidates)) if len(candidates) == 1 else None

    def copy_from_targets(self, anon_targets: List[str]) -> Tuple[int, int]:
        if not anon_targets:
            print("Aucun fichier anonymisé fourni.", flush=True)
            return 0, 0

        json_lookup: Dict[str, str] = self._load_json_mapping()
        os.makedirs(self.output_dir, exist_ok=True)
        print(
            f"{len(anon_targets)} cible(s) à traiter -> '{self.output_dir}'\n",
            flush=True,
        )

        copied: int = 0
        missing: int = 0
        seen_sources: Set[str] = set()

        for target in anon_targets:
            norm_key: str = os.path.normpath(target).lower()
            src_path: Optional[str] = json_lookup.get(norm_key) or json_lookup.get(
                os.path.basename(norm_key)
            )
            if not src_path or not os.path.exists(src_path):
                src_path = self._resolve_via_fallback(target)

            if not src_path or not os.path.exists(src_path):
                print(f"[INTROUVABLE] {target}", flush=True)
                missing += 1
                continue

            abs_src: str = os.path.abspath(src_path)
            if abs_src in seen_sources:
                continue
            seen_sources.add(abs_src)

            try:
                rel_path: str = os.path.relpath(abs_src, self.config.transcriptions_dir)
                if rel_path.startswith(".."):
                    rel_path = os.path.basename(abs_src)
            except ValueError:
                rel_path = os.path.basename(abs_src)

            dest_path: str = os.path.join(self.output_dir, rel_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(abs_src, dest_path)
            print(f"[COPIÉ] {rel_path}", flush=True)
            copied += 1

        print(f"\nTerminé : {copied} fichier(s) copié(s), {missing} introuvable(s).", flush=True)
        return copied, missing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copie les transcriptions brutes correspondant à une liste de fichiers anonymisés."
    )
    parser.add_argument("-l", "--list-file", default="", help="Fichier .txt ou .md listant les chemins/noms anonymisés.")
    parser.add_argument("targets", nargs="*", help="Chemins ou noms de fichiers anonymisés passés directement en arguments.")
    parser.add_argument("-o", "--output", default="transcriptions_non_anonymisees", help="Dossier de sortie (défaut : transcriptions_non_anonymisees).")
    parser.add_argument("-m", "--mapping", default=None, help="Chemin vers source_files_mapping.json (optionnel).")
    parser.add_argument("-c", "--config", default="config.ini", help="Chemin vers config.ini (défaut : config.ini).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg_path: str = SharedCoreUtils.resolve_config_path(args.config, ROOT_DIR)
    config = PipelineConfig(cfg_path)
    copier = UnmaskedTranscriptionCopier(config=config, output_dir=args.output, mapping_file=args.mapping)
    targets: List[str] = list(args.targets)
    if args.list_file:
        targets.extend(copier.extract_targets_from_list_file(args.list_file))
    if not targets:
        print("Spécifiez --list-file <fichier.txt|md> ou passez des chemins en arguments.", flush=True)
        sys.exit(1)
    copier.copy_from_targets(list(dict.fromkeys(targets)))


if __name__ == "__main__":
    main()
