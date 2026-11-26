import configparser
import os
import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Dict, Optional
from doc_anonymizer.gui_widgets import (
    UI_COLORS,
    make_card,
    make_modern_dropdown,
    make_modern_entry,
    make_styled_button,
    register_scalable_font,
    scaled_size,
)


class WorkspaceSettingsManager:
    """Lit et sauvegarde les paramètres d'extraction et d'anonymisation d'un config.ini."""

    WHISPER_MODELS = ["tiny", "base", "small", "medium"]

    @staticmethod
    def load_settings(ini_path: str) -> Dict[str, Any]:
        cfg = configparser.ConfigParser()
        if ini_path and os.path.isfile(ini_path):
            cfg.read(ini_path, encoding="utf-8")
        return {
            "masked_birth_dates": cfg.get("anonymization", "masked_birth_dates", fallback="").strip(),
            "numbered_placeholders": cfg.getboolean("anonymization", "numbered_placeholders", fallback=False),
            "mask_ssn": cfg.getboolean("anonymization", "mask_ssn", fallback=True),
            "mask_addresses": cfg.getboolean("anonymization", "mask_addresses", fallback=True),
            "mask_financial_and_admin_ids": cfg.getboolean("anonymization", "mask_financial_and_admin_ids", fallback=True),
            "mask_urls": cfg.getboolean("anonymization", "mask_urls", fallback=True),
            "extra_locations": cfg.get("anonymizer", "extra_locations", fallback="").strip(),
            "enable_ocr": cfg.getboolean("extraction", "enable_ocr", fallback=True),
            "enable_audio": cfg.getboolean("extraction", "enable_audio", fallback=True),
            "enable_diarization": cfg.getboolean("extraction", "enable_diarization", fallback=True),
            "whisper_model": cfg.get("extraction", "whisper_model", fallback="base").strip() or "base",
        }

    @staticmethod
    def save_settings(ini_path: str, values: Dict[str, Any]) -> None:
        cfg = configparser.ConfigParser()
        if ini_path and os.path.isfile(ini_path):
            cfg.read(ini_path, encoding="utf-8")
        for sec in ("anonymization", "anonymizer", "extraction"):
            if not cfg.has_section(sec):
                cfg.add_section(sec)
        cfg.set("anonymization", "masked_birth_dates", str(values.get("masked_birth_dates") or "").strip())
        cfg.set("anonymization", "numbered_placeholders", "true" if values.get("numbered_placeholders") else "false")
        cfg.set("anonymization", "mask_ssn", "true" if values.get("mask_ssn") else "false")
        cfg.set("anonymization", "mask_addresses", "true" if values.get("mask_addresses") else "false")
        cfg.set("anonymization", "mask_financial_and_admin_ids", "true" if values.get("mask_financial_and_admin_ids") else "false")
        cfg.set("anonymization", "mask_urls", "true" if values.get("mask_urls") else "false")
        cfg.set("anonymizer", "extra_locations", str(values.get("extra_locations") or "").strip())
        cfg.set("extraction", "enable_ocr", "true" if values.get("enable_ocr") else "false")
        cfg.set("extraction", "enable_audio", "true" if values.get("enable_audio") else "false")
        cfg.set("extraction", "enable_diarization", "true" if values.get("enable_diarization", True) else "false")
        wm: str = str(values.get("whisper_model") or "base").strip()
        cfg.set("extraction", "whisper_model", wm if wm in WorkspaceSettingsManager.WHISPER_MODELS else "base")
        with open(ini_path, "w", encoding="utf-8") as f_out:
            cfg.write(f_out)
