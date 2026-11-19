# Commandes pip à exécuter : Aucune dépendance externe requise

from collections import defaultdict
import html
import json
import os
import re
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple
from doc_anonymizer.chat_extractors import MultiPlatformChatExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.text_utils import DocumentTextUtils


class TeamsChatExtractor:
    """
    Extrait et structure les historiques de conversations et transcriptions
    Microsoft Teams (JSON export personnel/Graph API, HTML et WebVTT .vtt).
    """

    VTT_CUE_RE = re.compile(
        r"^(\d{2}:\d{2}:\d{2}(?:\.\d{3})?)\s*-->\s*(\d{2}:\d{2}:\d{2}(?:\.\d{3})?)"
    )
    VTT_VOICE_RE = re.compile(r"(?is)<v\s+([^>]+)>(.*?)(?:</v>|$)")

    def __init__(self, config: PipelineConfig) -> None:
        """
        Initialise l'extracteur Microsoft Teams.

        :param config: Instance de PipelineConfig.
        """
        self.config: PipelineConfig = config

    @staticmethod
    def _clean_teams_html_body(raw_body: str) -> str:
        """
        Convertit le contenu HTML d'un message Teams (dont balises <at>) en texte brut.

        :param raw_body: Contenu HTML ou texte brut du message.
        :return: Texte lisible nettoyé.
        """
        if not raw_body:
            return ""
        cleaned: str = re.sub(r"(?is)<at\b[^>]*>(.*?)</at>", r"@\1", raw_body)
        if "\x3c" in cleaned and "\x3e" in cleaned:
            cleaned = DocumentTextUtils.html_to_plain_text(cleaned)
        else:
            cleaned = html.unescape(cleaned)
        return cleaned.strip()

    @staticmethod
    def _group_by_month(
        room_title: str, entries: List[Tuple[str, int, str]]
    ) -> Dict[str, str]:
        """
        Regroupe et trie chronologiquement les messages Teams par période AAAA-MM.

        :param room_title: Nom de la discussion ou du canal Teams.
        :param entries: Liste de tuples (période, clé_tri, bloc_texte).
        :return: Dictionnaire période -> contenu formaté.
        """
        by_month: DefaultDict[str, List[Tuple[int, str]]] = defaultdict(list)
        for period, sort_key, block in entries:
            by_month[period].append((sort_key, block))

        output: Dict[str, str] = {}
        for period, items in sorted(by_month.items()):
            items.sort(key=lambda x: x)
            header: str = (
                "========================================\n"
                f"MICROSOFT TEAMS : {room_title}\n"
                "----------------------------------------\n"
            )
            output[period] = header + "".join(b for _, b in items) + "\n"
        return output

    @classmethod
    def is_teams_json_payload(cls, payload: Any) -> bool:
        """
        Détecte si un objet JSON provient d'un export Microsoft Teams.

        :param payload: Objet JSON décodé.
        :return: True si la structure correspond à Microsoft Teams.
        """
        if not isinstance(payload, dict):
            return False
        convs: Any = payload.get("conversations")
        if isinstance(convs, list) and convs:
            first_c: Any = next(iter(convs), None)
            if isinstance(first_c, dict) and "MessageList" in first_c:
                return True
        if isinstance(payload.get("MessageList"), list):
            return True
        values: Any = payload.get("value")
        if isinstance(values, list) and values:
            first_v: Any = next(iter(values), None)
            if isinstance(first_v, dict) and (
                "createdDateTime" in first_v and "body" in first_v
            ):
                return True
        return False
    def _parse_teams_message_list(
        self,
        room_title: str,
        messages: List[Any],
        discovered_emails: Set[str],
    ) -> Dict[str, str]:
        """
        Parse une liste de messages au format export personnel Microsoft Teams.

        :param room_title: Titre du fil de discussion.
        :param messages: Liste brute MessageList.
        :param discovered_emails: Collecteur des e-mails découverts.
        :return: Dictionnaire période AAAA-MM -> texte formaté.
        """
        entries: List[Tuple[str, int, str]] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            msg_type: str = str(msg.get("messagetype") or "")
            if msg_type.startswith(("ThreadActivity/", "Event/")):
                continue

            sender: str = str(msg.get("displayName") or "").strip()
            raw_from: str = str(msg.get("from") or "").strip()
            if "@" in raw_from:
                em_match = DocumentTextUtils.REGEX_EMAIL.search(raw_from)
                if em_match:
                    norm_em: str = DocumentTextUtils.normalize_identifier(em_match.group(0))
                    if sender and len(sender.split()) >= 2:
                        discovered_emails.add(f"{norm_em}|{sender}")
                    else:
                        discovered_emails.add(norm_em)
            if not sender:
                sender = raw_from or "Participant Teams"

            body_txt: str = self._clean_teams_html_body(str(msg.get("content") or ""))
            props: Any = msg.get("properties")
            att_names: List[str] = []
            if isinstance(props, dict) and isinstance(props.get("files"), str):
                try:
                    files_list: Any = json.loads(props["files"])
                    if isinstance(files_list, list):
                        for f_item in files_list:
                            if isinstance(f_item, dict) and f_item.get("fileName"):
                                att_names.append(str(f_item["fileName"]).strip())
                except Exception:
                    pass
            att_line: str = (
                f"[Pièce(s) jointe(s) Teams : {', '.join(att_names)}]\n"
                if att_names
                else ""
            )
            if not body_txt and not att_line:
                continue

            period, dt_str, sort_k = MultiPlatformChatExtractor.parse_human_timestamp(
                str(msg.get("originalarrivaltime") or "")
            )
            block: str = (
                f"[{dt_str}] DE : {sender}\n"
                f"{att_line}{body_txt}\n"
                "----------------------------------------\n"
            )
            entries.append((period, sort_k, block))

        return self._group_by_month(room_title, entries)

    def _parse_teams_graph_values(
        self,
        room_title: str,
        values: List[Any],
        discovered_emails: Set[str],
    ) -> Dict[str, str]:
        """
        Parse un export JSON issu de l'API Microsoft Graph (/chats/.../messages).

        :param room_title: Titre du canal ou de la conversation.
        :param values: Liste des objets messages Graph API.
        :param discovered_emails: Collecteur des adresses e-mail rencontrées.
        :return: Dictionnaire période AAAA-MM -> texte formaté.
        """
        entries: List[Tuple[str, int, str]] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            from_obj: Any = item.get("from")
            sender: str = "Participant Teams"
            if isinstance(from_obj, dict) and isinstance(from_obj.get("user"), dict):
                user_obj: Dict[str, Any] = from_obj["user"]
                sender = str(user_obj.get("displayName") or sender).strip()
                raw_upn: str = str(user_obj.get("userPrincipalName") or "").strip()
                if "@" in raw_upn:
                    norm_upn: str = DocumentTextUtils.normalize_identifier(raw_upn)
                    discovered_emails.add(
                        f"{norm_upn}|{sender}" if len(sender.split()) >= 2 else norm_upn
                    )

            body_obj: Any = item.get("body")
            raw_content: str = (
                str(body_obj.get("content") or "")
                if isinstance(body_obj, dict)
                else str(body_obj or "")
            )
            body_txt: str = self._clean_teams_html_body(raw_content)
            if not body_txt:
                continue

            period, dt_str, sort_k = MultiPlatformChatExtractor.parse_human_timestamp(
                str(item.get("createdDateTime") or "")
            )
            block: str = (
                f"[{dt_str}] DE : {sender}\n"
                f"{body_txt}\n"
                "----------------------------------------\n"
            )
            entries.append((period, sort_k, block))

        return self._group_by_month(room_title, entries)
    def extract_teams_json(
        self,
        file_path: str,
        payload: Dict[str, Any],
        discovered_emails: Set[str],
    ) -> Dict[str, str]:
        """
        Extrait toutes les conversations contenues dans un fichier JSON Microsoft Teams.

        :param file_path: Chemin vers le fichier JSON.
        :param payload: Contenu JSON décodé.
        :param discovered_emails: Collecteur des e-mails découverts.
        :return: Dictionnaire période AAAA-MM -> texte formaté.
        """
        file_stem, _ = os.path.splitext(os.path.basename(file_path))
        default_title: str = file_stem or "Discussion Teams"
        merged_by_month: DefaultDict[str, List[str]] = defaultdict(list)

        if isinstance(payload.get("conversations"), list):
            for conv in payload["conversations"]:
                if not isinstance(conv, dict):
                    continue
                c_title: str = (
                    str(conv.get("displayName") or "").strip()
                    or str(conv.get("id") or "").strip()
                    or default_title
                )
                sub: Dict[str, str] = self._parse_teams_message_list(
                    c_title, conv.get("MessageList", []), discovered_emails
                )
                for per, blk in sub.items():
                    merged_by_month[per].append(blk)
        elif isinstance(payload.get("MessageList"), list):
            c_title = str(payload.get("displayName") or "").strip() or default_title
            sub = self._parse_teams_message_list(
                c_title, payload["MessageList"], discovered_emails
            )
            for per, blk in sub.items():
                merged_by_month[per].append(blk)
        elif isinstance(payload.get("value"), list):
            sub = self._parse_teams_graph_values(
                default_title, payload["value"], discovered_emails
            )
            for per, blk in sub.items():
                merged_by_month[per].append(blk)

        return {per: "".join(blocks) for per, blocks in sorted(merged_by_month.items())}

    def extract_teams_vtt(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrait la transcription d'une réunion Microsoft Teams au format WebVTT (.vtt).

        :param file_path: Chemin vers le fichier .vtt.
        :return: Tuple (texte_transcription_formate, erreur_ou_None).
        """
        file_name: str = os.path.basename(file_path)
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines: List[str] = f.read().splitlines()

            out_lines: List[str] = []
            cur_time: str = ""
            for raw_ln in lines:
                stripped: str = raw_ln.strip()
                if not stripped or stripped == "WEBVTT" or stripped.isdigit():
                    continue
                m_cue = self.VTT_CUE_RE.match(stripped)
                if m_cue:
                    cur_time = m_cue.group(1)[:8]
                    continue
                m_voice = self.VTT_VOICE_RE.match(stripped)
                if m_voice:
                    speaker: str = html.unescape(m_voice.group(1)).strip()
                    spoken: str = DocumentTextUtils.html_to_plain_text(m_voice.group(2)).strip()
                    if spoken:
                        prefix: str = f"[{cur_time}] " if cur_time else ""
                        out_lines.append(f"{prefix}{speaker} : {spoken}")
                elif not stripped.startswith(("NOTE", "STYLE", "REGION")):
                    plain_ln: str = DocumentTextUtils.html_to_plain_text(stripped).strip()
                    if plain_ln:
                        prefix = f"[{cur_time}] " if cur_time else ""
                        out_lines.append(f"{prefix}{plain_ln}")

            if not out_lines:
                return None, "Transcription VTT Teams vide"

            header: str = (
                "========================================\n"
                f"TRANSCRIPTION RÉUNION TEAMS : {file_name}\n"
                "----------------------------------------\n"
            )
            return header + "\n".join(out_lines) + "\n\n", None
        except Exception as exc:
            return None, f"Erreur lecture VTT Teams ({exc})"
