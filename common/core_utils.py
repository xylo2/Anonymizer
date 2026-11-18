# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import re
import tempfile
import unicodedata
from typing import Set


class SharedCoreUtils:
    """
    Centralise les utilitaires partagés entre google_contacts_parser et doc_anonymizer :
    normalisation Unicode, identifiants (téléphones/e-mails), écriture atomique
    et résolution des chemins de configuration.
    """

    @staticmethod
    def strip_accents(text: str) -> str:
        """
        Supprime les diacritiques et accents d'une chaîne Unicode via NFD.

        :param text: Texte source brut.
        :return: Texte sans accents.
        """
        return "".join(
            ch
            for ch in unicodedata.normalize("NFD", text)
            if unicodedata.category(ch) != "Mn"
        )

    @classmethod
    def normalize_token(cls, text: str) -> str:
        """
        Normalise un jeton en minuscules sans accents ni espaces périphériques.

        :param text: Chaîne brute.
        :return: Chaîne normalisée.
        """
        return cls.strip_accents(text).lower().strip()

    @classmethod
    def normalize_compact_text(cls, text: str) -> str:
        """
        Normalise un nom en minuscules sans accents, espaces, tirets ni apostrophes.

        :param text: Texte brut à comparer.
        :return: Chaîne compacte normalisée.
        """
        base: str = cls.normalize_token(text)
        return re.sub(r"[\s\-'\u2019]", "", base)

    @staticmethod
    def normalize_email_alias(email: str, lowercase: bool = True) -> str:
        """
        Retire l'extension d'alias '+...' dans la partie locale d'un e-mail.

        :param email: Adresse e-mail brute.
        :param lowercase: Convertit l'adresse en minuscules si True.
        :return: Adresse e-mail canonique.
        """
        cleaned: str = re.sub(r"^mailto:", "", email.strip(), flags=re.IGNORECASE)
        if "@" not in cleaned:
            return cleaned
        local_part, domain_part = cleaned.rsplit("@", 1)
        if "+" in local_part:
            local_part, _ = local_part.split("+", 1)
        result: str = f"{local_part}@{domain_part}"
        return result.lower() if lowercase else result
    @classmethod
    def normalize_identifier(cls, value: str, lowercase_email: bool = True) -> str:
        """
        Uniformise un numéro de téléphone français (format 0XXXXXXXXX)
        ou international ainsi qu'une adresse e-mail.

        :param value: Coordonnée brute (téléphone ou e-mail).
        :param lowercase_email: Met l'e-mail en minuscules si True.
        :return: Identifiant normalisé.
        """
        val: str = value.strip()
        if "@" in val:
            return cls.normalize_email_alias(val, lowercase=lowercase_email)
        num: str = re.sub(r"[\s.\-\u00a0()]", "", val)
        if num.startswith("+330"):
            num = "0" + num[4:]
        elif num.startswith("+33"):
            num = "0" + num[3:]
        elif num.startswith("00330"):
            num = "0" + num[5:]
        elif num.startswith("0033"):
            num = "0" + num[4:]
        return num

    @staticmethod
    def atomic_write_text(target_path: str, content: str, encoding: str = "utf-8") -> None:
        """
        Écrit un fichier texte de façon atomique via un fichier temporaire
        dans le répertoire cible afin d'éviter toute corruption.

        :param target_path: Chemin final du fichier sur disque.
        :param content: Contenu complet à enregistrer.
        :param encoding: Encodage cible (défaut : utf-8).
        """
        parent_dir: str = os.path.dirname(os.path.abspath(target_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=parent_dir, prefix=".tmp_atom_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding=encoding, newline="\n") as f_tmp:
                f_tmp.write(content)
            os.replace(tmp_path, target_path)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    @staticmethod
    def resolve_config_path(raw_config: str, root_dir: str) -> str:
        """
        Résout le chemin vers config.ini en vérifiant le chemin fourni
        puis la racine du dépôt.

        :param raw_config: Chemin brut passé en argument CLI.
        :param root_dir: Répertoire racine du projet.
        :return: Chemin absolu existant vers config.ini.
        """
        if os.path.isabs(raw_config):
            if os.path.exists(raw_config):
                return raw_config
            raise FileNotFoundError(f"Fichier de configuration introuvable : '{raw_config}'")

        root_candidate: str = os.path.normpath(os.path.join(root_dir, raw_config))
        if os.path.exists(root_candidate):
            return root_candidate

        cwd_candidate: str = os.path.abspath(raw_config)
        if os.path.exists(cwd_candidate):
            return cwd_candidate

        raise FileNotFoundError(
            f"Fichier de configuration '{raw_config}' introuvable "
            f"(cherché dans '{root_candidate}' et '{cwd_candidate}')."
        )

    @classmethod
    def load_first_names_set(cls, file_path: str) -> Set[str]:
        """
        Charge et normalise les prénoms depuis le fichier prenoms.txt partagé.

        :param file_path: Chemin vers prenoms.txt.
        :return: Ensemble des prénoms normalisés sans accents.
        """
        names: Set[str] = set()
        if not os.path.exists(file_path):
            return names
        with open(file_path, "r", encoding="utf-8") as f_in:
            for raw_line in f_in:
                cleaned: str = raw_line.strip()
                if cleaned and not cleaned.startswith("#"):
                    norm: str = cls.normalize_token(cleaned)
                    if norm:
                        names.add(norm)
        return names
