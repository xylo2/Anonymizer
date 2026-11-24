# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import tkinter as tk
from typing import Callable


def show_startup_error_dialog(
    exc: BaseException, details: str, root_dir: str
) -> None:
    """Affiche une boîte de dialogue d'erreur critique au démarrage de l'interface."""
    root = tk.Tk()
    root.title("Erreur au démarrage — AnonVault — Pièces protégées")
    root.geometry("680x420")
    root.configure(bg="#f8fafc")
    ico_p: str = os.path.join(root_dir, "assets", "anonvault_icon.ico")
    if os.name == "nt" and os.path.isfile(ico_p):
        try:
            root.iconbitmap(default=ico_p)
        except tk.TclError:
            pass
    full_msg: str = f"Erreur : {exc}\n\nDétails techniques :\n{details.strip()}"
    hdr = tk.Frame(root, bg="#dc2626", padx=16, pady=12)
    hdr.pack(fill="x")
    tk.Label(
        hdr,
        text="Une erreur est survenue au démarrage",
        bg="#dc2626",
        fg="#ffffff",
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w")
    txt = tk.Text(
        root,
        wrap="word",
        font=("Consolas", 9),
        bg="#ffffff",
        fg="#0f172a",
        relief="solid",
        bd=1,
        padx=10,
        pady=8,
    )
    txt.pack(fill="both", expand=True, padx=16, pady=(12, 8))
    txt.insert("1.0", full_msg)
    txt.configure(state="disabled")
    bar = tk.Frame(root, bg="#f8fafc", padx=16, pady=10)
    bar.pack(fill="x")
    tk.Button(
        bar,
        text="Copier l'erreur",
        command=lambda: (
            root.clipboard_clear(),
            root.clipboard_append(full_msg),
            root.update(),
        ),
        bg="#2563eb",
        fg="#ffffff",
        relief="flat",
        padx=14,
        pady=7,
        font=("Segoe UI", 9, "bold"),
    ).pack(side="left")
    tk.Button(
        bar,
        text="Fermer",
        command=root.destroy,
        bg="#e2e8f0",
        fg="#0f172a",
        relief="flat",
        padx=14,
        pady=7,
        font=("Segoe UI", 9),
    ).pack(side="right")
    root.mainloop()


def run_with_optional_error_dialog(
    app_loop_fn: Callable[[], None],
    root_dir: str,
    enable_gui_errors: bool = False,
) -> int:
    """Exécute la boucle principale Tkinter avec capture d'erreur graphique optionnelle."""
    if not enable_gui_errors:
        app_loop_fn()
        return 0
    try:
        app_loop_fn()
        return 0
    except Exception as exc:
        import traceback

        show_startup_error_dialog(exc, traceback.format_exc(), root_dir)
        return 1
