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
    """
    Restaure les noms d'origine des transcriptions ayant subi un masquage
    prématuré et les replace dans le bon sous-dossier périodique AAAA-MM.
    """

    HEADER_SOURCE_RE = re.compile(
        r"^(?:AUDIO|DOCUMENT PDF|DOCUMENT WORD|DOCUMENT ODT|DOCUMENT RTF|"
        r"CLASSEUR EXCEL|PRÉSENTATION PPTX|IMAGE \(OCR\)|PAGE WEB|TEXTE|"
        r"AGENDA ICS|EMAIL)\s*(?:\(([^)]+)\)|:\s*(.+?))\s*(?:\|.*)?$",
        re.MULTILINE,
    )

    def __init__(self, config: PipelineConfig, dry_run: bool = True) -> None:
        """
        Initialise le restaurateur avec la configuration du pipeline.

        :param config: Instance de PipelineConfig.
        :param dry_run: Si True, simule sans modifier les fichiers.
        """
        self.config: PipelineConfig = config
        self.dry_run: bool = dry_run
        self.extractor: DocumentExtractionRunner = DocumentExtractionRunner(config=config)

    def _build_masked_to_raw_map(self) -> Dict[Tuple[str, str], str]:
        """
        Construit une table (catégorie, ancien_nom_masqué) -> nom_brut
        à partir des fichiers présents dans le répertoire sources.

        :return: Dictionnaire de correspondance des noms.
        """
        target_phones, _ = self.extractor.load_all_filter_contacts()
        phone_map: Dict[str, str] = target_phones or {}
        mapping: Dict[Tuple[str, str], str] = {}

        for src_path in self.extractor.collect_source_files():
            file_name: str = os.path.basename(src_path)
            stem, ext_raw = os.path.splitext(file_name)
            cat: str = self.extractor.categorize_extension(ext_raw.lower())
            raw_stem: str = DocumentExtractionRunner._sanitize_filesystem_stem(stem)
            old_masked: str = DocumentTextUtils.mask_identifiers_in_filename(stem, phone_map)
            old_masked_clean: str = DocumentExtractionRunner._sanitize_filesystem_stem(old_masked)
            if old_masked_clean != raw_stem:
                mapping[(cat, f"{old_masked_clean}.txt")] = f"{raw_stem}.txt"
        return mapping

    def _extract_raw_name_from_header(self, txt_path: str) -> Optional[str]:
        """
        Lit les premières lignes d'une transcription pour récupérer le nom
        du fichier source enregistré dans l'en-tête.

        :param txt_path: Chemin complet vers le fichier .txt.
        :return: Nom de fichier .txt restauré ou None.
        """
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
        raw_stem: str = DocumentExtractionRunner._sanitize_filesystem_stem(stem)
        return f"{raw_stem}.txt"
    def _resolve_target_path(
        self, current_root: str, category: str, target_name: str
    ) -> str:
        """
        Détermine le chemin cible extracted_texts/AAAA-MM/Catégorie/fichier.txt.

        :param current_root: Dossier parent actuel du fichier.
        :param category: Catégorie thématique.
        :param target_name: Nom de fichier restauré.
        :return: Chemin complet cible sur disque.
        """
        if category in {"SMS", "Emails"}:
            return os.path.join(current_root, target_name)

        detected_period: Optional[str] = DocumentTextUtils.detect_period_in_text(target_name)
        if detected_period:
            return os.path.join(
                self.config.transcriptions_dir,
                detected_period,
                category,
                target_name,
            )
        return os.path.join(current_root, target_name)

    def _cleanup_empty_dirs(self, base_dir: str) -> None:
        """
        Supprime les sous-dossiers devenus vides après déplacement.

        :param base_dir: Répertoire racine extracted_texts.
        """
        for root_path, dirs, files in os.walk(base_dir, topdown=False):
            if root_path == base_dir:
                continue
            if not dirs and not files:
                try:
                    os.rmdir(root_path)
                except OSError:
                    pass

    def run(self) -> int:
        """
        Parcourt extracted_texts, restaure les noms et replace les fichiers
        dans leur dossier périodique AAAA-MM exact.

        :return: Nombre de fichiers déplacés ou renommés.
        """
        trans_dir: str = self.config.transcriptions_dir
        if not os.path.isdir(trans_dir):
            print(f"Dossier introuvable : '{trans_dir}'", flush=True)
            return 0

        fallback_map: Dict[Tuple[str, str], str] = self._build_masked_to_raw_map()
        moved_count: int = 0

        for root_path, _, files in os.walk(trans_dir):
            category: str = os.path.basename(root_path)
            for file_name in sorted(files):
                if (
                    file_name.startswith(".")
                    or file_name in {"rapport_extraction.txt", "extraction_report.txt"}
                    or not file_name.lower().endswith(".txt")
                ):
                    continue

                full_path: str = os.path.join(root_path, file_name)
                target_name: str = fallback_map.get((category, file_name), file_name)
                if target_name == file_name and (
                    "NUMERO_MASQUE" in file_name or "EMAIL_MASQUE" in file_name
                ):
                    extracted = self._extract_raw_name_from_header(full_path)
                    if extracted:
                        target_name = extracted

                new_path: str = self._resolve_target_path(root_path, category, target_name)
                if os.path.normpath(new_path) == os.path.normpath(full_path):
                    continue

                if os.path.exists(new_path):
                    print(f"[IGNORÉ - EXISTE DÉJÀ] '{full_path}' -> '{new_path}'", flush=True)
                    continue

                rel_src: str = os.path.relpath(full_path, trans_dir)
                rel_dst: str = os.path.relpath(new_path, trans_dir)
                mode_tag: str = "[SIMULATION]" if self.dry_run else "[DÉPLACÉ]"
                print(f"{mode_tag} '{rel_src}' -> '{rel_dst}'", flush=True)

                if not self.dry_run:
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
                    os.rename(full_path, new_path)
                moved_count += 1

        if not self.dry_run and moved_count > 0:
            self._cleanup_empty_dirs(trans_dir)

        action: str = "à déplacer/renommer" if self.dry_run else "traité(s)"
        print(f"\nBilan : {moved_count} fichier(s) {action}.", flush=True)
        return moved_count


def main() -> None:
    """Point d'entrée du script de restauration des noms."""
    parser = argparse.ArgumentParser(description="Restaure les noms bruts et classe par période AAAA-MM.")
    parser.add_argument("-c", "--config", default="config.ini", help="Chemin vers config.ini.")
    parser.add_argument("--apply", action="store_true", help="Applique réellement les renommages.")
    args = parser.parse_args()
    cfg_path: str = SharedCoreUtils.resolve_config_path(args.config, ROOT_DIR)
    TranscriptionNameRestorer(PipelineConfig(cfg_path), dry_run=not args.apply).run()


if __name__ == "__main__":
    main()
