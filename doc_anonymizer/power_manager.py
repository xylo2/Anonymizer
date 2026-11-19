# Commandes pip à exécuter : Aucune dépendance externe requise

from __future__ import annotations
import ctypes
import os
import shutil
import subprocess
import sys
import threading
from typing import Any, Optional, Type


class SystemSleepInhibitor:
    """
    Gestionnaire de contexte multiplateforme empêchant la mise en veille
    ou l'extinction automatique sous Windows (SetThreadExecutionState avec
    rafraîchissement périodique et AwayMode) et sous Linux (systemd-inhibit).
    """

    ES_CONTINUOUS: int = 0x80000000
    ES_SYSTEM_REQUIRED: int = 0x00000001
    ES_AWAYMODE_REQUIRED: int = 0x00000040

    def __init__(self, enabled: bool = True, refresh_interval: float = 30.0) -> None:
        """
        Initialise le contrôleur d'alimentation multiplateforme.

        :param enabled: Active ou désactive le blocage de la mise en veille.
        :param refresh_interval: Intervalle en secondes de renouvellement Windows.
        """
        self.enabled: bool = enabled
        self.refresh_interval: float = refresh_interval
        self._win_active: bool = False
        self._stop_heartbeat: threading.Event = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._linux_proc: Optional[subprocess.Popen[bytes]] = None

    def _apply_windows_state(self) -> int:
        """
        Applique les drapeaux d'éveil Windows sur le thread courant.

        :return: État précédent retourné par l'API Win32 (0 en cas d'échec).
        """
        flags: ctypes.c_uint = ctypes.c_uint(
            self.ES_CONTINUOUS
            | self.ES_SYSTEM_REQUIRED
            | self.ES_AWAYMODE_REQUIRED
        )
        res: int = ctypes.windll.kernel32.SetThreadExecutionState(flags)  # type: ignore[attr-defined]
        if res == 0:
            fallback: ctypes.c_uint = ctypes.c_uint(
                self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED
            )
            res = ctypes.windll.kernel32.SetThreadExecutionState(fallback)  # type: ignore[attr-defined]
        return res

    def _windows_heartbeat_loop(self) -> None:
        """
        Renouvelle périodiquement l'état d'éveil sur un thread dédié afin
        d'empêcher Windows Modern Standby de suspendre le processus.
        """
        while not self._stop_heartbeat.is_set():
            try:
                self._apply_windows_state()
            except Exception:
                pass
            self._stop_heartbeat.wait(self.refresh_interval)
    def _enable_windows(self) -> None:
        """
        Active le maintien en éveil sous Windows et démarre le thread de maintien.
        """
        try:
            res: int = self._apply_windows_state()
            self._win_active = res != 0
            if self._win_active:
                self._stop_heartbeat.clear()
                self._heartbeat_thread = threading.Thread(
                    target=self._windows_heartbeat_loop,
                    name="windows-sleep-inhibitor",
                    daemon=True,
                )
                self._heartbeat_thread.start()
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

    def __enter__(self) -> SystemSleepInhibitor:
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
            self._stop_heartbeat.set()
            if self._heartbeat_thread is not None:
                self._heartbeat_thread.join(timeout=1.5)
                self._heartbeat_thread = None
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(  # type: ignore[attr-defined]
                    ctypes.c_uint(self.ES_CONTINUOUS)
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
