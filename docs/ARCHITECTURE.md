# Architecture Technique : Chaîne d'Anonymisation Documentaire

> **Navigation :** [← Retour au README](../README.md) | [Guide d'utilisation](GUIDE_UTILISATION.md) | **Guides d'export :** [Contacts & E-mails](exports/CONTACTS_ET_EMAILS.md) • [Google Chat & Teams](exports/MESSAGERIES_PRO.md) • [WhatsApp, Messenger & Signal](exports/MESSAGERIES_PERSO.md)

## 1. Vue d'ensemble du système

L'écosystème repose sur **deux sous-projets autonomes** (`google_contacts_parser` et `doc_anonymizer`) et un **socle commun (`common/`)** pilotés depuis la racine par `config.ini` et deux lanceurs (`lancer_contacts.py`, `lancer_documents.py`).

```text
+----------------------------------------------------------------------+

|              RESSOURCES PARTAGÉES (RACINE & DATA/)                   |
| [.venv/] | [requirements.txt] | [.gitignore] | [common/core_utils.py]|
| [data/prenoms.txt, villes_masquees.txt, collisions_noms.txt, ...]    |
| [config.ini] <-------------------------> [output_contacts/contacts.txt]|
| [lancer_contacts.py]                       [lancer_documents.py]     |
+--------|----------------------------------------|--------------------+

         |                                        |
         v                                        v
+----------------------------------+   +-------------------------------+

| PROJET 1: google_contacts_parser |   | PROJET 2: doc_anonymizer      |
| [export_contacts/*.csv]          |   | [fichiers sources/]           |
|        |                         |   |        |                      |
|        v                         |   |        v (Extraction)         |
| Extraction -> Anonymisation      |   | [transcriptions/AAAA-MM/...]  |
|        |                         |   |        |                      |
|        +-> [.intermediaires/*]   |   |        v (Au fil de l'eau)    |
|        +-> [output_contacts/     |   | Masquage & Audit temps réel   |
|             contacts.txt]        |   |        |                      |
+----------------------------------+   |        +-> [lot_XX/*.txt]     |

                                       |        +-> [audits/*.txt]     |
                                       +-------------------------------+
```

---

## 2. Organisation des répertoires

* **`data/`** : référentiels lexicaux partagés (`prenoms.txt`, `villes_masquees.txt`, `collisions_noms.txt`, `mots_exclus.txt`).
* **`output_contacts/`** : annuaire inversé final (`contacts.txt`), règles manuelles (`contacts_manuels.txt`), contacts découverts (`contacts_emails_decouverts.txt`) et fichiers de travail dans `.intermediaires/`.
* **`audits/`** : rapports d'audit des noms résiduels (`audit_noms_residuels.txt`, `audit_noms_residuels_copier.txt`) et listes d'identifiants rencontrés (`tous_emails_trouves.txt`, `tous_numeros_sms.txt`).
* **`docs/`** : guides d'utilisation, architecture et fiches d'export (`docs/exports/`).
* **`common/`**, **`google_contacts_parser/`**, **`doc_anonymizer/`**, **`tools/`**, **`tests/`** : modules Python et suite de tests unitaires avec mesure de couverture.
