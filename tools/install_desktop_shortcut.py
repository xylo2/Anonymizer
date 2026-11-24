# Commandes pip à exécuter : Aucune dépendance externe requise

import hashlib
import os
import shutil
import stat
import subprocess
import sys
from typing import List

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _prepare_cache_busted_ico(assets_dir: str, ico_path: str) -> str:
    """Copie le .ico sous un nom horodaté par SHA-256 pour contourner le cache Windows."""
    with open(ico_path, "rb") as f_in:
        digest: str = hashlib.sha256(f_in.read()).hexdigest()[:8]
    for fn in os.listdir(assets_dir):
        if fn.startswith("anonvault_icon_") and fn.endswith(".ico"):
            try:
                os.remove(os.path.join(assets_dir, fn))
            except OSError:
                pass
    busted_ico: str = os.path.join(assets_dir, f"anonvault_icon_{digest}.ico")
    shutil.copy2(ico_path, busted_ico)
    return busted_ico


def create_windows_shortcut(desktop_dir: str, ico_path: str) -> str:
    bat_path: str = os.path.join(ROOT_DIR, "Lancer_Anonymiseur.bat")
    lnk_path: str = os.path.join(desktop_dir, "AnonVault - Pièces protégées.lnk")
    if os.path.isfile(lnk_path):
        try:
            os.remove(lnk_path)
        except OSError:
            pass
    assets_dir: str = os.path.dirname(os.path.abspath(ico_path))
    unique_ico: str = _prepare_cache_busted_ico(assets_dir, ico_path)
    ps_cmd: str = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{lnk_path}'); "
        f"$s.TargetPath = '{bat_path}'; "
        f"$s.WorkingDirectory = '{ROOT_DIR}'; "
        f"$s.IconLocation = '{unique_ico},0'; "
        "$s.Description = 'AnonVault — Pièces protégées'; "
        "$s.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
    subprocess.run(["ie4uinit.exe", "-show"], check=False)
    return lnk_path


def create_linux_desktop_entry(desktop_dir: str, png_path: str) -> str:
    sh_path: str = os.path.join(ROOT_DIR, "Lancer_Anonymiseur.sh")
    if os.path.isfile(sh_path):
        st = os.stat(sh_path)
        os.chmod(sh_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP)

    content: str = (
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Type=Application\n"
        "Name=AnonVault — Pièces protégées\n"
        "Comment=Extraction et anonymisation locale de pièces confidentielles\n"
        f"Exec=\"{sh_path}\"\n"
        f"Path={ROOT_DIR}\n"
        f"Icon={png_path}\n"
        "Terminal=false\n"
        "Categories=Utility;Office;\n"
    )
    targets: List[str] = [os.path.join(desktop_dir, "anonvault.desktop")]
    apps_dir: str = os.path.expanduser("~/.local/share/applications")
    if os.path.isdir(apps_dir):
        targets.append(os.path.join(apps_dir, "anonvault.desktop"))

    for target in targets:
        with open(target, "w", encoding="utf-8") as f_out:
            f_out.write(content)
        os.chmod(target, 0o755)
    return next(iter(targets))


def main() -> int:
    assets_dir: str = os.path.join(ROOT_DIR, "assets")
    ico_path: str = os.path.join(assets_dir, "anonvault_icon.ico")
    png_path: str = os.path.join(assets_dir, "anonvault_icon.png")
    if not os.path.isfile(ico_path) or not os.path.isfile(png_path):
        from tools.generate_app_icon import AppIconGenerator
        AppIconGenerator.export_icons(output_dir=assets_dir)

    desktop_dir: str = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(desktop_dir):
        desktop_dir = os.path.join(os.path.expanduser("~"), "Bureau")
    os.makedirs(desktop_dir, exist_ok=True)

    created: str = (
        create_windows_shortcut(desktop_dir, ico_path)
        if os.name == "nt"
        else create_linux_desktop_entry(desktop_dir, png_path)
    )
    print(f"[OK] Lanceur avec icône créé : {created}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
