# Commandes pip à exécuter : Aucune dépendance externe requise

import re
import time
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional, Tuple
from doc_anonymizer.contact_csv_importer import normalize_phone_identifier


class TreeviewTableHelper:
    """Fournit la protection trackpad (anti-clic lors du scroll/glisser) et le formatage lisible des tableaux."""

    @staticmethod
    def format_phone_display(raw_phone: str) -> str:
        """Formate un numéro FR en paires lisibles (ex: 0612345678 -> 06 12 34 56 78)."""
        norm: str = normalize_phone_identifier(raw_phone)
        if len(norm) == 10 and norm.startswith("0") and norm.isdigit():
            return " ".join(norm[i : i + 2] for i in range(0, 10, 2))
        return norm

    @classmethod
    def split_contact_identifiers(cls, identifiers: List[str]) -> Tuple[str, str]:
        """Sépare proprement numéros de téléphone (sans libellés ni doublons) et adresses e-mail."""
        phones: List[str] = []
        emails: List[str] = []
        seen_norms: set[str] = set()
        for raw_id in identifiers:
            clean_id: str = str(raw_id).lstrip("* ").strip()
            if not clean_id:
                continue
            if "@" in clean_id:
                low_m: str = clean_id.lower()
                if low_m not in seen_norms:
                    seen_norms.add(low_m)
                    emails.append(clean_id)
            else:
                norm_p: str = normalize_phone_identifier(clean_id)
                if not norm_p or not any(ch.isdigit() for ch in norm_p):
                    continue
                if norm_p not in seen_norms:
                    seen_norms.add(norm_p)
                    phones.append(cls.format_phone_display(norm_p))
        return "  •  ".join(phones), "  •  ".join(emails)

    @staticmethod
    def bind_trackpad_safe_toggle(tree: ttk.Treeview, on_toggle_row: Callable[[str], None]) -> None:
        """Empêche toute sélection/désélection involontaire pendant un défilement trackpad ou un glisser."""
        state: Dict[str, Any] = {"last_scroll": 0.0, "press_xy": None, "dragged": False}

        def _on_scroll(_event: Any = None) -> None:
            state["last_scroll"] = time.monotonic()

        def _on_press(event: Any) -> None:
            state["press_xy"] = (event.x, event.y)
            state["dragged"] = False

        def _on_motion(event: Any) -> None:
            px_py = state.get("press_xy")
            if px_py is not None:
                px, py = px_py
                if abs(event.x - px) > 4 or abs(event.y - py) > 4:
                    state["dragged"] = True

        def _on_release(event: Any) -> None:
            if tree.identify_region(event.x, event.y) == "heading":
                return
            if state.get("dragged"):
                state["dragged"] = False
                return
            if (time.monotonic() - float(state.get("last_scroll", 0.0))) < 0.25:
                return
            row_id: str = tree.identify_row(event.y)
            if row_id:
                on_toggle_row(row_id)

        tree.bind("<MouseWheel>", _on_scroll, add="+")
        tree.bind("<Button-4>", _on_scroll, add="+")
        tree.bind("<Button-5>", _on_scroll, add="+")
        tree.bind("<ButtonPress-1>", _on_press, add="+")
        tree.bind("<B1-Motion>", _on_motion, add="+")
        tree.bind("<ButtonRelease-1>", _on_release, add="+")
