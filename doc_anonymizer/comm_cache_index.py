import hashlib
import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple
from doc_anonymizer.text_utils import DocumentTextUtils


class CommunicationExtractionCache:
    """Indexe sur disque les blocs SMS et Chats par fichier source."""

    def __init__(self, audits_dir: str) -> None:
        self.cache_dir: str = os.path.join(
            os.path.abspath(audits_dir), ".comm_extraction_cache"
        )

    @staticmethod
    def _file_signature(file_path: str) -> Optional[Tuple[str, int, int]]:
        try:
            st = os.stat(file_path)
            return (os.path.abspath(file_path), int(st.st_size), int(st.st_mtime_ns))
        except OSError:
            return None

    def _entry_path(self, file_path: str) -> Optional[Tuple[str, List[Any]]]:
        sig = self._file_signature(file_path)
        if sig is None:
            return None
        abs_p, sz, mt = sig
        digest: str = hashlib.sha256(
            os.path.normcase(abs_p).encode("utf-8")
        ).hexdigest()[:24]
        return os.path.join(self.cache_dir, f"{digest}.json"), [abs_p, sz, mt]

    def get_or_build(
        self,
        source_path: str,
        kind: str,
        builder_fn: Callable[[], Any],
    ) -> Any:
        """Retourne les données indexées depuis le cache disque ou builder_fn."""
        info = self._entry_path(source_path)
        if info is not None:
            c_path, sig_list = info
            if os.path.isfile(c_path):
                try:
                    with open(c_path, "r", encoding="utf-8") as f_in:
                        payload = json.load(f_in)
                    if (
                        isinstance(payload, dict)
                        and payload.get("kind") == kind
                        and payload.get("sig") == sig_list
                    ):
                        return payload.get("data")
                except (OSError, ValueError, json.JSONDecodeError):
                    pass
        built = builder_fn()
        if info is not None:
            c_path, sig_list = info
            try:
                os.makedirs(self.cache_dir, exist_ok=True)
                DocumentTextUtils.atomic_write_text(
                    c_path,
                    json.dumps(
                        {"kind": kind, "sig": sig_list, "data": built},
                        ensure_ascii=False,
                    ),
                )
            except OSError:
                pass
        return built
