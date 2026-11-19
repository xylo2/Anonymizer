# Architecture Technique : Chaîne d'Anonymisation Documentaire

> **Navigation :** [← Retour au README](README.md) | [Guide d'utilisation](GUIDE_UTILISATION.md) | **Guides d'export :** [Contacts & E-mails](docs/exports/CONTACTS_ET_EMAILS.md) • [Google Chat & Teams](docs/exports/MESSAGERIES_PRO.md) • [WhatsApp, Messenger & Signal](docs/exports/MESSAGERIES_PERSO.md)

## 1. Vue d'ensemble du système

L'écosystème repose sur **deux sous-projets autonomes** et un **socle commun (`common/`)** exécutés dans un environnement virtuel Python (`.venv/`), pilotés depuis la racine par un **fichier de configuration unique (`config.ini`)**, des **référentiels lexicaux partagés** (`prenoms.txt`, `villes_masquees.txt`, `collisions_noms.txt`, `mots_exclus.txt`) et deux lanceurs (`lancer_contacts.py`, `lancer_documents.py`). Les données personnelles et `config.ini` sont protégés par `.gitignore`.

```text
+----------------------------------------------------------------------+

|              RESSOURCES PARTAGÉES (RACINE COMMUNE)                   |
| [.venv/] | [requirements.txt] | [.gitignore] | [common/core_utils.py]|
| [prenoms.txt] | [villes_masquees.txt] | [collisions_noms.txt]        |
| [config.ini] <-------------------------------------> [contacts.txt]  |
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
|        +-> [contacts_indexes]    |   |        v (Au fil de l'eau)    |
|        +-> [contacts_anonymises] |   | Masquage & Audit temps réel   |
|        +-> [noms_famille_...]    |   |        |                      |
|        +-> [contacts.txt]        |   |        +-> [lot_XX/*.txt]     |
+----------------------------------+   |        +-> [audit_noms...txt] |
                                       +-------------------------------+
```

---

## 2. Socle commun (`common/`), utilitaires (`tools/`) et documentation (`docs/`)

* `common/core_utils.py` (`SharedCoreUtils`) : primitives de normalisation Unicode (NFKD), normalisation des téléphones français (`0XXXXXXXXX`), suppression des alias `+...` sur les e-mails, écriture atomique sur disque et inhibition de mise en veille multiplateforme.
* `tools/` :
  * `completer_contacts_manuels.py` : complète automatiquement les lignes `Prénom Nom = ` vides dans `contacts_manuels.txt`.
  * `sync_contacts.py` : synchronise `contacts.txt` en préservant `contacts_manuels.txt`.
  * `restaurer_noms_transcriptions.py` : restaure les noms d'origine des transcriptions et reclasse par période `AAAA-MM`.
  * `generate_pdf_guide.py` : convertit les `.md` en `.pdf` paginés via PyMuPDF (`DocumentWriter` en mémoire).
* `docs/exports/` : fiches méthodologiques dédiées aux exports ([Contacts & E-mails](docs/exports/CONTACTS_ET_EMAILS.md), [Google Chat & Teams](docs/exports/MESSAGERIES_PRO.md), [WhatsApp, Messenger & Signal](docs/exports/MESSAGERIES_PERSO.md)).
---

## 3. Sous-projet 1 : `google_contacts_parser`

Transforme des exports CSV multi-sources (**Google Contacts** et **Microsoft 365 / Outlook**) en un annuaire inversé et trié (`Alias = coordonnée`) via la bibliothèque standard Python.

### 3.1 Fichiers principaux
* `lancer_contacts.py` (racine) : point d'entrée CLI avec gestion propre de `Ctrl+C`.
* `google_contacts_parser/` :
  * `config_manager.py` (`ContactsConfig`) : résout les chemins depuis `config.ini`, charge la géographie française et liste les CSV dans `export_contacts/`.
  * `geo_data.py` & `text_utils.py` : catalogue géographique français, normalisation Unicode et nettoyage des enseignes.
  * `csv_reader.py` (`GoogleContactsReader`) : détection auto des délimiteurs (`,` et `;`), en-têtes Google/Outlook (FR/EN), couples et déduction d'identité depuis les e-mails.
  * `anonymizer.py`, `deduplicator.py`, `inverter.py`, `first_name_suggester.py` & `pipeline_runner.py` : pseudonymisation des noms (`Prénom N.`), résolution des homonymes (`Jean Du-2`), export `noms_famille_contacts.txt`, suggestions `prenoms_suggeres.txt` et exécution en 4 étapes (`contacts_indexes.txt` -> `contacts_anonymises.txt` -> `contacts_dedoublonnes.txt` -> `contacts.txt`).

---

## 4. Sous-projet 2 : `doc_anonymizer`

Assure l'extraction multi-formats parallèle, l'OCR/audio, le parsing des messageries instantanées et l'anonymisation **au fil de l'eau**.

### 4.1 Fichiers principaux
* `lancer_documents.py` (racine) : point d'entrée CLI avec options `--complete-manual`, `--manual-only`, `--dry-run`, `--sync-contacts` et `--allow-sleep`.
* `doc_anonymizer/` :
  * `config_manager.py` (`PipelineConfig`) : résout les chemins de `config.ini` et charge `prenoms.txt`, `villes_masquees.txt`, `collisions_noms.txt`, `mots_exclus.txt` et `masked_birth_dates`.
  * `power_manager.py` : empêche la mise en veille OS (Windows API / `systemd-inhibit` Linux).
  * `text_utils.py` : regex de masquage (NIR, IBAN, BIC, SPI fiscal, France Travail, CAF/MSA, RPPS/CNI/MRZ, plaques, digicodes, adresses, codes postaux), automates Trie tolérants OCR et détection prioritaire de la date (`AAAA-MM`).
  * `office_extractors.py` : extraction PDF (`pymupdf` + chargement paresseux `rapidocr-onnxruntime`), `.docx`, `.odt`, `.rtf`, `.xlsx`, `.pptx`, `.html`, `.txt`, `.md`, images et `.ics`.
  * `comm_extractors.py` : parsing streaming XML SMS/MMS (anti-XXE), `.mbox`/`.eml` (avec pièces jointes PDF), audio `faster-whisper` (chargement paresseux + cache `.whisper_cache/`) et Audacity `.aup3`.
  * `chat_extractors.py`, `whatsapp_zip_extractor.py` & `teams_chat_extractor.py` : extraction chronologique par mois (`Chats/`) des conversations **Google Chat** (`messages.json` + `group_info.json`), **WhatsApp** (`.txt` et archives `.zip` sécurisées avec médias joints), **Messenger** (JSON Meta avec réparation mojibake Latin-1 et HTML), **Signal** (`.json`) et **Microsoft Teams** (`messages.json`, Graph API et transcriptions `.vtt`).
  * `extraction_runner.py` : inventaire parallèle (`ThreadPoolExecutor`) de `fichiers sources/` et classement par mois (`transcriptions/AAAA-MM/Catégorie/`).
  * `contact_rules_loader.py` & `discovered_contacts_builder.py` : compile les règles issues de `contacts.txt`, `contacts_emails_decouverts.txt` et `contacts_manuels.txt`.
  * `audit_state_manager.py` : persistance JSON (`.etat_anonymisation.json`), jetons SHA-256 (`TEL_XXX`, `EMAIL_XXX`) et mise à jour temps réel de `audit_noms_residuels.txt` et `audit_noms_residuels_copier.txt`.
  * `anonymization_runner.py` & `pipeline_runner.py` : masquage par tranches de 32 Ko, découpage en lots (`lot_XX/anonymise_partie_XXX.txt`) et orchestration au fil de l'eau avec seconde passe automatique.

---

## 5. Persistance et confidentialité

* **Reprise incrémentale :** `transcriptions/.etat_extraction.json`, `transcriptions/.etat_sms.txt` et `resultats_anonymisation/.etat_anonymisation.json` mémorisent l'avancement à chaque lot.
* **Traçabilité masquée :** Balises `[ENVOYÉ/REÇU par <main_character_name>]`, `PARTICIPANTS` audio et masquage des données sensibles dans les noms de fichiers sources.
