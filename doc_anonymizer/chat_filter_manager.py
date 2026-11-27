import json
import os
import re
import shutil
from typing import Any, Dict, List, Optional, Set
from doc_anonymizer.chat_extractors import MultiPlatformChatExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_csv_importer import ContactCatalogImporter
from doc_anonymizer.duplicate_files_manager import DuplicateFilesManager
from doc_anonymizer.linked_sources_manager import LinkedSourcesManager
from doc_anonymizer.teams_chat_extractor import TeamsChatExtractor
from doc_anonymizer.text_utils import DocumentTextUtils


class ChatFilterManager:
    """Détecte les exports de messageries, gère un cache et filtre les conversations."""

    WHATSAPP_LINE_RE = re.compile(
        r"^\[?\d{1,4}[/.\-]\d{1,2}[/.\-]\d{2,4}[,\s]+\d{1,2}:\d{2}"
    )

    def __init__(self, paths: Dict[str, str], importer: ContactCatalogImporter) -> None:
        self.paths: Dict[str, str] = paths
        self.importer: ContactCatalogImporter = importer

    def _get_cache_file_path(self) -> str:
        ws_root: str = (
            self.paths.get("workspace_root")
            or os.path.dirname(self.paths["contacts_dir"])
        )
        return os.path.join(ws_root, "audits", ".chats_filter_cache.json")

    @classmethod
    def _detect_chat_platform(cls, file_path: str) -> Optional[str]:
        if not file_path or not os.path.isfile(file_path):
            return None
        fname: str = os.path.basename(file_path)
        low_fn: str = fname.lower()
        if fname.startswith(".") or low_fn in {"group_info.json", "user_info.json"}:
            return None
        ext: str = os.path.splitext(low_fn)[-1]
        norm_unix: str = file_path.replace("\\", "/").lower()
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f_h:
                head: str = f_h.read(8192)
        except OSError:
            return None
        if ext == ".vtt" and "WEBVTT" in head[:120]:
            return "Microsoft Teams (.vtt)"
        if ext == ".txt" and cls.WHATSAPP_LINE_RE.search(head.lstrip()):
            return "WhatsApp"
        if ext in {".html", ".htm"} and (
            "messenger" in norm_unix or "_2-p_" in head or "pam _3-95" in head
        ):
            return "Messenger (HTML)"
        if ext == ".json":
            if '"messages"' in head and ('"creator"' in head or "google chat" in norm_unix):
                return "Google Chat"
            if '"messages"' in head and ('"sender_name"' in head or "messages/" in norm_unix):
                return "Messenger / Instagram"
            if '"conversations"' in head or ('"messages"' in head and ('"from"' in head or '"displayname"' in head.lower())):
                return "Microsoft Teams"
            if '"source"' in head and ('"sourcename"' in head.lower() or '"body"' in head):
                return "Signal"
        return None

    @classmethod
    def is_chat_export_file(cls, file_path: str) -> bool:
        return cls._detect_chat_platform(file_path) is not None

    def list_export_files(self) -> List[str]:
        src_dir: str = self.paths["sources_dir"]
        ws_root: str = self.paths.get("workspace_root") or os.path.dirname(src_dir)
        ignored_dups: Set[str] = DuplicateFilesManager(self.paths).load_ignored_paths()
        found: List[str] = []
        seen: Set[str] = set()
        if os.path.isdir(src_dir):
            for root, _, files in os.walk(src_dir):
                for fn in sorted(files):
                    full_p: str = os.path.normpath(os.path.join(root, fn))
                    norm_k: str = os.path.normcase(full_p)
                    if norm_k in ignored_dups or norm_k in seen:
                        continue
                    if self.is_chat_export_file(full_p):
                        seen.add(norm_k)
                        found.append(full_p)
        linked, _ = LinkedSourcesManager(ws_root).expand_linked_files(set())
        for full_p in linked:
            norm_k = os.path.normcase(full_p)
            if norm_k in ignored_dups or norm_k in seen:
                continue
            if self.is_chat_export_file(full_p):
                seen.add(norm_k)
                found.append(full_p)
        return found
    def organize_chat_exports(self, move: bool = True) -> int:
        src_dir: str = self.paths["sources_dir"]
        if not os.path.isdir(src_dir):
            return 0
        chat_dir: str = os.path.abspath(os.path.join(src_dir, "chat_exports"))
        moved_count: int = 0
        for root, _, files in os.walk(src_dir):
            if os.path.abspath(root).startswith(chat_dir):
                continue
            for fn in sorted(files):
                full_p: str = os.path.join(root, fn)
                if not self.is_chat_export_file(full_p):
                    continue
                os.makedirs(chat_dir, exist_ok=True)
                dest_p: str = os.path.join(chat_dir, fn)
                if os.path.abspath(full_p) == os.path.abspath(dest_p):
                    continue
                if os.path.exists(dest_p):
                    stem, ext = os.path.splitext(fn)
                    idx: int = 2
                    while os.path.exists(os.path.join(chat_dir, f"{stem}_{idx}{ext}")):
                        idx += 1
                    dest_p = os.path.join(chat_dir, f"{stem}_{idx}{ext}")
                if move:
                    shutil.move(full_p, dest_p)
                else:
                    shutil.copy2(full_p, dest_p)
                moved_count += 1
        return moved_count

    @classmethod
    def inspect_chat_file_metadata(cls, file_path: str) -> Optional[Dict[str, Any]]:
        platform: Optional[str] = cls._detect_chat_platform(file_path)
        if not platform:
            return None
        fname: str = os.path.basename(file_path)
        parent_name: str = os.path.basename(os.path.dirname(file_path))
        stem, ext_raw = os.path.splitext(fname)
        ext: str = ext_raw.lower()
        title: str = (
            parent_name
            if fname.lower() in {"messages.json", "message_1.json", "message_1.html", "_chat.txt"}
            and parent_name
            and parent_name.lower() != "chat_exports"
            else stem
        )
        cfg = PipelineConfig.__new__(PipelineConfig)
        dummy_p: Set[str] = set()
        dummy_e: Set[str] = set()
        participants: List[str] = []
        msg_count: int = 0
        try:
            if ext == ".vtt":
                txt, _ = TeamsChatExtractor(cfg).extract_teams_vtt(file_path)
                found_p: List[str] = []
                for ln in txt.splitlines():
                    if " : " in ln:
                        msg_count += 1
                        spk: str = re.sub(r"^\[[^\]]+\]\s*", "", ln.split(" : ", 1)[0]).strip()
                        if spk and spk not in found_p:
                            found_p.append(spk)
                participants = found_p
            elif ext == ".json":
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f_j:
                    data = json.load(f_j)
                if isinstance(data, dict) and isinstance(data.get("title"), str) and data["title"].strip():
                    title = data["title"].strip()
                buckets, _ = MultiPlatformChatExtractor(cfg).extract_json_chat(
                    file_path, {}, set(), dummy_p, dummy_e,
                    allowed_names=set(), participants_out=participants,
                )
                msg_count = sum(b.count("\n[") + (1 if b.startswith("[") else 0) for b in buckets.values())
            elif ext in {".html", ".htm"}:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f_h:
                    raw_h: str = f_h.read()
                buckets = MultiPlatformChatExtractor(cfg).extract_messenger_html(
                    file_path, raw_h, allowed_names=set(), participants_out=participants,
                )
                msg_count = sum(b.count("\n[") + (1 if b.startswith("[") else 0) for b in buckets.values())
            elif ext == ".txt":
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f_t:
                    raw_t: str = f_t.read()
                buckets = MultiPlatformChatExtractor(cfg).extract_whatsapp_text(
                    file_path, raw_t, allowed_names=set(), participants_out=participants,
                )
                msg_count = sum(b.count("\n[") + (1 if b.startswith("[") else 0) for b in buckets.values())
        except Exception:
            pass
        return {
            "file_path": file_path,
            "platform": platform,
            "title": title,
            "participants": participants,
            "participants_display": ", ".join(participants) if participants else "Interlocuteurs non nommés",
            "count": max(1, msg_count),
        }

    def _inspect_files_cached(self, chat_files: List[str]) -> List[Dict[str, Any]]:
        sig: List[List[Any]] = []
        for cp in sorted(chat_files):
            try:
                st = os.stat(cp)
                sig.append([os.path.abspath(cp), int(st.st_size), int(st.st_mtime_ns)])
            except OSError:
                continue
        cache_path: str = self._get_cache_file_path()
        if sig and os.path.isfile(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f_c:
                    cached = json.load(f_c)
                if isinstance(cached, dict) and cached.get("signature") == sig and isinstance(cached.get("metas"), list):
                    return list(cached["metas"])
            except (OSError, json.JSONDecodeError):
                pass
        metas: List[Dict[str, Any]] = []
        for fp in chat_files:
            m = self.inspect_chat_file_metadata(fp)
            if m is not None:
                metas.append(m)
        if sig:
            try:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                DocumentTextUtils.atomic_write_text(
                    cache_path, json.dumps({"signature": sig, "metas": metas}, ensure_ascii=False)
                )
            except OSError:
                pass
        return metas

    def load_conversation_filter_items(self) -> List[Dict[str, Any]]:
        wl_chat_file: str = os.path.join(self.paths["contacts_dir"], "whitelist_chats.json")
        existing_titles: Optional[Set[str]] = None
        if os.path.isfile(wl_chat_file):
            try:
                with open(wl_chat_file, "r", encoding="utf-8") as f_wc:
                    data = json.load(f_wc)
                if isinstance(data, list):
                    existing_titles = {DocumentTextUtils.normalize_word(str(x)) for x in data if str(x).strip()}
            except (OSError, json.JSONDecodeError):
                pass
        items: List[Dict[str, Any]] = []
        for meta in self._inspect_files_cached(self.list_export_files()):
            norm_t: str = DocumentTextUtils.normalize_word(str(meta["title"]))
            is_kept: bool = (norm_t in existing_titles) if existing_titles is not None else True
            items.append({
                "file_path": meta["file_path"],
                "platform": meta["platform"],
                "conversation": meta["title"],
                "participants": meta["participants"],
                "participants_display": meta["participants_display"],
                "count": int(meta["count"]),
                "selected": is_kept,
            })
        items.sort(key=lambda it: (-int(it["count"]), str(it["conversation"]).lower()))
        return items

    def save_conversation_filter_selection(self, items: List[Dict[str, Any]]) -> int:
        selected_titles: List[str] = []
        seen: Set[str] = set()
        for it in items:
            if it.get("selected"):
                title: str = str(it.get("conversation") or "").strip()
                norm_t: str = DocumentTextUtils.normalize_word(title)
                if title and norm_t and norm_t not in seen:
                    seen.add(norm_t)
                    selected_titles.append(title)
        os.makedirs(self.paths["contacts_dir"], exist_ok=True)
        wl_chat_file: str = os.path.join(self.paths["contacts_dir"], "whitelist_chats.json")
        DocumentTextUtils.atomic_write_text(wl_chat_file, json.dumps(selected_titles, ensure_ascii=False, indent=2))
        return len(selected_titles)
