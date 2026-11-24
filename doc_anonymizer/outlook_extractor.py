# Commandes pip à exécuter : pip install extract-msg libpff-python

from collections import defaultdict
import email.utils
import os
import re
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.text_utils import DocumentTextUtils


class OutlookArchiveExtractor:
    """Extrait les courriels Outlook (.msg, .pst, .ost) et leurs PDF joints."""

    def __init__(self, doc_extractor: OfficeAndDocumentExtractor) -> None:
        self.doc_extractor: OfficeAndDocumentExtractor = doc_extractor

    @staticmethod
    def _format_date(raw_date: Any) -> Tuple[str, str]:
        if raw_date is None:
            return "0000-00", "Date inconnue"
        if hasattr(raw_date, "strftime"):
            return raw_date.strftime("%Y-%m"), raw_date.strftime("%Y-%m-%d %H:%M:%S")
        s: str = str(raw_date).strip()
        if not s:
            return "0000-00", "Date inconnue"
        try:
            dt = email.utils.parsedate_to_datetime(s)
            return dt.strftime("%Y-%m"), dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            period: str = DocumentTextUtils.detect_period_in_text(s) or "0000-00"
            return period, s

    @staticmethod
    def _collect_emails(
        raw_headers: List[str], discovered_emails: Set[str]
    ) -> Set[str]:
        found: Set[str] = set()
        for hdr in raw_headers:
            if not hdr:
                continue
            for disp_name, addr in email.utils.getaddresses([hdr]):
                norm_m: str = DocumentTextUtils.normalize_identifier(addr)
                if "@" in norm_m:
                    found.add(norm_m)
                    clean_d: str = disp_name.strip()
                    if len(clean_d.split()) >= 2:
                        discovered_emails.add(f"{norm_m}|{clean_d}")
                    else:
                        discovered_emails.add(norm_m)
        return found
    def _extract_pdf_bytes(self, pdf_data: bytes, label: str) -> Optional[str]:
        safe_name: str = re.sub(r"[\r\n<>:\"/\\|?*]", "_", label).strip()
        txt, err = self.doc_extractor.extract_pdf(
            pdf_source=pdf_data,
            display_name=safe_name or "piece_jointe_outlook.pdf",
            is_stream=True,
        )
        return txt if (txt and not err) else None

    def extract_msg(
        self, file_path: str, allowed_emails: Set[str], discovered_emails: Set[str]
    ) -> Tuple[Dict[str, List[str]], Optional[str]]:
        try:
            import extract_msg  # type: ignore[import-not-found]
        except ImportError:
            return {}, "Module 'extract-msg' requis (pip install extract-msg)"
        by_month: DefaultDict[str, List[str]] = defaultdict(list)
        msg: Any = None
        try:
            msg = extract_msg.Message(file_path)
            sender: str = str(getattr(msg, "sender", "") or "").strip()
            to_h: str = str(getattr(msg, "to", "") or "").strip()
            cc_h: str = str(getattr(msg, "cc", "") or "").strip()
            msg_mails = self._collect_emails([sender, to_h, cc_h], discovered_emails)
            if allowed_emails and msg_mails and not (msg_mails & allowed_emails):
                return {}, None
            subject: str = str(getattr(msg, "subject", "") or "(Sans objet)").strip()
            period, date_disp = self._format_date(getattr(msg, "date", None))
            body: str = str(getattr(msg, "body", "") or "").strip()
            if not body and getattr(msg, "htmlBody", None):
                raw_h = msg.htmlBody
                h_str = raw_h.decode("utf-8", "ignore") if isinstance(raw_h, bytes) else str(raw_h)
                body = DocumentTextUtils.html_to_plain_text(h_str).strip()
            pdfs: List[str] = []
            for att in getattr(msg, "attachments", []) or []:
                fn: str = str(getattr(att, "longFilename", "") or getattr(att, "shortFilename", "") or "")
                data = getattr(att, "data", None)
                if fn.lower().endswith(".pdf") and isinstance(data, bytes) and data:
                    pt = self._extract_pdf_bytes(data, fn)
                    if pt:
                        pdfs.append(pt)
            if not body and not pdfs:
                return {}, None
            att_sec: str = ("\n" + "\n".join(pdfs)) if pdfs else ""
            blk: str = (
                f"{'=' * 40}\nEMAIL OUTLOOK : {os.path.basename(file_path)}\n"
                f"DATE : {date_disp}\nOBJET : {subject}\nFROM : {sender}\n"
                f"TO : {to_h}\n{'-' * 40}\n{body}{att_sec}\n\n"
            )
            by_month[period].append(blk)
            return dict(by_month), None
        except Exception as exc:
            return {}, f"Erreur extraction MSG ({exc})"
        finally:
            if msg is not None and hasattr(msg, "close"):
                try:
                    msg.close()
                except Exception:
                    pass
    def _walk_pst_folder(
        self, folder: Any, file_name: str, allowed_emails: Set[str],
        discovered_emails: Set[str], by_month: DefaultDict[str, List[str]],
    ) -> None:
        for i in range(int(getattr(folder, "number_of_sub_messages", 0) or 0)):
            m = folder.get_sub_message(i)
            sender: str = str(getattr(m, "sender_name", "") or "").strip()
            hdrs: str = str(getattr(m, "transport_headers", "") or "")
            msg_mails = self._collect_emails([sender, hdrs], discovered_emails)
            if allowed_emails and msg_mails and not (msg_mails & allowed_emails):
                continue
            subj: str = str(getattr(m, "subject", "") or "(Sans objet)").strip()
            raw_dt = getattr(m, "delivery_time", None) or getattr(m, "creation_time", None)
            period, date_disp = self._format_date(raw_dt)
            body: str = str(getattr(m, "plain_text_body", "") or "").strip()
            if not body and getattr(m, "html_body", None):
                hb = m.html_body
                h_s = hb.decode("utf-8", "ignore") if isinstance(hb, bytes) else str(hb)
                body = DocumentTextUtils.html_to_plain_text(h_s).strip()
            pdfs: List[str] = []
            for j in range(int(getattr(m, "number_of_attachments", 0) or 0)):
                att = m.get_attachment(j)
                fn: str = str(getattr(att, "name", "") or "")
                sz: int = int(getattr(att, "size", 0) or 0)
                if fn.lower().endswith(".pdf") and sz > 0 and hasattr(att, "read_buffer"):
                    pt = self._extract_pdf_bytes(att.read_buffer(sz), fn)
                    if pt:
                        pdfs.append(pt)
            if not body and not pdfs:
                continue
            att_sec: str = ("\n" + "\n".join(pdfs)) if pdfs else ""
            blk: str = (
                f"{'=' * 40}\nEMAIL OUTLOOK ({file_name})\nDATE : {date_disp}\n"
                f"OBJET : {subj}\nFROM : {sender}\n{'-' * 40}\n{body}{att_sec}\n\n"
            )
            by_month[period].append(blk)
        for k in range(int(getattr(folder, "number_of_sub_folders", 0) or 0)):
            self._walk_pst_folder(
                folder.get_sub_folder(k), file_name, allowed_emails, discovered_emails, by_month
            )

    def extract_pst_or_ost(
        self, file_path: str, allowed_emails: Set[str], discovered_emails: Set[str]
    ) -> Tuple[Dict[str, List[str]], Optional[str]]:
        try:
            import pypff  # type: ignore[import-not-found]
        except ImportError:
            return {}, "Module 'libpff-python' requis (pip install libpff-python)"
        by_month: DefaultDict[str, List[str]] = defaultdict(list)
        pst: Any = pypff.file()
        try:
            pst.open(file_path)
            root = pst.get_root_folder()
            if root is not None:
                self._walk_pst_folder(
                    root, os.path.basename(file_path), allowed_emails, discovered_emails, by_month
                )
            return dict(by_month), None
        except Exception as exc:
            return {}, f"Erreur lecture archive Outlook ({exc})"
        finally:
            try:
                pst.close()
            except Exception:
                pass
