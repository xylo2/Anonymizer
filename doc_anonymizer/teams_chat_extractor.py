# Commandes pip à exécuter : Aucune dépendance externe requise

import datetime
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from doc_anonymizer.text_utils import DocumentTextUtils


class TeamsChatExtractor:
    """
    Extracteur dédié aux exports Microsoft Teams (messages.json et
    transcriptions de réunions WebVTT .vtt).
    """

    def __init__(self, config: Optional[Any] = None) -> None:
        """Initialise l'extracteur Teams avec une configuration optionnelle."""
        self.config: Optional[Any] = config

    @staticmethod
    def _register_discovered_email(
        discovered_emails: Optional[Any],
        email_addr: str,
        display_name: str = "",
    ) -> None:
        """Enregistre un e-mail découvert dans un set ou un dict selon le conteneur passé."""
        if discovered_emails is None or not email_addr:
            return
        norm_m: str = DocumentTextUtils.normalize_identifier(email_addr)
        if not norm_m:
            return
        if isinstance(discovered_emails, set):
            discovered_emails.add(norm_m)
        elif isinstance(discovered_emails, dict):
            discovered_emails.setdefault(norm_m, display_name or norm_m)

    def _clean_teams_html_body(
        self,
        raw_html: str,
        discovered_emails: Optional[Any] = None,
    ) -> str:
        """Nettoie le contenu HTML Teams en préservant les mentions <at> et e-mails."""
        if not raw_html:
            return ""

        extra_mails: List[str] = []

        def _repl_at(m: re.Match) -> str:
            attrs: str = m.group(1) or ""
            label: str = m.group(2).strip()
            m_mail = DocumentTextUtils.REGEX_EMAIL.search(attrs)
            if m_mail:
                mail_found: str = m_mail.group(0)
                self._register_discovered_email(discovered_emails, mail_found, label)
                return f"@{label} ({mail_found})" if label else mail_found
            return f"@{label}"

        cleaned: str = re.sub(
            r"(?is)<at\b([^>]*)>(.*?)</at>",
            _repl_at,
            raw_html,
        )
        for m_any in DocumentTextUtils.REGEX_EMAIL.finditer(cleaned):
            mail_val: str = m_any.group(0)
            if mail_val not in extra_mails:
                extra_mails.append(mail_val)
            self._register_discovered_email(discovered_emails, mail_val)
        plain: str = DocumentTextUtils.html_to_plain_text(cleaned)
        for mv in extra_mails:
            if mv not in plain:
                plain = f"{plain} ({mv})".strip()
        return plain

    @staticmethod
    def _parse_teams_timestamp(raw_ts: Any) -> Tuple[str, str]:
        """Convertit un horodatage ISO Teams en (AAAA-MM, AAAA-MM-JJ HH:MM:SS)."""
        if not raw_ts:
            return "0000-00", "Date inconnue"
        s: str = str(raw_ts).strip()
        m_iso = re.match(
            r"^((?:19|20)\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])[T ](\d{2}:\d{2}:\d{2})",
            s,
        )
        if m_iso:
            month_k: str = f"{m_iso.group(1)}-{m_iso.group(2)}"
            full_ts: str = f"{month_k}-{m_iso.group(3)} {m_iso.group(4)}"
            return month_k, full_ts
        try:
            num_val: float = float(s)
            if num_val > 1e11:
                num_val /= 1000.0
            dt = datetime.datetime.fromtimestamp(num_val, tz=datetime.timezone.utc)
            return dt.strftime("%Y-%m"), dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError, OverflowError):
            pass
        return "0000-00", s

    @staticmethod
    def _extract_teams_sender(msg: Dict[str, Any]) -> Tuple[str, str]:
        """Extrait (Nom_Affiché, Email) depuis les différents formats d'export Teams."""
        sender_obj = msg.get("from") or msg.get("sender")
        if isinstance(sender_obj, dict):
            for nested_key in ("user", "application", "device"):
                user_obj = sender_obj.get(nested_key)
                if isinstance(user_obj, dict):
                    disp: str = str(user_obj.get("displayName") or user_obj.get("name") or "").strip()
                    mail: str = str(
                        user_obj.get("email")
                        or user_obj.get("userPrincipalName")
                        or user_obj.get("mail")
                        or user_obj.get("address")
                        or ""
                    ).strip()
                    if disp or mail:
                        return disp or mail, mail
            disp_direct: str = str(
                sender_obj.get("displayName") or sender_obj.get("name") or ""
            ).strip()
            mail_direct: str = str(
                sender_obj.get("email")
                or sender_obj.get("userPrincipalName")
                or sender_obj.get("mail")
                or sender_obj.get("address")
                or ""
            ).strip()
            if disp_direct or mail_direct:
                return disp_direct or mail_direct, mail_direct

        im_name: str = str(
            msg.get("imdisplayname") or msg.get("displayName") or msg.get("author") or ""
        ).strip()
        im_mail: str = str(
            msg.get("email") or msg.get("userPrincipalName") or msg.get("mail") or ""
        ).strip()
        if not im_mail and isinstance(sender_obj, str) and "@" in sender_obj:
            m_mail = DocumentTextUtils.REGEX_EMAIL.search(sender_obj)
            if m_mail:
                im_mail = m_mail.group(0)
        return im_name or im_mail or "Utilisateur Teams", im_mail
    @staticmethod
    def _extract_teams_attachments(msg: Dict[str, Any]) -> List[str]:
        """Liste les pièces jointes (attachments, properties.files, etc.) d'un message Teams."""
        names: List[str] = []
        attachments = msg.get("attachments")
        if isinstance(attachments, list):
            for att in attachments:
                if isinstance(att, str) and att.strip():
                    names.append(att.strip())
                elif isinstance(att, dict):
                    att_name: str = str(
                        att.get("name")
                        or att.get("fileName")
                        or att.get("title")
                        or att.get("contentUrl")
                        or ""
                    ).strip()
                    if att_name:
                        names.append(att_name)

        props = msg.get("properties")
        if isinstance(props, dict) and props.get("files"):
            raw_files: Any = props["files"]
            if isinstance(raw_files, str):
                try:
                    raw_files = json.loads(raw_files)
                except ValueError:
                    raw_files = []
            if isinstance(raw_files, list):
                for f_item in raw_files:
                    if isinstance(f_item, dict):
                        fn: str = str(
                            f_item.get("fileName") or f_item.get("name") or f_item.get("title") or ""
                        ).strip()
                        if fn and fn not in names:
                            names.append(fn)
        return names

    @classmethod
    def _collect_mentions_emails(
        cls,
        msg: Dict[str, Any],
        discovered_emails: Optional[Any],
    ) -> List[str]:
        """Extrait les adresses e-mail présentes dans les mentions ou métadonnées d'un message Teams."""
        found: List[str] = []
        mentions = msg.get("mentions")
        if isinstance(mentions, list):
            for m_item in mentions:
                if not isinstance(m_item, dict):
                    continue
                mentioned = m_item.get("mentioned")
                if isinstance(mentioned, dict):
                    user_obj = mentioned.get("user")
                    if isinstance(user_obj, dict):
                        mail: str = str(
                            user_obj.get("email") or user_obj.get("userPrincipalName") or ""
                        ).strip()
                        disp: str = str(
                            user_obj.get("displayName") or m_item.get("mentionText") or ""
                        ).strip()
                        if mail and "@" in mail:
                            found.append(mail)
                            cls._register_discovered_email(discovered_emails, mail, disp)

        raw_blob: str = json.dumps(msg, ensure_ascii=False)
        for m_any in DocumentTextUtils.REGEX_EMAIL.finditer(raw_blob):
            mail_val: str = m_any.group(0)
            if mail_val not in found:
                found.append(mail_val)
            cls._register_discovered_email(discovered_emails, mail_val)
        return found

    def _parse_teams_message_list(
        self,
        messages: List[Any],
        conv_title: str,
        discovered_emails: Optional[Any] = None,
    ) -> Dict[str, str]:
        """Regroupe et formate une liste de messages Teams par mois AAAA-MM."""
        buckets: Dict[str, List[str]] = {}
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            mention_mails: List[str] = self._collect_mentions_emails(msg, discovered_emails)
            msg_type: str = str(msg.get("messageType") or "message").lower()
            if msg_type not in {"message", "richtext/html", "text"}:
                continue

            raw_ts: Any = (
                msg.get("createdDateTime")
                or msg.get("originalarrivaltime")
                or msg.get("composetime")
            )
            month_key, ts_str = self._parse_teams_timestamp(raw_ts)
            sender_name, sender_email = self._extract_teams_sender(msg)
            self._register_discovered_email(discovered_emails, sender_email, sender_name)

            body_txt: str = self._clean_teams_html_body(
                str(msg.get("content") or ""), discovered_emails
            )
            attachments: List[str] = self._extract_teams_attachments(msg)
            if not body_txt and not attachments:
                continue

            sender_label: str = (
                f"{sender_name} ({sender_email})"
                if sender_email and sender_email.lower() not in sender_name.lower()
                else sender_name
            )
            block_lines: List[str] = [f"[{ts_str}] DE : {sender_label}"]
            for mm in mention_mails:
                if mm not in body_txt and mm not in sender_label:
                    block_lines.append(f"[Mention Teams : {mm}]")
            if attachments:
                block_lines.append(f"[Pièce(s) jointe(s) Teams : {', '.join(attachments)}]")
            if body_txt:
                block_lines.append(body_txt)
            block_lines.append("-" * 40)

            buckets.setdefault(month_key, []).append("\n".join(block_lines))

        rendered: Dict[str, str] = {}
        for month_key, entries in sorted(buckets.items()):
            header: str = (
                f"{'=' * 40}\n"
                f"MICROSOFT TEAMS : {conv_title}\n"
                f"{'-' * 40}\n"
            )
            rendered[month_key] = header + "\n".join(entries) + "\n"
        return rendered
    @staticmethod
    def is_teams_json_payload(payload: Any) -> bool:
        """Détermine si un objet JSON désérialisé correspond à un export Microsoft Teams."""
        if isinstance(payload, dict):
            if isinstance(payload.get("conversations"), list):
                return True
            msgs = payload.get("messages")
            if isinstance(msgs, list) and any(
                isinstance(m, dict)
                and any(
                    k in m
                    for k in ("messageType", "createdDateTime", "originalarrivaltime", "imdisplayname")
                )
                for m in msgs[:5]
            ):
                return True
        elif isinstance(payload, list) and any(
            isinstance(m, dict)
            and any(
                k in m
                for k in ("messageType", "createdDateTime", "originalarrivaltime", "imdisplayname")
            )
            for m in payload[:5]
        ):
            return True
        return False

    def _persist_discovered_teams_emails(self, found_emails: Set[str]) -> None:
        """Enregistre les e-mails Teams inconnus dans discovered_email_contacts.txt."""
        if not found_emails or self.config is None:
            return
        contacts_file: str = getattr(self.config, "contacts_file", "") or ""
        known_mails: Set[str] = set()
        if contacts_file and os.path.exists(contacts_file):
            try:
                with open(contacts_file, "r", encoding="utf-8", errors="ignore") as f_c:
                    for ln in f_c:
                        if "=" in ln and not ln.strip().startswith("#"):
                            k_raw, v_raw = ln.split("=", 1)
                            _, _, nid = DocumentTextUtils.resolve_contact_pair(k_raw, v_raw)
                            if nid:
                                known_mails.add(nid)
            except OSError:
                pass

        root_dir: str = getattr(self.config, "root_dir", "") or ""
        disc_path: str = (
            getattr(self.config, "discovered_emails_file", "")
            or getattr(self.config, "discovered_email_contacts_file", "")
            or (os.path.join(root_dir, "output_contacts", "discovered_email_contacts.txt") if root_dir else "")
        )
        if not disc_path:
            return

        existing_map: Dict[str, str] = {}
        if os.path.exists(disc_path):
            try:
                with open(disc_path, "r", encoding="utf-8", errors="ignore") as f_d:
                    for ln in f_d:
                        if "=" in ln and not ln.strip().startswith("#"):
                            k_raw, v_raw = ln.split("=", 1)
                            _, alias_v, nid = DocumentTextUtils.resolve_contact_pair(k_raw, v_raw)
                            if nid and alias_v:
                                existing_map[nid] = alias_v
            except OSError:
                pass

        next_idx: int = len(existing_map) + 1
        changed: bool = False
        for raw_m in sorted(found_emails):
            norm_m: str = DocumentTextUtils.normalize_identifier(raw_m)
            if not norm_m or norm_m in known_mails or norm_m in existing_map:
                continue
            existing_map[norm_m] = f"Contact_Mail_{next_idx:03d}"
            next_idx += 1
            changed = True

        if changed:
            try:
                os.makedirs(os.path.dirname(disc_path), exist_ok=True)
                with open(disc_path, "w", encoding="utf-8") as f_out:
                    for k_m, v_a in sorted(existing_map.items()):
                        f_out.write(f"{k_m} = {v_a}\n")
            except OSError:
                pass

    def extract_teams_json(
        self,
        file_path: str,
        payload: Any,
        discovered_emails: Optional[Any] = None,
    ) -> Dict[str, str]:
        """Extrait un export JSON Microsoft Teams (conversations ou messages plats)."""
        all_buckets: Dict[str, List[str]] = {}
        base_title, _ = os.path.splitext(os.path.basename(file_path))

        local_mails: Set[str] = set()
        try:
            raw_payload_str: str = json.dumps(payload, ensure_ascii=False)
            for m_glob in DocumentTextUtils.REGEX_EMAIL.finditer(raw_payload_str):
                mail_found: str = m_glob.group(0)
                local_mails.add(mail_found)
                self._register_discovered_email(discovered_emails, mail_found)
        except (TypeError, ValueError):
            pass

        if isinstance(payload, dict) and isinstance(payload.get("conversations"), list):
            for conv in payload["conversations"]:
                if not isinstance(conv, dict):
                    continue
                c_title: str = (
                    str(conv.get("displayName") or conv.get("id") or base_title).strip()
                )
                msgs = conv.get("MessageList") or conv.get("messages") or []
                if isinstance(msgs, list):
                    sub = self._parse_teams_message_list(msgs, c_title, discovered_emails)
                    for mk, txt in sub.items():
                        all_buckets.setdefault(mk, []).append(txt)
        elif isinstance(payload, dict) and isinstance(payload.get("messages"), list):
            sub = self._parse_teams_message_list(
                payload["messages"], base_title, discovered_emails
            )
            for mk, txt in sub.items():
                all_buckets.setdefault(mk, []).append(txt)
        elif isinstance(payload, list):
            sub = self._parse_teams_message_list(payload, base_title, discovered_emails)
            for mk, txt in sub.items():
                all_buckets.setdefault(mk, []).append(txt)

        if local_mails:
            self._persist_discovered_teams_emails(local_mails)
            if all_buckets:
                first_mk: str = next(iter(sorted(all_buckets.keys())))
                all_buckets[first_mk].append(
                    f"[Participants Teams : {', '.join(sorted(local_mails))}]\n"
                )

        return {mk: "\n".join(chunks) for mk, chunks in sorted(all_buckets.items())}

    @staticmethod
    def extract_teams_vtt(
        file_path: str, raw_vtt: Optional[str] = None
    ) -> Tuple[str, str]:
        """Extrait une transcription de réunion Teams WebVTT (.vtt) et retourne (texte, période)."""
        content: str = raw_vtt or ""
        if raw_vtt is None:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f_in:
                content = f_in.read()
        base_name: str = os.path.basename(file_path)
        period: str = DocumentTextUtils.resolve_file_period(content, base_name, file_path)
        parsed_dialogue: str = DocumentTextUtils.parse_teams_vtt_content(content)
        if not parsed_dialogue:
            return "", period
        vtt_mails: List[str] = sorted(
            set(DocumentTextUtils.REGEX_EMAIL.findall(content))
        )
        extra_footer: str = (
            f"[Participants réunion Teams : {', '.join(vtt_mails)}]\n"
            if vtt_mails
            else ""
        )
        header: str = (
            f"{'=' * 40}\n"
            f"TRANSCRIPTION RÉUNION TEAMS : {base_name}\n"
            f"{'-' * 40}\n"
        )
        return f"{header}{parsed_dialogue}\n{extra_footer}", period
