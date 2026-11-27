# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Utilisateur_A

import os
import tempfile
import unittest
from unittest.mock import patch
from doc_anonymizer.duplicate_files_manager import DuplicateFilesManager
from doc_anonymizer.linked_sources_manager import LinkedSourcesManager


class TestLinkedAndDuplicates(unittest.TestCase):
    """Vérifie la fusion parent/enfant des liens et le tri des doublons par typologie."""

    def test_add_links_merges_child_files_and_supports_remove_and_copy(self) -> None:
        """Couvre fusion parent/enfant, suppression de lien, copie locale et support UNC."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_dir: str = os.path.join(tmp_dir, "workspace")
            ext_dir: str = os.path.join(tmp_dir, "dossier_pieces")
            sub_dir: str = os.path.join(ext_dir, "sous_dossier")
            dest_copy: str = os.path.join(ws_dir, "input_documents")
            os.makedirs(sub_dir, exist_ok=True)
            file_a: str = os.path.join(ext_dir, "piece_a.txt")
            file_b: str = os.path.join(sub_dir, "piece_b.txt")
            with open(file_a, "w", encoding="utf-8") as f_a:
                f_a.write("contenu A\n")
            with open(file_b, "w", encoding="utf-8") as f_b:
                f_b.write("contenu B\n")

            mgr = LinkedSourcesManager(ws_dir)
            self.assertEqual(mgr.add_links([file_a, file_b]), 2)
            self.assertEqual(len(mgr.load_links()), 2)

            self.assertEqual(mgr.add_links([ext_dir]), 1)
            links = mgr.load_links()
            self.assertEqual(len(links), 1)
            first_link = next(iter(links))
            self.assertEqual(first_link["kind"], "dir")
            self.assertEqual(first_link["path"], os.path.normpath(os.path.abspath(ext_dir)))

            self.assertEqual(mgr.add_links([file_a, file_b]), 0)
            self.assertEqual(LinkedSourcesManager.copy_paths_into_directory([file_a, sub_dir], dest_copy), 2)
            self.assertTrue(os.path.isfile(os.path.join(dest_copy, "piece_a.txt")))

            self.assertTrue(mgr.remove_link(ext_dir))
            self.assertFalse(mgr.remove_link(ext_dir))
            is_ext, lbl = LinkedSourcesManager.classify_storage_location("//SERVEUR/Partage/Docs")
            self.assertTrue(is_ext)
            self.assertIn("SERVEUR", lbl)

    def test_duplicates_partitioned_by_extension_and_size_with_sha_cache(self) -> None:
        """Deux fichiers de même taille mais d'extensions différentes ne sont jamais hachés."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_dir: str = os.path.join(tmp_dir, "workspace")
            docs_dir: str = os.path.join(ws_dir, "input_documents")
            os.makedirs(docs_dir, exist_ok=True)

            json_file: str = os.path.join(docs_dir, "chat_export.json")
            img_file: str = os.path.join(docs_dir, "capture_ecran.png")
            dup_json: str = os.path.join(docs_dir, "copie_chat.json")
            payload: bytes = b"0123456789ABCDEF" * 4

            for target_p in (json_file, img_file, dup_json):
                with open(target_p, "wb") as f_out:
                    f_out.write(payload)

            mgr = DuplicateFilesManager({"workspace_root": ws_dir, "sources_dir": docs_dir})
            hashed_paths: list[str] = []
            orig_sha = DuplicateFilesManager.compute_sha256

            def _spy_sha(path: str, chunk_size: int = 65536) -> str:
                hashed_paths.append(os.path.basename(path))
                return orig_sha(path, chunk_size)

            with patch.object(DuplicateFilesManager, "compute_sha256", side_effect=_spy_sha):
                dups = mgr.find_duplicate_items()
                self.assertNotIn("capture_ecran.png", hashed_paths)
                self.assertEqual(len(dups), 2)

                hashed_paths.clear()
                dups_cached = mgr.find_duplicate_items()
                self.assertEqual(hashed_paths, [])
                self.assertEqual(len(dups_cached), 2)
