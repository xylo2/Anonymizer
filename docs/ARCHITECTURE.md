# Architecture Technique : Chaîne d'Anonymisation Documentaire

> **Navigation :** [← Retour au README](../README.md) | [Guide pas-à-pas](../GUIDE_UTILISATION.md) | [Guide d'utilisation](GUIDE_UTILISATION.md) | **Guides d'export :** [Contacts & E-mails](exports/CONTACTS_ET_EMAILS.md) • [Google Chat & Teams](exports/MESSAGERIES_PRO.md) • [WhatsApp, Messenger & Signal](exports/MESSAGERIES_PERSO.md)

## 1. Vue d'ensemble du système

L'écosystème repose sur **deux sous-projets autonomes** (`google_contacts_parser` et `doc_anonymizer`), un **socle commun (`common/`)** et une **interface graphique guidée (`gui_anonymizer.py`)** exécutés dans un environnement virtuel Python (`venv/` ou `.venv/`). Chaque dossier créé via l'interface dispose de son espace isolé sous `dossiers/<nom>/` avec son propre `config.ini`, tandis qu'en ligne de commande les lanceurs (`run_contacts.py`, `run_documents.py`) utilisent `config.ini` (copié depuis `config.example.ini`) ou l'option `--config <chemin>`. Les données personnelles et `config.ini` sont protégés par `.gitignore`.

```text
+----------------------------------------------------------------------+

|              RESSOURCES PARTAGÉES (RACINE & DATA/)                   |
| [venv/] | [requirements.txt] | [.gitignore] | [common/core_utils.py] |
| [data/prenoms.txt, villes_masquees.txt, collisions_noms.txt, ...]    |
| [gui_anonymizer.py] <-> [dossiers/<nom>/config.ini] <-> [CLI runners]|
+--------|----------------------------------------|--------------------+

         |                                        |
         v                                        v
+----------------------------------+   +-------------------------------+

| PROJET 1: google_contacts_parser |   | PROJET 2: doc_anonymizer      |
| [input_contacts/*.csv, *.vcf]    |   | [input_documents/]            |
|        |                         |   |        |                      |
|        v                         |   |        v (Extraction)         |
| Extraction -> Anonymisation      |   | [extracted_texts/AAAA-MM/...] |
| -> Pré-scan chats/mails & Fusion |   |        |                      |
|        |                         |   |        v (Au fil de l'eau)    |
|        +-> [.intermediates/*]    |   | Masquage & Audit temps réel   |
|        +-> [output_contacts/     |   |        |                      |
|             contacts.txt]        |   |        +-> [batch_XX/*.txt]   |
+----------------------------------+   |        +-> [audits/*.txt,     |

                                       |             *.json]           |
                                       |        +-> [pack_avocat/*]    |
                                       +-------------------------------+
```

## 2. Socle commun (`common/`), modules clés et répertoires

* **`common/core_utils.py` (`SharedCoreUtils`)** : normalisation Unicode (NFKD), téléphones français (`0XXXXXXXXX`), suppression des alias `+...` sur les e-mails, écriture atomique sur disque et inhibition de mise en veille.
* **`doc_anonymizer/extraction_runner.py` & `doc_anonymizer/extraction_helpers.py`** : orchestration parallèle de l'extraction (`DocumentExtractionRunner`), chargement des listes blanches (`ExtractionFilterLoader`) et rapports finaux (`ExtractionReportWriter`).
* **`doc_anonymizer/outlook_extractor.py` (`OutlookArchiveExtractor`)** : lecture native des archives et messages du client lourd Outlook (`.pst`, `.ost`, `.msg`) et extraction de leurs pièces jointes PDF.
* **`doc_anonymizer/sensitive_masker.py` & `doc_anonymizer/masker_lexicons.py`** : moteur de masquage contextuel multi-passes (`SensitiveTextMasker`) et dictionnaires lexicaux (`MaskerLexicons`).
* **`doc_anonymizer/audit_state_manager.py` & `doc_anonymizer/audit_lexicons.py`** : détection des noms résiduels, rapprochement phonétique, persistance JSON (`AuditAndStateManager`) et stopwords (`AuditLexicons`).
* **`gui_anonymizer.py` & `doc_anonymizer/gui_*.py`** : interface Tkinter guidée modulaire (`AnonymizerGuiApp`, `AnonymizerGuiController`, `GuiGateMixin`, `GuiIngestMixin`, `GuiPagesMixin`, `GuiPagesFiltersMixin`, `BeforeAfterPreviewDialog`, `ExportGuideDialog`, `CleanDropdown` dans `gui_dropdown.py`, dialogue d'erreur critique dans `gui_startup_error.py`).
* **`doc_anonymizer/dossier_exporter.py` (`LawyerDossierExporter`)** : génère le Pack Avocat nominatif et chronologique (`Recueil_Chronologique_Avocat.docx`, `Bordereau_des_Pieces.csv`, `Pieces_Numerotees/` avec originaux audio/images côte à côte et `Pack_Avocat_Complet.zip`).
* **`doc_anonymizer/source_mapping_manager.py` (`SourceMappingManager`)** : maintient `audits/source_files_mapping.json` reliant chaque chemin anonymisé (`# SOURCE TRANSCRIPTION : ...`) au fichier extrait brut (`extracted_texts/`), au fichier source initial (`input_documents/`) et au lot final (`batch_XX/`).
* **`tools/`** :
  * `copy_unmasked_transcriptions.py` (`UnmaskedTranscriptionCopier`) : copie les transcriptions `.txt` brutes (`extracted_texts/`) correspondant à une liste de fichiers anonymisés via `audits/source_files_mapping.json`.
  * `complete_manual_contacts.py` (`ManualContactsAutoCompleter`) : complète automatiquement les lignes `Prénom Nom = ` vides dans `output_contacts/manual_contacts.txt`.
  * `sync_contacts.py` (`ContactsSynchronizer`) : synchronise `output_contacts/contacts.txt` en préservant `manual_contacts.txt`.
  * `restore_transcription_names.py` (`TranscriptionNameRestorer`) : restaure les noms d'origine dans `extracted_texts/` et reclasse par période `AAAA-MM`.
  * `generate_app_icon.py` & `install_desktop_shortcut.py` : génèrent les icônes SVG/PNG/ICO et les raccourcis bureau Windows/Linux.
  * `generate_pdf_guide.py` & `run_tests_clip.py` : convertit les `.md` en `.pdf` et exécute `tests/run_all_tests.py`.

---

## 3. Persistance et reprise incrémentale

* **Extraction (`extracted_texts/`)** : `.extraction_state.txt` (chemins déjà extraits), `.sms_state.txt` (numéros SMS traités) et `.email_state.txt`.
* **Anonymisation (`anonymized_results/`)** : `.anonymization_state.json` mémorise l'avancement à chaque lot écrit (`batch_XX/anonymized_part_XXX.txt`), les statistiques du tableau de bord, le coffre de réversibilité (`audits/deanon_vault.json`) et la traçabilité (`audits/source_files_mapping.json`).
