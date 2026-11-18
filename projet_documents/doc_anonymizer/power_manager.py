# Commandes pip à exécuter : Aucune dépendance externe requise

import ctypes
import os
import shutil
import subprocess
import sys
from typing import Any, Optional, Type


class SystemSleepInhibitor:
    """
    Gestionnaire de contexte multiplateforme empêchant la mise en veille
    ou l'extinction automatique sous Windows (SetThreadExecutionState)
    et sous Linux (systemd-inhibit) pendant un traitement long.
    """

    ES_CONTINUOUS: int = 0x80000000
    ES_SYSTEM_REQUIRED: int = 0x00000001

    def __init__(self, enabled: bool = True) -> None:
        """
        Initialise le contrôleur d'alimentation multiplateforme.

        :param enabled: Active ou désactive le blocage de la mise en veille.
        """
        self.enabled: bool = enabled
        self._win_active: bool = False
        self._linux_proc: Optional[subprocess.Popen[bytes]] = None

    def _enable_windows(self) -> None:
        """
        Active le maintien en éveil sous Windows via kernel32.
        """
        try:
            flags: int = self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED
            res: int = ctypes.windll.kernel32.SetThreadExecutionState(flags)  # type: ignore[attr-defined]
            self._win_active = res != 0
            if self._win_active:
                print(
                    "[ALIMENTATION] Mise en veille Windows désactivée "
                    "pendant le traitement.",
                    flush=True,
                )
        except Exception as exc:
            print(
                f"[AVERTISSEMENT] Blocage mise en veille Windows : {exc}",
                flush=True,
            )

    def _enable_linux(self) -> None:
        """
        Active le maintien en éveil sous Linux via systemd-inhibit.
        """
        inhibit_bin: Optional[str] = shutil.which("systemd-inhibit")
        if not inhibit_bin:
            return
        try:
            self._linux_proc = subprocess.Popen(
                [
                    inhibit_bin,
                    "--what=idle:sleep",
                    "--who=doc_anonymizer",
                    "--why=Transcription et anonymisation en cours",
                    "--mode=block",
                    "sleep",
                    "infinity",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(
                "[ALIMENTATION] Mise en veille Linux bloquée "
                "(systemd-inhibit).",
                flush=True,
            )
        except Exception as exc:
            self._linux_proc = None
            print(
                f"[AVERTISSEMENT] Blocage mise en veille Linux : {exc}",
                flush=True,
            )

    def __enter__(self) -> "SystemSleepInhibitor":
        """
        Active le maintien en éveil selon le système d'exploitation.

        :return: Instance courante de SystemSleepInhibitor.
        """
        if not self.enabled:
            return self
        if os.name == "nt":
            self._enable_windows()
        elif sys.platform.startswith("linux"):
            self._enable_linux()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """
        Restaure les paramètres normaux d'alimentation à la sortie du bloc.
        """
        if self._win_active:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(  # type: ignore[attr-defined]
                    self.ES_CONTINUOUS
                )
                print(
                    "[ALIMENTATION] Paramètres de mise en veille "
                    "Windows restaurés.",
                    flush=True,
                )
            except Exception:
                pass
            self._win_active = False

        if self._linux_proc is not None:
            try:
                self._linux_proc.terminate()
                self._linux_proc.wait(timeout=3)
                print(
                    "[ALIMENTATION] Verrou systemd-inhibit Linux libéré.",
                    flush=True,
                )
            except Exception:
                try:
                    self._linux_proc.kill()
                except Exception:
                    pass
            self._linux_proc = None
