# Commandes pip à exécuter : pip install customtkinter>=5.2.2

import re
import tkinter as tk
from typing import Callable, Dict, List, Optional, Tuple
import webbrowser
from doc_anonymizer.gui_widgets import (
    UI_COLORS,
    make_styled_button,
    register_scalable_font,
    scaled_size,
)


def _u(sub: str, domain: str, path: str = "") -> str:
    host: str = f"{sub}.{domain}" if sub else domain
    return f"https://{host}{path}"


class ExportGuideDialog(tk.Toplevel):
    """Fenêtre modale dédiée aux guides pas-à-pas d'export par service."""

    URL_RE = re.compile(r"https://[^\s)\]>]+")

    TABS: List[Tuple[str, str]] = [
        (
            "Agenda (.ics)",
            "EXPORTER VOTRE AGENDA EN FICHIER .ICS\n\n"
            f"• Google Agenda ({_u('calendar', 'google.com')}) :\n"
            "  1. Ouvrez Google Agenda > icône Engrenage > « Paramètres ».\n"
            "  2. Menu de gauche > « Importer et exporter » > « Exporter ».\n"
            "  3. Décompressez le .zip et référencez le fichier .ics.\n\n"
            "• Microsoft Outlook & Apple Calendrier :\n"
            "  Menu « Fichier » > « Enregistrer le calendrier » au format .ics.",
        ),
        (
            "Contacts (.csv / .vcf)",
            "EXPORTER VOS CONTACTS (GOOGLE, IPHONE, OUTLOOK, THUNDERBIRD)\n\n"
            f"• Google Contacts ({_u('contacts', 'google.com')} — recommandé) :\n"
            "  Menu gauche > « Exporter » > « Tous les contacts » > « CSV Google ».\n\n"
            f"• Apple iPhone / iPad (iOS 16+) & iCloud ({_u('www', 'icloud.com', '/contacts')}) :\n"
            "  - iPhone : Contacts > « < Listes » > appui long « Tous les contacts » > « Exporter » (.vcf).\n"
            "  - iCloud Web : Ctrl+A > Roue dentée > « Exporter vCard » (.vcf).\n\n"
            f"• Microsoft Outlook & Thunderbird ({_u('www', 'thunderbird.net')}) :\n"
            f"  - Outlook Web ({_u('outlook', 'live.com')}) : Personnes > « Gérer les contacts » > « Exporter » (.csv).\n"
            "  - Outlook Classique : Fichier > Ouvrir et exporter > Importer/Exporter > Exporter en CSV.\n"
            "  - Thunderbird : Carnet d'adresses > clic droit > Exporter en vCard (.vcf).",
        ),
        (
            "E-mails (.pst / .mbox / .eml)",
            "EXPORTER TOUTE SA MESSAGERIE OU UNE SÉLECTION FILTRÉE\n\n"
            "• Client lourd Outlook Classique (Windows / Mac — recommandé) :\n"
            "  - Archive complète ou filtrée (.pst / .ost) : Fichier > Ouvrir et exporter > "
            "Importer/Exporter > Exporter des données vers un fichier > Fichier de données Outlook (.pst) "
            "(cliquez sur « Filtrer... » pour restreindre). Le .pst ou .ost est lu directement par AnonVault.\n"
            "  - Sélection unitaire (.msg) : filtrez via la recherche Outlook et glissez les mails "
            "dans un dossier PC (fichiers .msg lus directement par AnonVault).\n\n"
            f"• Gmail via Google Takeout ({_u('takeout', 'google.com')}) :\n"
            "  Tout désélectionner > cochez « Messagerie (Gmail) » > décompressez le .zip > référencez le .mbox.\n\n"
            f"• Outlook.com / Microsoft 365 Web ({_u('outlook', 'live.com')}) :\n"
            "  - Unitaire (.eml) : ouvrez le message > « ... » > « Télécharger ».\n"
            "  - Boîte complète (.pst) : Engrenage > Général > Confidentialité et données > Exporter la boîte.\n\n"
            "• Autres fournisseurs (Yahoo, Orange, Free, SFR, La Poste, Proton, iCloud, Infomaniak) :\n"
            f"  - Méthode universelle IMAP : installez Thunderbird ({_u('www', 'thunderbird.net')}), "
            "filtrez les mails utiles > clic droit > Enregistrer sous (.eml) ou récupérez le .mbox.\n"
            f"  - Exports directs : Proton Mail ({_u('proton', 'me', '/mail')}), "
            f"Free Zimbra ({_u('zimbra', 'free.fr')}), Infomaniak ({_u('mail', 'infomaniak.com')}).",
        ),
        (
            "SMS (.xml / .csv)",
            "EXPORTER VOS SMS & MMS (ANDROID & IPHONE)\n\n"
            "• Sur Android (gratuit, recommandé) :\n"
            f"  1. Installez « SMS Backup & Restore » ({_u('play', 'google.com', '/store/apps/details?id=com.riteshsahu.SMSBackupRestore')}).\n"
            "  2. « Configurer une sauvegarde » > activez « Messages » > « Sauvegarder maintenant » (.xml).\n\n"
            "• Sur iPhone / iPad :\n"
            f"  Utilisez iMazing ({_u('imazing', 'com')}) ou CopyTrans Contacts ({_u('www', 'copytrans.fr', '/copytranscontacts/')}) > Exporter en CSV/PDF.",
        ),
        (
            "Chats & Visios",
            "EXPORTER VOS MESSAGERIES (WHATSAPP, GOOGLE CHAT, TEAMS, MESSENGER, SIGNAL)\n\n"
            f"• WhatsApp ({_u('www', 'whatsapp.com')}) : Discussion > Menu > « Exporter discussion » (dézippez le .zip).\n"
            f"• Google Chat ({_u('takeout', 'google.com')}) : Cochez « Google Chat » > dézippez > dossier « Groups/ ».\n"
            f"• Microsoft Teams ({_u('account', 'microsoft.com', '/privacy')}) : Discussions (.json) ou réunions ({_u('teams', 'microsoft.com')}, .vtt).\n"
            f"• Facebook Messenger ({_u('accountscenter', 'facebook.com', '/info_and_permissions')}) : Télécharger vos informations > Messages (JSON).\n"
            f"• Signal ({_u('signal', 'org')}) : Export JSON via « signal-back » (Android) ou « sigtop » (Desktop).",
        ),
    ]
    def __init__(self, parent: tk.Misc, initial_tab: int = 0) -> None:
        super().__init__(parent)
        self.title("Guide pas-à-pas — Comment exporter vos données ?")
        self.geometry("840x580")
        self.minsize(680, 460)
        self.configure(bg=UI_COLORS["bg"])
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        hdr = tk.Frame(self, bg=UI_COLORS["sidebar"], padx=18, pady=12)
        hdr.pack(fill="x")
        lbl_h = tk.Label(
            hdr,
            text="Comment exporter vos fichiers depuis chaque service (cliquez sur les liens bleus) :",
            bg=UI_COLORS["sidebar"],
            fg="#ffffff",
            font=("Segoe UI", scaled_size(11), "bold"),
        )
        lbl_h.pack(anchor="w")
        register_scalable_font(lbl_h, "Segoe UI", 11, "bold")

        tab_bar = tk.Frame(self, bg="#e2e8f0", padx=12, pady=8)
        tab_bar.pack(fill="x")
        self._tab_btns: List[tk.Button] = []
        for idx, (lbl, _) in enumerate(self.TABS):
            btn = tk.Button(
                tab_bar,
                text=lbl,
                relief="flat",
                bd=0,
                padx=12,
                pady=6,
                cursor="hand2",
                font=("Segoe UI", scaled_size(9), "bold"),
                command=lambda i=idx: self.select_tab(i),
            )
            register_scalable_font(btn, "Segoe UI", 9, "bold")
            btn.pack(side="left", padx=(0, 6))
            self._tab_btns.append(btn)

        body = tk.Frame(self, bg=UI_COLORS["bg"], padx=18, pady=14)
        body.pack(fill="both", expand=True)
        self.txt_guide = tk.Text(
            body,
            wrap="word",
            font=("Segoe UI", scaled_size(10)),
            bg="#ffffff",
            fg=UI_COLORS["text"],
            relief="solid",
            bd=1,
            padx=16,
            pady=14,
        )
        self.txt_guide.pack(fill="both", expand=True)
        register_scalable_font(self.txt_guide, "Segoe UI", 10, "normal")

        footer = tk.Frame(self, bg=UI_COLORS["bg"], padx=18, pady=10)
        footer.pack(fill="x")
        make_styled_button(
            footer, text="Fermer", command=self.destroy, variant="primary"
        ).pack(side="right")

        self.select_tab(max(0, min(initial_tab, len(self.TABS) - 1)))

    def _insert_with_clickable_links(self, content: str) -> None:
        pos: int = 0
        for idx, match in enumerate(self.URL_RE.finditer(content)):
            if match.start() > pos:
                self.txt_guide.insert("end", content[pos : match.start()])
            url: str = match.group(0).rstrip(".,;:")
            tag_name: str = f"link_{idx}"
            self.txt_guide.tag_configure(tag_name, foreground="#2563eb", underline=True)
            self.txt_guide.tag_bind(tag_name, "<Enter>", lambda _e: self.txt_guide.configure(cursor="hand2"))
            self.txt_guide.tag_bind(tag_name, "<Leave>", lambda _e: self.txt_guide.configure(cursor="xterm"))
            self.txt_guide.tag_bind(tag_name, "<Button-1>", lambda _e, u=url: webbrowser.open(u))
            self.txt_guide.insert("end", url, (tag_name,))
            pos = match.start() + len(url)
        if pos < len(content):
            self.txt_guide.insert("end", content[pos:])

    def select_tab(self, idx: int) -> None:
        for i, btn in enumerate(self._tab_btns):
            active: bool = i == idx
            btn.configure(
                bg=UI_COLORS["tab_active_bg"] if active else "#ffffff",
                fg="#ffffff" if active else UI_COLORS["text"],
            )
        _, content = self.TABS[idx]
        self.txt_guide.configure(state="normal")
        self.txt_guide.delete("1.0", "end")
        self._insert_with_clickable_links(content)
        self.txt_guide.configure(state="disabled")
