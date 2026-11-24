# Commandes pip à exécuter : Aucune dépendance externe requise

from collections import defaultdict
from datetime import datetime
import html
import json
import os
import re
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class MultiPlatformChatExtractor:
    """
    Extrait, filtre selon les contacts sélectionnés et classe par mois (AAAA-MM)
    les conversations Google Chat (Takeout), WhatsApp (.txt), Messenger (Meta JSON/HTML)
    et Signal (JSON).
    """

    FRENCH_MONTH_MAP: Dict[str, str] = {
        "janvier": "01", "janv": "01", "jan": "01",
        "fevrier": "02", "fevr": "02", "feb": "02",
        "mars": "03", "mar": "03",
        "avril": "04", "avr": "04", "apr": "04",
        "mai": "05", "may": "05",
        "juin": "06", "jun": "06",
        "juillet": "07", "juil": "07", "jul": "07",
        "aout": "08", "aug": "08",
        "septembre": "09", "sept": "09", "sep": "09",
        "octobre": "10", "oct": "10",
        "novembre": "11", "nov": "11",
        "decembre": "12", "dec": "12",
    }

    WHATSAPP_LINE_RE = re.compile(
        r"^[\u200e\u200f]*"
        r"(?:\[(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})[,\s]+(\d{1,2}:\d{2}(?::\d{2})?)\]\s*"
        r"|(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})[,\s]+(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*)"
        r"([^:\n]{1,80}?)\s*:\s*(.*)$"
    )

    def __init__(self, config: PipelineConfig) -> None:
        self.config: PipelineConfig = config

    @staticmethod
    def _decode_meta_mojibake(raw_text: str) -> str:
        if not raw_text:
            return ""
        try:
            return raw_text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return DocumentTextUtils.repair_mojibake(raw_text)

    @staticmethod
    def _epoch_to_period_and_dt(raw_ts: Any) -> Tuple[str, str, int]:
        try:
            ts_val: float = float(raw_ts)
            if ts_val <= 0:
                return "0000-00", "Date inconnue", 0
            if ts_val > 1e11:
                ts_val /= 1000.0
            dt: datetime = datetime.fromtimestamp(ts_val)
            return dt.strftime("%Y-%m"), dt.strftime("%Y-%m-%d %H:%M:%S"), int(dt.timestamp())
        except (ValueError, TypeError, OSError):
            return "0000-00", "Date inconnue", 0

    @classmethod
    def parse_human_timestamp(cls, raw_date: str) -> Tuple[str, str, int]:
        cleaned: str = raw_date.strip()
        if not cleaned:
            return "0000-00", "Date inconnue", 0

        m_iso = re.search(r"(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})(?::(\d{2}))?", cleaned)
        if m_iso:
            y, mo, d, hh, mm, ss = m_iso.groups()
            s_pad: str = (ss or "00").zfill(2)
            return f"{y}-{mo}", f"{y}-{mo}-{d} {hh}:{mm}:{s_pad}", int(f"{y}{mo}{d}{hh}{mm}{s_pad}")

        m_fr = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})[,\s]+(\d{1,2}):(\d{2})(?::(\d{2}))?", cleaned)
        if m_fr:
            d_s, mo_s, y_s, hh_s, mm_s, ss_s = m_fr.groups()
            year_full: str = f"20{y_s}" if len(y_s) == 2 else y_s
            d_p, mo_p = d_s.zfill(2), mo_s.zfill(2)
            h_p, m_p, s_p = hh_s.zfill(2), mm_s.zfill(2), (ss_s or "00").zfill(2)
            return f"{year_full}-{mo_p}", f"{year_full}-{mo_p}-{d_p} {h_p}:{m_p}:{s_p}", int(f"{year_full}{mo_p}{d_p}{h_p}{m_p}{s_p}")

        from common.core_utils import SharedCoreUtils

        norm_date: str = SharedCoreUtils.strip_accents(cleaned.lower())
        m_text = re.search(
            r"\b(\d{1,2})\s+([a-z]{3,10})\.?\s+(20\d{2}|19\d{2})\b.*?(\d{1,2}):(\d{2})(?::(\d{2}))?",
            norm_date,
        )
        if m_text:
            day_s, month_w, year_s, hh_s, mm_s, ss_s = m_text.groups()
            mo_num: str = cls.FRENCH_MONTH_MAP.get(month_w, "00")
            if mo_num != "00":
                d_p, h_p, m_p = day_s.zfill(2), hh_s.zfill(2), mm_s.zfill(2)
                s_p = (ss_s or "00").zfill(2)
                return f"{year_s}-{mo_num}", f"{year_s}-{mo_num}-{d_p} {h_p}:{m_p}:{s_p}", int(f"{year_s}{mo_num}{d_p}{h_p}{m_p}{s_p}")

        fallback: str = DocumentTextUtils.detect_period_in_text(cleaned) or "0000-00"
        return fallback, cleaned, 0
    @staticmethod
    def _participants_match_filter(
        participants: Set[str],
        allowed_names: Optional[Set[str]],
    ) -> bool:
        """Vérifie si une conversation implique au moins un contact coché (lorsqu'un filtre est actif)."""
        if not allowed_names:
            return True
        for raw_p in participants:
            norm_p: str = DocumentTextUtils.normalize_word(raw_p)
            if not norm_p:
                continue
            if norm_p in allowed_names:
                return True
            for allowed in allowed_names:
                if len(allowed) >= 4 and (allowed in norm_p or norm_p in allowed):
                    return True
        return False

    @staticmethod
    def _record_extracted_participants(
        participants: Set[str],
        room_title: str,
        participants_out: Optional[List[str]],
    ) -> None:
        if participants_out is None:
            return
        seen: Set[str] = {p.lower() for p in participants_out}
        for name in sorted(participants):
            clean_n: str = name.strip()
            if clean_n and clean_n != room_title and clean_n.lower() not in seen:
                seen.add(clean_n.lower())
                participants_out.append(clean_n)

    def _group_entries_by_month(
        self, platform_label: str, room_title: str, entries: List[Tuple[str, int, str]]
    ) -> Dict[str, str]:
        by_month: DefaultDict[str, List[Tuple[int, str]]] = defaultdict(list)
        for period, sort_key, block in entries:
            by_month[period].append((sort_key, block))

        output: Dict[str, str] = {}
        for period, items in sorted(by_month.items()):
            items.sort(key=lambda x: x)
            header: str = (
                "========================================\n"
                f"{platform_label} : {room_title}\n"
                "----------------------------------------\n"
            )
            output[period] = header + "".join(b for _, b in items) + "\n"
        return output

    @classmethod
    def is_whatsapp_text_file(cls, raw_text: str) -> bool:
        if not raw_text:
            return False
        for line in raw_text.splitlines()[:40]:
            if cls.WHATSAPP_LINE_RE.match(line.strip()):
                return True
        return False

    def extract_whatsapp_text(
        self,
        file_path: str,
        raw_text: str,
        allowed_names: Optional[Set[str]] = None,
        participants_out: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        stem, _ = os.path.splitext(os.path.basename(file_path))
        room_title: str = re.sub(
            r"(?i)^discussion\s+whatsapp\s+avec\s+", "", stem
        ).strip() or stem

        entries: List[Tuple[str, int, str]] = []
        participants: Set[str] = {room_title}
        cur_period: str = "0000-00"
        cur_dt: str = "Date inconnue"
        cur_sort: int = 0
        cur_sender: str = ""
        cur_lines: List[str] = []

        def _flush_msg() -> None:
            if cur_sender and cur_lines:
                body_str: str = "\n".join(cur_lines).strip()
                if body_str:
                    blk: str = (
                        f"[{cur_dt}] DE : {cur_sender}\n"
                        f"{body_str}\n"
                        "----------------------------------------\n"
                    )
                    entries.append((cur_period, cur_sort, blk))

        for line in raw_text.splitlines():
            m = self.WHATSAPP_LINE_RE.match(line.strip())
            if m:
                _flush_msg()
                d_str: str = m.group(1) or m.group(3) or ""
                t_str: str = m.group(2) or m.group(4) or ""
                cur_sender = (m.group(5) or "").strip()
                if cur_sender:
                    participants.add(cur_sender)
                first_msg: str = (m.group(6) or "").strip()
                cur_period, cur_dt, cur_sort = self.parse_human_timestamp(f"{d_str} {t_str}")
                cur_lines = [first_msg] if first_msg else []
            elif cur_sender:
                cur_lines.append(line.rstrip())

        _flush_msg()
        self._record_extracted_participants(participants, room_title, participants_out)
        if not self._participants_match_filter(participants, allowed_names):
            return {}
        return self._group_entries_by_month("WHATSAPP", room_title, entries)
    @classmethod
    def is_messenger_html_file(cls, file_path: str, raw_html: str) -> bool:
        if not raw_html:
            return False
        markers: Tuple[str, ...] = ("_a6-g", "_a6-p", "_a6-o", "_2pin", "pam _3-95", "_2lel")
        if any(m in raw_html for m in markers):
            return True
        norm_path: str = file_path.replace("\\", "/").lower()
        return "/inbox/" in norm_path and "message_" in os.path.basename(norm_path)

    def extract_messenger_html(
        self,
        file_path: str,
        raw_html: str,
        allowed_names: Optional[Set[str]] = None,
        participants_out: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        title_match = re.search(r"(?is)<title>(.*?)</title>", raw_html)
        room_title: str = (
            (html.unescape(title_match.group(1)).strip() if title_match else "")
            or os.path.basename(os.path.dirname(file_path))
            or "Conversation Messenger"
        )
        participants: Set[str] = {room_title}
        entries: List[Tuple[str, int, str]] = []
        block_re = re.compile(
            r'(?is)<div[^>]*class="[^"]*(?:_a6-g|_3-96|_2lel|pam)[^"]*"[^>]*>'
            r'.*?<div[^>]*class="[^"]*(?:_2pin|_a6-h|_3-95|_2lel)[^"]*"[^>]*>(.*?)</div>'
            r'.*?<div[^>]*class="[^"]*(?:_a6-p|_3-96|_2let)[^"]*"[^>]*>(.*?)</div>\s*</div>'
            r'.*?<div[^>]*class="[^"]*(?:_a6-o|_3-94|_2lem)[^"]*"[^>]*>(.*?)</div>'
        )
        for m in block_re.finditer(raw_html):
            sender: str = DocumentTextUtils.html_to_plain_text(m.group(1)).strip()
            if sender:
                participants.add(sender)
            body: str = DocumentTextUtils.html_to_plain_text(m.group(2)).strip()
            raw_date: str = DocumentTextUtils.html_to_plain_text(m.group(3)).strip()
            if not body:
                continue
            period, dt_str, sort_k = self.parse_human_timestamp(raw_date)
            block: str = f"[{dt_str}] DE : {sender or 'Expéditeur inconnu'}\n{body}\n----------------------------------------\n"
            entries.append((period, sort_k, block))

        self._record_extracted_participants(participants, room_title, participants_out)
        if not self._participants_match_filter(participants, allowed_names):
            return {}
        return self._group_entries_by_month("MESSENGER", room_title, entries)

    def _extract_messenger_json(
        self,
        file_path: str,
        payload: Dict[str, Any],
        allowed_names: Optional[Set[str]] = None,
        participants_out: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        room_title: str = self._decode_meta_mojibake(str(payload.get("title") or "")).strip() or os.path.basename(os.path.dirname(file_path)) or "Conversation Messenger"
        participants: Set[str] = {room_title}
        for p in payload.get("participants", []):
            if isinstance(p, dict) and p.get("name"):
                participants.add(self._decode_meta_mojibake(str(p["name"])).strip())
        entries: List[Tuple[str, int, str]] = []
        for msg in payload.get("messages", []):
            if not isinstance(msg, dict):
                continue
            sender: str = self._decode_meta_mojibake(str(msg.get("sender_name") or "")).strip()
            if sender:
                participants.add(sender)
            content: str = self._decode_meta_mojibake(str(msg.get("content") or "")).strip()
            if not content:
                continue
            period, dt_str, sort_k = self._epoch_to_period_and_dt(msg.get("timestamp_ms", 0))
            block: str = f"[{dt_str}] DE : {sender or 'Expéditeur inconnu'}\n{content}\n----------------------------------------\n"
            entries.append((period, sort_k, block))
        self._record_extracted_participants(participants, room_title, participants_out)
        if not self._participants_match_filter(participants, allowed_names):
            return {}
        return self._group_entries_by_month("MESSENGER", room_title, entries)

    def _extract_google_chat(
        self,
        file_path: str,
        payload: Dict[str, Any],
        allowed_emails: Set[str],
        discovered_emails: Set[str],
        allowed_names: Optional[Set[str]] = None,
        participants_out: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        parent_dir: str = os.path.dirname(file_path)
        room_title: str = ""
        group_info_path: str = os.path.join(parent_dir, "group_info.json")
        if os.path.isfile(group_info_path):
            try:
                with open(group_info_path, "r", encoding="utf-8", errors="ignore") as f_gi:
                    gi = json.load(f_gi)
                if isinstance(gi, dict):
                    room_title = str(gi.get("name") or "").strip()
            except Exception:
                pass
        room_title = room_title or os.path.basename(parent_dir) or "Google Chat"
        participants: Set[str] = {room_title}
        conv_emails: Set[str] = set()
        entries: List[Tuple[str, int, str]] = []
        for msg in payload.get("messages", []):
            if not isinstance(msg, dict):
                continue
            creator = msg.get("creator") if isinstance(msg.get("creator"), dict) else {}
            c_name: str = str(creator.get("name") or "").strip()
            c_mail: str = DocumentTextUtils.normalize_identifier(str(creator.get("email") or ""))
            if c_name:
                participants.add(c_name)
            if "@" in c_mail:
                conv_emails.add(c_mail)
                discovered_emails.add(f"{c_mail}|{c_name}" if len(c_name.split()) >= 2 else c_mail)
            text_body: str = str(msg.get("text") or "").strip()
            att_names: List[str] = [
                str(a.get("original_name") or a.get("export_name") or "").strip()
                for a in msg.get("attached_files", [])
                if isinstance(a, dict) and (a.get("original_name") or a.get("export_name"))
            ]
            att_line: str = f"[Pièce(s) jointe(s) : {', '.join(att_names)}]\n" if att_names else ""
            if not text_body and not att_line:
                continue
            period, dt_str, sort_k = self.parse_human_timestamp(str(msg.get("created_date") or ""))
            sender_disp: str = f"{c_name} ({c_mail})" if (c_name and c_mail) else (c_name or c_mail or "Utilisateur Google Chat")
            block: str = f"[{dt_str}] DE : {sender_disp}\n{att_line}{text_body}\n----------------------------------------\n"
            entries.append((period, sort_k, block))
        self._record_extracted_participants(participants, room_title, participants_out)
        if allowed_emails and conv_emails and not (conv_emails & allowed_emails):
            return {}
        if not self._participants_match_filter(participants, allowed_names):
            return {}
        return self._group_entries_by_month("GOOGLE CHAT", room_title, entries)
    def _extract_signal_json(
        self,
        file_path: str,
        payload: Any,
        target_phones: Dict[str, str],
        discovered_phones: Set[str],
        allowed_names: Optional[Set[str]] = None,
        participants_out: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        raw_msgs: List[Any] = payload.get("messages", []) if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])
        file_stem, _ = os.path.splitext(os.path.basename(file_path))
        room_title: str = (str(payload.get("title") or payload.get("name") or "").strip() if isinstance(payload, dict) else "") or file_stem

        conv_phones: Set[str] = set()
        participants: Set[str] = {room_title}
        entries: List[Tuple[str, int, str]] = []

        for msg in raw_msgs:
            if not isinstance(msg, dict):
                continue
            body: str = str(msg.get("body") or msg.get("text") or "").strip()
            attachments: Any = msg.get("attachments")
            att_line: str = f"[Pièce(s) jointe(s) Signal : {len(attachments)}]\n" if isinstance(attachments, list) and attachments else ""
            if not body and not att_line:
                continue
            raw_src: str = str(msg.get("source") or msg.get("address") or msg.get("phone") or "").strip()
            src_name: str = str(msg.get("sourceName") or msg.get("sender") or "").strip()
            if src_name:
                participants.add(src_name)
            norm_phone: str = DocumentTextUtils.normalize_any_phone(raw_src)
            if norm_phone:
                discovered_phones.add(norm_phone)
                conv_phones.add(norm_phone)

            msg_type: str = str(msg.get("type") or "").lower()
            sender_disp: str = "{MAIN_CHARACTER} (sortant)" if msg_type in {"outgoing", "sent"} else (src_name or norm_phone or "Contact Signal")
            raw_ts: Any = msg.get("timestamp") or msg.get("sent_at") or msg.get("date")
            period, dt_str, sort_k = self._epoch_to_period_and_dt(raw_ts) if (isinstance(raw_ts, (int, float)) or (isinstance(raw_ts, str) and raw_ts.isdigit())) else self.parse_human_timestamp(str(raw_ts or ""))
            block: str = f"[{dt_str}] DE : {sender_disp}\n{att_line}{body}\n----------------------------------------\n"
            entries.append((period, sort_k, block))

        self._record_extracted_participants(participants, room_title, participants_out)
        if target_phones or allowed_names:
            phone_ok: bool = bool(target_phones and conv_phones and (conv_phones & set(target_phones.keys())))
            name_ok: bool = bool(allowed_names and self._participants_match_filter(participants, allowed_names))
            if not (phone_ok or name_ok):
                return {}
        return self._group_entries_by_month("SIGNAL", room_title, entries)

    def extract_json_chat(
        self,
        file_path: str,
        target_phones: Dict[str, str],
        allowed_emails: Set[str],
        discovered_phones: Set[str],
        discovered_emails: Set[str],
        allowed_names: Optional[Set[str]] = None,
        participants_out: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, str], Optional[str]]:
        from doc_anonymizer.teams_chat_extractor import TeamsChatExtractor

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                payload: Any = json.load(f)
        except Exception as exc:
            return {}, f"Erreur lecture JSON ({exc})"

        if TeamsChatExtractor.is_teams_json_payload(payload):
            buckets_t = TeamsChatExtractor(self.config).extract_teams_json(file_path, payload, discovered_emails)
            if participants_out is not None:
                seen_t: Set[str] = {p.lower() for p in participants_out}
                for txt_b in buckets_t.values():
                    for m_s in re.finditer(r"^\[[^\]]+\]\s*DE\s*:\s*([^\r\n(]+)", txt_b, re.MULTILINE):
                        spk: str = m_s.group(1).strip()
                        if spk and spk.lower() not in seen_t:
                            seen_t.add(spk.lower())
                            participants_out.append(spk)
            return buckets_t, None

        if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
            msgs: List[Any] = payload["messages"]
            sample: Any = next(iter(msgs), None)
            base_low: str = os.path.basename(file_path).lower()
            if "participants" in payload or (isinstance(sample, dict) and ("sender_name" in sample or "timestamp_ms" in sample)):
                return self._extract_messenger_json(file_path, payload, allowed_names=allowed_names, participants_out=participants_out), None
            if isinstance(sample, dict) and any(k in sample for k in ("source", "sourceName", "threadId", "sent_at")):
                return self._extract_signal_json(file_path, payload, target_phones, discovered_phones, allowed_names=allowed_names, participants_out=participants_out), None
            if base_low == "messages.json" or (isinstance(sample, dict) and ("creator" in sample or "created_date" in sample)):
                return self._extract_google_chat(file_path, payload, allowed_emails, discovered_emails, allowed_names=allowed_names, participants_out=participants_out), None

        if isinstance(payload, list) and payload:
            first_item: Any = next(iter(payload), None)
            if isinstance(first_item, dict) and any(k in first_item for k in ("source", "sourceName", "body", "timestamp")):
                return self._extract_signal_json(file_path, payload, target_phones, discovered_phones, allowed_names=allowed_names, participants_out=participants_out), None

        return {}, None
