import json
import os
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any, Dict, List, Optional, Set, Tuple
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.extraction_helpers import ExtractionFilterLoader
from doc_anonymizer.text_utils import DocumentTextUtils


class MultiPlatformChatExtractor:
    """
    Extrait et filtre les discussions multi-plateformes :
    Google Chat (Takeout), Messenger HTML/JSON, WhatsApp TXT,
    Instagram JSON, Discord JSON, Telegram JSON, Signal JSON et Teams JSON.
    """

    RE_WHATSAPP_LINE = re.compile(
        r"^[\u200e\u200f\ufeff\s]*\[?"
        r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})"
        r"[, àa\s]+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap]\.?[Mm]\.?)?)"
        r"\]?\s*(?:-|\u2013|:)?\s*([^:]{1,60}):\s*(.*)$"
    )
    RE_HTML_TAG = re.compile(r"<[^>]+>")
    RE_MOIS_FR = {
        "janv": "01", "janvier": "01", "jan": "01",
        "févr": "02", "février": "02", "fevr": "02", "fevrier": "02", "feb": "02",
        "mars": "03", "mar": "03",
        "avr": "04", "avril": "04", "apr": "04",
        "mai": "05", "may": "05",
        "juin": "06", "jun": "06",
        "juil": "07", "juillet": "07", "jul": "07",
        "août": "08", "aout": "08", "aug": "08",
        "sept": "09", "septembre": "09", "sep": "09",
        "oct": "10", "octobre": "10",
        "nov": "11", "novembre": "11",
        "déc": "12", "décembre": "12", "dec": "12", "decembre": "12",
    }

    def __init__(self, config: PipelineConfig) -> None:
        self.config: PipelineConfig = config
    @staticmethod
    def _is_sender_allowed(
        sender: str, allowed_names: Optional[Set[str]]
    ) -> bool:
        """Vérifie si l'expéditeur est autorisé par la liste blanche contacts."""
        if allowed_names is None:
            return True
        if not allowed_names:
            return False
        norm_s: str = DocumentTextUtils.normalize_identifier(sender)
        if not norm_s:
            return False
        if norm_s in allowed_names:
            return True
        s_tokens: Set[str] = {t for t in norm_s.split() if len(t) >= 3}
        for allowed in allowed_names:
            a_tokens: Set[str] = {t for t in allowed.split() if len(t) >= 3}
            if a_tokens and a_tokens.issubset(s_tokens):
                return True
        return False

    @classmethod
    def is_whatsapp_text_file(cls, sample_text: str) -> bool:
        """Détecte un export texte WhatsApp."""
        for raw_line in sample_text.splitlines()[:40]:
            cleaned: str = raw_line.replace("\u202f", " ").replace("\xa0", " ").strip()
            if cls.RE_WHATSAPP_LINE.match(cleaned):
                return True
        return False

    @staticmethod
    def is_messenger_html_file(file_path: str, sample_html: str) -> bool:
        """Détecte un export HTML Facebook Messenger."""
        low_p: str = file_path.replace("\\", "/").lower()
        low_h: str = sample_html.lower()
        if any(k in low_p for k in ("/messages/inbox/", "/messenger/inbox/", "/messages/archived_threads/", "/messages/filtered_threads/", "/your_facebook_activity/messages/")):
            return True
        if any(k in low_h for k in ("pam _3-95", "_3-95", "_a6-g", "_a6-p")):
            return True
        return ("facebook" in low_h or "messenger" in low_h) and "messages" in low_h

    @staticmethod
    def is_google_chat_file(file_path: str, data: Any) -> bool:
        """Détecte un export JSON Google Chat Takeout."""
        low_p: str = file_path.replace("\\", "/").lower()
        if ("google chat" in low_p or "/groups/" in low_p) and isinstance(data, dict) and isinstance(data.get("messages"), list):
            return True
        if isinstance(data, dict) and isinstance(data.get("messages"), list) and data["messages"]:
            first = next(iter(data["messages"]), None)
            if isinstance(first, dict) and ("creator" in first or "created_date" in first):
                return True
        return False

    @staticmethod
    def is_instagram_json_file(file_path: str, data: Any) -> bool:
        """Détecte un export JSON Messenger / Instagram."""
        return isinstance(data, dict) and isinstance(data.get("participants"), list) and isinstance(data.get("messages"), list)

    @staticmethod
    def is_discord_json_file(file_path: str, data: Any) -> bool:
        """Détecte un export JSON Discord."""
        low_p: str = file_path.replace("\\", "/").lower()
        if not isinstance(data, dict):
            return False
        return ("discord" in low_p and isinstance(data.get("messages"), list)) or isinstance(data.get("guild"), dict) or isinstance(data.get("channel"), dict)

    @staticmethod
    def is_telegram_json_file(file_path: str, data: Any) -> bool:
        """Détecte un export JSON Telegram."""
        if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
            return False
        if "id" in data and data.get("type") in {"personal_chat", "private_group", "private_supergroup", "public_group", "public_supergroup"}:
            return True
        first = next(iter(data["messages"]), None) if data["messages"] else None
        return isinstance(first, dict) and ("date_unixtime" in first or "from" in first)

    @staticmethod
    def is_signal_json_file(file_path: str, data: Any) -> bool:
        """Détecte un export JSON Signal."""
        low_p: str = file_path.replace("\\", "/").lower()
        return ("signal" in low_p and isinstance(data, (dict, list))) or (isinstance(data, dict) and isinstance(data.get("conversations"), list))
    @staticmethod
    def _decode_fb_mojibake(text: str) -> str:
        """Corrige l'encodage Latin-1/UTF-8 des exports JSON Meta."""
        if not text:
            return ""
        try:
            return text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return text

    @staticmethod
    def _ts_to_period(raw_ts: Any) -> str:
        """Convertit un horodatage numérique ou textuel en période AAAA-MM."""
        if raw_ts is None:
            return "Date_Inconnue"
        if isinstance(raw_ts, (int, float)):
            val: float = float(raw_ts)
            if val > 1e11:
                val /= 1000.0
            try:
                return datetime.fromtimestamp(val, tz=timezone.utc).strftime("%Y-%m")
            except (ValueError, OSError):
                return "Date_Inconnue"
        s_ts: str = str(raw_ts).strip()
        if s_ts.isdigit():
            return MultiPlatformChatExtractor._ts_to_period(int(s_ts))
        m_iso = re.match(r"(\d{4})[-/](\d{2})", s_ts)
        if m_iso:
            return f"{m_iso.group(1)}-{m_iso.group(2)}"
        m_en = re.search(r"\b([A-Za-z]+)\s+\d{1,2},\s+(20\d{2})\b", s_ts)
        if m_en:
            mon_num_en: Optional[str] = MultiPlatformChatExtractor.RE_MOIS_FR.get(m_en.group(1).lower())
            if mon_num_en:
                return f"{m_en.group(2)}-{mon_num_en}"
        m_fr = re.search(r"\b(\d{1,2})\s+([a-zA-Zéèêëàâäîïôöùûüç.]+)\s+(20\d{2})\b", s_ts)
        if m_fr:
            mon_num: Optional[str] = MultiPlatformChatExtractor.RE_MOIS_FR.get(m_fr.group(2).lower().rstrip("."))
            if mon_num:
                return f"{m_fr.group(3)}-{mon_num}"
        return "Date_Inconnue"

    def extract_whatsapp_text(
        self, file_path: str, raw_text: str, allowed_names: Optional[Set[str]] = None
    ) -> Dict[str, str]:
        """Extrait un fil WhatsApp .txt par mois avec en-tête WHATSAPP : <Interlocuteur>."""
        buckets: Dict[str, List[str]] = {}
        cur_period: str = "Date_Inconnue"
        cur_allowed: bool = True
        senders_seen: List[str] = []
        for raw_line in raw_text.splitlines():
            clean_l: str = raw_line.replace("\u202f", " ").replace("\xa0", " ").lstrip("\u200e\u200f\ufeff").rstrip()
            m_wa = self.RE_WHATSAPP_LINE.match(clean_l)
            if m_wa:
                d_str, t_str, sender, body = m_wa.groups()
                s_clean: str = sender.strip()
                if s_clean and s_clean not in senders_seen:
                    senders_seen.append(s_clean)
                parts = [p for p in re.split(r"[/.-]", d_str) if p.isdigit()]
                if len(parts) == 3:
                    a, b, c = parts
                    yr: int = int(c) + 2000 if len(c) == 2 else int(c)
                    mo: int = int(b) if int(b) <= 12 else int(a)
                    if 1 <= mo <= 12 and 1990 <= yr <= 2100:
                        cur_period = f"{yr:04d}-{mo:02d}"
                cur_allowed = self._is_sender_allowed(s_clean, allowed_names)
                if cur_allowed:
                    buckets.setdefault(cur_period, []).append(f"[{d_str} {t_str}] {s_clean} : {body.strip()}")
            elif clean_l.strip() and cur_allowed:
                buckets.setdefault(cur_period, []).append(clean_l.strip())
        stem, _ = os.path.splitext(os.path.basename(file_path))
        m_title = re.search(r"(?:avec|with)\s+(.+)$", stem, re.IGNORECASE)
        chat_title: str = m_title.group(1).strip() if m_title else (", ".join(senders_seen[:2]) or stem)
        return {p: f"WHATSAPP : {chat_title}\n" + "\n".join(lines) for p, lines in buckets.items() if lines}
    def extract_messenger_html(
        self, file_path: str, raw_html: str, allowed_names: Optional[Set[str]] = None
    ) -> Dict[str, str]:
        """Extrait un fil HTML Facebook Messenger par mois avec en-tête MESSENGER : <Titre>."""
        cleaned_h: str = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", "", raw_html, flags=re.IGNORECASE | re.DOTALL)
        stem, _ = os.path.splitext(os.path.basename(file_path))
        m_title = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
        conv_title: str = unescape(self.RE_HTML_TAG.sub("", m_title.group(1))).strip() if m_title else stem
        blocks = re.split(r"<(?:div|p|li|tr|h[1-4])\b[^>]*>|</(?:div|p|li|tr|h[1-4])>|<br\s*/?>", cleaned_h, flags=re.IGNORECASE)
        lines: List[str] = [" ".join(unescape(self.RE_HTML_TAG.sub(" ", b)).split()).strip() for b in blocks]
        lines = [ln for ln in lines if ln]
        buckets: Dict[str, List[str]] = {}
        pending_msgs: List[str] = []
        cur_period: str = "Date_Inconnue"
        cur_sender: str = ""
        cur_allowed: bool = True
        for line in lines:
            p_cand: str = self._ts_to_period(line)
            if p_cand != "Date_Inconnue":
                cur_period = p_cand
                if pending_msgs:
                    buckets.setdefault(cur_period, []).extend(pending_msgs)
                    pending_msgs.clear()
                if len(line) <= 75:
                    continue
            if len(line) <= 45 and not any(ch in line for ch in ".!?"):
                cur_sender = line
                cur_allowed = self._is_sender_allowed(cur_sender, allowed_names)
                continue
            if cur_allowed:
                prefix: str = f"{cur_sender} : " if cur_sender else ""
                if cur_period == "Date_Inconnue":
                    pending_msgs.append(f"{prefix}{line}")
                else:
                    buckets.setdefault(cur_period, []).append(f"{prefix}{line}")
        if pending_msgs:
            buckets.setdefault(cur_period, []).extend(pending_msgs)
        return {p: f"MESSENGER : {conv_title}\n" + "\n".join(msgs) for p, msgs in buckets.items() if msgs}

    def _resolve_json_chat_header(self, file_path: str, data: Any) -> str:
        """Construit l'en-tête normalisé (GOOGLE CHAT / MESSENGER / SIGNAL) d'un JSON."""
        low_p: str = file_path.replace("\\", "/").lower()
        stem, _ = os.path.splitext(os.path.basename(file_path))
        raw_title: str = str(data.get("channelName") or data.get("displayName") or data.get("topic") or data.get("name") or data.get("title") or "").strip() if isinstance(data, dict) else ""
        if not raw_title:
            grp_info: str = os.path.join(os.path.dirname(file_path), "group_info.json")
            if os.path.isfile(grp_info):
                try:
                    with open(grp_info, "r", encoding="utf-8", errors="ignore") as f_g:
                        g_data = json.load(f_g)
                    if isinstance(g_data, dict):
                        raw_title = str(g_data.get("name") or g_data.get("title") or "").strip()
                except Exception:
                    pass
        title: str = self._decode_fb_mojibake(raw_title) if raw_title else stem
        if self.is_google_chat_file(file_path, data):
            return f"GOOGLE CHAT : {title}\n"
        if "signal" in low_p or self.is_signal_json_file(file_path, data):
            return f"SIGNAL : {title}\n"
        if self.is_instagram_json_file(file_path, data) or "messenger" in low_p or "facebook" in low_p:
            return f"MESSENGER : {title}\n"
        return f"CHAT JSON : {title}\n"

    def extract_json_chat(
        self, file_path: str, target_phones: Dict[str, str],
        allowed_emails: Set[str], disc_phones: Set[str], disc_emails: Set[str],
        allowed_names: Optional[Set[str]] = None,
    ) -> Tuple[Dict[str, str], Optional[str]]:
        """Extrait les messages d'un export JSON de messagerie par mois."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f_in:
                data = json.load(f_in)
        except Exception as exc:
            return {}, f"JSON invalide : {exc}"
        is_fb: bool = self.is_instagram_json_file(file_path, data)
        messages: List[Any] = data if isinstance(data, list) else []
        if isinstance(data, dict):
            for k_list in ("messages", "value", "entries"):
                if isinstance(data.get(k_list), list):
                    messages = data[k_list]
                    break
            if not messages and isinstance(data.get("conversations"), list):
                for conv in data["conversations"]:
                    if isinstance(conv, dict) and isinstance(conv.get("messages"), list):
                        messages.extend(conv["messages"])
        buckets: Dict[str, List[str]] = {}
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            sender: str = ""
            sender_em: str = ""
            raw_c = msg.get("creator") or msg.get("sender_name") or msg.get("from") or msg.get("author") or msg.get("sourceName") or msg.get("sender")
            if isinstance(raw_c, dict):
                u_obj = raw_c.get("user") if isinstance(raw_c.get("user"), dict) else raw_c
                sender = str(u_obj.get("displayName") or u_obj.get("name") or u_obj.get("email") or "")
                sender_em = DocumentTextUtils.normalize_identifier(str(u_obj.get("email") or ""))
                if sender_em:
                    disc_emails.add(sender_em)
            elif raw_c:
                sender = str(raw_c)
            if is_fb:
                sender = self._decode_fb_mojibake(sender)
            em_ok: bool = bool(sender_em and allowed_emails and sender_em in allowed_emails)
            if not em_ok and not self._is_sender_allowed(sender, allowed_names):
                continue
            body_raw = msg.get("text") or msg.get("content") or msg.get("body") or msg.get("message") or ""
            if isinstance(body_raw, dict):
                body_raw = body_raw.get("content") or body_raw.get("text") or ""
            elif isinstance(body_raw, list):
                body_raw = " ".join(str(x.get("text", x) if isinstance(x, dict) else x) for x in body_raw)
            body: str = re.sub(r"<[^>]+>", " ", self._decode_fb_mojibake(str(body_raw)) if is_fb else str(body_raw)).strip()
            att_names = [str(a.get("original_name") or a.get("export_name") or a.get("name") or "").strip() for a in msg.get("attached_files", []) if isinstance(a, dict)]
            att_names = [a for a in att_names if a]
            if att_names:
                body = f"{body} [Pièce(s) jointe(s) : {', '.join(att_names)}]".strip()
            if not body:
                continue
            for m_p in DocumentTextUtils.REGEX_PHONE.finditer(body):
                np: str = ExtractionFilterLoader.normalize_any_phone(m_p.group(0))
                if np:
                    disc_phones.add(np)
            ts_raw = msg.get("created_date") or msg.get("createdDateTime") or msg.get("timestamp_ms") or msg.get("date_unixtime") or msg.get("date") or msg.get("timestamp")
            period: str = self._ts_to_period(ts_raw)
            buckets.setdefault(period, []).append(f"{sender.strip() or 'Participant'} : {body}")
        header: str = self._resolve_json_chat_header(file_path, data)
        return {p: header + "\n".join(rows) for p, rows in buckets.items() if rows}, None
