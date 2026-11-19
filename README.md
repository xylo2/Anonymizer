# Extraction et anonymisation locale de contacts et documents

Suite d'outils Python **100 % locale** permettant d'extraire, structurer et anonymiser des carnets d'adresses (Google Contacts / Outlook CSV) ainsi que des corpus documentaires hétérogènes (PDF, bureautique, e-mails, SMS/MMS, audio, images, agendas).

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
# Étape 1 : Générer contacts.txt et noms_famille_contacts.txt depuis export_contacts/*.csv
python lancer_contacts.py

# Étape 2 : Extraire fichiers sources/ et produire les lots anonymisés dans resultats_anonymisation/
python lancer_documents.py
```

### 3. Boucle d'audit et règles manuelles

```bash
# Compléter automatiquement les lignes 'Prénom Nom = ' ajoutées dans contacts_manuels.txt
python lancer_documents.py --complete-manual

# Réappliquer uniquement contacts_manuels.txt sur les lots existants
python lancer_documents.py --manual-only
```

---

## Documentation et tests

* **Guide complet** : consultez [`GUIDE_UTILISATION.md`](GUIDE_UTILISATION.md) ou générez sa version PDF paginée :
  ```bash
  python tools/generate_pdf_guide.py GUIDE_UTILISATION.md -o GUIDE_UTILISATION.pdf
  ```
* **Tests unitaires et d'intégration** :
  ```bash
  python tests/run_all_tests.py
