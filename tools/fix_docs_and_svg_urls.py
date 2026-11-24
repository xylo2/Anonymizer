# Commandes pip à exécuter : Aucune dépendance externe requise

import os
from typing import List, Tuple

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _u(sub: str, domain: str, path: str = "") -> str:
    host: str = f"{sub}.{domain}" if sub else domain
    return f"https://{host}{path}"


def fix_svg_namespace(base_dir: str) -> List[str]:
    """Restaure le namespace W3C complet dans generate_app_icon.py et anonvault_icon.svg."""
    valid_ns: str = "http://" + "www." + "w3.org" + "/2000/svg"
    broken_ns: str = "http://" + "w3.org"
    updated: List[str] = []
    for rel in ("tools/generate_app_icon.py", "assets/anonvault_icon.svg"):
        fp: str = os.path.join(base_dir, rel)
        if not os.path.isfile(fp):
            continue
        with open(fp, "r", encoding="utf-8") as f_in:
            txt: str = f_in.read()
        new_txt: str = txt.replace(f'xmlns="{broken_ns}"', f'xmlns="{valid_ns}"')
        if new_txt != txt:
            with open(fp, "w", encoding="utf-8") as f_out:
                f_out.write(new_txt)
            updated.append(rel)
    return updated


def fix_chat_domain_in_python(base_dir: str) -> List[str]:
    """Répare les domaines ://google.com dans le code Python."""
    chat_host: str = "chat." + "google.com"
    broken_host: str = "://" + "google.com"
    updated: List[str] = []
    targets = (
        "doc_anonymizer/comm_extractors.py",
        "doc_anonymizer/discovered_contacts_builder.py",
        "doc_anonymizer/extraction_runner.py",
    )
    for rel in targets:
        fp: str = os.path.join(base_dir, rel)
        if not os.path.isfile(fp):
            continue
        with open(fp, "r", encoding="utf-8") as f_in:
            txt: str = f_in.read()
        new_txt: str = txt.replace(broken_host, chat_host)
        if new_txt != txt:
            with open(fp, "w", encoding="utf-8") as f_out:
                f_out.write(new_txt)
            updated.append(rel)
    return updated
def _build_md_replacements() -> List[Tuple[str, str]]:
    play_sms: str = _u("play", "google.com", "/store/apps/details?id=com.riteshsahu.SMSBackupRestore")
    return [
        (f"[Google Contacts]({_u('', 'google.com')})", f"[Google Contacts]({_u('contacts', 'google.com')})"),
        (f"[Google Agenda]({_u('', 'google.com')})", f"[Google Agenda]({_u('calendar', 'google.com')})"),
        (f"[Google Takeout]({_u('', 'google.com')})", f"[Google Takeout]({_u('takeout', 'google.com')})"),
        ("`://google.com` > **Exporter**", f"[Google Contacts]({_u('contacts', 'google.com')}) > **Exporter**"),
        ("`://google.com` > cocher uniquement **Messagerie**", f"[Google Takeout]({_u('takeout', 'google.com')}) > cocher uniquement **Messagerie**"),
        ("`://google.com` > **Google Chat**", f"[Google Takeout]({_u('takeout', 'google.com')}) > **Google Chat**"),
        (f"[Outlook Web]({_u('', 'live.com')})", f"[Outlook Web]({_u('outlook', 'live.com')})"),
        (f"[Microsoft 365]({_u('', 'office.com')})", f"[Microsoft 365]({_u('outlook', 'office.com')})"),
        (f"[iCloud Contacts]({_u('', 'icloud.com')})", f"[iCloud Contacts]({_u('www', 'icloud.com', '/contacts')})"),
        (f"[Mozilla Thunderbird]({_u('', 'thunderbird.net')})", f"[Mozilla Thunderbird]({_u('www', 'thunderbird.net')})"),
        (f"[Outlook.com]({_u('', 'live.com')})", f"[Outlook.com]({_u('outlook', 'live.com')})"),
        (f"[Microsoft 365 Web]({_u('', 'office.com')})", f"[Microsoft 365 Web]({_u('outlook', 'office.com')})"),
        (f"[Yahoo Mail]({_u('', 'yahoo.com')})", f"[Yahoo Mail]({_u('mail', 'yahoo.com')})"),
        (f"[Orange]({_u('', 'orange.fr')})", f"[Orange]({_u('messagerie', 'orange.fr')})"),
        (f"[Free Zimbra]({_u('', 'free.fr')})", f"[Free Zimbra]({_u('zimbra', 'free.fr')})"),
        (f"[SFR Mail]({_u('', 'sfr.fr')})", f"[SFR Mail]({_u('webmail', 'sfr.fr')})"),
        (f"[SFR]({_u('', 'sfr.fr')})", f"[SFR]({_u('webmail', 'sfr.fr')})"),
        (f"[La Poste]({_u('', 'laposte.net')})", f"[La Poste]({_u('www', 'laposte.net')})"),
        (f"[iCloud Mail]({_u('', 'icloud.com')})", f"[iCloud Mail]({_u('www', 'icloud.com', '/mail')})"),
        (f"[Infomaniak]({_u('', 'infomaniak.com')})", f"[Infomaniak]({_u('mail', 'infomaniak.com')})"),
        (f"[Infomaniak Mail]({_u('', 'infomaniak.com')})", f"[Infomaniak Mail]({_u('mail', 'infomaniak.com')})"),
        (f"[Proton Mail]({_u('', 'proton.me')})", f"[Proton Mail]({_u('mail', 'proton.me')})"),
        (f"[SMS Backup & Restore]({_u('', 'google.com')})", f"[SMS Backup & Restore]({play_sms})"),
        (f"[iMazing]({_u('', 'imazing.com')})", f"[iMazing]({_u('imazing', 'com')})"),
        (f"[CopyTrans Contacts]({_u('', 'copytrans.fr')})", f"[CopyTrans Contacts]({_u('www', 'copytrans.fr', '/copytranscontacts/')})"),
        (f"[WhatsApp]({_u('', 'whatsapp.com')})", f"[WhatsApp]({_u('www', 'whatsapp.com')})"),
        (f"[Facebook Messenger]({_u('', 'facebook.com')})", f"[Facebook Messenger]({_u('www', 'facebook.com')})"),
        (f"[Facebook]({_u('', 'facebook.com')})", f"[Facebook]({_u('www', 'facebook.com')})"),
        (f"[Centre de comptes Meta]({_u('', 'facebook.com')})", f"[Centre de comptes Meta]({_u('accountscenter', 'facebook.com', '/info_and_permissions')})"),
        (f"[Signal Desktop]({_u('', 'signal.org')})", f"[Signal Desktop]({_u('signal', 'org', '/download/')})"),
        (f"[sigtop]({_u('', 'github.com')})", f"[sigtop]({_u('github', 'com', '/tbvdm/sigtop')})"),
        (f"[signal-back]({_u('', 'github.com')})", f"[signal-back]({_u('github', 'com', '/xeals/signal-back')})"),
        (f"[Portail de confidentialité Microsoft]({_u('', 'microsoft.com')})", f"[Portail de confidentialité Microsoft]({_u('account', 'microsoft.com', '/privacy')})"),
        (f"[Mon Compte Microsoft 365]({_u('', 'microsoft.com')})", f"[Mon Compte Microsoft 365]({_u('myaccount', 'microsoft.com')})"),
        (f"[Microsoft Teams]({_u('', 'microsoft.com')})", f"[Microsoft Teams]({_u('teams', 'microsoft.com')})"),
    ]


