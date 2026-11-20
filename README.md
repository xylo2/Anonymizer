# Anonymiseur Local de Documents Confidentiels

Outil **100 % local et hors-ligne** (Windows & Linux) permettant d'extraire, de classer chronologiquement (`AAAA-MM`) et d'anonymiser des dossiers documentaires volumineux et hétérogènes (santé, affaires familiales, démarches prud'homales, litiges administratifs) avant toute analyse ou partage sécurisé.

Aucun document, contact ou enregistrement audio n'est envoyé sur Internet.

---

## Points forts

* **Multi-formats natif** : PDF natifs et scannés (OCR Tesseract), documents Word/LibreOffice (`.docx`, `.odt`), tableaux (`.xlsx`, `.ods`, `.csv`), e-mails (`.mbox`, `.eml`), SMS/MMS Android (`SMS Backup & Restore` `.xml`), messageries instantanées (Google Chat, WhatsApp, Facebook/Instagram, Microsoft Teams `.json` / `.vtt`), pages Web/HTML et fichiers audio/vidéo (transcription locale via `faster-whisper`).
* **Anonymisation cohérente et intelligente** :
  * Abréviation stable des personnes (`Prénom N.`) avec gestion automatique des homonymes (`Jean D.`, `Jean Du.`, `Jean Du-2`).
  * Extraction automatique des noms de famille depuis `contacts.txt`, détection des formes collées OCR (`PrénomNom` / `NomPrénom`), des titres médicaux/civils (`Dr`, `Docteur`, `Mme`, `Me`), des initiales (`I. NOM`) et des noms composés.
  * Masquage des adresses e-mail (`Contact_Mail_001` / `EMAIL_001`), numéros de téléphone (`Contact_Tel_001` / `TEL_001`, y compris dictés à l'oral), numéros de Sécurité sociale (NIR), IBAN/BIC, références fiscales/CAF/CNI, plaques d'immatriculation, zones MRZ, adresses postales, communes et dates de naissance.
* **Double mode d'utilisation (Windows & Linux)** :
  * **Interface graphique guidée** (`gui_anonymizer.py`) : création de dossiers isolés par affaire/salarié/enfant, dépôt des documents, barre de progression et validation visuelle des noms restants en 1 clic.
  * **Ligne de commande** (`run_documents.py`, `run_contacts.py`) : traitement automatisable et options avancées (`--anonymize-only`, `--reset-results`, `--config`).
* **Audit intégré** : génère automatiquement la liste des noms potentiels résiduels (`audits/residual_names_copy.txt`) prêts à être approuvés ou ignorés.

---

## Prérequis système (Windows & Linux)

### 1. Python 3.10+ et bibliothèques Python
```bash
pip install pypdf pdf2image pytesseract pillow python-docx odfpy openpyxl faster-whisper
```
*(Sous Linux Debian/Ubuntu, installez également `python3-tk` si `tkinter` n'est pas préinstallé : `sudo apt install python3-tk`.)*

### 2. Outils système externes (pour PDF scannés et audio)
* **Tesseract OCR** (langue française `fra`) + **Poppler** (`pdftoppm`) pour les PDF images/scannés.
* **FFmpeg** pour la conversion et transcription des fichiers audio/vidéo.

---

## Démarrage rapide

### Option A — Interface graphique (recommandé)
* **Sous Windows** : double-cliquez sur **`Lancer_Anonymiseur.bat`** (ou lancez `python gui_anonymizer.py`).
* **Sous Linux / macOS** : lancez **`./lancer_anonymiseur.sh`** ou **`python3 gui_anonymizer.py`**.

### Option B — Ligne de commande (Windows & Linux)
```bash
# 1. Extraire, pré-scanner les chats/e-mails et unifier les contacts
python run_contacts.py

# 2. Extraire tous les documents sources et produire les lots anonymisés
python run_documents.py

# 3. Ré-anonymiser uniquement (rapide, après ajout de règles dans manual_contacts.txt)
python run_documents.py --anonymize-only --reset-results

# 4. Cibler un dossier isolé spécifique
python run_documents.py --config dossiers/Mon_Dossier/config.ini
```

---

## Structure du projet

```text
├── gui_anonymizer.py              # Interface graphique Tkinter (Windows & Linux)
├── Lancer_Anonymiseur.bat         # Lanceur double-clic Windows
├── lancer_anonymiseur.sh          # Lanceur shell Linux / macOS
├── run_documents.py               # Point d'entrée CLI du pipeline documentaire
├── run_contacts.py                # Point d'entrée CLI du pipeline contacts + pré-scan
├── config.ini                     # Configuration principale
├── GUIDE_UTILISATION.md           # Guide pas-à-pas grand public (parents, syndicats)
├── LICENSE                        # Licence GNU GPL v3 (copyleft fort)
├── data/                          # Dictionnaires partagés (prénoms, villes, exclusions)
├── input_documents/               # Documents bruts à traiter
├── input_contacts/                # Exports CSV de contacts bruts
├── output_contacts/               # Règles générées (contacts.txt, manual_contacts.txt...)
├── extracted_texts/               # Transcriptions brutes classées par mois (AAAA-MM)
├── anonymized_results/            # Lots finaux anonymisés (batch_XX/anonymized_part_XXX.txt)
├── audits/                        # Rapports de vérification des noms résiduels
├── dossiers/                      # Espaces isolés créés depuis l'interface graphique
├── doc_anonymizer/                # Modules du moteur documentaire et de l'interface
└── tests/                         # Suite de tests unitaires et d'intégration
```

---

## Exécution des tests

```bash
python tests/run_all_tests.py
# Ou avec résumé compact copié automatiquement dans le presse-papiers :
python tools/run_tests_clip.py
```

---

## Licence

Ce programme est un logiciel libre distribué sous licence **GNU General Public License v3.0 (GPL-3.0)** — voir le fichier [`LICENSE`](LICENSE). Toute redistribution, modifiée ou non, doit conserver cette licence et mettre à disposition le code source complet.
