# Extraction et anonymisation locale de contacts et documents

Suite d'outils Python **100 % locale** permettant d'extraire, structurer et anonymiser des carnets d'adresses (Google Contacts / Outlook CSV) ainsi que des corpus documentaires hétérogènes (PDF natifs/OCR, bureautique, e-mails, SMS/MMS, messageries instantanées, audio, images, agendas).

> **Documentation :** [Guide d'utilisation](docs/GUIDE_UTILISATION.md) | [Architecture technique](docs/ARCHITECTURE.md) | **Guides d'export :** [Contacts & E-mails](docs/exports/CONTACTS_ET_EMAILS.md) • [Google Chat & Teams](docs/exports/MESSAGERIES_PRO.md) • [WhatsApp, Messenger & Signal](docs/exports/MESSAGERIES_PERSO.md)

---

## Démarrage rapide

### 1. Installation

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
# source .venv/bin/activate  # Linux / macOS
pip install -r requirements.txt
```

### 2. Préparation des exports sources

Déposez vos fichiers CSV dans **`input_contacts/`** et vos autres documents/dossiers décompressés dans **`input_documents/`** en suivant les guides pas-à-pas dédiés :

* **[Export Contacts, Courriels & SMS](docs/exports/CONTACTS_ET_EMAILS.md)** : Google Contacts, Microsoft Outlook/365, Gmail (`.mbox`), `.eml` et SMS/MMS Android (`.xml`).
* **[Export Messageries Professionnelles](docs/exports/MESSAGERIES_PRO.md)** : Google Chat (`messages.json`) et Microsoft Teams (`messages.json` & transcriptions `.vtt`).
* **[Export Messageries Personnelles](docs/exports/MESSAGERIES_PERSO.md)** : WhatsApp (archive `.zip` **dézippée manuellement** ou `.txt`), Messenger (`.json` / `.html`) et Signal (`.json`).

### 3. Exécution des pipelines

```bash
# Étape 1 : Générer output_contacts/contacts.txt au format unifié Identifiant_Brut = Alias
python run_contacts.py

# Étape 2 : Extraire input_documents/ et produire les lots anonymisés dans anonymized_results/
python run_documents.py

# Variante : Lancer uniquement l'anonymisation complète depuis extracted_texts/ (sans extraction)
python run_documents.py --anonymize-only
python run_documents.py --anonymize-only --reset-results
```

### 4. Boucle d'audit, règles manuelles et récupération des bruts

```bash
# Compléter automatiquement les lignes 'Prénom Nom = ' ajoutées dans output_contacts/manual_contacts.txt
python run_documents.py --complete-manual

# Réappliquer uniquement output_contacts/manual_contacts.txt sur les lots existants
python run_documents.py --manual-only

# Copier les transcriptions brutes (.txt) correspondant à une liste de fichiers anonymisés
python run_documents.py --copy-unmasked liste_fichiers_a_revoir.md --unmasked-dir transcriptions_a_revoir
```

## Format unifié des règles (`Identifiant_Brut = Alias`)

Tous les fichiers de correspondance dans **`output_contacts/`** utilisent désormais le même sens de lecture (`Donnée_Sensible_À_Masquer = Valeur_De_Remplacement`) :

* **`output_contacts/contacts.txt`** (généré par `run_contacts.py`) :
  ```ini
  camille.dupont@exemple.fr=Camille D.
  06 12 34 56 78=Camille D.
  ```
* **`output_contacts/discovered_email_contacts.txt`** & **`discovered_chat_contacts.txt`** : enrichis automatiquement depuis les en-têtes `.mbox`/`.eml` et les historiques de chats.
* **`output_contacts/manual_contacts.txt`** (géré manuellement, jamais écrasé) : règles d'exceptions, variantes OCR collées (`DUPONTCAMILLE = Camille D.`) et dates de naissance sensibles (`14/07/1985 = [DATE_MASQUEE]`).

## Organisation des dossiers

* **`input_contacts/`** : dépôt des fichiers CSV Google Contacts / Outlook.
* **`input_documents/`** : dépôt des documents et dossiers décompressés à traiter.
* **`extracted_texts/`** : transcriptions brutes extraites, classées par mois (`AAAA-MM/<Catégorie>/`), avec les fichiers de suivi `.extraction_state.txt`, `.sms_state.txt` et `.email_state.txt`.
* **`anonymized_results/`** : lots finaux anonymisés (`batch_XX/anonymized_part_XXX.txt`) et état de reprise `.anonymization_state.json`.
* **`data/`** : référentiels lexicaux (`prenoms.txt`, `villes_masquees.txt`, `collisions_noms.txt`, `mots_exclus.txt`).
* **`output_contacts/`** : annuaire unifié (`contacts.txt`), règles manuelles (`manual_contacts.txt`), contacts découverts et fichiers intermédiaires (`.intermediates/`).
* **`audits/`** : rapports d'audit (`residual_names_audit.txt`, `residual_names_copy.txt`), table de correspondance JSON (`source_files_mapping.json`), rapport d'erreurs d'extraction (`extraction_report.txt`) et listes d'identifiants.
* **`docs/`** & **`tools/`** : documentation complète et utilitaires CLI (`copy_unmasked_transcriptions.py`, `complete_manual_contacts.py`, `restore_transcription_names.py`, `sync_contacts.py`, `generate_pdf_guide.py`).

## Documentation et tests

* **Guides complets** : [`docs/GUIDE_UTILISATION.md`](docs/GUIDE_UTILISATION.md) et [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — génération des versions PDF paginées :
  ```bash
  python tools/generate_pdf_guide.py docs/GUIDE_UTILISATION.md -o docs/GUIDE_UTILISATION.pdf
  python tools/generate_pdf_guide.py docs/ARCHITECTURE.md -o docs/ARCHITECTURE.pdf
  ```
* **Tests unitaires et couverture de code** :
  ```bash
  python tests/run_all_tests.py
