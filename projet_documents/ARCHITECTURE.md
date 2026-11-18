# Architecture Technique : Chaîne d'Anonymisation Documentaire

## 1. Vue d'ensemble du système

L'écosystème repose sur **deux sous-projets autonomes** exécutés dans un environnement virtuel Python (`venv/`), pilotés depuis la racine par un **fichier de configuration unique (`config.ini`, initialisé depuis `config.example.ini`)**, un **référentiel de prénoms partagé (`prenoms.txt`)** et deux lanceurs (`lancer_contacts.py`, `lancer_documents.py`). Les données personnelles et `config.ini` sont protégés par `.gitignore`.

```text
+----------------------------------------------------------------------+

|              RESSOURCES PARTAGÉES (RACINE COMMUNE)                   |
| [venv/] | [requirements.txt] | [.gitignore] | [prenoms.txt]          |
| [config.example.ini] -> [config.ini] <---> [contacts.txt]            |
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
|        +-> [contacts.txt]        |   |        |                      |
+----------------------------------+   |        +-> [lot_XX/*.txt]     |

                                       |        +-> [audit_noms...txt] |
                                       +-------------------------------+
```

---

## 2. Sous-projet 1 : `google_contacts_parser`

Transforme des exports CSV multi-sources (**Google Contacts** et **Microsoft 365 / Outlook**) en un annuaire inversé et trié (`Alias = coordonnée`) via la bibliothèque standard Python.

### 2.1 Fichiers principaux
* `lancer_contacts.py` (racine) & `projet_contacts/run_contacts_pipeline.py` : points d'entrée CLI avec gestion propre de `Ctrl+C`.
* `projet_contacts/google_contacts_parser/` :
  * `config_manager.py` (`ContactsConfig`) : résout les chemins depuis `config.ini`, charge la géographie française et liste les CSV dans `export_contacts/`.
  * `geo_data.py` & `text_utils.py` : catalogue géographique français, normalisation Unicode et nettoyage des enseignes.
  * `csv_reader.py` (`GoogleContactsReader`) : détection auto des délimiteurs (`,` et `;`), en-têtes Google/Outlook (FR/EN), couples et déduction depuis les e-mails.
  * `anonymizer.py` & `pipeline_runner.py` : pseudonymisation des noms (`Prénom N.`), homonymes (`Jean Du-2`) et exécution en 4 étapes (`contacts_indexes.txt` -> `contacts_anonymises.txt` -> `contacts_dedoublonnes.txt` -> `contacts.txt`).

---

## 3. Sous-projet 2 : `doc_anonymizer`

Assure l'extraction multi-formats, l'OCR/audio et l'anonymisation **au fil de l'eau**.

### 3.1 Fichiers principaux
* `lancer_documents.py` (racine) & `projet_documents/run_doc_anonymizer_pipeline.py` : points d'entrée avec double interruption `Ctrl+C` sécurisée et anti-veille.
* `projet_documents/generate_pdf_guide.py` : convertit les `.md` en `.pdf` paginés via PyMuPDF (`DocumentWriter` en mémoire).
* `projet_documents/doc_anonymizer/` :
  * `config_manager.py` (`PipelineConfig`) : résout les chemins de `config.ini` et charge `prenoms.txt`, `extra_locations`, `contacts_indexes.txt` et `contacts_anonymises.txt`.
  * `power_manager.py` : empêche la mise en veille OS (Windows API / `systemd-inhibit` Linux).
  * `text_utils.py` : regex de masquage (NIR, IBAN, BIC, SPI fiscal, France Travail, CAF/MSA, adresses, codes postaux) et détection prioritaire de la date du nom de fichier (`AAAA-MM`).
  * `office_extractors.py` : extraction PDF (`pymupdf` + chargement paresseux `rapidocr-onnxruntime`), `.docx`, `.odt`, `.rtf`, `.xlsx`, `.pptx`, `.html`, `.txt`, `.md`, images et `.ics`.
  * `comm_extractors.py` : parsing streaming XML SMS/MMS, `.mbox`/`.eml` (priorité date du nom `.eml` + pièces jointes PDF), audio `faster-whisper` (chargement paresseux + cache `.whisper_cache/`) et Audacity `.aup3`.
  * `extraction_runner.py` : inventaire de `fichiers sources/` et classement par mois (`transcriptions/AAAA-MM/Catégorie/`).
  * `contact_rules_loader.py` : trie `contacts.txt` et déduit les noms complets (`Prénom Nom`, `Nom Prénom`, `Titre Nom` -> `Prénom N.`) depuis `contacts_indexes.txt` / `contacts_anonymises.txt`.
  * `audit_state_manager.py` : persistance JSON (`.etat_anonymisation.json`), jetons SHA-256 (`TEL_XXX`, `EMAIL_XXX`) et mise à jour en temps réel de `audit_noms_residuels.txt`.
  * `anonymization_runner.py` & `pipeline_runner.py` : masquage, découpage en lots de 180 Ko (`lot_XX/anonymise_partie_XXX.txt`) et orchestration au fil de l'eau.

---

## 4. Persistance et confidentialité

* **Reprise incrémentale :** `transcriptions/.fichiers_extraits.txt`, `transcriptions/.sms_numeros_traites.txt` et `resultats_anonymisation/.etat_anonymisation.json` mémorisent l'avancement à chaque lot.
* **Traçabilité masquée :** Balises `[ENVOYÉ/REÇU par <main_character_name>]`, `PARTICIPANTS` audio et masquage des données sensibles dans les noms de fichiers sources.
