# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import hmac
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse


class _StatusRequestHandler(BaseHTTPRequestHandler):
    """
    Gestionnaire HTTP répondant aux requêtes de statut, lecture de vérification,
    exécution des tests, export de projet et arrêt de l'extension Chrome.
    """

    target_dir: str = "."
    default_test_runner: str = "tools/run_tests_clip.py"
    api_token: str = ""
    allowed_origin: str = ""
    assembler_ref: Any = None

    def _is_authorized(self) -> bool:
        if not self.api_token:
            return True
        provided: str = self.headers.get("X-Watcher-Token", "")
        return hmac.compare_digest(provided, self.api_token)

    def _is_within_allowed_roots(self, candidate: str, roots: List[str]) -> bool:
        for root in roots:
            try:
                if os.path.commonpath([root, candidate]) == root and candidate != root:
                    return True
            except ValueError:
                continue
        return False

    def _read_saved_file_from_header(self, header: str) -> Tuple[bool, str, str]:
        clean_header: str = header.strip()
        if not clean_header:
            return False, "", "En-tête de fichier vide."

        base_real: str = os.path.realpath(self.target_dir)
        temp_dir_name: str = ".watch_clipboard"
        encoding: str = "utf-8"
        if self.assembler_ref is not None:
            base_real = os.path.realpath(getattr(self.assembler_ref, "base_dir", base_real))
            cfg = getattr(self.assembler_ref, "config", None)
            if cfg is not None:
                temp_dir_name = getattr(cfg, "temp_dir_name", temp_dir_name)
                encoding = getattr(cfg, "encoding", encoding)

        temp_real: str = os.path.realpath(os.path.join(base_real, temp_dir_name))

        if "|" in clean_header:
            rel_part, part_spec = [x.strip() for x in clean_header.split("|", 1)]
            rel_norm: str = rel_part.replace("\\", "/")
            if not rel_norm or rel_norm.startswith("/") or os.path.isabs(rel_norm):
                return False, "", "Chemin relatif non autorisé."
            num_str: str = part_spec.split("/", 1)[0].strip()
            if not num_str.isdigit() or int(num_str) < 1:
                return False, "", "Numéro de partie invalide."
            part_num: int = int(num_str)
            candidate: str = os.path.realpath(os.path.join(temp_real, f"{rel_norm}.part{part_num}"))
            if not self._is_within_allowed_roots(candidate, [temp_real]):
                return False, "", "Chemin cache hors périmètre autorisé."
            attach_name: str = f"{os.path.basename(rel_norm)}.part{part_num}.txt"
        else:
            rel_norm = clean_header.replace("\\", "/")
            if not rel_norm or rel_norm.startswith("/") or os.path.isabs(rel_norm):
                return False, "", "Chemin relatif non autorisé."
            candidate = os.path.realpath(os.path.join(base_real, rel_norm))
            if not self._is_within_allowed_roots(candidate, [base_real]):
                return False, "", "Chemin cible hors périmètre autorisé."
            attach_name = os.path.basename(rel_norm)

        if not os.path.isfile(candidate):
            return False, "", f"Fichier introuvable sur disque : {candidate}"

        with open(candidate, "r", encoding=encoding, errors="replace") as f_in:
            return True, attach_name, f_in.read()
    def _resolve_exporter_package_dir(self) -> Optional[str]:
        base_real: str = os.path.realpath(self.target_dir)
        parent_real: str = os.path.dirname(base_real)
        watcher_dir: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        watcher_parent: str = os.path.dirname(watcher_dir)
        candidates: List[str] = [
            os.path.join(base_real, "export"),
            os.path.join(base_real, "tools", "export"),
            os.path.join(parent_real, "export"),
            os.path.join(parent_real, "tools", "export"),
            os.path.join(watcher_parent, "export"),
        ]
        for cand in candidates:
            if os.path.isdir(os.path.join(cand, "project_exporter")):
                return cand
        return None

    def _run_project_export(self) -> Tuple[bool, str, str, int]:
        exporter_root: Optional[str] = self._resolve_exporter_package_dir()
        if not exporter_root:
            return False, "", "Package project_exporter introuvable dans le workspace.", 0

        target_real: str = os.path.realpath(self.target_dir)
        with tempfile.TemporaryDirectory(prefix="watch_clip_export_") as tmp_dir:
            code: str = (
                "import logging, sys; from pathlib import Path; "
                "from project_exporter.config import ExporterConfig; "
                "from project_exporter.exporter import ProjectExporter; "
                "logger = logging.getLogger('export'); logger.addHandler(logging.NullHandler()); "
                "_, exp_s, target_s, out_s = sys.argv; "
                "exp_root, target, out_dir = Path(exp_s), Path(target_s), Path(out_s); "
                "cfg = ExporterConfig(exp_root / 'config.ini', logger); "
                "fname = cfg.build_output_filename(target.name); "
                "out_file = out_dir / fname; "
                "cnt = ProjectExporter(target, cfg, out_file, exp_root / 'export_project.py', logger).export(); "
                "print(f'{fname}|{cnt}')"
            )
            env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONPATH": exporter_root}
            proc = subprocess.run(
                [sys.executable, "-c", code, exporter_root, target_real, tmp_dir],
                cwd=target_real,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
            if proc.returncode != 0:
                err_txt: str = (proc.stderr or proc.stdout or "Erreur export").strip()
                return False, "", err_txt, 0

            meta_line: str = (proc.stdout or "").strip().splitlines()[-1]
            fname_out, cnt_str = meta_line.split("|", 1)
            out_path: str = os.path.join(tmp_dir, fname_out)
            if not os.path.isfile(out_path):
                return False, "", "Fichier d'export non généré.", 0
            with open(out_path, "r", encoding="utf-8", errors="replace") as f_out:
                content: str = f_out.read()
            return True, fname_out, content, int(cnt_str)

    def _resolve_test_runner_path(self, custom_path: str = "") -> Optional[str]:
        raw_custom: str = custom_path.strip()
        is_custom: bool = bool(raw_custom) and raw_custom != self.default_test_runner
        rel_path: str = (raw_custom or self.default_test_runner).replace("\\", "/")
        if not rel_path or rel_path.startswith("/") or os.path.isabs(rel_path) or not rel_path.endswith(".py"):
            return None

        base_real: str = os.path.realpath(self.target_dir)
        parent_real: str = os.path.dirname(base_real)
        allowed_roots: List[str] = [base_real]
        if parent_real and parent_real != base_real:
            allowed_roots.append(parent_real)

        direct_candidate: str = os.path.realpath(os.path.join(base_real, rel_path))
        if not self._is_within_allowed_roots(direct_candidate, allowed_roots):
            return None
        if os.path.isfile(direct_candidate):
            return direct_candidate

        if is_custom:
            if parent_real and parent_real != base_real:
                parent_cand: str = os.path.realpath(os.path.join(parent_real, rel_path))
                if self._is_within_allowed_roots(parent_cand, allowed_roots) and os.path.isfile(parent_cand):
                    return parent_cand
            return None

        search_bases: List[str] = [base_real, os.path.join(base_real, "watch_clipboard")]
        if parent_real and parent_real != base_real:
            search_bases.append(parent_real)

        for search_dir in search_bases:
            candidate: str = os.path.realpath(os.path.join(search_dir, rel_path))
            if self._is_within_allowed_roots(candidate, allowed_roots) and os.path.isfile(candidate):
                return candidate
        return None
    def _send_cors_headers(self) -> None:
        origin: str = self.headers.get("Origin", "")
        allow_val: str = self.allowed_origin or (origin if origin.startswith("chrome-extension://") else "null")
        self.send_header("Access-Control-Allow-Origin", allow_val)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Watcher-Token")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _send_json(self, status_code: int, data: dict) -> None:
        payload: bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if not self._is_authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if parsed.path == "/read-file":
            header_val: str = next(iter(params.get("header", [])), "")
            ok, filename, content_or_err = self._read_saved_file_from_header(header_val)
            if not ok:
                self._send_json(404, {"ok": False, "error": content_or_err})
                return
            self._send_json(200, {"ok": True, "filename": filename, "content": content_or_err})
            return
        if parsed.path not in ("/status", "/health", "/"):
            self._send_json(404, {"error": "not_found"})
            return
        custom_runner: str = next(iter(params.get("test_runner", [])), "")
        abs_target: str = os.path.abspath(self.target_dir)
        test_script: Optional[str] = self._resolve_test_runner_path(custom_runner)
        has_tests: bool = bool(test_script and os.path.isfile(test_script))
        has_exporter: bool = self._resolve_exporter_package_dir() is not None
        cmdline: str = " ".join(shlex.quote(arg) for arg in [sys.executable, *sys.argv])
        last_event: Optional[str] = getattr(self.assembler_ref, "last_event", None)
        self._send_json(200, {
            "status": "running", "service": "watch_clipboard", "pid": os.getpid(),
            "target_dir": abs_target, "command": cmdline, "has_run_tests_clip": has_tests,
            "has_exporter": has_exporter, "configured_test_runner": custom_runner or self.default_test_runner,
            "test_runner_path": test_script if has_tests else None, "last_event": last_event,
        })

    def _execute_tests_streaming(self, test_script: str) -> Tuple[int, str]:
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        is_clip_runner: bool = os.path.basename(test_script) == "run_tests_clip.py"
        with tempfile.TemporaryDirectory(prefix="watch_clip_tests_") as tmp_dir:
            report_path: str = os.path.join(tmp_dir, "compact_report.txt")
            cmd: List[str] = [sys.executable, "-u", test_script]
            if is_clip_runner:
                cmd.extend(["--no-clipboard", "--report-file", report_path])

            proc = subprocess.Popen(
                cmd,
                cwd=os.path.abspath(self.target_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            timed_out: List[bool] = []

            def _kill_on_timeout() -> None:
                timed_out.append(True)
                try:
                    proc.kill()
                except OSError:
                    pass

            watchdog = threading.Timer(180.0, _kill_on_timeout)
            watchdog.daemon = True
            watchdog.start()
            live_lines: List[str] = []
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    live_lines.append(line)
                rc: int = proc.wait(timeout=10)
            finally:
                watchdog.cancel()
            if timed_out:
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=180)
            if is_clip_runner and os.path.isfile(report_path):
                with open(report_path, "r", encoding="utf-8", errors="replace") as f_rep:
                    compact_out: str = f_rep.read().strip()
            else:
                compact_out = "".join(live_lines).strip()

            clean_out: str = re.sub(r"^\[PRESSE-PAPIERS\].*$", "", compact_out, flags=re.MULTILINE).strip()
            return rc, clean_out

    def do_POST(self) -> None:
        if not self._is_authorized():
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return
        parsed = urlparse(self.path)
        if parsed.path == "/shutdown":
            self._send_json(200, {"status": "stopping", "pid": os.getpid()})
            threading.Timer(0.15, lambda: os.kill(os.getpid(), signal.SIGINT)).start()
            return
        if parsed.path == "/export-project":
            ok, filename, payload_or_err, count = self._run_project_export()
            if not ok:
                self._send_json(500, {"ok": False, "error": payload_or_err})
                return
            self._send_json(200, {"ok": True, "filename": filename, "content": payload_or_err, "file_count": count})
            return
        if parsed.path == "/run-tests":
            custom_runner: str = ""
            content_len: int = int(self.headers.get("Content-Length", "0") or "0")
            if content_len > 0:
                try:
                    body = json.loads(self.rfile.read(content_len).decode("utf-8"))
                    if isinstance(body, dict):
                        custom_runner = str(body.get("test_runner", "")).strip()
                except Exception:
                    pass
            test_script: Optional[str] = self._resolve_test_runner_path(custom_runner)
            if test_script is None:
                self._send_json(403, {"ok": False, "error": "Chemin du lanceur de tests non autorisé."})
                return
            if not os.path.isfile(test_script):
                self._send_json(404, {"ok": False, "error": f"Lanceur introuvable : {test_script}"})
                return
            try:
                rc, clean_out = self._execute_tests_streaming(test_script)
                has_warnings: bool = bool(re.search(r"(?:WARNINGS DÉTECTÉS|ResourceWarning|DeprecationWarning|UserWarning|RuntimeWarning)", clean_out))
                self._send_json(200, {"ok": True, "passed": rc == 0 and not has_warnings, "returncode": rc, "output": clean_out})
            except subprocess.TimeoutExpired:
                self._send_json(504, {"ok": False, "error": "Délai dépassé (180s) pendant les tests."})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return
        self._send_json(404, {"error": "not_found"})

    def log_message(self, format: str, *args: object) -> None:
        return


class StatusServer:
    """Serveur HTTP léger exécuté dans un thread démon."""

    def __init__(self, host: str, port: int, target_dir: str, test_runner_path: str = "tools/run_tests_clip.py", api_token: str = "", allowed_origin: str = "", assembler: Any = None) -> None:
        self.host, self.port, self.target_dir = host, port, target_dir
        self.test_runner_path, self.api_token, self.allowed_origin, self.assembler = test_runner_path, api_token, allowed_origin, assembler
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        handler_cls = type("BoundStatusHandler", (_StatusRequestHandler,), {
            "target_dir": self.target_dir, "default_test_runner": self.test_runner_path,
            "api_token": self.api_token, "allowed_origin": self.allowed_origin, "assembler_ref": self.assembler,
        })
        try:
            self._httpd = ThreadingHTTPServer((self.host, self.port), handler_cls)
        except OSError as exc:
            print(f"[AVERTISSEMENT] Serveur de statut impossible sur {self.host}:{self.port} ({exc})")
            return False
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        print(f"API de statut active : http://{self.host}:{self.port}/status")
        return True

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