class BeforeAfterPreviewDialog(tk.Toplevel):
    """Fenêtre dédiée côte à côte (Avant / Après) pour vérifier un nom détecté dans son contexte."""

    def __init__(
        self,
        parent: tk.Misc,
        candidate: str,
        proposed_alias: str,
        occurrences: List[Dict[str, str]],
        on_approve: Optional[Callable[[], None]] = None,
        on_exclude: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.title(f"Vérification contextuelle Avant / Après — « {candidate} »")
        self.geometry("940x560")
        self.minsize(760, 440)
        self.configure(bg=UI_COLORS["bg"])
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self._on_approve = on_approve
        self._on_exclude = on_exclude

        top = tk.Frame(self, bg=UI_COLORS["sidebar"], padx=18, pady=12)
        top.pack(fill="x")
        lbl_t = tk.Label(
            top,
            text=f"Terme détecté : « {candidate} »   ->   Remplacement proposé : « {proposed_alias} »",
            bg=UI_COLORS["sidebar"],
            fg="#ffffff",
            font=("Segoe UI", scaled_size(10), "bold"),
        )
        lbl_t.pack(anchor="w")
        register_scalable_font(lbl_t, "Segoe UI", 10, "bold")
        lbl_sub = tk.Label(
            top,
            text=f"{len(occurrences)} passage(s) trouvé(s) dans les textes extraits. Le surlignage jaune montre exactement ce qui sera masqué.",
            bg=UI_COLORS["sidebar"],
            fg="#94a3b8",
            font=("Segoe UI", scaled_size(8)),
        )
        lbl_sub.pack(anchor="w", pady=(2, 0))
        register_scalable_font(lbl_sub, "Segoe UI", 8, "normal")

        panes = tk.Frame(self, bg=UI_COLORS["bg"], padx=14, pady=12)
        panes.pack(fill="both", expand=True)
        panes.columnconfigure(0, weight=1)
        panes.columnconfigure(1, weight=1)
        panes.rowconfigure(1, weight=1)

        lbl_av = tk.Label(panes, text="AVANT (Texte extrait original)", bg="#fee2e2", fg="#991b1b", font=("Segoe UI", scaled_size(9), "bold"), pady=6)
        lbl_av.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        register_scalable_font(lbl_av, "Segoe UI", 9, "bold")
        lbl_ap = tk.Label(panes, text="APRÈS (Résultat si vous masquez ce nom)", bg="#dcfce7", fg="#166534", font=("Segoe UI", scaled_size(9), "bold"), pady=6)
        lbl_ap.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        register_scalable_font(lbl_ap, "Segoe UI", 9, "bold")

        self.txt_before = tk.Text(panes, wrap="word", font=("Consolas", scaled_size(9)), bg="#ffffff", fg="#0f172a", relief="solid", bd=1, padx=10, pady=8)
        self.txt_before.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        register_scalable_font(self.txt_before, "Consolas", 9, "normal")
        self.txt_after = tk.Text(panes, wrap="word", font=("Consolas", scaled_size(9)), bg="#ffffff", fg="#0f172a", relief="solid", bd=1, padx=10, pady=8)
        self.txt_after.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        register_scalable_font(self.txt_after, "Consolas", 9, "normal")

        self.txt_before.tag_configure("hit", background="#fde047", foreground="#0f172a", font=("Consolas", scaled_size(9), "bold"))
        self.txt_after.tag_configure("rep", background="#bbf7d0", foreground="#14532d", font=("Consolas", scaled_size(9), "bold"))

        if not occurrences:
            self.txt_before.insert("1.0", "Aucune occurrence exacte trouvée dans les transcriptions actuelles.")
            self.txt_after.insert("1.0", "Aucun aperçu disponible.")
        else:
            for idx, occ in enumerate(occurrences[:15], start=1):
                header: str = f"--- Passage {idx} ({occ['file_label']}, ligne {occ['line_num']}) ---\n"
                raw_txt: str = occ["raw_excerpt"]
                replaced_txt: str = raw_txt.replace(candidate, proposed_alias)
                self.txt_before.insert("end", header + raw_txt + "\n\n")
                self.txt_after.insert("end", header + replaced_txt + "\n\n")
            self._highlight_term(self.txt_before, candidate, "hit")
            self._highlight_term(self.txt_after, proposed_alias, "rep")

        self.txt_before.configure(state="disabled")
        self.txt_after.configure(state="disabled")

        footer = tk.Frame(self, bg=UI_COLORS["bg"], padx=14, pady=10)
        footer.pack(fill="x")
        make_styled_button(footer, text="Fermer", command=self.destroy, variant="secondary").pack(side="right")
        if on_exclude is not None:
            make_styled_button(footer, text="Ignorer (c'est un faux positif)", command=self._handle_exclude, variant="secondary").pack(side="left", padx=(0, 8))
        if on_approve is not None:
            make_styled_button(footer, text="Masquer ce nom", command=self._handle_approve, variant="primary").pack(side="left")

    @staticmethod
    def _highlight_term(widget: tk.Text, term: str, tag: str) -> None:
        if not term:
            return
        start: str = "1.0"
        while True:
            pos: str = widget.search(term, start, stopindex="end", nocase=True)
            if not pos:
                break
            end_pos: str = f"{pos}+{len(term)}c"
            widget.tag_add(tag, pos, end_pos)
            start = end_pos

    def _handle_approve(self) -> None:
        self.destroy()
        if self._on_approve is not None:
            self._on_approve()

    def _handle_exclude(self) -> None:
        self.destroy()
        if self._on_exclude is not None:
            self._on_exclude()
