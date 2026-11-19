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

### 2. Exécution des pipelines

```bash
# Étape 1 : Générer output_contacts/contacts.txt depuis export_contacts/*.csv
python run_contacts.py

# Étape 2 : Extraire fichiers sources/ et produire les lots anonymisés dans resultats_anonymisation/
python run_documents.py

# Variante : Lancer uniquement l'anonymisation complète depuis transcriptions/ (sans extraction)
python run_documents.py --anonymize-only
python run_documents.py --anonymize-only --reset-results
```

### 3. Boucle d'audit et règles manuelles

```bash
# Compléter automatiquement les lignes 'Prénom Nom = ' ajoutées dans output_contacts/contacts_manuels.txt
python run_documents.py --complete-manual

# Réappliquer uniquement output_contacts/contacts_manuels.txt sur les lots existants
python run_documents.py --manual-only
```

---

## Organisation des dossiers

* **`data/`** : référentiels lexicaux (`prenoms.txt`, `villes_masquees.txt`, `collisions_noms.txt`, `mots_exclus.txt`).
* **`output_contacts/`** : annuaire généré (`contacts.txt`), règles manuelles (`contacts_manuels.txt`), contacts découverts (`contacts_emails_decouverts.txt`) et fichiers intermédiaires (`.intermediaires/`).
* **`audits/`** : rapports d'audit (`audit_noms_residuels.txt`, `audit_noms_residuels_copier.txt`) et tampons d'identifiants.
* **`docs/`** : documentation complète et guides d'export.
* **`tools/`** : utilitaires CLI (`complete_manual_contacts.py`, `restore_transcription_names.py`, `sync_contacts.py`, `generate_pdf_guide.py`).

---

## Documentation et tests

* **Guides complets** : [`docs/GUIDE_UTILISATION.md`](docs/GUIDE_UTILISATION.md) et [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — génération PDF paginée :
  ```bash
  python tools/generate_pdf_guide.py docs/GUIDE_UTILISATION.md -o docs/GUIDE_UTILISATION.pdf
  ```
* **Tests unitaires et couverture de code** :
  ```bash
  python tests/run_all_tests.py
