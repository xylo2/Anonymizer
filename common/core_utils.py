# Commandes pip à exécuter : Aucune dépendance externe requise

import ctypes
import os
import re
import subprocess
import tempfile
from typing import Optional, Set
import unicodedata


class SharedCoreUtils:
    """
    Fournit les primitives partagées de normalisation Unicode, de téléphones FR,
    d'identifiants, d'écriture atomique, de durée et d'inhibition de veille.
    """

    _sleep_process: Optional[subprocess.Popen] = None

    @staticmethod
    def strip_accents(text: str) -> str:
        """
        Supprime les signes diacritiques d'une chaîne Unicode (NFKD).

        :param text: Texte source accentué.
        :return: Texte sans accents.
        """
        nfkd: str = unicodedata.normalize("NFKD", text)
        return "".join(ch for ch in nfkd if not unicodedata.combining(ch))

    @classmethod
    def normalize_word(cls, word: str) -> str:
        """
        Normalise un mot en minuscules sans accents ni ponctuation périphérique.

        :param word: Mot brut.
        :return: Mot normalisé.
        """
        no_acc: str = cls.strip_accents(word.strip().lower())
        return re.sub(r"^[^\w]+|[^\w]+$", "", no_acc)

    @classmethod
    def normalize_token(cls, token: str) -> str:
        """
        Alias vers normalize_word pour la normalisation de jetons individuels.

        :param token: Jeton brut.
        :return: Jeton normalisé.
        """
        return cls.normalize_word(token)

    @classmethod
    def normalize_compact_text(cls, text: str) -> str:
        """
        Normalise une expression en minuscules sans accents avec espaces simples.

        :param text: Texte brut.
        :return: Texte normalisé compact.
        """
        no_acc: str = cls.strip_accents(text.strip().lower())
        cleaned: str = re.sub(r"[^\w\s'-]+", " ", no_acc)
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def normalize_fr_phone(raw_val: str) -> str:
        """
        Normalise un numéro français au format canonique '0XXXXXXXXX'.

        :param raw_val: Numéro brut.
        :return: Numéro normalisé ou chaîne vide si non reconnu.
        """
        digits: str = re.sub(r"[\s.\-()]+", "", raw_val.strip())
        if digits.startswith("+33") and len(digits) == 12 and digits[3:].isdigit():
            return "0" + digits[3:]
        if digits.startswith("0033") and len(digits) == 13 and digits[4:].isdigit():
            return "0" + digits[4:]
        if digits.startswith("0") and len(digits) == 10 and digits.isdigit():
            return digits
        return ""
    @staticmethod
    def normalize_email_alias(raw_email: str, lowercase: bool = True) -> str:
        """
        Normalise une adresse e-mail et supprime les suffixes +alias.

        :param raw_email: Adresse e-mail brute.
        :param lowercase: Convertit l'adresse en minuscules si True.
        :return: Adresse e-mail normalisée.
        """
        cleaned: str = raw_email.strip()
        if lowercase:
            cleaned = cleaned.lower()
        if "@" not in cleaned:
            return cleaned
        return re.sub(r"\+[^@]+(?=@)", "", cleaned).strip()

    @classmethod
    def normalize_identifier(cls, raw_val: str) -> str:
        """
        Normalise un e-mail (sans +alias) ou un numéro de téléphone français.

        :param raw_val: Coordonnée brute.
        :return: Identifiant normalisé.
        """
        cleaned: str = raw_val.strip()
        if not cleaned:
            return ""
        if "@" in cleaned:
            return cls.normalize_email_alias(cleaned, lowercase=True)
        norm_phone: str = cls.normalize_fr_phone(cleaned)
        return norm_phone if norm_phone else cleaned.lower()

    @staticmethod
    def resolve_config_path(config_arg: str, root_dir: str) -> str:
        """
        Résout le chemin vers config.ini par rapport à la racine si relatif.

        :param config_arg: Chemin passé en argument CLI.
        :param root_dir: Répertoire racine du projet.
        :return: Chemin absolu normalisé.
        """
        if os.path.isabs(config_arg):
            return os.path.normpath(config_arg)
        if os.path.exists(config_arg):
            return os.path.abspath(config_arg)
        return os.path.normpath(os.path.join(root_dir, config_arg))

    @classmethod
    def load_words_set(cls, file_path: str) -> Set[str]:
        """
        Charge un fichier dictionnaire ligne par ligne en un ensemble normalisé.

        :param file_path: Chemin vers le fichier dictionnaire.
        :return: Ensemble des entrées normalisées.
        """
        items: Set[str] = set()
        if not file_path or not os.path.exists(file_path):
            return items
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line: str = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                norm: str = cls.normalize_compact_text(line)
                if norm:
                    items.add(norm)
        return items

    @classmethod
    def load_first_names_set(cls, file_path: str) -> Set[str]:
        """
        Charge le référentiel des prénoms en un ensemble normalisé.

        :param file_path: Chemin vers prenoms.txt.
        :return: Ensemble des prénoms normalisés.
        """
        return cls.load_words_set(file_path)

    @classmethod
    def load_locations_set(cls, file_path: str) -> Set[str]:
        """
        Charge un fichier de communes/lieux et retourne un ensemble normalisé.

        :param file_path: Chemin vers le fichier villes_masquees.txt.
        :return: Ensemble des noms de lieux normalisés.
        """
        return cls.load_words_set(file_path)

    @staticmethod
    def atomic_write_text(
        target_path: str, content: str, encoding: str = "utf-8"
    ) -> None:
        """
        Écrit un fichier texte de façon atomique via un fichier temporaire.

        :param target_path: Chemin du fichier cible.
        :param content: Contenu texte à écrire.
        :param encoding: Encodage cible (défaut : 'utf-8').
        """
        parent_dir: str = os.path.dirname(os.path.abspath(target_path))
        os.makedirs(parent_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=parent_dir, prefix=".tmp_shared_", suffix=".txt"
        )
        try:
            with os.fdopen(fd, "w", encoding=encoding, newline="\n") as f_out:
                f_out.write(content)
            os.replace(tmp_path, target_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Formate une durée en secondes sous forme lisible (ex: '1 h 05 min 12s').

        :param seconds: Durée écoulée en secondes.
        :return: Chaîne formatée.
        """
        total: float = max(0.0, seconds)
        if total < 60.0:
            return f"{total:.1f}s"
        mins: int = int(total // 60)
        rem_sec: int = int(round(total % 60.0))
        if rem_sec == 60:
            mins += 1
            rem_sec = 0
        if mins < 60:
            return f"{mins} min {rem_sec}s"
        hours: int = mins // 60
        rem_min: int = mins % 60
        return f"{hours} h {rem_min:02d} min {rem_sec}s"

    @classmethod
    def prevent_sleep(cls, enable: bool = True) -> None:
        """
        Empêche ou réautorise la mise en veille du système (Windows et Linux).

        :param enable: True pour inhiber la veille, False pour restaurer.
        """
        if os.name == "nt":
            es_continuous: int = 0x80000000
            es_system_required: int = 0x00000001
            es_awaymode_required: int = 0x00000040
            raw_flags: int = (
                (es_continuous | es_system_required | es_awaymode_required)
                if enable
                else es_continuous
            )
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(  # type: ignore[attr-defined]
                    ctypes.c_uint(raw_flags)
                )
            except Exception:
                pass
            return

        if enable:
            if cls._sleep_process is not None:
                return
            try:
                cls._sleep_process = subprocess.Popen(
                    [
                        "systemd-inhibit",
                        "--what=idle:sleep",
                        "--who=watch_clipboard",
                        "--why=Anonymisation documentaire en cours",
                        "sleep",
                        "infinity",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                cls._sleep_process = None
        else:
            if cls._sleep_process is not None:
                try:
                    cls._sleep_process.terminate()
                    cls._sleep_process.wait(timeout=2.0)
                except Exception:
                    pass
                cls._sleep_process = None
