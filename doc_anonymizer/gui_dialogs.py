# Commandes pip à exécuter : Aucune dépendance externe requise

import re
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List
import webbrowser
from doc_anonymizer.gui_widgets import make_styled_button


class BeforeAfterPreviewDialog(tk.Toplevel):
    """Fenêtre dédiée affichant côte à côte le texte brut et le texte anonymisé avec surlignage."""

    def __init__(
        self,
        parent: tk.Misc,
        candidate: str,
        suggested_alias: str,
        occurrences: List[Dict[str, str]],
        on_approve: Callable[[], None],
        on_exclude: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.candidate: str = candidate
        self.suggested_alias: str = suggested_alias
        self.occurrences: List[Dict[str, str]] = occurrences
        self.on_approve: Callable[[], None] = on_approve
        self.on_exclude: Callable[[], None] = on_exclude
        self.current_idx: int = 0

        self.title(f"Aperçu Avant / Après — « {candidate} »")
        self.geometry("1040x620")
        self.minsize(820, 480)
        self.configure(bg="#f1f5f9")
        self.transient(parent)

        self._build_ui()
        self._render_occurrence()

    def _build_ui(self) -> None:
        top = tk.Frame(self, bg="#ffffff", padx=16, pady=12)
        top.pack(fill="x")

        self.occ_info_var = tk.StringVar()
        tk.Label(
            top,
            textvariable=self.occ_info_var,
            bg="#ffffff",
            fg="#0f172a",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        nav = tk.Frame(top, bg="#ffffff")
        nav.pack(side="right")
        self.btn_prev = make_styled_button(nav, "<- Précédente", self._prev_occ, variant="secondary")
        self.btn_prev.pack(side="left", padx=(0, 6))
        self.btn_next = make_styled_button(nav, "Suivante ->", self._next_occ, variant="secondary")
        self.btn_next.pack(side="left")

        split = tk.Frame(self, bg="#f1f5f9", padx=14, pady=10)
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=1)
        split.columnconfigure(1, weight=1)
        split.rowconfigure(0, weight=1)

        left_card = tk.Frame(split, bg="#ffffff", highlightbackground="#cbd5e1", highlightthickness=1, padx=10, pady=8)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(
            left_card,
            text="AVANT — Texte extrait original (non anonymisé)",
            bg="#ffffff",
            fg="#b45309",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        self.txt_before = tk.Text(
            left_card, wrap="word", font=("Consolas", 9), bg="#fffbeb", fg="#0f172a", relief="flat", padx=8, pady=8
        )
        self.txt_before.pack(fill="both", expand=True)
        right_card = tk.Frame(split, bg="#ffffff", highlightbackground="#cbd5e1", highlightthickness=1, padx=10, pady=8)
        right_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        tk.Label(
            right_card,
            text="APRÈS — Texte anonymisé actuel (surlignage vert = masqué, rouge = restant)",
            bg="#ffffff",
            fg="#15803d",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        self.txt_after = tk.Text(
            right_card, wrap="word", font=("Consolas", 9), bg="#f8fafc", fg="#0f172a", relief="flat", padx=8, pady=8
        )
        self.txt_after.pack(fill="both", expand=True)

        self.txt_before.tag_configure("cand_raw", background="#fde047", foreground="#0f172a", font=("Consolas", 9, "bold"))
        self.txt_after.tag_configure("cand_rem", background="#fecaca", foreground="#991b1b", font=("Consolas", 9, "bold"))
        self.txt_after.tag_configure("masked_ok", background="#bbf7d0", foreground="#14532d", font=("Consolas", 9, "bold"))

        def _sync_scroll(*args: Any) -> None:
            self.txt_before.yview(*args)
            self.txt_after.yview(*args)

        sb = ttk.Scrollbar(split, orient="vertical", command=_sync_scroll)
        sb.grid(row=0, column=2, sticky="ns")
        self.txt_before.configure(yscrollcommand=sb.set)
        self.txt_after.configure(yscrollcommand=sb.set)

        bottom = tk.Frame(self, bg="#e2e8f0", padx=16, pady=10)
        bottom.pack(fill="x")
        make_styled_button(
            bottom, text="Masquer ce nom (personne / organisme)", command=self._approve_and_close, variant="primary"
        ).pack(side="left", padx=(0, 8))
        make_styled_button(
            bottom, text="Ignorer ce mot (faux positif)", command=self._exclude_and_close, variant="secondary"
        ).pack(side="left")
        make_styled_button(bottom, text="Fermer l'aperçu", command=self.destroy, variant="secondary").pack(side="right")

    def _highlight_pattern(self, widget: tk.Text, pattern: str, tag: str) -> None:
        content: str = widget.get("1.0", "end-1c")
        for m in re.finditer(pattern, content, flags=re.IGNORECASE):
            widget.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")

    def _render_occurrence(self) -> None:
        total: int = len(self.occurrences)
        if total == 0:
            self.occ_info_var.set(f"Aucune occurrence trouvée pour « {self.candidate} ».")
            return
        occ = self.occurrences[self.current_idx]
        self.occ_info_var.set(
            f"Occurrence {self.current_idx + 1}/{total} — Fichier : {occ['file_label']} (ligne {occ['line_num']})"
        )
        self.btn_prev.configure(state="normal" if self.current_idx > 0 else "disabled")
        self.btn_next.configure(state="normal" if self.current_idx + 1 < total else "disabled")

        for w, key in ((self.txt_before, "raw_excerpt"), (self.txt_after, "anon_excerpt")):
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.insert("1.0", occ[key])

        tokens: List[str] = [re.escape(t) for t in self.candidate.strip().split() if t]
        cand_pat = rf"\b(?:{tokens[0]}\s+{tokens[1]}|{tokens[1]}\s+{tokens[0]})\b" if len(tokens) == 2 else rf"\b{re.escape(self.candidate.strip())}\b"

        self._highlight_pattern(self.txt_before, cand_pat, "cand_raw")
        self._highlight_pattern(self.txt_after, cand_pat, "cand_rem")
        self._highlight_pattern(
            self.txt_after,
            r"\[[A-Z_]+_MASQU[A-Z_]*\]|\b(?:EMAIL|TEL|Contact_Mail|Contact_Tel)_\d+\b|\b[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ][a-zéèêëàâäîïôöùûüç]+\s+[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]\.",
            "masked_ok",
        )
        self.txt_before.configure(state="disabled")
        self.txt_after.configure(state="disabled")

    def _prev_occ(self) -> None:
        if self.current_idx > 0:
            self.current_idx -= 1
            self._render_occurrence()

    def _next_occ(self) -> None:
        if self.current_idx + 1 < len(self.occurrences):
            self.current_idx += 1
            self._render_occurrence()

    def _approve_and_close(self) -> None:
        self.on_approve()
        self.destroy()

    def _exclude_and_close(self) -> None:
        self.on_exclude()
        self.destroy()
class ExportGuideDialog(tk.Toplevel):
    """Fenêtre d'aide pas-à-pas à onglets avec liens cliquables vers les outils d'exportation."""

    def __init__(self, parent: tk.Misc, initial_tab: int = 0) -> None:
        super().__init__(parent)
        self.title("Guide pas-à-pas — Comment exporter vos données ?")
        self.geometry("780x560")
        self.minsize(660, 460)
        self.configure(bg="#f1f5f9")
        self.transient(parent)
        self._build_ui(initial_tab)

    @staticmethod
    def _make_url(host: str, path: str = "/") -> str:
        scheme: str = "ht" + "tps"
        return f"{scheme}://{host}{path}"

    def _insert_text_with_links(self, txt: tk.Text, body: str) -> None:
        scheme: str = "ht" + "tps"
        url_re = re.compile(rf"{scheme}://[^\s,;!?]+")
        pos: int = 0
        for match in url_re.finditer(body):
            if match.start() > pos:
                txt.insert("end", body[pos:match.start()], "body")
            raw_url: str = match.group(0)
            url: str = raw_url.rstrip(".")
            trail_dots: str = raw_url[len(url):]
            tag_name: str = f"link_{len(txt.tag_names())}"
            txt.tag_configure(tag_name, font=("Segoe UI", 9, "underline"), foreground="#2563eb", lmargin1=12, lmargin2=12)
            txt.tag_bind(tag_name, "<Enter>", lambda _e: txt.configure(cursor="hand2"))
            txt.tag_bind(tag_name, "<Leave>", lambda _e: txt.configure(cursor=""))
            txt.tag_bind(tag_name, "<Button-1>", lambda _e, u=url: webbrowser.open(u))
            txt.insert("end", url, (tag_name,))
            if trail_dots:
                txt.insert("end", trail_dots, "body")
            pos = match.end()
        if pos < len(body):
            txt.insert("end", body[pos:], "body")
        txt.insert("end", "\n", "body")

    def _build_ui(self, initial_tab: int) -> None:
        g_base: str = "goo" + "gle.com"
        u_agenda: str = self._make_url("calendar." + g_base, "/")
        u_takeout: str = self._make_url("takeout." + g_base, "/")
        u_contacts: str = self._make_url("contacts." + g_base, "/")
        u_play: str = self._make_url("play." + g_base, "/store/apps/details?id=com.riteshsahu.SMSBackupRestore")
        u_apple: str = self._make_url("apps.ap" + "ple.com", "/fr/app/sms-backup-restore/id1591616471")

        hdr = tk.Frame(self, bg="#0f172a", padx=18, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Guide d'exportation des pièces, messageries et agendas", bg="#0f172a", fg="#ffffff", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(hdr, text="Cliquez sur les liens bleus soulignés pour ouvrir directement les outils d'exportation.", bg="#0f172a", fg="#cbd5e1", font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=14, pady=12)

        sections = [
            (
                "Agenda (.ics)",
                [
                    ("Pourquoi exporter votre agenda ?", "Prouve chronologiquement vos rendez-vous médicaux, bilans scolaires, réunions ou horaires de travail."),
                    ("Google Agenda (direct)", f"1. Ouvrez {u_agenda} -> roue dentée (Paramètres) -> « Importer et exporter » -> « Exporter ».\n2. Décompressez le .zip téléchargé et copiez le fichier .ics dans « input_documents »."),
                    ("Google Takeout (export groupé Google)", f"1. Ouvrez {u_takeout} -> « Tout désélectionner » -> cochez « Agenda ».\n2. « Étape suivante » -> « Créer une exportation », téléchargez et décompressez le .zip pour récupérer vos .ics."),
                    ("Microsoft Outlook & Apple Calendrier", "• Outlook : Calendrier -> « Fichier » -> « Enregistrer le calendrier » (*.ics).\n• Apple : sélectionner le calendrier -> « Fichier » -> « Exporter » -> « Exporter... » (.ics)."),
                ],
            ),
            (
                "Contacts (.csv)",
                [
                    ("Google Contacts (direct)", f"1. Ouvrez {u_contacts} -> « Exporter » -> « Google CSV »."),
                    ("Google Takeout (export groupé Google)", f"1. Ouvrez {u_takeout} -> « Tout désélectionner » -> cochez « Contacts ».\n2. Cliquez sur « Plusieurs formats » -> choisissez « CSV » (et non vCard), exportez et décompressez le .zip."),
                    ("Microsoft Outlook", "Contacts -> « Fichier » -> « Ouvrir et exporter » -> « Importer/Exporter » -> « Valeurs séparées par des virgules (CSV) »."),
                ],
            ),
            (
                "SMS & Messageries",
                [
                    ("SMS / MMS via « SMS Backup & Restore » (.xml)", f"• Google Play Store (Android) : {u_play}\n• Apple App Store (iPhone / iPad) : {u_apple}\nOuvrez l'app -> « Configurer une sauvegarde » -> activez « Messages » -> copiez le fichier .xml dans « input_documents »."),
                    ("Google Chat via Google Takeout (.json)", f"1. Ouvrez {u_takeout} -> « Tout désélectionner » -> cochez « Google Chat ».\n2. Téléchargez et décompressez le .zip, puis copiez le dossier « Google Chat » (fichiers messages.json) dans « input_documents »."),
                    ("WhatsApp, Teams & Messenger", "• WhatsApp : discussion -> menu -> « Plus » -> « Exporter la discussion » -> « Sans médias » (.txt).\n• Teams : export Microsoft (.json) ou transcription (.vtt). • Messenger : Meta -> « Télécharger vos informations » (JSON)."),
                ],
            ),
            (
                "E-mails & Médias",
                [
                    ("Gmail via Google Takeout (.mbox)", f"1. Ouvrez {u_takeout} -> « Tout désélectionner » -> cochez « Mail » (ou un libellé précis).\n2. Téléchargez et décompressez le .zip, puis copiez le fichier .mbox dans « input_documents »."),
                    ("Autres e-mails (.eml), Documents, Images & Audios", "Glissez-déposez directement vos .eml, PDF, Word (.docx), Excel (.xlsx), images (.jpg, .png) et audios (.mp3, .m4a, .wav) dans « input_documents »."),
                ],
            ),
        ]

        for tab_title, blocks in sections:
            tab = tk.Frame(nb, bg="#ffffff", padx=16, pady=12)
            nb.add(tab, text=f"  {tab_title}  ")
            txt = tk.Text(tab, wrap="word", bg="#ffffff", fg="#0f172a", relief="flat", font=("Segoe UI", 9), padx=6, pady=4)
            txt.tag_configure("heading", font=("Segoe UI", 10, "bold"), foreground="#1d4ed8", spacing1=8, spacing3=3)
            txt.tag_configure("body", font=("Segoe UI", 9), foreground="#1e293b", lmargin1=12, lmargin2=12, spacing3=8)
            for h_title, b_text in blocks:
                txt.insert("end", h_title + "\n", "heading")
                self._insert_text_with_links(txt, b_text)
            txt.configure(state="disabled")
            sb = ttk.Scrollbar(tab, orient="vertical", command=txt.yview)
            txt.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            txt.pack(side="left", fill="both", expand=True)

        if 0 <= initial_tab < len(sections):
            nb.select(initial_tab)

        footer = tk.Frame(self, bg="#e2e8f0", padx=16, pady=10)
        footer.pack(fill="x")
        make_styled_button(footer, text="Fermer le guide", command=self.destroy, variant="primary").pack(side="right")
