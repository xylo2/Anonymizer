# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
import time
from typing import List, Pattern
from common.core_utils import SharedCoreUtils
from doc_anonymizer.audit_state_manager import AuditAndStateManager
from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_rules_loader import ContactRulesLoader
from doc_anonymizer.text_utils import DocumentTextUtils


class DocumentAnonymizationRunner:
    """
    Orchestre l'anonymisation par lots au fil de l'eau et l'audit
    en temps réel des noms propres résiduels.
    """

    TEXT_CHUNK_LIMIT: int = 32768

    AUTO_TITLE_PATTERN: Pattern[str] = re.compile(
        r"(?<![A-Za-zÀ-ÿ])(Dr|Docteur|DOCTEUR|Pr|Professeur|Mme|MME|Madame|M\.|Monsieur|"
        r"Mlle|Mademoiselle|Me|Maître|Maitre|Famille|Pharmacie|PHARMACIE)\.?\s+"
        r"(?:((?:de|du|des|d'|le|la|van|von|ben|el|al|ould|dos|da|di)(?:\s+(?:la|le|les))?)\s+)?"
        r"([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]"
        r"[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'-]{2,25}(?:\s+[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'-]{2,25})?)(?![A-Za-zÀ-ÿ])"
    )

    AUTO_PERSON_PAIR_PATTERN: Pattern[str] = re.compile(
        r"(?<![A-Za-zÀ-ÿ])((?:[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]|l(?=[a-zéèêëàâäîïôöùûüç]{4,}))[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'-]{2,21})\s+"
        r"(?:((?:De|Du|Des|de|du|des|Le|La|le|la|Van|Von|Ben|El|Al|Ould|Dos|Da|Di)(?:\s+(?:La|Le|Les|la|le|les))?)\s+)?"
        r"([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]"
        r"[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'-]{2,25}(?:\s+[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'-]{2,25})?)(?![A-Za-zÀ-ÿ])"
    )

    UPPER_PAIR_PATTERN: Pattern[str] = re.compile(
        r"(?<![A-Za-zÀ-ÿ])([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç'-]{2,22})\s+([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]{3,25})(?![A-Za-zÀ-ÿ])"
        r"|(?<![A-Za-zÀ-ÿ])([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]{4,25})\s+([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç'-]{2,22})(?![A-Za-zÀ-ÿ])"
    )

    MIME_TOKEN_RECIPIENT_PATTERN: Pattern[str] = re.compile(
        r'("(?:\\")?)(E\.|EMAIL_\d+)\s+([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç\'-]{2,25})((?:\\")?")'
    )

    MRZ_LINE_PATTERN: Pattern[str] = re.compile(
        r"\b(?:IDFRA|P<FRA|[A-Z0-9×]{9,}[<«]{2,})[A-Z0-9×<«]{10,}"
    )

    HTML_INLINE_TAG_CLEANUP: Pattern[str] = re.compile(
        r"(?i)</?(?:a|u|b|strong|span|em|i)\b[^>]*>"
    )
    PARENS_PSEUDO_PATTERN: Pattern[str] = re.compile(
        r"(?i)\b((?:vinted|colis|mondial\s*relay|locker|le\s*bon\s*coin|rakuten)\b[^\n\(]{0,35})\(([a-z0-9_.-]{4,25})\)"
    )

    GLUED_TITLE_OR_CAMEL: Pattern[str] = re.compile(
        r"\b(DOCTEUR|Docteur|Dr|DR|MME|Mme|MADAME|MONSIEUR|Monsieur|PROFESSEUR|PHARMACIE|CHU|Enfant|IDFR[A-Z]?)"
        r"([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç]{2,})\b"
        r"|([a-zà-ÿ]{3,})([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]{4,}[a-zà-ÿ]{0,2})\b"
        r"|([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]{4,})([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zà-ÿ]{3,})\b"
    )

    DUPLICATE_ALIAS_CLEANUP: Pattern[str] = re.compile(
        r"\b(Docteur|Dr|Mme|M\.|Pr|Me)(?:\s+\1)+\b"
        r"|\b([A-Z]\.(?:-[A-Z]\.)?)(?:\s+\2)+\b"
    )
    def __init__(
        self, config: PipelineConfig, manual_only: bool = False
    ) -> None:
        """Initialise l'orchestrateur d'anonymisation."""
        self.config: PipelineConfig = config
        self.manual_only: bool = manual_only
        self.rules: ContactRulesLoader = ContactRulesLoader(
            config, manual_only=manual_only
        )
        self.audit: AuditAndStateManager = AuditAndStateManager(
            config, self.rules
        )
        self._initialized: bool = False
        self.current_chunk: List[str] = []
        self.current_size: int = 0
        self.current_batch_files: List[str] = []
        self.processed_in_session: int = 0

    def initialize(self) -> bool:
        """Charge les règles et restaure l'état JSON de reprise."""
        if self._initialized:
            return True
        if not self.rules.load_all():
            print(
                "[ERREUR ANONYMIZER] Chargement des règles impossible.",
                flush=True,
            )
            return False
        self.audit.load()
        print(
            f"[INIT ANONYMIZER] État chargé : "
            f"{len(self.audit.already_processed)} fichier(s) déjà traité(s), "
            f"prochain index de lot = {self.audit.file_idx}.",
            flush=True,
        )
        self._initialized = True
        return True

    @staticmethod
    def _split_glued_tokens(match: re.Match[str]) -> str:
        """Sépare les jetons collés par casse CamelCase ou titre majuscule."""
        if match.group(1) and match.group(2):
            return f"{match.group(1)} {match.group(2)}"
        if match.group(3) and match.group(4):
            return f"{match.group(3)} {match.group(4)}"
        return f"{match.group(5)} {match.group(6)}"

    def _is_non_surname_word(
        self, word: str, after_known_first_name: bool = False
    ) -> bool:
        """Vérifie si un mot est un mot-outil, un lieu ou un terme exclu."""
        for tok in word.split():
            norm: str = DocumentTextUtils.normalize_word(tok)
            if (
                norm in AuditAndStateManager.COMMON_FRENCH_STOPWORDS
                or norm in self.config.surname_collisions
                or norm in self.config.excluded_words
                or norm in self.rules.alias_words
            ):
                return True
            if not after_known_first_name and (
                norm in self.config.masked_locations
                or norm in DocumentTextUtils.ORG_GENERIC_WORDS
            ):
                return True
        return False
    @staticmethod
    def _format_surname_initials(surname: str) -> str:
        """Formate un nom de famille en initiale(s) majuscule(s)."""
        space_parts: List[str] = [p.strip() for p in surname.split() if p.strip()]
        if len(space_parts) >= 2:
            return " ".join(
                DocumentAnonymizationRunner._format_surname_initials(sp)
                for sp in space_parts
            )
        if "-" in surname:
            parts: List[str] = [p.strip() for p in surname.split("-") if p.strip()]
            if len(parts) >= 2:
                return "-".join(f"{p[:1].upper()}." for p in parts)
        return f"{surname.strip()[:1].upper()}."

    @staticmethod
    def _format_particle_initials(particle: str) -> str:
        """Abrège une particule nobiliaire par son initiale."""
        if not particle or not particle.strip():
            return ""
        tokens: List[str] = [t for t in particle.strip().split() if t]
        return " ".join(f"{t[:1].upper()}." for t in tokens) + " "

    def _is_known_first_name_ocr(self, token: str) -> bool:
        """Vérifie si le jeton est un prénom connu (avec tolérance OCR 'l' -> 'I')."""
        if self.rules.is_first_name(token):
            return True
        if token.startswith("l") and len(token) >= 5:
            return self.rules.is_first_name("I" + token[1:])
        return False

    @staticmethod
    def _is_title_case_token(token: str) -> bool:
        """Indique si un jeton commence par une majuscule suivie de minuscules."""
        return (
            len(token) >= 3
            and token[:1].isupper()
            and token[1:].islower()
        )

    def _replace_title_match(self, match: re.Match[str]) -> str:
        """Remplace un nom (avec ou sans prénom) précédé d'une civilité ou d'un titre."""
        title: str = match.group(1)
        particle: str = match.group(2) or ""
        raw_target: str = match.group(3)
        if self._is_non_surname_word(raw_target):
            return match.group(0)

        target_parts: List[str] = [p for p in raw_target.split() if p]
        if len(target_parts) >= 2 and self._is_known_first_name_ocr(next(iter(target_parts))):
            first_tok: str = next(iter(target_parts))
            surname_tok: str = " ".join(target_parts[1:])
            if self._is_non_surname_word(surname_tok, after_known_first_name=True):
                return match.group(0)
            part_init: str = self._format_particle_initials(particle)
            sur_init: str = self._format_surname_initials(surname_tok)
            return f"{title} {first_tok} {part_init}{sur_init}"

        norm_sur: str = DocumentTextUtils.normalize_word(raw_target)
        if not particle:
            known_aliases = self.rules.last_name_to_aliases.get(norm_sur, set())
            if len(known_aliases) == 1:
                return next(iter(known_aliases))

        is_protected: bool = norm_sur in self.rules.protected_surnames
        if (
            not is_protected
            and self._is_known_first_name_ocr(raw_target)
            and title.lower() not in {
                "dr", "docteur", "pr", "professeur", "me", "maître", "maitre",
            }
        ):
            return match.group(0)

        part_init = self._format_particle_initials(particle)
        sur_init = self._format_surname_initials(raw_target)
        return f"{title} {part_init}{sur_init}"
    def _replace_upper_pair_match(self, match: re.Match[str]) -> str:
        """Masque les paires Prénom NOM et NOM Prénom sans collision avec les sigles."""
        if match.group(1) and match.group(2):
            first_n, last_n = match.group(1), match.group(2)
            if len(last_n) == 3 and not self._is_known_first_name_ocr(first_n):
                prefix_slice: str = match.string[max(0, match.start() - 3):match.start()]
                if not prefix_slice or prefix_slice.endswith(("\n", ": ", ":\n")):
                    return match.group(0)
            if self._is_non_surname_word(first_n) or self._is_non_surname_word(last_n):
                return match.group(0)
            return f"{first_n} {self._format_surname_initials(last_n)}"
        last_n, first_n = match.group(3), match.group(4)
        if self._is_non_surname_word(last_n) or self._is_non_surname_word(first_n):
            return match.group(0)
        return f"{self._format_surname_initials(last_n)} {first_n}"

    def _replace_person_pair_match(self, match: re.Match[str]) -> str:
        """Remplace une paire Prénom Nom ou NOM Prénom détectée en contexte."""
        w1: str = match.group(1)
        particle: str = match.group(2) or ""
        w2: str = match.group(3)
        f1: bool = self._is_known_first_name_ocr(w1)
        if self._is_non_surname_word(w1) or self._is_non_surname_word(
            w2, after_known_first_name=f1
        ):
            return match.group(0)

        w2_parts: List[str] = [p for p in w2.split() if p]
        f2: bool = len(w2_parts) == 1 and self._is_known_first_name_ocr(w2)
        part_init: str = self._format_particle_initials(particle)

        if w2.isupper() and len(w2) >= 4 and (f1 or self._is_title_case_token(w1)):
            return f"{w1} {part_init}{self._format_surname_initials(w2)}"

        if w1.isupper() and len(w1) >= 4 and len(w2_parts) == 1 and (f2 or self._is_title_case_token(w2)):
            return f"{self._format_surname_initials(w1)} {part_init}{w2}"

        if f1 and (not f2 or particle or len(w2_parts) >= 2) and len(w2) >= 3:
            return f"{w1} {part_init}{self._format_surname_initials(w2)}"

        if not f1 and f2 and len(w1) >= 3:
            if w1.isupper() or DocumentTextUtils.normalize_word(w1) in self.rules.protected_surnames:
                return f"{self._format_surname_initials(w1)} {part_init}{w2}"

        return match.group(0)

    def _replace_mime_recipient(self, match: re.Match[str]) -> str:
        """Abrège le nom d'un destinataire MIME accolé à un jeton E. ou EMAIL_XXX."""
        surname: str = match.group(3)
        if self._is_non_surname_word(surname):
            return match.group(0)
        return f"{match.group(1)}{match.group(2)} {self._format_surname_initials(surname)}{match.group(4)}"

    def _replace_catalog_location(self, match: re.Match[str]) -> str:
        """Remplace une commune du référentiel national en temps constant O(1)."""
        token: str = match.group(0)
        norm: str = DocumentTextUtils.normalize_word(token)
        if (
            len(norm) < 4
            or norm in ContactRulesLoader.COMMON_WORD_COLLISIONS
            or norm in self.config.excluded_words
            or norm not in self.config.masked_locations
        ):
            return token
        prefix: str = match.string[max(0, match.start() - 30):match.start()]
        if re.search(r"[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'-]{2,}\s+", prefix):
            return token
        suffix: str = match.string[match.end():match.end() + 30]
        if re.match(r"^\s+[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'-]{2,}", suffix):
            return token
        return "[LIEU_MASQUE]"

    def _anonymize_chunk(self, text: str) -> str:
        """Applique les passes de masquage sur une tranche de texte bornée."""
        token: str = CommunicationExtractor.MAIN_CHARACTER_TOKEN
        text = text.replace(token, self.config.main_character_name)
        text = DocumentTextUtils.repair_mojibake(text)
        text = text.replace(r"\,", ",").replace(r"\;", ";")
        text = self.HTML_INLINE_TAG_CLEANUP.sub("", text)
        text = self.MRZ_LINE_PATTERN.sub("[MRZ_IDENTITE_MASQUEE]", text)
        text = self.GLUED_TITLE_OR_CAMEL.sub(self._split_glued_tokens, text)

        if self.config.mask_ssn:
            text = DocumentTextUtils.REGEX_SSN.sub("[NUM_SECU_MASQUE]", text)
        if self.config.mask_financial_and_admin_ids:
            text = DocumentTextUtils.REGEX_IBAN.sub("[IBAN_MASQUE]", text)
            text = DocumentTextUtils.REGEX_BIC.sub("[BIC_MASQUE]", text)
            text = DocumentTextUtils.REGEX_FISCAL_ID.sub("[NUM_FISCAL_MASQUE]", text)
            text = DocumentTextUtils.REGEX_FRANCE_TRAVAIL.sub("[ID_FRANCE_TRAVAIL_MASQUE]", text)
            text = DocumentTextUtils.REGEX_CAF_ALLOCATAIRE.sub("[NUM_ALLOCATAIRE_MASQUE]", text)
            text = DocumentTextUtils.REGEX_OFFICIAL_MEDICAL_ID.sub("[ID_ADMIN_MASQUE]", text)
            text = DocumentTextUtils.REGEX_BANK_TX_AND_CARDS.sub("[REF_BANCAIRE_TX_MASQUEE]", text)
            text = DocumentTextUtils.REGEX_MEETING_IDS.sub("[ID_REUNION_MASQUE]", text)
            text = DocumentTextUtils.REGEX_ACCESS_CODES.sub("[CODE_ACCES_MASQUE]", text)
            text = DocumentTextUtils.REGEX_ADMIN_REFS.sub("[REF_ADMIN_MASQUEE]", text)
            text = DocumentTextUtils.REGEX_ID_DOC_DATES.sub(r"\1[DATE_TITRE_MASQUEE]", text)
        text = DocumentTextUtils.REGEX_BIRTH_DATE.sub(r"\1[JOUR_MOIS_MASQUES]/\2", text)
        text = DocumentTextUtils.REGEX_EMAIL.sub(
            lambda m: self.audit.pseudonymize_id(m.group(0), "EMAIL"), text
        )
        text = DocumentTextUtils.REGEX_PHONE.sub(
            lambda m: self.audit.pseudonymize_id(m.group(0), "TEL"), text
        )
        if self.config.mask_financial_and_admin_ids:
            text = DocumentTextUtils.REGEX_ISOLATED_12_DIGITS.sub("[ID_CNI_PERMIS_MASQUE]", text)
        if self.config.mask_urls:
            text = DocumentTextUtils.REGEX_URL.sub("[URL_MASQUEE]", text)

        text = text.replace("//", " ")

        if self.config.mask_addresses:
            text = DocumentTextUtils.REGEX_POSTAL_CITY.sub("[LIEU_MASQUE]", text)
            text = DocumentTextUtils.REGEX_STREET_ADDRESS.sub("[ADRESSE_MASQUEE]", text)
            text = DocumentTextUtils.REGEX_FACILITIES_AND_ZONES.sub("[ETABLISSEMENT_LIEU_MASQUE]", text)

        if self.rules.combined_glued_pattern is not None:
            text = self.rules.combined_glued_pattern.sub(
                lambda m: self.rules.lookup_glued_alias(m.group(0)), text
            )

        text = self.AUTO_TITLE_PATTERN.sub(self._replace_title_match, text)

        if self.rules.combined_case_sensitive_pattern is not None:
            text = self.rules.combined_case_sensitive_pattern.sub(
                lambda m: self.rules.case_sensitive_keywords.get(m.group(0), m.group(0)),
                text,
            )

        if self.rules.combined_keyword_pattern is not None:
            text = self.rules.combined_keyword_pattern.sub(
                lambda m: self.rules.lookup_keyword_alias(m.group(0)), text
            )

        text = self.UPPER_PAIR_PATTERN.sub(self._replace_upper_pair_match, text)
        text = self.AUTO_PERSON_PAIR_PATTERN.sub(self._replace_person_pair_match, text)
        text = self.MIME_TOKEN_RECIPIENT_PATTERN.sub(self._replace_mime_recipient, text)
        text = self.PARENS_PSEUDO_PATTERN.sub(r"\1([PSEUDO_MASQUE])", text)

        if self.rules.combined_location_pattern is not None:
            text = self.rules.combined_location_pattern.sub("[LIEU_MASQUE]", text)
        elif self.config.masked_locations:
            text = re.sub(
                r"(?<![A-Za-zÀ-ÿ])[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç'\-]{3,}(?![A-Za-zÀ-ÿ])",
                self._replace_catalog_location,
                text,
            )

        text = self.DUPLICATE_ALIAS_CLEANUP.sub(
            lambda m: m.group(1) or m.group(2), text
        )
        return text

    def _anonymize_text(self, text: str) -> str:
        """Découpe les textes volumineux par tranches de 32 Ko pour éviter tout blocage regex."""
        if len(text) <= self.TEXT_CHUNK_LIMIT:
            return self._anonymize_chunk(text)
        out_parts: List[str] = []
        buf: List[str] = []
        buf_len: int = 0
        for line in text.splitlines(keepends=True):
            buf.append(line)
            buf_len += len(line)
            if buf_len >= self.TEXT_CHUNK_LIMIT:
                out_parts.append(self._anonymize_chunk("".join(buf)))
                buf = []
                buf_len = 0
        if buf:
            out_parts.append(self._anonymize_chunk("".join(buf)))
        return "".join(out_parts)
    def _anonymize_display_path(self, trans_path: str) -> str:
        """Masque les identifiants sensibles dans le nom de fichier source affiché."""
        folder, file_name = os.path.split(trans_path)
        masked: str = DocumentTextUtils.repair_mojibake(file_name)
        if self.config.mask_ssn:
            masked = DocumentTextUtils.REGEX_SSN.sub("NUM_SECU_MASQUE", masked)
        if self.config.mask_financial_and_admin_ids:
            masked = DocumentTextUtils.REGEX_IBAN.sub("IBAN_MASQUE", masked)
            masked = DocumentTextUtils.REGEX_OFFICIAL_MEDICAL_ID.sub("ID_ADMIN_MASQUE", masked)
            masked = DocumentTextUtils.REGEX_ACCESS_CODES.sub("CODE_ACCES_MASQUE", masked)
            masked = DocumentTextUtils.REGEX_ADMIN_REFS.sub("REF_ADMIN_MASQUEE", masked)
        masked = DocumentTextUtils.REGEX_EMAIL.sub(
            lambda m: self.audit.pseudonymize_id(m.group(0), "EMAIL"), masked
        )
        masked = DocumentTextUtils.REGEX_PHONE.sub(
            lambda m: self.audit.pseudonymize_id(m.group(0), "TEL"), masked
        )
        if self.config.mask_urls:
            masked = DocumentTextUtils.REGEX_URL.sub("URL_MASQUEE", masked)
        masked = self.AUTO_TITLE_PATTERN.sub(self._replace_title_match, masked)
        if self.rules.combined_case_sensitive_pattern is not None:
            masked = self.rules.combined_case_sensitive_pattern.sub(
                lambda m: self.rules.case_sensitive_keywords.get(m.group(0), m.group(0)),
                masked,
            )
        if self.rules.combined_keyword_pattern is not None:
            masked = self.rules.combined_keyword_pattern.sub(
                lambda m: self.rules.lookup_keyword_alias(m.group(0)), masked
            )
        if self.rules.combined_glued_pattern is not None:
            masked = self.rules.combined_glued_pattern.sub(
                lambda m: self.rules.lookup_glued_alias(m.group(0)), masked
            )
        masked = self.AUTO_PERSON_PAIR_PATTERN.sub(self._replace_person_pair_match, masked)
        if self.rules.combined_location_pattern is not None:
            masked = self.rules.combined_location_pattern.sub("LIEU_MASQUE", masked)
        return os.path.join(folder, masked)

    def flush_batch(self) -> None:
        """Écrit le lot en cours sur disque et met à jour l'état et l'audit."""
        if not self.current_chunk:
            self.audit.save()
            self.audit.write_report()
            return
        batch_num: int = ((self.audit.file_idx - 1) // self.config.files_per_folder) + 1
        batch_dir: str = os.path.join(self.config.results_dir, f"lot_{batch_num:02d}")
        os.makedirs(batch_dir, exist_ok=True)
        out_name: str = f"{self.config.file_prefix}partie_{self.audit.file_idx:03d}.txt"
        full_out_path: str = os.path.join(batch_dir, out_name)
        DocumentTextUtils.atomic_write_text(full_out_path, "".join(self.current_chunk))

        self.audit.already_processed.update(self.current_batch_files)
        self.audit.file_idx += 1
        self.audit.written_batches += 1
        self.current_chunk = []
        self.current_size = 0
        self.current_batch_files = []

        self.audit.save()
        count: int = self.audit.write_report()
        print(f"    [+] LOT ÉCRIT : '{full_out_path}' (Audit : {count} nom(s))", flush=True)
    def anonymize_single_file(self, trans_path: str, force_reprocess: bool = False) -> bool:
        """Anonymise une transcription individuelle et l'ajoute au lot courant."""
        if not self._initialized and not self.initialize():
            return False
        norm_path: str = os.path.normpath(trans_path)
        if not force_reprocess and norm_path in self.audit.already_processed:
            return False
        if not os.path.exists(trans_path):
            return False

        with open(trans_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_content: str = f.read()
        if not raw_content.strip():
            return False

        display_path: str = self._anonymize_display_path(trans_path)
        sep: str = "#" * 72
        header: str = f"{sep}\n# SOURCE TRANSCRIPTION : {display_path}\n{sep}\n"
        anonymized: str = self._anonymize_text(header + raw_content)
        self.audit.scan_residual_names(anonymized, display_path)

        block_bytes: int = len(anonymized.encode("utf-8"))
        max_files_per_batch: int = getattr(self.config, "max_batch_files", 50)
        if self.current_chunk and (
            self.current_size + block_bytes > self.config.max_batch_bytes
            or len(self.current_chunk) >= max_files_per_batch
        ):
            self.flush_batch()

        self.current_chunk.append(anonymized)
        self.current_size += block_bytes
        self.current_batch_files.append(norm_path)
        self.processed_in_session += 1
        return True

    def finalize(self, start_time: float) -> None:
        """Vide le dernier lot et génère les rapports finaux d'audit."""
        self.flush_batch()
        count: int = self.audit.write_report()
        elapsed_str: str = SharedCoreUtils.format_duration(time.time() - start_time)
        print(f"\n[100.0%] Terminé ({self.processed_in_session} fichier(s) anonymisé(s) en {elapsed_str}).", flush=True)
        print(f" * Lots totaux  : {self.audit.written_batches} dans '{self.config.results_dir}/lot_XX/'", flush=True)
        print(f" * Audit détail : {count} nom(s) dans '{self.config.audit_report_file}'", flush=True)
        print(f" * Audit copier : {count} nom(s) dans '{self.config.audit_copy_file}'", flush=True)

    def run_on_existing_results(self) -> None:
        """Réapplique les règles de contacts sur les lots déjà générés."""
        start_time: float = time.time()
        print("=== PASSE SUR PLACE : CONTACTS & AUTOMATISMES SUR RÉSULTATS ===", flush=True)
        if not self.initialize():
            return
        res_dir: str = self.config.results_dir
        if not os.path.isdir(res_dir):
            print(f"Erreur : '{res_dir}' introuvable.", flush=True)
            return

        lot_files: List[str] = sorted(
            os.path.join(rp, fn)
            for rp, _, files in os.walk(res_dir)
            for fn in files
            if fn.lower().endswith(".txt") and not fn.startswith(".")
        )
        if not lot_files:
            print(f"Aucun fichier de lot trouvé dans '{res_dir}'.", flush=True)
            return

        self.audit.pair_counter.clear()
        self.audit.files_by_name.clear()
        self.audit.canonical_labels.clear()

        total: int = len(lot_files)
        for idx, lot_path in enumerate(lot_files, start=1):
            with open(lot_path, "r", encoding="utf-8", errors="ignore") as f_in:
                updated_content: str = self._anonymize_text(f_in.read())
            DocumentTextUtils.atomic_write_text(lot_path, updated_content)
            self.audit.scan_residual_names(updated_content, os.path.basename(lot_path))
            if idx % 10 == 0 or idx == total or idx == 1:
                print(f"    ... [{idx}/{total}] {os.path.basename(lot_path)}", flush=True)

        self.audit.save()
        count: int = self.audit.write_report()
        elapsed_str: str = SharedCoreUtils.format_duration(time.time() - start_time)
        print(f"\n[100.0%] Passe sur place terminée sur {total} lot(s) en {elapsed_str}.", flush=True)
        print(f" * Audit détail : {count} nom(s) dans '{self.config.audit_report_file}'", flush=True)
        print(f" * Audit copier : {count} nom(s) dans '{self.config.audit_copy_file}'", flush=True)

    def run(self) -> None:
        """Exécute l'anonymisation complète sur le répertoire transcriptions."""
        if self.manual_only:
            self.run_on_existing_results()
            return
        start_time: float = time.time()
        print("=== ÉTAPE 2 : ANONYMISATION & AUDIT ===", flush=True)
        if not self.initialize():
            return
        trans_dir: str = self.config.transcriptions_dir
        if not os.path.exists(trans_dir):
            print(f"Erreur : '{trans_dir}' introuvable.", flush=True)
            return

        all_txts: List[str] = sorted(
            os.path.join(rp, fn)
            for rp, _, files in os.walk(trans_dir)
            for fn in files
            if fn.lower().endswith(".txt") and fn != "rapport_extraction.txt" and not fn.startswith(".")
        )
        pending: List[str] = [f for f in all_txts if os.path.normpath(f) not in self.audit.already_processed]
        total: int = len(pending)
        for idx, trans_path in enumerate(pending, start=1):
            if idx % 10 == 0 or idx == total or idx == 1:
                print(f"    ... [{(idx / total) * 100:5.1f}% | {idx}/{total}] ...", flush=True)
            self.anonymize_single_file(trans_path)
        self.finalize(start_time)