class WorkspaceSettingsDialog(tk.Toplevel):
    """Fenêtre modale permettant de configurer les paramètres du dossier actif."""

    def __init__(
        self,
        parent: tk.Misc,
        ini_path: str,
        on_saved: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.ini_path: str = ini_path
        self.on_saved = on_saved
        self.title("Paramètres du dossier actif")
        self.geometry("680x560")
        self.minsize(580, 480)
        self.configure(bg=UI_COLORS["bg"])
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        data = WorkspaceSettingsManager.load_settings(ini_path)
        hdr = tk.Frame(self, bg=UI_COLORS["sidebar"], padx=18, pady=12)
        hdr.pack(fill="x")
        lbl_h = tk.Label(hdr, text="Paramètres d'anonymisation et d'extraction du dossier", bg=UI_COLORS["sidebar"], fg="#ffffff", font=("Segoe UI", scaled_size(11), "bold"))
        lbl_h.pack(anchor="w")
        register_scalable_font(lbl_h, "Segoe UI", 11, "bold")

        body = tk.Frame(self, bg=UI_COLORS["bg"], padx=16, pady=12)
        body.pack(fill="both", expand=True)

        card_anon = make_card(body, title="Protection & Réversibilité", accent_color="#2563eb")
        tk.Label(card_anon, text="Dates de naissance exactes à masquer (séparées par des virgules) :", bg=UI_COLORS["card"], fg=UI_COLORS["text"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.birth_dates_var = tk.StringVar(value=str(data["masked_birth_dates"]))
        make_modern_entry(card_anon, self.birth_dates_var, width=420, placeholder="Ex. 14/07/1985, 02/05/2013").pack(anchor="w", pady=(3, 8))

        tk.Label(card_anon, text="Communes ou lieux supplémentaires à masquer :", bg=UI_COLORS["card"], fg=UI_COLORS["text"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.extra_locs_var = tk.StringVar(value=str(data["extra_locations"]))
        make_modern_entry(card_anon, self.extra_locs_var, width=420, placeholder="Ex. Ville-Alpha, Bourg-Beta").pack(anchor="w", pady=(3, 8))

        self.numbered_var = tk.BooleanVar(value=bool(data["numbered_placeholders"]))
        self.ssn_var = tk.BooleanVar(value=bool(data["mask_ssn"]))
        self.addr_var = tk.BooleanVar(value=bool(data["mask_addresses"]))
        self.fin_var = tk.BooleanVar(value=bool(data["mask_financial_and_admin_ids"]))
        self.url_var = tk.BooleanVar(value=bool(data["mask_urls"]))
        for var, txt in (
            (self.numbered_var, "Balises numérotées ([LIEU_01], [DATE_01]) pour désanonymisation exacte"),
            (self.ssn_var, "Masquer les numéros de Sécurité sociale (NIR)"),
            (self.addr_var, "Masquer les adresses postales et établissements"),
            (self.fin_var, "Masquer IBAN, références bancaires, CNI, plaques et dossiers"),
            (self.url_var, "Masquer les liens web (URLs)"),
        ):
            tk.Checkbutton(card_anon, text=txt, variable=var, bg=UI_COLORS["card"], fg=UI_COLORS["text"], font=("Segoe UI", 9)).pack(anchor="w")

        card_ext = make_card(body, title="Extraction OCR & Transcription Audio", accent_color="#059669")
        self.ocr_var = tk.BooleanVar(value=bool(data["enable_ocr"]))
        self.audio_var = tk.BooleanVar(value=bool(data["enable_audio"]))
        self.diarization_var = tk.BooleanVar(value=bool(data["enable_diarization"]))
        tk.Checkbutton(card_ext, text="Activer la reconnaissance de texte sur images et PDF scannés (OCR)", variable=self.ocr_var, bg=UI_COLORS["card"], fg=UI_COLORS["text"], font=("Segoe UI", 9)).pack(anchor="w")
        row_w = tk.Frame(card_ext, bg=UI_COLORS["card"])
        row_w.pack(fill="x", pady=(4, 0))
        tk.Checkbutton(row_w, text="Activer la transcription audio/vidéo — Modèle Whisper :", variable=self.audio_var, bg=UI_COLORS["card"], fg=UI_COLORS["text"], font=("Segoe UI", 9)).pack(side="left")
        self.whisper_var = tk.StringVar(value=str(data["whisper_model"]))
        make_modern_dropdown(row_w, self.whisper_var, WorkspaceSettingsManager.WHISPER_MODELS, width=120).pack(side="left", padx=(8, 0))
        tk.Checkbutton(card_ext, text="Distinguer automatiquement les interlocuteurs (Interlocuteur_1, Interlocuteur_2...)", variable=self.diarization_var, bg=UI_COLORS["card"], fg=UI_COLORS["text"], font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))

        footer = tk.Frame(self, bg=UI_COLORS["bg"], padx=16, pady=10)
        footer.pack(fill="x")
        make_styled_button(footer, text="Annuler", command=self.destroy, variant="secondary").pack(side="right")
        make_styled_button(footer, text="Enregistrer les paramètres", command=self._save, variant="primary").pack(side="right", padx=(0, 8))

    def _save(self) -> None:
        WorkspaceSettingsManager.save_settings(self.ini_path, {
            "masked_birth_dates": self.birth_dates_var.get(),
            "extra_locations": self.extra_locs_var.get(),
            "numbered_placeholders": self.numbered_var.get(),
            "mask_ssn": self.ssn_var.get(),
            "mask_addresses": self.addr_var.get(),
            "mask_financial_and_admin_ids": self.fin_var.get(),
            "mask_urls": self.url_var.get(),
            "enable_ocr": self.ocr_var.get(),
            "enable_audio": self.audio_var.get(),
            "enable_diarization": self.diarization_var.get(),
            "whisper_model": self.whisper_var.get(),
        })
        if self.on_saved is not None:
            self.on_saved()
        self.destroy()
