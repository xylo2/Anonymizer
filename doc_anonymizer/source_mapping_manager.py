# Commandes pip à exécuter : Aucune dépendance externe requise

import json
import os
import re
from typing import Any, Dict, Optional
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class SourceMappingManager:
    """
    Maintient un dictionnaire JSON associant chaque chemin de transcription anonymisé
    au fichier extrait brut (extracted_texts/...) et au fichier source initial
    (input_documents/...).
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
        """
        Initialise le gestionnaire de correspondances et indexe les sources brutes.

        :param config: Instance de PipelineConfig.
        :param mapping_file: Chemin personnalisé optionnel vers le fichier JSON.
        """
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

    def _index_original_sources(self) -> None:
        """Indexe les fichiers présents dans sources_dir par nom et par radical."""
        src_dir: str = self.config.sources_dir
        if not os.path.isdir(src_dir):
            return
        for root_p, dirs, files in os.walk(src_dir):
            dirs[:] = [
                d for d in sorted(dirs)
                if d not in self.config.ignored_dirs and not d.startswith(".")
            ]
            for fname in sorted(files):
                if fname.startswith("."):
                    continue
                full_p: str = os.path.normpath(os.path.join(root_p, fname))
                low_fn: str = fname.lower()
                stem_low: str = next(iter(os.path.splitext(low_fn)), "")
                self._source_index_by_name.setdefault(low_fn, full_p)
                self._source_index_by_stem.setdefault(stem_low, full_p)

    def _resolve_original_source(
        self, extracted_path: str, raw_text: str
    ) -> str:
        """
        Déduit le chemin du fichier source initial à partir de l'en-tête interne
        de la transcription ou du nom du fichier extrait.

        :param extracted_path: Chemin vers le fichier extrait dans extracted_texts/.
        :param raw_text: Contenu brut du fichier extrait.
        :return: Chemin du fichier source initial dans input_documents/, ou chaîne vide.
        """
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
            raw_files: Any = (
                payload.get("files", payload) if isinstance(payload, dict) else {}
            )
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
        """
        Enregistre ou met à jour la correspondance d'un fichier anonymisé.

        :param anonymized_path: Chemin anonymisé écrit dans l'en-tête du lot.
        :param extracted_path: Chemin vers le fichier texte extrait brut.
        :param raw_text: Contenu brut du fichier extrait.
        :param batch_file: Chemin vers le lot final contenant ce document.
        """
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
        """
        Met à jour le chemin du lot final pour un ensemble de clés anonymisées.

        :param keys: Liste des chemins anonymisés inclus dans le lot.
        :param batch_file: Chemin du fichier lot écrit sur disque.
        """
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