def fix_markdown_docs(base_dir: str) -> List[str]:
    """Restaure tous les sous-domaines/chemins et sections CLI dans docs/."""
    replacements = _build_md_replacements()
    md_files = (
        "docs/GUIDE_UTILISATION.md",
        "docs/exports/CONTACTS_ET_EMAILS.md",
        "docs/exports/MESSAGERIES_PRO.md",
        "docs/exports/MESSAGERIES_PERSO.md",
    )
    updated: List[str] = []
    for rel in md_files:
        fp: str = os.path.join(base_dir, rel)
        if not os.path.isfile(fp):
            continue
        with open(fp, "r", encoding="utf-8") as f_in:
            txt: str = f_in.read()
        new_txt: str = txt
        for old_s, new_s in replacements:
            new_txt = new_txt.replace(old_s, new_s)
        if rel == "docs/GUIDE_UTILISATION.md" and "--copy-unmasked" not in new_txt:
            extra_cli: str = (
                "\n### Commandes d'audit et de complétion manuelle\n\n"
                "```bash\n"
                "python run_documents.py --copy-unmasked liste_fichiers.md --unmasked-dir a_revoir\n"
                "python run_documents.py --complete-manual\n"
                "python run_documents.py --manual-only\n"
                "```\n"
            )
            new_txt = new_txt.replace("## 5. Exploitation", extra_cli + "\n## 5. Exploitation")
        if new_txt != txt:
            with open(fp, "w", encoding="utf-8") as f_out:
                f_out.write(new_txt)
            updated.append(rel)
    return updated


def cleanup_temp_files(base_dir: str) -> List[str]:
    """Supprime les fichiers temporaires de diagnostic à la racine."""
    removed: List[str] = []
    for fn in ("iaexport", "verification_liens.txt"):
        fp: str = os.path.join(base_dir, fn)
        if os.path.isfile(fp):
            os.remove(fp)
            removed.append(fn)
    return removed


def main() -> int:
    fixed: List[str] = (
        fix_svg_namespace(ROOT_DIR)
        + fix_chat_domain_in_python(ROOT_DIR)
        + fix_markdown_docs(ROOT_DIR)
    )
    cleaned: List[str] = cleanup_temp_files(ROOT_DIR)
    print(f"[OK] Fichiers réparés ({len(fixed)}) : {fixed}")
    print(f"[OK] Temporaires supprimés ({len(cleaned)}) : {cleaned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
