# Extraction et anonymisation locale de contacts et documents

Suite d'outils Python **100 % locale** permettant d'extraire, structurer et anonymiser des carnets d'adresses (Google Contacts / Outlook CSV) ainsi que des corpus documentaires hétérogènes (PDF natifs/OCR, bureautique, e-mails, SMS/MMS, audio, images, agendas).

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

## Couverture d'anonymisation et vigilance

* **Données masquées automatiquement** :
  * **Identités** : contacts issus des référentiels, paires `Prénom Nom` / `NOM Prénom`, prénoms composés (`Jean-Eudes L.`), titres civils et médicaux (`Dr`, `Mme`, `Me`, `Famille`, y compris collés par l'OCR comme `DrLAMOTTE`), destinataires MIME et pseudonymes de plateformes.
  * **Coordonnées et identifiants** : téléphones (`TEL_001`), e-mails (`EMAIL_001`), URLs (`[URL_MASQUEE]`), NIR (`[NUM_SECU_MASQUE]`), IBAN/BIC, identifiants fiscaux, France Travail, CAF, RPPS/FINESS/CNI/MRZ, digicodes et plaques d'immatriculation.
  * **Dates et lieux** : dates exactes déclarées dans `masked_birth_dates` de `config.ini` (`[DATE_MASQUEE]` sous tous formats, y compris ISO et OCR), dates de naissance contextuelles (`[JOUR_MOIS_MASQUES]/AAAA`), adresses postales même collées par l'OCR (`[ADRESSE_MASQUEE]`), communes (`[LIEU_MASQUE]`) et établissements (`[ETABLISSEMENT_LIEU_MASQUE]`).
* **Points de vigilance (relecture via `audit_noms_residuels.txt`)** :
  * Les **prénoms seuls** et surnoms familiers sont conservés par conception (ajoutez-les dans `contacts_manuels.txt` si vous souhaitez les pseudonymiser).
  * Les **noms de famille isolés** hors carnet d'adresses, les **employeurs/écoles spécifiques**, les **identifiants numériques libres sans libellé** et le **contenu clinique narratif** nécessitent une vérification finale dans `audit_noms_residuels.txt`.

---

## Documentation et tests

* **Guide complet** : consultez [`GUIDE_UTILISATION.md`](GUIDE_UTILISATION.md) ou générez sa version PDF paginée :
  ```bash
  python tools/generate_pdf_guide.py GUIDE_UTILISATION.md -o GUIDE_UTILISATION.pdf
  ```
* **Tests unitaires et d'intégration** :
  ```bash
  python tests/run_all_tests.py
