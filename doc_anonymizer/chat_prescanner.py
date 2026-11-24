# Commandes pip à exécuter : Aucune dépendance externe requise

import email
import email.header
import email.utils
import inspect
import json
import mailbox
import os
import re
from types import SimpleNamespace
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Set, Tuple
from doc_anonymizer import chat_extractors
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.outlook_extractor import OutlookArchiveExtractor
from doc_anonymizer.teams_chat_extractor import TeamsChatExtractor
from doc_anonymizer.text_utils import DocumentTextUtils


def _instantiate_chat_extractor(config: Optional[Any] = None) -> Any:
    """Instancie dynamiquement MultiPlatformChatExtractor avec une configuration minimale."""
    cfg_obj: Any = config or SimpleNamespace(
        known_first_names=set(),
        excluded_words=set(),
        masked_locations=set(),
        surname_collisions=set(),
    )
    for attr in dir(chat_extractors):
        obj = getattr(chat_extractors, attr)
        if isinstance(obj, type) and hasattr(obj, "extract_json_chat"):
            sig = inspect.signature(obj.__init__)
            if len(sig.parameters) > 1:
                return obj(cfg_obj)
            return obj()
    raise ImportError("Aucune classe extract_json_chat trouvée dans chat_extractors.py.")


class ChatContactPrescanner:
    """
    Pré-scanne rapidement input_documents/ (chats JSON/VTT, MBOX/EML,
    archives Outlook MSG/PST/OST, SMS XML) lors de run_contacts.py.
    """

    SENDER_LINE_RE = re.compile(
        r"^\[\d{4}-\d{2}-\d{2}[^\]]*\]\s*DE\s*:\s*([^\r\n(]+)",
        re.MULTILINE,
    )

    def __init__(
        self,
        sources_dir: str,
        discovered_chats_file: str,
        discovered_emails_file: str,
        contacts_file: str = "",
        known_first_names: Optional[Set[str]] = None,
    ) -> None:
        self.sources_dir: str = sources_dir
        self.discovered_chats_file: str = discovered_chats_file
        self.discovered_emails_file: str = discovered_emails_file
        self.contacts_file: str = contacts_file
        self.known_first_names: Set[str] = known_first_names or set()
        dummy_cfg = SimpleNamespace(
            known_first_names=self.known_first_names,
            excluded_words=set(),
            masked_locations=set(),
            surname_collisions=set(),
        )
        self.chat_extractor: Any = _instantiate_chat_extractor(dummy_cfg)
        self.teams_extractor: TeamsChatExtractor = TeamsChatExtractor(dummy_cfg)
        self.outlook_extractor: OutlookArchiveExtractor = OutlookArchiveExtractor(
            OfficeAndDocumentExtractor(enable_ocr=False)
        )
    @staticmethod
    def _decode_mime_header(raw_val: Optional[str]) -> str:
        """Décode proprement un en-tête MIME RFC 2047."""
        if not raw_val:
            return ""
        parts: List[str] = []
        for chunk, enc in email.header.decode_header(raw_val):
            if isinstance(chunk, bytes):
                parts.append(chunk.decode(enc or "utf-8", errors="replace"))
            else:
                parts.append(str(chunk))
        return "".join(parts).strip()

    @staticmethod
    def _load_existing_rules(file_path: str) -> Dict[str, Tuple[str, str]]:
        """Charge un fichier 'Identifiant = Alias' sous forme {norm_key: (raw_target, alias)}."""
        loaded: Dict[str, Tuple[str, str]] = {}
        if not file_path or not os.path.isfile(file_path):
            return loaded
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f_in:
                for raw_line in f_in:
                    line: str = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    left, right = line.split("=", 1)
                    target, alias, _ = DocumentTextUtils.resolve_contact_pair(left, right)
                    if not target or not alias:
                        continue
                    nkey: str = (
                        DocumentTextUtils.normalize_identifier(target)
                        if "@" in target
                        else DocumentTextUtils.normalize_word(target)
                    )
                    if nkey:
                        loaded[nkey] = (target, alias)
        except OSError:
            pass
        return loaded

    @classmethod
    def _collect_json_identities(
        cls,
        node: Any,
        names_out: Set[str],
        emails_out: Set[str],
    ) -> None:
        """Parcourt récursivement un JSON de chat pour en extraire noms et e-mails."""
        if isinstance(node, dict):
            for k in ("sender_name", "imdisplayname", "displayName", "author"):
                val = node.get(k)
                if isinstance(val, str) and val.strip():
                    names_out.add(val.strip())
            creator = node.get("creator")
            if isinstance(creator, dict):
                c_name = creator.get("name")
                c_mail = creator.get("email")
                if isinstance(c_name, str) and c_name.strip():
                    names_out.add(c_name.strip())
                if isinstance(c_mail, str) and "@" in c_mail:
                    emails_out.add(DocumentTextUtils.normalize_identifier(c_mail))
            for list_key in ("participants", "members"):
                items = node.get(list_key)
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            p_name = item.get("name") or item.get("displayName")
                            p_mail = item.get("email")
                            if isinstance(p_name, str) and p_name.strip():
                                names_out.add(p_name.strip())
                            if isinstance(p_mail, str) and "@" in p_mail:
                                emails_out.add(DocumentTextUtils.normalize_identifier(p_mail))
                        elif isinstance(item, str) and item.strip():
                            names_out.add(item.strip())
            for v in node.values():
                cls._collect_json_identities(v, names_out, emails_out)
        elif isinstance(node, list):
            for elem in node:
                cls._collect_json_identities(elem, names_out, emails_out)
    def _scan_json_file(
        self,
        file_path: str,
        chat_texts: List[str],
        discovered_emails: Set[str],
    ) -> None:
        """Extrait les participants et e-mails d'un export JSON de chat."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f_in:
                payload = json.load(f_in)
        except (OSError, ValueError):
            return

        if self.teams_extractor.is_teams_json_payload(payload):
            buckets = self.teams_extractor.extract_teams_json(
                file_path, payload, discovered_emails
            )
            chat_texts.extend(buckets.values())
            return

        target_phones: Dict[str, str] = {}
        allowed_emails: Set[str] = set()
        discovered_phones: Set[str] = set()
        result = self.chat_extractor.extract_json_chat(
            file_path, target_phones, allowed_emails, discovered_phones, discovered_emails
        )
        buckets = result[0] if isinstance(result, tuple) else result
        if isinstance(buckets, dict):
            for txt in buckets.values():
                chat_texts.append(txt)
                for m_mail in DocumentTextUtils.REGEX_EMAIL.finditer(txt):
                    discovered_emails.add(
                        DocumentTextUtils.normalize_identifier(m_mail.group(0))
                    )

        json_names: Set[str] = set()
        self._collect_json_identities(payload, json_names, discovered_emails)
        if json_names:
            synth_lines: List[str] = [
                f"[2024-01-01 00:00:00] DE : {n}" for n in sorted(json_names)
            ]
            chat_texts.append("\n".join(synth_lines))

    def _scan_vtt_file(
        self,
        file_path: str,
        chat_texts: List[str],
        discovered_emails: Set[str],
    ) -> None:
        """Extrait les intervenants et e-mails d'une transcription Teams .vtt."""
        try:
            txt, _ = self.teams_extractor.extract_teams_vtt(file_path)
            if txt:
                chat_texts.append(txt)
                for m_mail in DocumentTextUtils.REGEX_EMAIL.finditer(txt):
                    discovered_emails.add(
                        DocumentTextUtils.normalize_identifier(m_mail.group(0))
                    )
        except OSError:
            pass
    def _scan_sms_xml_file(
        self, file_path: str, chat_texts: List[str]
    ) -> None:
        try:
            tree = ET.parse(file_path)
            names: Set[str] = set()
            for elem in tree.getroot().iter():
                if elem.tag.lower() in {"sms", "mms"}:
                    c_name: str = (elem.attrib.get("contact_name") or "").strip()
                    if c_name and c_name.lower() not in {"(unknown)", "unknown", "inconnu"}:
                        names.add(c_name)
            if names:
                chat_texts.append("\n".join(f"[2024-01-01 00:00:00] DE : {n}" for n in sorted(names)))
        except (ET.ParseError, OSError):
            pass

    def _scan_email_archive(
        self, file_path: str, ext: str, discovered_emails: Set[str]
    ) -> None:
        if ext == ".msg":
            self.outlook_extractor.extract_msg(file_path, set(), discovered_emails)
            return
        if ext in {".pst", ".ost"}:
            self.outlook_extractor.extract_pst_or_ost(file_path, set(), discovered_emails)
            return
        messages: List[email.message.Message] = []
        try:
            if ext == ".eml":
                with open(file_path, "rb") as f_eml:
                    messages.append(email.message_from_binary_file(f_eml))
            elif ext == ".mbox":
                mbox = mailbox.mbox(file_path)
                try:
                    for msg in mbox:
                        messages.append(msg)
                finally:
                    mbox.close()
        except OSError:
            return
        for msg in messages:
            for hdr in ("From", "To", "Cc", "Reply-To"):
                raw_h: str = self._decode_mime_header(msg.get(hdr))
                for _, addr in email.utils.getaddresses([raw_h]) if raw_h else []:
                    norm_m: str = DocumentTextUtils.normalize_identifier(addr)
                    if norm_m and "@" in norm_m:
                        discovered_emails.add(norm_m)

    def _persist_chats(
        self, chat_texts: List[str], known_contacts: Dict[str, Tuple[str, str]]
    ) -> int:
        if not chat_texts or not self.discovered_chats_file:
            return 0
        existing = self._load_existing_rules(self.discovered_chats_file)
        next_idx: int = len(existing) + 1
        added: int = 0
        for txt in chat_texts:
            for m_sender in self.SENDER_LINE_RE.finditer(txt):
                raw_name: str = m_sender.group(1).strip()
                if not raw_name or "@" in raw_name or raw_name.lower() in {"système", "system"}:
                    continue
                nkey: str = DocumentTextUtils.normalize_word(raw_name)
                if not nkey or len(nkey) <= 2 or nkey in known_contacts or nkey in existing:
                    continue
                tokens: List[str] = [t for t in re.split(r"[\s_]+", raw_name) if t]
                if len(tokens) >= 2 and not any(ch.isdigit() for ch in raw_name):
                    first_t, last_t = next(iter(tokens)), tokens[-1]
                    alias: str = f"{first_t[:1].upper()}{first_t[1:]} {last_t[:1].upper()}."
                else:
                    alias = f"Contact_Chat_{next_idx:03d}"
                    next_idx += 1
                existing[nkey] = (raw_name, alias)
                added += 1
        if added > 0:
            os.makedirs(os.path.dirname(self.discovered_chats_file), exist_ok=True)
            with open(self.discovered_chats_file, "w", encoding="utf-8") as f_out:
                for raw_t, als in sorted(existing.values(), key=lambda x: next(iter(x)).lower()):
                    f_out.write(f"{raw_t} = {als}\n")
        return added

    def _persist_emails(
        self, discovered_emails: Set[str], known_contacts: Dict[str, Tuple[str, str]]
    ) -> int:
        if not discovered_emails or not self.discovered_emails_file:
            return 0
        existing = self._load_existing_rules(self.discovered_emails_file)
        next_idx: int = len(existing) + 1
        added: int = 0
        for norm_m in sorted(discovered_emails):
            if not norm_m or "@" not in norm_m or norm_m in known_contacts or norm_m in existing:
                continue
            existing[norm_m] = (norm_m, f"Contact_Mail_{next_idx:03d}")
            next_idx += 1
            added += 1
        if added > 0:
            os.makedirs(os.path.dirname(self.discovered_emails_file), exist_ok=True)
            with open(self.discovered_emails_file, "w", encoding="utf-8") as f_out:
                for raw_m, als in sorted(existing.values(), key=lambda x: next(iter(x)).lower()):
                    f_out.write(f"{raw_m} = {als}\n")
        return added

    def prescan_sources(self) -> Tuple[int, int]:
        if not self.sources_dir or not os.path.isdir(self.sources_dir):
            return 0, 0
        chat_texts: List[str] = []
        discovered_emails: Set[str] = set()
        for root_p, _, files in os.walk(self.sources_dir):
            for fname in sorted(files):
                fpath: str = os.path.join(root_p, fname)
                ext: str = os.path.splitext(fname)[-1].lower()
                if ext == ".json":
                    self._scan_json_file(fpath, chat_texts, discovered_emails)
                elif ext == ".vtt":
                    self._scan_vtt_file(fpath, chat_texts, discovered_emails)
                elif ext == ".xml":
                    self._scan_sms_xml_file(fpath, chat_texts)
                elif ext in {".mbox", ".eml", ".msg", ".pst", ".ost"}:
                    self._scan_email_archive(fpath, ext, discovered_emails)
        known_contacts = self._load_existing_rules(self.contacts_file)
        return self._persist_chats(chat_texts, known_contacts), self._persist_emails(discovered_emails, known_contacts)
