# Commandes pip à exécuter : Aucune dépendance externe requise

import os
from typing import List
from doc_anonymizer.audit_state_manager import AuditAndStateManager
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.source_mapping_manager import SourceMappingManager
from doc_anonymizer.text_utils import DocumentTextUtils


class AnonymizedBatchWriter:
    """Gère le découpage par lots (batch_XX/anonymized_part_XXX.txt) et leur écriture atomique."""

    def __init__(
        self,
        config: PipelineConfig,
        audit: AuditAndStateManager,
        source_mapper: SourceMappingManager,
    ) -> None:
        self.config: PipelineConfig = config
        self.audit: AuditAndStateManager = audit
        self.source_mapper: SourceMappingManager = source_mapper
        self.current_chunk: List[str] = []
        self.current_chunk_keys: List[str] = []
        self.current_size: int = 0

    def add_block(self, block: str, anon_header_path: str) -> None:
        """Ajoute un bloc documentaire au tampon courant et vide le lot si le seuil est atteint."""
        block_bytes: int = len(block.encode("utf-8"))
        if self.current_chunk and (
            self.current_size + block_bytes > self.config.max_batch_bytes
            or len(self.current_chunk) >= self.config.max_batch_files
        ):
            self.flush()

        self.current_chunk.append(block)
        self.current_chunk_keys.append(anon_header_path)
        self.current_size += block_bytes

    def flush(self) -> None:
        """Écrit sur disque le lot courant, met à jour la cartographie des sources et l'audit."""
        if not self.current_chunk:
            return
        folder_num: int = ((self.audit.file_idx - 1) // self.config.files_per_folder) + 1
        batch_folder: str = os.path.join(self.config.results_dir, f"batch_{folder_num:02d}")
        os.makedirs(batch_folder, exist_ok=True)
        out_file: str = os.path.join(
            batch_folder, f"{self.config.file_prefix}part_{self.audit.file_idx:03d}.txt"
        )
        merged_content: str = "".join(self.current_chunk)
        DocumentTextUtils.atomic_write_text(out_file, merged_content)

        self.source_mapper.update_batch_for_keys(self.current_chunk_keys, out_file)
        self.source_mapper.save()

        count: int = self.audit.write_report()
        self.audit.save()
        print(f"    [+] LOT ÉCRIT : '{out_file}' (Audit : {count} nom(s))", flush=True)
        self.audit.file_idx += 1
        self.current_chunk.clear()
        self.current_chunk_keys.clear()
        self.current_size = 0
