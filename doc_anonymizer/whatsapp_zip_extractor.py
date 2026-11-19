# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
import tempfile
from typing import Dict, List, Optional, Tuple
import zipfile
from doc_anonymizer.chat_extractors import MultiPlatformChatExtractor
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.text_utils import DocumentTextUtils


class WhatsAppZipExtractor:
    """
    Extrait de manière sécurisée les archives .zip exportées depuis WhatsApp
    (_chat.txt et pièces jointes PDF, images, audio et documents Office).
    """

    MAX_UNCOMPRESSED_BYTES: int = 512 * 1024 * 1024

    def __init__(
        self,
        config: PipelineConfig,
        doc_extractor: OfficeAndDocumentExtractor,
        comm_extractor: CommunicationExtractor,
        chat_extractor: MultiPlatformChatExtractor,
    ) -> None:
        """
        Initialise l'extracteur d'archives WhatsApp avec les moteurs existants.

        :param config: Instance de PipelineConfig.
        :param doc_extractor: Extracteur PDF/OCR/Office.
        :param comm_extractor: Extracteur audio Whisper.
        :param chat_extractor: Extracteur texte WhatsApp.
        """
        self.config: PipelineConfig = config
        self.doc_extractor: OfficeAndDocumentExtractor = doc_extractor
        self.comm_extractor: CommunicationExtractor = comm_extractor
        self.chat_extractor: MultiPlatformChatExtractor = chat_extractor

    @staticmethod
    def _is_safe_member_path(base_dir: str, member_name: str) -> Optional[str]:
        """
        Vérifie qu'une entrée ZIP ne tente pas de traversée de répertoire (ZipSlip).

        :param base_dir: Répertoire temporaire d'extraction.
        :param member_name: Chemin relatif interne dans l'archive.
        :return: Chemin cible résolu si sûr, sinon None.
        """
        if not member_name or member_name.endswith("/"):
            return None
        abs_base: str = os.path.abspath(base_dir)
        target: str = os.path.abspath(os.path.join(abs_base, member_name))
        if not target.startswith(abs_base + os.sep):
            return None
        return target

    @classmethod
    def is_whatsapp_zip(cls, zip_path: str) -> bool:
        """
        Vérifie rapidement si une archive .zip contient une discussion WhatsApp.

        :param zip_path: Chemin vers le fichier .zip.
        :return: True si l'archive contient un fichier texte WhatsApp valide.
        """
        if not zipfile.is_zipfile(zip_path):
            return False
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir() or not info.filename.lower().endswith(".txt"):
                        continue
                    if info.file_size > 50 * 1024 * 1024:
                        continue
                    raw_sample: str = zf.read(info.filename)[:16384].decode(
                        "utf-8", errors="ignore"
                    )
                    if MultiPlatformChatExtractor.is_whatsapp_text_file(raw_sample):
                        return True
        except Exception:
            return False
        return False
    def _extract_attachment_file(
        self, file_path: str, file_name: str
    ) -> Optional[str]:
        """
        Extrait le texte d'une pièce jointe WhatsApp selon son extension.

        :param file_path: Chemin temporaire du fichier extrait.
        :param file_name: Nom d'origine de la pièce jointe.
        :return: Texte formaté ou None si non pris en charge / vide.
        """
        _, ext_raw = os.path.splitext(file_name)
        ext: str = ext_raw.lower()
        extractors_map = {
            ".pdf": lambda p: self.doc_extractor.extract_pdf(p, file_name),
            ".rtf": self.doc_extractor.extract_rtf,
            ".docx": self.doc_extractor.extract_docx,
            ".odt": self.doc_extractor.extract_odt,
            ".xlsx": self.doc_extractor.extract_xlsx,
            ".pptx": self.doc_extractor.extract_pptx,
            ".ics": self.doc_extractor.extract_ics,
        }
        audio_exts = {".wav", ".mp3", ".m4a", ".ogg", ".opus", ".flac", ".aac", ".amr"}
        image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

        text_out: Optional[str] = None
        if ext in extractors_map:
            text_out, _ = extractors_map[ext](file_path)
        elif ext in image_exts:
            text_out, _ = self.doc_extractor.extract_image(file_path)
        elif ext in audio_exts:
            text_out, _ = self.comm_extractor.extract_audio(file_path)

        return text_out

    def extract_whatsapp_zip(
        self, zip_path: str
    ) -> Tuple[Dict[str, str], List[Tuple[str, str, str, str]], Optional[str]]:
        """
        Extrait la discussion texte et les pièces jointes d'un export WhatsApp .zip.

        :param zip_path: Chemin vers l'archive .zip.
        :return: Tuple (chats_par_mois, liste_pieces_jointes(période, cat, stem, texte), erreur).
        """
        if not self.is_whatsapp_zip(zip_path):
            return {}, [], None

        raw_zip_stem, _ = os.path.splitext(os.path.basename(zip_path))
        zip_stem: str = re.sub(r'[<>:"/\\|?*]', "_", raw_zip_stem).strip()
        chats_by_month: Dict[str, str] = {}
        attachments_out: List[Tuple[str, str, str, str]] = []

        try:
            with tempfile.TemporaryDirectory(prefix="wa_zip_") as tmp_dir:
                total_unpacked: int = 0
                extracted_files: List[Tuple[str, str]] = []

                with zipfile.ZipFile(zip_path, "r") as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        total_unpacked += info.file_size
                        if total_unpacked > self.MAX_UNCOMPRESSED_BYTES:
                            return {}, [], "Archive ZIP WhatsApp trop volumineuse (limite sécurité)"
                        safe_target: Optional[str] = self._is_safe_member_path(
                            tmp_dir, info.filename
                        )
                        if not safe_target:
                            continue
                        os.makedirs(os.path.dirname(safe_target), exist_ok=True)
                        with zf.open(info, "r") as src_f, open(safe_target, "wb") as dst_f:
                            dst_f.write(src_f.read())
                        extracted_files.append((os.path.basename(info.filename), safe_target))

                default_period: str = "0000-00"
                for orig_name, local_path in extracted_files:
                    if orig_name.lower().endswith(".txt"):
                        with open(local_path, "r", encoding="utf-8", errors="ignore") as f_chat:
                            raw_chat: str = f_chat.read()
                        if self.chat_extractor.is_whatsapp_text_file(raw_chat):
                            parsed: Dict[str, str] = self.chat_extractor.extract_whatsapp_text(
                                zip_path, raw_chat
                            )
                            for per, blk in parsed.items():
                                chats_by_month[per] = chats_by_month.get(per, "") + blk
                            valid_periods: List[str] = sorted(
                                p for p in parsed.keys() if p != "0000-00"
                            )
                            if valid_periods:
                                default_period = next(iter(valid_periods))

                for orig_name, local_path in extracted_files:
                    if orig_name.lower().endswith(".txt"):
                        continue
                    att_text: Optional[str] = self._extract_attachment_file(
                        local_path, orig_name
                    )
                    if not att_text:
                        continue
                    att_period: str = (
                        DocumentTextUtils.detect_period_in_text(orig_name)
                        or DocumentTextUtils.detect_period_in_text(att_text[:2000])
                        or default_period
                    )
                    att_stem_raw, ext_raw = os.path.splitext(orig_name)
                    ext_low: str = ext_raw.lower()
                    if ext_low == ".pdf":
                        cat = "PDF"
                    elif ext_low in {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}:
                        cat = "Images"
                    elif ext_low in {".wav", ".mp3", ".m4a", ".ogg", ".opus", ".flac", ".aac", ".amr"}:
                        cat = "Audio"
                    else:
                        cat = "Documents"
                    safe_att_stem: str = re.sub(
                        r'[<>:"/\\|?*]', "_", f"{zip_stem}_{att_stem_raw}"
                    ).strip()
                    attachments_out.append((att_period, cat, safe_att_stem, att_text))

            return chats_by_month, attachments_out, None
        except Exception as exc:
            return {}, [], f"Erreur extraction archive WhatsApp ({exc})"
