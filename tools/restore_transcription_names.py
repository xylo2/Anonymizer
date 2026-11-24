# Commandes pip à exécuter : Aucune dépendance externe requise

import argparse
import os
import re
import sys
from typing import Dict, Optional, Tuple

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common.core_utils import SharedCoreUtils
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.extraction_runner import DocumentExtractionRunner
from doc_anonymizer.text_utils import DocumentTextUtils


class TranscriptionNameRestorer:
    """Restaure les noms d'origine des transcriptions et les reclasse par période AAAA-MM."""

    HEADER_SOURCE_RE = re.compile(
        r"^(?:AUDIO|DOCUMENT PDF|DOCUMENT WORD|DOCUMENT ODT|DOCUMENT RTF|"
        r"CLASSEUR EXCEL|PRÉSENTATION PPTX|IMAGE \(OCR\)|PAGE WEB|TEXTE|"
        r"AGENDA ICS|EMAIL)\s*(?:\(([^)]+)\)|:\s*(.+?))\s*(?:\|.*)?$",
        re.MULTILINE,
    )

    EXT_TO_CATEGORY: Dict[str, str] = {
        ".pdf": "PDF", ".ics": "Agendas", ".xml": "SMS", ".mbox": "Emails",
        ".eml": "Emails", ".json": "Chats", ".vtt": "Chats", ".png": "Images",
        ".jpg": "Images", ".jpeg": "Images", ".bmp": "Images", ".tiff": "Images",
        ".webp": "Images", ".mp3": "Audio", ".wav": "Audio", ".ogg": "Audio",
        ".m4a": "Audio", ".flac": "Audio", ".aup3": "Audio",
    }

    def __init__(self, config: PipelineConfig, dry_run: bool = True) -> None:
        self.config: PipelineConfig = config
        self.dry_run: bool = dry_run
        self.extractor: DocumentExtractionRunner = DocumentExtractionRunner(config=config)

    def _build_masked_to_raw_map(self) -> Dict[Tuple[str, str], str]:
        target_phones, _ = self.extractor.load_all_filter_contacts()
        phone_map: Dict[str, str] = target_phones or {}
        mapping: Dict[Tuple[str, str], str] = {}
        for src_path in self.extractor.collect_source_files():
            file_name: str = os.path.basename(src_path)
            stem, ext_raw = os.path.splitext(file_name)
            cat: str = self.EXT_TO_CATEGORY.get(ext_raw.lower(), "Documents")
            raw_stem: str = DocumentTextUtils.sanitize_filename_component(stem)
            old_masked: str = DocumentTextUtils.mask_identifiers_in_filename(stem, phone_map)
            old_masked_clean: str = DocumentTextUtils.sanitize_filename_component(old_masked)
            if old_masked_clean != raw_stem:
                mapping[(cat, f"{old_masked_clean}.txt")] = f"{raw_stem}.txt"
        return mapping

    def _extract_raw_name_from_header(self, txt_path: str) -> Optional[str]:
        try:
            with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                head: str = f.read(1500)
        except OSError:
            return None
        match = self.HEADER_SOURCE_RE.search(head)
        if not match:
            return None
        source_file_name: str = (match.group(1) or match.group(2) or "").strip()
        if not source_file_name:
            return None
        stem, _ = os.path.splitext(os.path.basename(source_file_name))
        return f"{DocumentTextUtils.sanitize_filename_component(stem)}.txt"

    def _resolve_target_path(self, current_root: str, category: str, target_name: str) -> str:
        if category in {"SMS", "Emails"}:
            return os.path.join(current_root, target_name)
        detected_period: Optional[str] = DocumentTextUtils.detect_period_in_text(target_name)
        if detected_period:
            return os.path.join(self.config.transcriptions_dir, detected_period, category, target_name)
        return os.path.join(current_root, target_name)

    def run(self) -> int:
        trans_dir: str = self.config.transcriptions_dir
        if not os.path.isdir(trans_dir):
            return 0
        fallback_map: Dict[Tuple[str, str], str] = self._build_masked_to_raw_map()
        moved_count: int = 0
        for root_path, _, files in os.walk(trans_dir):
            category: str = os.path.basename(root_path)
            for file_name in sorted(files):
                if file_name.startswith(".") or file_name in {"rapport_extraction.txt", "extraction_report.txt"} or not file_name.lower().endswith(".txt"):
                    continue
                full_path: str = os.path.join(root_path, file_name)
                target_name: str = fallback_map.get((category, file_name), file_name)
                if target_name == file_name and ("NUMERO_MASQUE" in file_name or "EMAIL_MASQUE" in file_name):
                    target_name = self._extract_raw_name_from_header(full_path) or file_name
                new_path: str = self._resolve_target_path(root_path, category, target_name)
                if os.path.normpath(new_path) == os.path.normpath(full_path) or os.path.exists(new_path):
                    continue
                if not self.dry_run:
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
                    os.rename(full_path, new_path)
                moved_count += 1
        return moved_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaure les noms bruts et classe par période AAAA-MM.")
    parser.add_argument("-c", "--config", default="config.ini")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    TranscriptionNameRestorer(PipelineConfig(SharedCoreUtils.resolve_config_path(args.config, ROOT_DIR)), dry_run=not args.apply).run()


if __name__ == "__main__":
    main()
