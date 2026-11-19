# Commandes pip à exécuter : Aucune dépendance externe requise

from collections import defaultdict
from datetime import datetime
import json
import os
import re
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class GoogleChatExtractor:
    """
    Extrait et structure les historiques de conversations issus de Google Takeout
    (Google Chat : fichiers messages.json et métadonnées group_info.json).
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

    def __init__(self, config: PipelineConfig) -> None:
        """
        Initialise l'extracteur Google Chat avec la configuration du pipeline.

        :param config: Instance de PipelineConfig.
        """
        self.config: PipelineConfig = config

    @classmethod
    def is_google_chat_messages_file(cls, file_path: str, payload: Any) -> bool:
        """
        Vérifie si le fichier JSON correspond à un export de messages Google Chat.

        :param file_path: Chemin vers le fichier JSON inspecté.
        :param payload: Structure JSON déjà décodée.
        :return: True s'il s'agit d'un fichier messages.json Google Chat valide.
        """
        if not isinstance(payload, dict):
            return False
        messages: Any = payload.get("messages")
        if not isinstance(messages, list):
            return False
        base_name: str = os.path.basename(file_path).lower()
        if base_name == "messages.json":
            return True
        if not messages:
            return False
        first_item: Any = next(iter(messages), None)
        return isinstance(first_item, dict) and (
            "creator" in first_item or "created_date" in first_item
        )

    @classmethod
    def parse_chat_timestamp(cls, raw_date: str) -> Tuple[str, str, int]:
        """
        Convertit une date Google Chat (française ou anglaise Takeout) en
        (période AAAA-MM, horodatage lisible, clé de tri entière).

        :param raw_date: Chaîne de date brute (ex: 'lundi 15 mai 2024 à 14:30:00 UTC').
        :return: Tuple (période, date_formatée, timestamp_tri).
        """
        cleaned: str = raw_date.strip()
        if not cleaned:
            return "0000-00", "Date inconnue", 0

        m_iso = re.search(
            r"(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2}):(\d{2})", cleaned
        )
        if m_iso:
            y, mo, d, hh, mm, ss = m_iso.groups()
            sort_key: int = int(f"{y}{mo}{d}{hh}{mm}{ss}")
            return f"{y}-{mo}", f"{y}-{mo}-{d} {hh}:{mm}:{ss}", sort_key

        norm_date: str = DocumentTextUtils.normalize_word(cleaned)
        m_text = re.search(
            r"\b(\d{1,2})\s+([a-z]{3,10})\.?\s+(20\d{2}|19\d{2})\b.*?"
            r"(\d{1,2}):(\d{2})(?::(\d{2}))?",
            norm_date,
        )
        if m_text:
            day_s, month_w, year_s, hh_s, mm_s, ss_s = m_text.groups()
            mo_num: str = cls.FRENCH_MONTH_MAP.get(month_w, "00")
            if mo_num != "00":
                d_pad: str = day_s.zfill(2)
                h_pad: str = hh_s.zfill(2)
                m_pad: str = mm_s.zfill(2)
                s_pad: str = (ss_s or "00").zfill(2)
                sort_key = int(f"{year_s}{mo_num}{d_pad}{h_pad}{m_pad}{s_pad}")
                return (
                    f"{year_s}-{mo_num}",
                    f"{year_s}-{mo_num}-{d_pad} {h_pad}:{m_pad}:{s_pad}",
                    sort_key,
                )

        fallback_period: str = (
            DocumentTextUtils.detect_period_in_text(cleaned) or "0000-00"
        )
        return fallback_period, cleaned, 0
    def _load_group_metadata(
        self, messages_path: str, discovered_emails: Set[str]
    ) -> Tuple[str, Set[str]]:
        """
        Lit group_info.json adjacent s'il existe pour récupérer le nom du salon
        et les adresses e-mail des participants.

        :param messages_path: Chemin vers messages.json.
        :param discovered_emails: Collecteur global des e-mails découverts.
        :return: Tuple (titre_discussion, ensemble_emails_participants).
        """
        parent_dir: str = os.path.dirname(messages_path)
        group_info_path: str = os.path.join(parent_dir, "group_info.json")
        folder_label: str = os.path.basename(parent_dir) or "Discussion"
        member_emails: Set[str] = set()

        if not os.path.exists(group_info_path):
            return folder_label, member_emails

        try:
            with open(group_info_path, "r", encoding="utf-8", errors="ignore") as f:
                info: Any = json.load(f)
            if not isinstance(info, dict):
                return folder_label, member_emails

            raw_title: str = str(info.get("name") or "").strip()
            title: str = raw_title if raw_title else folder_label
            members: Any = info.get("members")
            if isinstance(members, list):
                for member in members:
                    if not isinstance(member, dict):
                        continue
                    raw_mail: str = str(member.get("email") or "").strip()
                    raw_name: str = str(member.get("name") or "").strip()
                    if "@" in raw_mail:
                        norm_mail: str = DocumentTextUtils.normalize_identifier(raw_mail)
                        member_emails.add(norm_mail)
                        if raw_name and len(raw_name.split()) >= 2:
                            discovered_emails.add(f"{norm_mail}|{raw_name}")
                        else:
                            discovered_emails.add(norm_mail)
            return title, member_emails
        except Exception:
            return folder_label, member_emails

    @staticmethod
    def _format_attachments(msg_obj: Dict[str, Any]) -> str:
        """
        Formate les pièces jointes éventuelles d'un message Google Chat.

        :param msg_obj: Dictionnaire représentant un message.
        :return: Ligne descriptive des pièces jointes ou chaîne vide.
        """
        attachments: Any = msg_obj.get("attached_files")
        if not isinstance(attachments, list) or not attachments:
            return ""
        names: List[str] = []
        for att in attachments:
            if isinstance(att, dict):
                fname: str = str(
                    att.get("original_name") or att.get("export_name") or ""
                ).strip()
                if fname:
                    names.append(fname)
        if not names:
            return ""
        return f"[Pièce(s) jointe(s) : {', '.join(names)}]\n"

    def extract_chat_file(
        self,
        file_path: str,
        allowed_emails: Set[str],
        discovered_emails: Set[str],
    ) -> Tuple[Dict[str, str], Optional[str]]:
        """
        Extrait les messages d'un export Google Chat groupés par mois AAAA-MM.

        :param file_path: Chemin vers le fichier JSON candidat.
        :param allowed_emails: Ensemble des e-mails autorisés (vide = tout accepter).
        :param discovered_emails: Collecteur des e-mails rencontrés.
        :return: Tuple (dict_periode_vers_texte, message_erreur_ou_None).
        """
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                payload: Any = json.load(f)
        except Exception as exc:
            return {}, f"Erreur lecture JSON ({exc})"

        if not self.is_google_chat_messages_file(file_path, payload):
            return {}, None

        room_title, room_emails = self._load_group_metadata(
            file_path, discovered_emails
        )
        raw_messages: List[Any] = payload.get("messages", [])
        msg_emails: Set[str] = set(room_emails)
        parsed_entries: List[Tuple[str, int, str]] = []

        for item in raw_messages:
            if not isinstance(item, dict):
                continue
            creator: Any = item.get("creator")
            sender_name: str = "Expéditeur inconnu"
            sender_mail: str = ""
            if isinstance(creator, dict):
                sender_name = str(creator.get("name") or "").strip() or sender_name
                raw_em: str = str(creator.get("email") or "").strip()
                if "@" in raw_em:
                    sender_mail = DocumentTextUtils.normalize_identifier(raw_em)
                    msg_emails.add(sender_mail)
                    if len(sender_name.split()) >= 2:
                        discovered_emails.add(f"{sender_mail}|{sender_name}")
                    else:
                        discovered_emails.add(sender_mail)

            body_txt: str = str(item.get("text") or "").strip()
            att_line: str = self._format_attachments(item)
            if not body_txt and not att_line:
                continue

            period, formatted_dt, sort_key = self.parse_chat_timestamp(
                str(item.get("created_date") or "")
            )
            sender_tag: str = (
                f"{sender_name} ({sender_mail})" if sender_mail else sender_name
            )
            block: str = (
                f"[{formatted_dt}] DE : {sender_tag}\n"
                f"{att_line}{body_txt}\n"
                "----------------------------------------\n"
            )
            parsed_entries.append((period, sort_key, block))

        if allowed_emails and msg_emails and not (msg_emails & allowed_emails):
            return {}, None

        by_month: DefaultDict[str, List[Tuple[int, str]]] = defaultdict(list)
        for period, sort_key, block in parsed_entries:
            by_month[period].append((sort_key, block))

        result_by_period: Dict[str, str] = {}
        for period, items in sorted(by_month.items()):
            items.sort(key=lambda x: x[0])
            header: str = (
                "========================================\n"
                f"GOOGLE CHAT : {room_title}\n"
                "----------------------------------------\n"
            )
            result_by_period[period] = header + "".join(b for _, b in items) + "\n"

        return result_by_period, None
