# Commandes pip à exécuter : Aucune dépendance externe requise

from collections import Counter, defaultdict
from difflib import SequenceMatcher
import hashlib
import json
import os
import re
from typing import Any, DefaultDict, Dict, FrozenSet, List, Optional, Pattern, Set, Tuple
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_rules_loader import ContactRulesLoader
from doc_anonymizer.text_utils import DocumentTextUtils


class AuditAndStateManager:
    """
    Gère la persistance JSON de reprise, la pseudonymisation SHA-256,
    les statistiques du tableau de bord et les rapports d'audit.
    """

    PAIR_PATTERN: Pattern[str] = re.compile(
        r"\b([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]"
        r"[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç-]{1,25})[ \t]+"
        r"(?:(?:de|du|des|d'|le|la|van|von|ben|el|al|dos|da|di)[ \t]+)?"
        r"([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]"
        r"[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç-]{1,25})\b"
    )

    TITLE_PATTERN: Pattern[str] = re.compile(
        r"\b(?:Dr|Docteur|Pr|Professeur|Mme|Madame|M\.|Monsieur|"
        r"Mlle|Mademoiselle|Me|Maître|Maitre|Famille)\.?\s+"
        r"(?:(?:de|du|des|d'|le|la|van|von|ben|el|al|dos|da|di)\s+)?"
        r"([A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]"
        r"[A-Za-zÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç-]{1,25})\b"
    )

    MASKED_PREFIXES: Tuple[str, ...] = (
        "TEL_", "EMAIL_", "AUTRE_", "CONTACT_MAIL_",
        "LIEU_MASQUE", "URL_MASQUEE", "ADRESSE_MASQUEE",
        "NUM_SECU", "IBAN_", "BIC_", "ID_FRANCE", "NUM_ALLOCATAIRE",
        "NUM_FISCAL", "PERSONNAGE_",
    )

    COMPOUND_PLACE_PARTICLES: FrozenSet[str] = frozenset({
        "de", "du", "des", "d", "sur", "sous", "en", "les", "la", "le", "aux", "au",
    })

    COMMON_FRENCH_STOPWORDS: FrozenSet[str] = frozenset({
        "le", "la", "les", "un", "une", "des", "du", "de", "au", "aux",
        "ce", "cet", "cette", "ces", "mon", "ton", "son", "ma", "ta", "sa",
        "mes", "tes", "ses", "notre", "votre", "leur", "nos", "vos", "leurs",
        "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
        "qui", "que", "quoi", "dont", "ou", "et", "mais", "donc", "or", "ni",
        "car", "pour", "par", "avec", "sans", "sous", "sur", "dans", "vers",
        "chez", "entre", "apres", "avant", "depuis", "pendant", "selon",
        "tres", "plus", "moins", "bien", "mal", "tout", "tous", "toute",
        "toutes", "autre", "autres", "meme", "memes", "aucun", "aucune",
        "chaque", "quel", "quelle", "quels", "quelles", "ici", "la", "oui",
        "non", "pas", "ne", "en", "y", "est", "sont", "etait", "etaient",
        "etre", "avoir", "fait", "faire", "dit", "dire", "voir", "vu",
        "bonjour", "bonsoir", "salut", "merci", "cordialement", "sinceres",
        "salutations", "objet", "sujet", "date", "heure", "lieu", "page",
        "pages", "total", "montant", "numero", "reference", "dossier",
        "document", "documents", "fichier", "fichiers", "piece", "jointe",
        "annexe", "copie", "original", "version", "note", "notes", "avis",
        "compte", "rendu", "bilan", "rapport", "synthese", "resume",
        "contrat", "facture", "devis", "commande", "paiement", "reglement",
        "attestation", "certificat", "ordonnance", "prescription", "courrier",
        "lettre", "message", "mail", "email", "telephone", "adresse", "code",
        "postal", "ville", "pays", "france", "europe", "region", "departement",
        "mairie", "prefecture", "tribunal", "ministere", "service", "services",
        "direction", "directeur", "directrice", "president", "presidente",
        "general", "generale", "secretaire", "responsable", "chef", "agent",
        "docteur", "professeur", "madame", "monsieur", "mademoiselle", "maitre",
        "cabinet", "clinique", "hopital", "centre", "laboratoire", "pharmacie",
        "banque", "assurance", "mutuelle", "caisse", "allocations", "impots",
        "article", "chapitre", "section", "titre", "point", "liste", "tableau",
        "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
        "lun", "mar", "mer", "jeu", "ven", "sam", "dim",
        "janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
        "aout", "septembre", "octobre", "novembre", "decembre", "janv", "fevr",
        "avr", "juil", "sept", "oct", "nov", "dec", "nord", "sud", "est",
        "ouest", "saint", "sainte", "rue", "avenue", "boulevard", "place",
        "delivery", "carte", "recap", "parking", "nouveau", "arbitrage",
        "backlog", "daily", "coord", "donne", "enf", "finalement", "origine",
        "passe", "signature", "signez", "tome", "visualiser", "voici",
        "apparemment", "besoin", "bises", "coordination", "dessins", "dsn",
        "demo", "demonstration", "developpement", "epic", "examens", "fax",
        "fourmi", "gazette", "genre", "gestion", "lorsque", "mascarade",
        "mondial", "plein", "preparation", "puree", "quant", "respire",
        "retour", "reorganisation", "reunions", "taper", "trancher", "union",
        "unite", "appart",
    })

    AMBIGUOUS_FIRST_NAMES: FrozenSet[str] = frozenset({
        "aime", "aimee", "ange", "aube", "aurore", "blanc", "blanche",
        "bon", "cerise", "clair", "claire", "clement", "constance", "desire",
        "douce", "esperance", "fidele", "fleur", "flore", "france", "gai",
        "grace", "guy", "honore", "iris", "jean", "joie", "joli", "joy",
        "juste", "laurier", "loup", "luce", "lumiere", "marc", "marine",
        "max", "may", "modeste", "noel", "olive", "paix", "parfait",
        "patience", "pierre", "premier", "prime", "prudence", "rose",
        "sage", "sauveur", "solange", "soleil", "victoire", "violette",
    })

    def __init__(
        self, config: PipelineConfig, rules: ContactRulesLoader
    ) -> None:
        """
        Initialise le gestionnaire d'état, les compteurs de statistiques et d'audit.

        :param config: Instance de PipelineConfig.
        :param rules: Instance de ContactRulesLoader.
        """
        self.config: PipelineConfig = config
        self.rules: ContactRulesLoader = rules
        self.already_processed: Set[str] = set()
        self.auto_cache: Dict[str, str] = {}
        self.counters: Dict[str, int] = {"TEL": 1, "EMAIL": 1}
        self.pair_counter: Counter[str] = Counter()
        self.files_by_name: DefaultDict[str, Set[str]] = defaultdict(set)
        self.canonical_labels: Dict[str, str] = {}
        self.file_idx: int = 1
        self.written_batches: int = 0
        self.stats: Dict[str, Any] = {
            "documents_traites": 0,
            "noms_masques": 0,
            "coordonnees_masquees": 0,
            "identifiants_masques": 0,
            "lieux_dates_masques": 0,
            "par_categorie": {},
            "zip_ignores": [],
        }

    @staticmethod
    def _phonetic_french_key(word: str) -> str:
        """
        Calcule une clé phonétique française simplifiée pour rapprocher les
        erreurs de transcription vocale/OCR (ex: 'dubunt' ~ 'dupont').

        :param word: Mot normalisé sans accents.
        :return: Empreinte phonétique compacte.
        """
        s: str = DocumentTextUtils.normalize_word(word)
        s = re.sub(r"[^a-z]", "", s)
        if not s:
            return ""
        s = s.replace("ph", "f").replace("qu", "k").replace("q", "k")
        s = s.replace("c", "k").replace("g", "k")
        s = s.replace("p", "b").replace("t", "d")
        s = s.replace("v", "f").replace("z", "s")
        s = re.sub(r"[aeiouy]+", "a", s)
        s = re.sub(r"(.)\1+", r"\1", s)
        if len(s) > 3 and s[-1] in {"d", "s", "x"}:
            s = s[:-1]
        return s
    def _suggest_alias_from_fuzzy_last_name(
        self, display_name: str
    ) -> Optional[Tuple[str, str]]:
        """
        Recherche si le nom de famille candidat est proche orthographiquement
        d'un vrai nom de famille connu, sans jamais suggérer sur un prénom seul.

        :param display_name: Libellé candidat détecté par l'audit.
        :return: Tuple (alias_suggéré, nom_famille_proche) ou None.
        """
        if not self.rules.last_name_to_aliases:
            return None

        tokens: List[str] = display_name.strip().split()
        candidate_last: str = tokens[-1] if tokens else display_name.strip()
        if self.rules.is_first_name(candidate_last):
            return None

        norm_cand: str = DocumentTextUtils.normalize_word(candidate_last)
        if len(norm_cand) < 5 or norm_cand in self.COMMON_FRENCH_STOPWORDS:
            return None

        cand_phon: str = self._phonetic_french_key(norm_cand)
        best_score: float = 0.0
        best_known: str = ""

        for known_last in self.rules.last_name_to_aliases.keys():
            if len(known_last) < 5 or known_last == norm_cand:
                continue
            if abs(len(known_last) - len(norm_cand)) > 2:
                continue
            ratio: float = SequenceMatcher(
                None, norm_cand, known_last
            ).ratio()
            known_phon: str = self._phonetic_french_key(known_last)
            if cand_phon and cand_phon == known_phon and ratio >= 0.65:
                ratio = min(1.0, ratio + 0.15)
            if ratio > best_score:
                best_score = ratio
                best_known = known_last

        if best_score >= 0.78 and best_known:
            disp_known: str = self.rules.last_name_display.get(
                best_known, best_known.capitalize()
            )
            if len(tokens) >= 2:
                first_disp: str = self._format_first_name_case(next(iter(tokens)))
                suggested: str = f"{first_disp} {disp_known[:1].upper()}."
            else:
                suggested = f"{disp_known[:1].upper()}."
            return suggested, disp_known
        return None

    @staticmethod
    def _format_first_name_case(token: str) -> str:
        """
        Capitalise proprement un prénom (gère les prénoms composés et majuscules).

        :param token: Jeton prénom brut.
        :return: Prénom mis en forme (ex: 'FLORIAN' -> 'Florian').
        """
        parts: List[str] = re.split(r"(-)", token.strip())
        return "".join(p.capitalize() if p != "-" else p for p in parts)

    def _canonicalize_key(self, raw_key: str) -> Tuple[str, str]:
        """
        Ordonne une paire en 'Prénom Nom' grâce au référentiel des prénoms
        et retourne (clé_normalisée_unique, libellé_affichable).

        :param raw_key: Clé candidate ('Nom Prénom', 'Prénom Nom' ou nom seul).
        :return: Tuple (identifiant_canonique, libellé_d_affichage).
        """
        tokens: List[str] = raw_key.strip().split()
        if len(tokens) == 2:
            p1, p2 = tokens
            f1: bool = self.rules.is_first_name(p1)
            f2: bool = self.rules.is_first_name(p2)
            if f2 and not f1:
                first_tok, last_tok = p2, p1
            else:
                first_tok, last_tok = p1, p2
            display_first: str = self._format_first_name_case(first_tok)
            display_label: str = f"{display_first} {last_tok}"
        else:
            display_label = raw_key.strip()

        norm_id: str = DocumentTextUtils.normalize_word(display_label)
        existing: str = self.canonical_labels.get(norm_id, "")
        if not existing or (existing.isupper() and not display_label.isupper()):
            self.canonical_labels[norm_id] = display_label
        return norm_id, self.canonical_labels[norm_id]
    def _is_truncated_place_fragment(self, cleaned: str) -> bool:
        """
        Détecte un fragment de toponyme composé tronqué (ex: 'Saint-Martin-De').

        :param cleaned: Mot ou composé brut à évaluer.
        :return: True si le jeton est un fragment géographique incomplet.
        """
        if "-" not in cleaned:
            return False
        hyphen_parts: List[str] = [
            DocumentTextUtils.normalize_word(p)
            for p in cleaned.split("-")
            if p.strip()
        ]
        if not hyphen_parts:
            return True
        if hyphen_parts[-1] in self.COMPOUND_PLACE_PARTICLES:
            return True
        if next(iter(hyphen_parts)) in {"saint", "sainte", "st", "ste"}:
            return True
        return False

    def _is_valid_word(self, word: str) -> bool:
        """
        Vérifie qu'un mot candidat est un nom propre plausible et non un
        jeton masqué, un mot-outil français ou un terme exclu.

        :param word: Mot brut à évaluer.
        :return: True si le mot est éligible pour l'audit.
        """
        cleaned: str = word.strip().strip("-")
        if len(cleaned) < 2 or cleaned.upper().startswith(self.MASKED_PREFIXES):
            return False
        if any(ch.isdigit() for ch in cleaned):
            return False
        if self._is_truncated_place_fragment(cleaned):
            return False
        norm: str = DocumentTextUtils.normalize_word(cleaned)
        if len(norm) < 2:
            return False
        return (
            norm not in self.COMMON_FRENCH_STOPWORDS
            and norm not in self.config.excluded_words
            and norm not in self.rules.alias_words
            and norm not in self.config.masked_locations
        )

    def _is_plausible_pair(self, p1: str, p2: str) -> bool:
        """
        Valide une paire (p1, p2) en écartant les faux positifs liés aux
        prénoms ambigus (mots courants) et aux sigles tout en majuscules.

        :param p1: Premier mot candidat.
        :param p2: Second mot candidat.
        :return: True si la paire est un nom de personne probable.
        """
        if not (self._is_valid_word(p1) and self._is_valid_word(p2)):
            return False
        if p1.isupper() and p2.isupper() and len(p1) <= 4 and len(p2) <= 4:
            return False

        f1: bool = self.rules.is_first_name(p1)
        f2: bool = self.rules.is_first_name(p2)
        if not (f1 or f2) or (f1 and f2):
            return False

        first_tok: str = p1 if f1 else p2
        last_tok: str = p2 if f1 else p1
        norm_first: str = DocumentTextUtils.normalize_word(first_tok)
        norm_last: str = DocumentTextUtils.normalize_word(last_tok)

        if len(norm_last) < 3:
            return False
        if norm_first in self.AMBIGUOUS_FIRST_NAMES:
            if (
                norm_last not in self.rules.last_name_to_aliases
                and not last_tok.isupper()
            ):
                return False

        nk: str = DocumentTextUtils.normalize_word(f"{p1} {p2}")
        ni: str = DocumentTextUtils.normalize_word(f"{p2} {p1}")
        return (
            nk not in self.rules.full_targets
            and ni not in self.rules.full_targets
        )

    def _is_entry_still_valid(self, display_name: str) -> bool:
        """
        Vérifie si une entrée déjà présente dans l'état JSON reste valide
        en écartant notamment tout prénom seul.

        :param display_name: Libellé enregistré dans l'état.
        :return: True si l'entrée doit être conservée.
        """
        tokens: List[str] = display_name.strip().split()
        if len(tokens) == 2:
            tok_first, tok_second = tokens
            return self._is_plausible_pair(tok_first, tok_second)
        if len(tokens) == 1:
            tok: str = next(iter(tokens))
            norm: str = DocumentTextUtils.normalize_word(tok)
            return (
                self._is_valid_word(tok)
                and not self.rules.is_first_name(tok)
                and len(norm) >= 3
                and norm not in self.rules.full_targets
            )
        return False
    def load(self) -> None:
        """Restaure, filtre et fusionne l'état JSON depuis le disque s'il existe."""
        os.makedirs(self.config.results_dir, exist_ok=True)
        if not os.path.exists(self.config.resume_state_file):
            return
        try:
            with open(
                self.config.resume_state_file, "r", encoding="utf-8"
            ) as f:
                st: Dict[str, Any] = json.load(f)
            self.already_processed = set(st.get("fichiers_traites", []))
            self.auto_cache = st.get("cache_auto", {})
            self.counters = st.get("compteurs", {"TEL": 1, "EMAIL": 1})
            self.file_idx = st.get("idx_fichier", 1)
            self.written_batches = st.get("nb_lots_ecrits", 0)
            if isinstance(st.get("stats_anonymisation"), dict):
                self.stats.update(st["stats_anonymisation"])

            raw_counts: Dict[str, int] = st.get("compteur_paires", {})
            raw_files: Dict[str, List[str]] = st.get("fichiers_par_nom", {})
            for raw_name, count in raw_counts.items():
                if not self._is_entry_still_valid(raw_name):
                    continue
                norm_id, _ = self._canonicalize_key(raw_name)
                self.pair_counter[norm_id] += int(count)
                self.files_by_name[norm_id].update(raw_files.get(raw_name, []))
        except Exception:
            pass

    def save(self) -> None:
        """Sauvegarde l'état courant et les statistiques sur le disque de façon atomique."""
        os.makedirs(self.config.results_dir, exist_ok=True)
        exported_counts: Dict[str, int] = {
            self.canonical_labels.get(nid, nid): cnt
            for nid, cnt in self.pair_counter.items()
        }
        exported_files: Dict[str, List[str]] = {
            self.canonical_labels.get(nid, nid): sorted(paths)
            for nid, paths in self.files_by_name.items()
        }
        payload: Dict[str, Any] = {
            "fichiers_traites": sorted(self.already_processed),
            "idx_fichier": self.file_idx,
            "nb_lots_ecrits": self.written_batches,
            "cache_auto": self.auto_cache,
            "compteurs": self.counters,
            "compteur_paires": exported_counts,
            "fichiers_par_nom": exported_files,
            "stats_anonymisation": self.stats,
        }
        DocumentTextUtils.atomic_write_text(
            self.config.resume_state_file,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )

    def pseudonymize_id(self, raw_val: str, category: str) -> str:
        """Remplace un téléphone ou e-mail par son alias ou un jeton SHA-256."""
        norm_id: str = DocumentTextUtils.normalize_identifier(raw_val)
        if norm_id in self.rules.contacts_id:
            return self.rules.contacts_id[norm_id]
        salted: bytes = (norm_id + self.config.secret_salt).encode("utf-8")
        digest: str = hashlib.sha256(salted).hexdigest()[:10]
        if digest not in self.auto_cache:
            self.auto_cache[digest] = (
                f"{category}_{self.counters[category]:03d}"
            )
            self.counters[category] += 1
        return self.auto_cache[digest]

    def scan_residual_names(self, text: str, display_path: str) -> None:
        """Détecte et regroupe les noms propres résiduels sans retenir de prénom seul."""
        for m in self.PAIR_PATTERN.finditer(text):
            p1, p2 = m.group(1), m.group(2)
            if not self._is_plausible_pair(p1, p2):
                continue
            norm_id, _ = self._canonicalize_key(f"{p1} {p2}")
            self.pair_counter[norm_id] += 1
            self.files_by_name[norm_id].add(display_path)

        for m in self.TITLE_PATTERN.finditer(text):
            name: str = m.group(1)
            norm_name: str = DocumentTextUtils.normalize_word(name)
            if (
                self._is_valid_word(name)
                and not self.rules.is_first_name(name)
                and len(norm_name) >= 3
                and norm_name not in self.rules.full_targets
            ):
                norm_id, _ = self._canonicalize_key(name)
                self.pair_counter[norm_id] += 1
                self.files_by_name[norm_id].add(display_path)

    @staticmethod
    def _audit_sort_key(entry: Tuple[str, str, int]) -> Tuple[int, str]:
        """Calcule la clé de tri (occurrences décroissantes, puis libellé)."""
        _, display_name, count = entry
        return (-count, display_name.lower())

    def _format_audit_entry(
        self, norm_id: str, display_name: str, count: int, pad_width: int
    ) -> Tuple[str, str]:
        """Formate la ligne complète d'audit et la ligne épurée pour copier-coller."""
        short_names: List[str] = sorted(
            {os.path.basename(p) for p in self.files_by_name[norm_id]}
        )
        preview: str = ", ".join(short_names[:3])
        extra: int = len(short_names) - 3
        if extra > 0:
            preview += f" (+{extra} autre(s))"

        suggestion = self._suggest_alias_from_fuzzy_last_name(display_name)
        if suggestion:
            suggested_alias, close_last = suggestion
            rule_col: str = f"{display_name:<{pad_width}} = {suggested_alias}"
            detailed: str = (
                f"{rule_col}   # [{count:>3}x] "
                f"(Proche de '{close_last}') {preview}\n"
            )
            copy_line: str = f"{display_name} = {suggested_alias}\n"
            return detailed, copy_line

        rule_col = f"{display_name:<{pad_width}} = A_MASQUER"
        detailed = f"{rule_col}   # [{count:>3}x] {preview}\n"
        copy_line = f"{display_name} = \n"
        return detailed, copy_line

    def write_report(self) -> int:
        """Actualise simultanément audit_noms_residuels.txt et audit_noms_residuels_copier.txt."""
        manual_name: str = os.path.basename(self.config.manual_contacts_file)
        copy_name: str = os.path.basename(self.config.audit_copy_file)
        results: List[Tuple[str, str, int]] = sorted(
            [
                (nid, self.canonical_labels.get(nid, nid), cnt)
                for nid, cnt in self.pair_counter.items()
                if cnt >= self.config.min_audit_occurrences
            ],
            key=self._audit_sort_key,
        )
        sep_main: str = "=" * 78
        sep_sub: str = "-" * 78
        report_lines: List[str] = [
            f"# {sep_main}\n",
            "# RAPPORT D'AUDIT DES NOMS PROPRES RÉSIDUELS\n",
            f"# Fichiers analysés : {len(self.already_processed)} | "
            f"Noms détectés : {len(results)} | "
            f"Seuil min : {self.config.min_audit_occurrences}x\n",
            f"# {sep_main}\n",
            "# MODE D'EMPLOI :\n",
            f"#   1. Ouvrez '{copy_name}' pour récupérer directement les "
            "lignes 'Prénom Nom = ' sans texte superflu.\n",
            f"#   2. Complétez l'alias (ex: Prénom I.) et collez-les "
            f"dans '{manual_name}' (jamais écrasé).\n",
            "#   3. Ajoutez les faux positifs récurrents dans "
            "'excluded_words' (config.ini).\n",
            f"# {sep_sub}\n\n",
        ]
        copy_lines: List[str] = []

        if not results:
            report_lines.append("Aucun nouveau nom propre résiduel probable détecté.\n")
        else:
            pad_width: int = max(len(disp) for _, disp, _ in results) + 1
            tiers: List[Tuple[str, List[Tuple[str, str, int]]]] = [
                (" PRIORITÉ HAUTE (5 occurrences et plus)", [(nid, disp, c) for nid, disp, c in results if c >= 5]),
                (" PRIORITÉ MOYENNE (2 à 4 occurrences)", [(nid, disp, c) for nid, disp, c in results if 2 <= c <= 4]),
                (" OCCURRENCES UNIQUES (1 seule apparition)", [(nid, disp, c) for nid, disp, c in results if c == 1]),
            ]
            for title, items in tiers:
                if not items:
                    continue
                report_lines.append(f"# {sep_sub}\n# {title} — {len(items)} entrée(s)\n# {sep_sub}\n")
                for nid, disp, count in items:
                    det_ln, cp_ln = self._format_audit_entry(nid, disp, count, pad_width)
                    report_lines.append(det_ln)
                    copy_lines.append(cp_ln)
                report_lines.append("\n")

        DocumentTextUtils.atomic_write_text(self.config.audit_report_file, "".join(report_lines))
        DocumentTextUtils.atomic_write_text(self.config.audit_copy_file, "".join(copy_lines))
        return len(results)
