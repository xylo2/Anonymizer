# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Utilisateur_A

import os
import shutil
import tempfile
import threading
import time
import unittest
from doc_anonymizer.gui_controller import AnonymizerGuiController
from doc_anonymizer.gui_ingest_mixin import GuiIngestMixin
from doc_anonymizer.workflow_navigator import WorkflowNavigator


class _DummyIngestApp(GuiIngestMixin):
    """Doublure légère de l'application GUI pour tester GuiIngestMixin."""

    def __init__(self, root_dir: str, ini_path: str) -> None:
        """Initialise la doublure minimale avec le contrôleur et l'état."""
        self.controller = AnonymizerGuiController(root_dir)
        self.current_ini_var = type(
            "Var", (), {"get": lambda _s: ini_path, "set": lambda _s, _v: None}
        )()
        self.status_var = type(
            "Var", (),
            {"_v": "", "get": lambda s: s._v, "set": lambda s, v: setattr(s, "_v", v)},
        )()
        self.active_page_key: str = "documents"
        self.duplicate_filter_items: list = []

    def _refresh_workspace_counters(self) -> None:
        """Simule le rafraîchissement des compteurs."""
        return None

    def _refresh_contact_filter_list(self) -> None:
        """Simule le rafraîchissement de la liste des contacts."""
        return None

    def _refresh_sms_number_list(self) -> None:
        """Simule le rafraîchissement de la liste des SMS."""
        return None

    def _refresh_chat_filter_list(self) -> None:
        """Simule le rafraîchissement de la liste des chats."""
        return None

    def _show_page(self, key: str) -> None:
        """Mémorise la page active."""
        self.active_page_key = key


class TestWorkflowNavigationAndPrewarm(unittest.TestCase):
    """Couvre WorkflowNavigator et le passage non bloquant de l'étape 1."""

    def setUp(self) -> None:
        """Prépare un répertoire temporaire avec les dictionnaires de base."""
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_wf_nav_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in (
            "mots_exclus.txt", "prenoms.txt",
            "collisions_noms.txt", "villes_masquees.txt",
        ):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")

    def tearDown(self) -> None:
        """Nettoie le répertoire temporaire."""
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_workflow_navigator_signature_and_background_scan(self) -> None:
        """Vérifie has_any_source, trigger_background_scan et get_cached_summary."""
        ws_dir: str = os.path.join(self.tmp_root, "ws_nav")
        docs_dir: str = os.path.join(ws_dir, "input_documents")
        os.makedirs(docs_dir, exist_ok=True)

        nav = WorkflowNavigator(ws_dir, docs_dir, ignored_dirs={"audits"})
        self.assertFalse(nav.has_any_source())

        p1: str = os.path.join(docs_dir, "piece_1.txt")
        with open(p1, "w", encoding="utf-8") as f_1:
            f_1.write("Contenu test\n")
        self.assertTrue(nav.has_any_source())

        done_evt = threading.Event()
        summaries: list[dict] = []
        started: bool = nav.trigger_background_scan(
            on_complete=lambda s: (summaries.append(s), done_evt.set())
        )
        self.assertTrue(started)
        self.assertTrue(done_evt.wait(timeout=3.0))
        self.assertEqual(len(summaries), 1)
        first_summary = next(iter(summaries))
        self.assertEqual(
            first_summary["active_steps"],
            ["documents", "filters_hub", "preview_export"],
        )

        hit_evt = threading.Event()
        self.assertFalse(nav.trigger_background_scan(on_complete=lambda _s: hit_evt.set()))
        self.assertTrue(hit_evt.is_set())

    def test_gui_advance_from_documents_does_not_block_when_prewarm_in_flight(self) -> None:
        """Vérifie que _advance_from_documents ouvre setup sans bloquer."""
        ctrl = AnonymizerGuiController(self.tmp_root)
        ini_path: str = ctrl.create_workspace("Affaire_Non_Bloquante")
        app = _DummyIngestApp(self.tmp_root, ini_path)

        release_evt = threading.Event()
        slow_thread = threading.Thread(
            target=lambda: release_evt.wait(timeout=2.0), daemon=True
        )
        slow_thread.start()
        app._prewarm_thread = slow_thread  # type: ignore[attr-defined]
        app._prewarm_cache_result = None  # type: ignore[attr-defined]

        try:
            t_start: float = time.perf_counter()
            app._advance_from_documents()
            elapsed: float = time.perf_counter() - t_start

            self.assertLess(elapsed, 0.2)
            self.assertEqual(app.active_page_key, "setup")
            app._on_background_prewarm_finished()
        finally:
            release_evt.set()
