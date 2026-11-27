import json
import os
import re
import shutil
from typing import Any, Dict, List, Optional, Set
from doc_anonymizer.chat_extractors import MultiPlatformChatExtractor
from doc_anonymizer.contact_csv_importer import ContactCatalogImporter
from doc_anonymizer.linked_sources_manager import LinkedSourcesManager
from doc_anonymizer.teams_chat_extractor import TeamsChatExtractor
from doc_anonymizer.text_utils import DocumentTextUtils


class ChatFilterManager:
    """Détecte les exports de messageries, gère un cache et filtre les conversations."""

    def __init__(self, paths: Dict[str, str], importer: ContactCatalogImporter) -> None:
        self.paths: Dict[str, str] = paths
        self.importer: ContactCatalogImporter = importer
        self.sources_dir: str = paths["sources_dir"]
        self.chat_exports_dir: str = os.path.join(self.sources_dir, "chat_exports")
        ws_root: str = paths.get("workspace_root") or os.path.dirname(self.sources_dir)
        self.audits_dir: str = os.path.join(ws_root, "audits")
        self.cache_file: str = os.path.join(self.audits_dir, ".chats_filter_cache.json")

    def _get_cache_file_path(self) -> str:
        return self.cache_file

    @staticmethod
    def is_chat_export_file(file_path: str) -> bool:
        if not os.path.isfile(file_path):
            return False
        fname: str = os.path.basename(file_path)
        low_fn: str = fname.lower()
        _, ext = os.path.splitext(low_fn)
        if fname.startswith(".") or low_fn in {"user_info.json", "group_info.json"}:
            return False
        if ext == ".vtt":
            return TeamsChatExtractor.is_teams_vtt_file(file_path)
        if ext in {".html", ".htm"}:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f_h:
                    return MultiPlatformChatExtractor.is_messenger_html_file(file_path, f_h.read(65536))
            except OSError:
                return False
        if ext in {".txt", ".md", ".csv", ".log"}:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f_t:
                    return MultiPlatformChatExtractor.is_whatsapp_text_file(f_t.read(16384))
            except OSError:
                return False
        if ext != ".json":
            return False
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f_j:
                data = json.load(f_j)
        except (OSError, ValueError, json.JSONDecodeError):
            return False
        return (
            MultiPlatformChatExtractor.is_google_chat_file(file_path, data)
            or MultiPlatformChatExtractor.is_instagram_json_file(file_path, data)
            or MultiPlatformChatExtractor.is_discord_json_file(file_path, data)
            or MultiPlatformChatExtractor.is_telegram_json_file(file_path, data)
            or MultiPlatformChatExtractor.is_signal_json_file(file_path, data)
        )

    def find_all_chat_files(self) -> List[str]:
        found: List[str] = []
        seen: Set[str] = set()
        for base in (self.sources_dir, self.chat_exports_dir):
            if not os.path.isdir(base):
                continue
            for root_p, dirs, files in os.walk(base):
                dirs[:] = [d for d in sorted(dirs) if not d.startswith(".")]
                for fn in sorted(files):
                    if fn.startswith("."):
                        continue
                    fp: str = os.path.normpath(os.path.join(root_p, fn))
                    norm_k: str = os.path.normcase(fp)
                    if norm_k not in seen and self.is_chat_export_file(fp):
                        seen.add(norm_k)
                        found.append(fp)
        ws_root: str = os.path.dirname(os.path.abspath(self.audits_dir))
        linked_files, _ = LinkedSourcesManager(ws_root).expand_linked_files(set())
        for fp in linked_files:
            norm_k = os.path.normcase(fp)
            if norm_k not in seen and self.is_chat_export_file(fp):
                seen.add(norm_k)
                found.append(fp)
        return sorted(found)

    def list_export_files(self) -> List[str]:
        return self.find_all_chat_files()
    def organize_chat_exports(self, move: bool = True) -> int:
        if not os.path.isdir(self.sources_dir):
            return 0
        moved: int = 0
        abs_chat_dir: str = os.path.abspath(self.chat_exports_dir)
        for root_p, dirs, files in os.walk(self.sources_dir):
            if os.path.abspath(root_p).startswith(abs_chat_dir):
                continue
            dirs[:] = [d for d in sorted(dirs) if not d.startswith(".")]
            for fn in sorted(files):
                if fn.startswith("."):
                    continue
                src_p: str = os.path.join(root_p, fn)
                if not self.is_chat_export_file(src_p):
                    continue
                os.makedirs(self.chat_exports_dir, exist_ok=True)
                dest_p: str = os.path.join(self.chat_exports_dir, fn)
                if os.path.abspath(src_p) == os.path.abspath(dest_p):
                    continue
                try:
                    shutil.move(src_p, dest_p) if move else shutil.copy2(src_p, dest_p)
                    moved += 1
                except OSError:
                    continue
        return moved

    @staticmethod
    def _inspect_chat_metadata(file_path: str) -> Dict[str, Any]:
        fname: str = os.path.basename(file_path)
        parent_name: str = os.path.basename(os.path.dirname(file_path))
        stem, ext_raw = os.path.splitext(fname)
        ext: str = ext_raw.lower()
        platform: str = "Messagerie"
        title: str = (
            parent_name
            if fname.lower() in {"messages.json", "message_1.json", "message_1.html", "_chat.txt"}
            and parent_name and parent_name.lower() != "chat_exports"
            else stem
        )
        participants: List[str] = []
        msg_count: int = 0

        def _add_p(raw_val: Any) -> None:
            s: str = str(raw_val or "").strip()
            if s and s not in participants:
                participants.append(s)

        if ext == ".vtt":
            platform = "Microsoft Teams"
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f_v:
                    for line in f_v:
                        m_v = re.match(r"<v\s+([^>]+)>", line.strip())
                        if m_v:
                            _add_p(m_v.group(1))
                            msg_count += 1
            except OSError:
                pass
            return {"platform": platform, "title": title, "participants": participants, "count": max(1, msg_count)}

        if ext in {".html", ".htm"}:
            platform = "Messenger"
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f_h:
                    raw_h: str = f_h.read(131072)
                m_t = re.search(r"<title[^>]*>(.*?)</title>", raw_h, re.IGNORECASE | re.DOTALL)
                if m_t:
                    title = re.sub(r"<[^>]+>", "", m_t.group(1)).strip() or title
            except OSError:
                pass
            return {"platform": platform, "title": title, "participants": participants, "count": max(1, msg_count)}

        if ext in {".txt", ".md", ".csv", ".log"}:
            platform = "WhatsApp"
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f_t:
                    for line in f_t:
                        clean_l: str = line.replace("\u202f", " ").replace("\xa0", " ").lstrip("\u200e\u200f\ufeff").rstrip()
                        m_wa = MultiPlatformChatExtractor.RE_WHATSAPP_LINE.match(clean_l)
                        if m_wa:
                            _add_p(m_wa.group(3))
                            msg_count += 1
            except OSError:
                pass
            return {"platform": platform, "title": title, "participants": participants, "count": max(1, msg_count)}

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f_j:
                data = json.load(f_j)
        except (OSError, ValueError, json.JSONDecodeError):
            return {"platform": platform, "title": title, "participants": participants, "count": 0}

        if MultiPlatformChatExtractor.is_google_chat_file(file_path, data):
            platform = "Google Chat"
        elif MultiPlatformChatExtractor.is_instagram_json_file(file_path, data):
            platform = "Instagram"
        elif MultiPlatformChatExtractor.is_discord_json_file(file_path, data):
            platform = "Discord"
        elif MultiPlatformChatExtractor.is_telegram_json_file(file_path, data):
            platform = "Telegram"
        elif MultiPlatformChatExtractor.is_signal_json_file(file_path, data):
            platform = "Signal"

        if isinstance(data, dict):
            title = str(data.get("channelName") or data.get("displayName") or data.get("name") or data.get("title") or title)
            for p_item in data.get("participants", []) if isinstance(data.get("participants"), list) else []:
                _add_p(p_item.get("name") or p_item.get("title") if isinstance(p_item, dict) else p_item)
            msgs: List[Any] = []
            for key in ("messages", "entries", "items"):
                if isinstance(data.get(key), list):
                    msgs = list(data[key])
                    break
            if not msgs and isinstance(data.get("conversations"), list):
                for conv in data["conversations"]:
                    if isinstance(conv, dict):
                        title = str(conv.get("name") or conv.get("title") or title)
                        for m_item in conv.get("members", []) if isinstance(conv.get("members"), list) else []:
                            _add_p(m_item.get("name") if isinstance(m_item, dict) else m_item)
                        for key in ("messages", "entries", "items"):
                            if isinstance(conv.get(key), list):
                                msgs.extend(conv[key])
            msg_count = len(msgs)
            for m in msgs[:200]:
                if not isinstance(m, dict):
                    continue
                raw_c = m.get("creator") or m.get("sender_name") or m.get("from") or m.get("author") or m.get("sender") or m.get("sourceName")
                if isinstance(raw_c, dict):
                    u_obj = raw_c.get("user") if isinstance(raw_c.get("user"), dict) else raw_c
                    _add_p(u_obj.get("displayName") or u_obj.get("name") or u_obj.get("email") or u_obj.get("phone"))
                elif raw_c:
                    _add_p(raw_c)
        return {"platform": platform, "title": title, "participants": participants, "count": max(1, msg_count)}

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
        for fp in self.find_all_chat_files():
            meta = self._inspect_chat_metadata(fp)
            norm_k: str = os.path.normpath(fp)
            norm_t: str = DocumentTextUtils.normalize_word(str(meta["title"]))
            is_kept: bool = (norm_t in existing_titles) if existing_titles is not None else True
            items.append({
                "file_path": norm_k,
                "path": norm_k,
                "platform": meta["platform"],
                "title": meta["title"],
                "conversation": meta["title"],
                "participants": list(meta["participants"]),
                "participants_display": ", ".join(meta["participants"]) if meta["participants"] else "Interlocuteurs non nommés",
                "count": int(meta["count"]),
                "messages_count": int(meta["count"]),
                "selected": is_kept,
            })
        items.sort(key=lambda it: (-int(it["count"]), str(it["conversation"]).lower()))
        try:
            os.makedirs(self.audits_dir, exist_ok=True)
            DocumentTextUtils.atomic_write_text(self.cache_file, json.dumps(items, ensure_ascii=False, indent=2))
        except OSError:
            pass
        return items

    def build_chat_filter_items(self) -> List[Dict[str, Any]]:
        return self.load_conversation_filter_items()

    def save_conversation_filter_selection(self, items: List[Dict[str, Any]]) -> int:
        selected_titles: List[str] = []
        seen: Set[str] = set()
        for it in items:
            if it.get("selected"):
                title: str = str(it.get("conversation") or it.get("title") or "").strip()
                norm_t: str = DocumentTextUtils.normalize_word(title)
                if title and norm_t and norm_t not in seen:
                    seen.add(norm_t)
                    selected_titles.append(title)
        os.makedirs(self.paths["contacts_dir"], exist_ok=True)
        wl_chat_file: str = os.path.join(self.paths["contacts_dir"], "whitelist_chats.json")
        DocumentTextUtils.atomic_write_text(wl_chat_file, json.dumps(selected_titles, ensure_ascii=False, indent=2))
        return len(selected_titles)

    def save_conversation_selection(self, items: List[Dict[str, Any]]) -> int:
        return self.save_conversation_filter_selection(items)
