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

Déposez vos fichiers CSV dans **`export_contacts/`** et vos autres documents/dossiers décompressés dans **`fichiers sources/`** en suivant les guides pas-à-pas dédiés :

* **[Export Contacts, Courriels & SMS](docs/exports/CONTACTS_ET_EMAILS.md)** : Google Contacts, Microsoft Outlook/365, Gmail (`.mbox`), `.eml` et SMS/MMS Android (`.xml`).
* **[Export Messageries Professionnelles](docs/exports/MESSAGERIES_PRO.md)** : Google Chat (`messages.json`) et Microsoft Teams (`messages.json` & transcriptions `.vtt`).
* **[Export Messageries Personnelles](docs/exports/MESSAGERIES_PERSO.md)** : WhatsApp (archive `.zip` **dézippée manuellement** ou `.txt`), Messenger (`.json` / `.html`) et Signal (`.json`).

### 3. Exécution des pipelines

```bash
# Étape 1 : Générer output_contacts/contacts.txt depuis export_contacts/*.csv
python lancer_contacts.py

# Étape 2 : Extraire fichiers sources/ et produire les lots anonymisés dans resultats_anonymisation/
python lancer_documents.py

# Variante : Lancer uniquement l'anonymisation complète depuis transcriptions/ (sans extraction)
python lancer_documents.py --anonymize-only
python lancer_documents.py --anonymize-only --reset-results
```

### 4. Boucle d'audit et règles manuelles

```bash
# Compléter automatiquement les lignes 'Prénom Nom = ' ajoutées dans output_contacts/contacts_manuels.txt
python lancer_documents.py --complete-manual

# Réappliquer uniquement output_contacts/contacts_manuels.txt sur les lots existants
python lancer_documents.py --manual-only
```

---

## Organisation des dossiers

* **`data/`** : référentiels lexicaux (`prenoms.txt`, `villes_masquees.txt`, `collisions_noms.txt`, `mots_exclus.txt`).
* **`output_contacts/`** : annuaire généré (`contacts.txt`), règles manuelles (`contacts_manuels.txt`), contacts découverts (`contacts_emails_decouverts.txt`) et fichiers intermédiaires (`.intermediaires/`).
* **`audits/`** : rapports d'audit (`audit_noms_residuels.txt`, `audit_noms_residuels_copier.txt`) et tampons d'identifiants.
* **`docs/`** : documentation complète et guides d'export.

---

## Documentation et tests

* **Guides complets** : [`docs/GUIDE_UTILISATION.md`](docs/GUIDE_UTILISATION.md) et [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — génération PDF paginée :
  ```bash
  python tools/generate_pdf_guide.py docs/GUIDE_UTILISATION.md -o docs/GUIDE_UTILISATION.pdf
  ```
* **Tests unitaires et couverture de code** :
  ```bash
  python tests/run_all_tests.py
