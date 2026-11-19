# Architecture Technique : Chaîne d'Anonymisation Documentaire

> **Navigation :** [← Retour au README](../README.md) | [Guide d'utilisation](GUIDE_UTILISATION.md) | **Guides d'export :** [Contacts & E-mails](exports/CONTACTS_ET_EMAILS.md) • [Google Chat & Teams](exports/MESSAGERIES_PRO.md) • [WhatsApp, Messenger & Signal](exports/MESSAGERIES_PERSO.md)

## 1. Vue d'ensemble du système

L'écosystème repose sur **deux sous-projets autonomes** (`google_contacts_parser` et `doc_anonymizer`) et un **socle commun (`common/`)** exécutés dans un environnement virtuel Python (`.venv/`), pilotés depuis la racine par `config.ini` et deux lanceurs (`run_contacts.py`, `run_documents.py`). Les données personnelles et `config.ini` sont protégés par `.gitignore`.

```text
+----------------------------------------------------------------------+

|              RESSOURCES PARTAGÉES (RACINE & DATA/)                   |
| [.venv/] | [requirements.txt] | [.gitignore] | [common/core_utils.py]|
| [data/prenoms.txt, villes_masquees.txt, collisions_noms.txt, ...]    |
| [config.ini] <-------------------------> [output_contacts/contacts.txt]|
| [run_contacts.py]                          [run_documents.py]        |
+--------|----------------------------------------|--------------------+

         |                                        |
         v                                        v
+----------------------------------+   +-------------------------------+

| PROJET 1: google_contacts_parser |   | PROJET 2: doc_anonymizer      |
| [input_contacts/*.csv]           |   | [input_documents/]            |
|        |                         |   |        |                      |
|        v                         |   |        v (Extraction)         |
| Extraction -> Anonymisation      |   | [extracted_texts/AAAA-MM/...] |
|        |                         |   |        |                      |
|        +-> [.intermediaires/*]   |   |        v (Au fil de l'eau)    |
|        +-> [output_contacts/     |   | Masquage & Audit temps réel   |
|             contacts.txt]        |   |        |                      |
+----------------------------------+   |        +-> [lot_XX/*.txt]     |

                                       |        +-> [audits/*.txt]     |
                                       +-------------------------------+
```

---

## 2. Socle commun (`common/`), utilitaires (`tools/`) et répertoires

* **`common/core_utils.py` (`SharedCoreUtils`)** : normalisation Unicode (NFKD), téléphones français (`0XXXXXXXXX`), suppression des alias `+...` sur les e-mails, écriture atomique sur disque et inhibition de mise en veille.
* **`tools/`** :
  * `complete_manual_contacts.py` (`ManualContactsAutoCompleter`) : complète automatiquement les lignes `Prénom Nom = ` vides dans `output_contacts/contacts_manuels.txt`.
  * `sync_contacts.py` (`ContactsSynchronizer`) : synchronise `output_contacts/contacts.txt` en préservant `contacts_manuels.txt`.
  * `restore_transcription_names.py` (`TranscriptionNameRestorer`) : restaure les noms d'origine dans `extracted_texts/` et reclasse par période `AAAA-MM`.
  * `generate_pdf_guide.py` (`MarkdownPdfConverter`) : convertit les `.md` en `.pdf` paginés via PyMuPDF.
* **`data/`** : référentiels lexicaux partagés (`prenoms.txt`, `villes_masquees.txt`, `collisions_noms.txt`, `mots_exclus.txt`).
* **`output_contacts/`** : annuaire inversé final (`contacts.txt`), règles manuelles (`contacts_manuels.txt`), contacts découverts (`contacts_emails_decouverts.txt`) et fichiers de travail dans `.intermediaires/`.
* **`audits/`** : rapports d'audit (`audit_noms_residuels.txt`, `audit_noms_residuels_copier.txt`), rapport d'extraction (`extraction_report.txt`) et listes d'identifiants rencontrés (`tous_emails_trouves.txt`, `tous_numeros_sms.txt`).

---

## 3. Persistance et reprise incrémentale

* **Extraction (`extracted_texts/`)** : `.extraction_state.txt` (chemins déjà extraits), `.sms_state.txt` (numéros SMS traités) et `.email_state.txt`.
* **Anonymisation (`anonymized_results/`)** : `.anonymization_state.json` mémorise l'avancement à chaque lot écrit (`lot_XX/anonymise_partie_XXX.txt`) et les jetons SHA-256 (`TEL_XXX`, `EMAIL_XXX`).
