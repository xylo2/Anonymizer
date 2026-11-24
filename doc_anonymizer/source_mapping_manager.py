# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import re
from typing import Any, Dict, Optional
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.linked_sources_manager import LinkedSourcesManager
from doc_anonymizer.text_utils import DocumentTextUtils


class SourceMappingManager:
    """
    Maintient un dictionnaire JSON associant chaque chemin de transcription anonymisé
    au fichier extrait brut (extracted_texts/...) et au fichier source initial
    (input_documents/... ou emplacements référencés en lecture seule).
    """

    HEADER_SOURCE_RE = re.compile(
        r"^(?:AUDIO|DOCUMENT PDF|DOCUMENT WORD|DOCUMENT ODT|DOCUMENT RTF|"
        r"CLASSEUR EXCEL|PRÉSENTATION PPTX|IMAGE \(OCR\)|PAGE WEB|TEXTE|"
        r"AGENDA ICS|EMAIL)\s*(?:\(([^)]+)\)|:\s*(.+?))\s*(?:\|.*)?$",
        re.MULTILINE,
    )

    def __init__(
        self, config: PipelineConfig, mapping_file: Optional[str] = None
    ) -> None:
        self.config: PipelineConfig = config
        default_path: str = os.path.join(
            os.path.dirname(self.config.audit_report_file),
            "source_files_mapping.json",
        )
        self.mapping_file: str = os.path.abspath(mapping_file or default_path)
        self.entries: Dict[str, Dict[str, str]] = {}
        self._source_index_by_name: Dict[str, str] = {}
        self._source_index_by_stem: Dict[str, str] = {}
        self._index_original_sources()

    def _register_indexed_file(self, full_p: str) -> None:
        fname: str = os.path.basename(full_p)
        low_fn: str = fname.lower()
        stem_low: str = next(iter(os.path.splitext(low_fn)), "")
        self._source_index_by_name.setdefault(low_fn, full_p)
        self._source_index_by_stem.setdefault(stem_low, full_p)

    def _index_original_sources(self) -> None:
        """Indexe les fichiers dans sources_dir ainsi que les fichiers référencés (lecture seule)."""
        src_dir: str = self.config.sources_dir
        if os.path.isdir(src_dir):
            for root_p, dirs, files in os.walk(src_dir):
                dirs[:] = [
                    d for d in sorted(dirs)
                    if d not in self.config.ignored_dirs and not d.startswith(".")
                ]
                for fname in sorted(files):
                    if fname.startswith("."):
                        continue
                    self._register_indexed_file(os.path.normpath(os.path.join(root_p, fname)))

        ws_root: str = os.path.dirname(os.path.abspath(self.config.config_path))
        linked_files, _ = LinkedSourcesManager(ws_root).expand_linked_files(self.config.ignored_dirs)
        for full_p in linked_files:
            self._register_indexed_file(full_p)

    def _resolve_original_source(
        self, extracted_path: str, raw_text: str
    ) -> str:
        """Déduit le chemin du fichier source initial depuis l'en-tête ou le nom du fichier extrait."""
        match = self.HEADER_SOURCE_RE.search(raw_text[:1500])
        if match:
            raw_header_name: str = (match.group(1) or match.group(2) or "").strip()
            base_header: str = os.path.basename(raw_header_name).lower()
            if base_header in self._source_index_by_name:
                return self._source_index_by_name[base_header]
            stem_header: str = next(iter(os.path.splitext(base_header)), "")
            if stem_header in self._source_index_by_stem:
                return self._source_index_by_stem[stem_header]

        ext_stem: str = next(iter(os.path.splitext(os.path.basename(extracted_path).lower())), "")
        return self._source_index_by_stem.get(ext_stem, "")

    def load(self) -> None:
        """Charge les entrées existantes depuis le fichier JSON s'il existe."""
        if not os.path.exists(self.mapping_file):
            return
        try:
            with open(self.mapping_file, "r", encoding="utf-8") as f_in:
                payload: Any = json.load(f_in)
            raw_files: Any = payload.get("files", payload) if isinstance(payload, dict) else {}
            if isinstance(raw_files, dict):
                for k, v in raw_files.items():
                    if isinstance(v, dict):
                        self.entries[str(k)] = {
                            "extracted_file": str(v.get("extracted_file") or ""),
                            "original_source_file": str(v.get("original_source_file") or ""),
                            "batch_file": str(v.get("batch_file") or ""),
                        }
        except Exception:
            pass

    def register_entry(
        self,
        anonymized_path: str,
        extracted_path: str,
        raw_text: str,
        batch_file: str = "",
    ) -> None:
        """Enregistre ou met à jour la correspondance d'un fichier anonymisé."""
        norm_ext: str = os.path.normpath(extracted_path)
        existing: Dict[str, str] = self.entries.get(anonymized_path, {})
        orig_src: str = existing.get("original_source_file") or self._resolve_original_source(
            norm_ext, raw_text
        )
        self.entries[anonymized_path] = {
            "extracted_file": norm_ext,
            "original_source_file": orig_src,
            "batch_file": os.path.normpath(batch_file) if batch_file else existing.get("batch_file", ""),
        }

    def update_batch_for_keys(self, keys: list[str], batch_file: str) -> None:
        """Met à jour le chemin du lot final pour un ensemble de clés anonymisées."""
        norm_batch: str = os.path.normpath(batch_file)
        for key in keys:
            if key in self.entries:
                self.entries[key]["batch_file"] = norm_batch

    def save(self) -> None:
        """Sauvegarde atomiquement le dictionnaire JSON sur disque."""
        parent_dir: str = os.path.dirname(self.mapping_file)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        payload: Dict[str, Any] = {
            "total_entries": len(self.entries),
            "files": dict(sorted(self.entries.items(), key=lambda item: next(iter(item)).lower())),
        }
        DocumentTextUtils.atomic_write_text(
            self.mapping_file,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
