# Guide complet d'utilisation : Export des contacts et Anonymisation

## Objectif du projet

Cette chaîne de traitement **convertit et anonymise localement** vos documents, messages et enregistrements afin de générer des lots de fichiers texte propres (180 Ko max par fichier) dépourvus de données personnelles (noms complets, téléphones, e-mails, NIR, IBAN/BIC, identifiants fiscaux/CAF/France Travail, adresses et lieux), prêts à être fournis en toute sécurité à une intelligence artificielle.

Le projet comprend **deux sous-projets indépendants** pilotés depuis la racine commune :
1. **`google_contacts_parser` (`lancer_contacts.py`)** : transforme vos exports CSV Google Contacts et Microsoft 365 / Outlook en un annuaire pseudonymisé `contacts.txt`.
2. **`doc_anonymizer` (`lancer_documents.py`)** : extrait le texte de vos fichiers et masque les données personnelles au fil de l'eau.

---

## Prérequis, environnement virtuel et initialisation

### 1. Environnement virtuel Python (`venv`)
Depuis la racine commune (`mon_espace_anonymisation/`) :
* **Créer :** `python -m venv venv`
* **Activer (Windows PowerShell) :** `.\venv\Scripts\Activate.ps1`
* **Activer (Linux / macOS) :** `source venv/bin/activate`
* **Installer les dépendances :** `pip install -r requirements.txt`

### 2. Initialiser `config.ini`
Le modèle générique **`config.example.ini`** est versionné sur Git, tandis que **`config.ini`** et vos données personnelles sont protégés par **`.gitignore`**. Copiez le modèle lors de l'installation :
* **Windows (PowerShell) :** `Copy-Item config.example.ini config.ini`
* **Linux / macOS :** `cp config.example.ini config.ini`

### 3. Arborescence de l'espace de travail

```text
mon_espace_anonymisation/
├── venv/                        # Environnement virtuel Python isolé
├── .gitignore                   # Protège config.ini et vos données sur Git
├── requirements.txt             # Dépendances Python du projet
├── config.example.ini           # Modèle de configuration générique
├── config.ini                   # Configuration personnelle active (ignorée Git)
├── prenoms.txt                  # Référentiel partagé des prénoms
├── lancer_contacts.py           # Lanceur racine du projet 1
├── lancer_documents.py          # Lanceur racine du projet 2
├── export_contacts/             # <-- Déposez ici vos exports CSV Google & Outlook
├── fichiers sources/            # <-- Déposez ici TOUS vos documents à anonymiser
├── contacts.txt                 # Annuaire généré (Alias = coordonnée)
├── contacts_indexes.txt         # Index brut (coordonnée = Prénom Nom)
├── contacts_anonymises.txt      # Index pseudonymisé (coordonnée = Prénom N.)
├── audit_noms_residuels.txt     # Rapport d'audit actualisé en temps réel
├── transcriptions/              # Extractions intermédiaires (généré auto)
├── resultats_anonymisation/     # Lots anonymisés prêts pour l'IA (généré auto)
├── projet_contacts/             # Code source du parseur de contacts
└── projet_documents/            # Code source de l'extracteur et anonymiseur
```

---

## ÉTAPE 1 : Export manuel des contacts (`export_contacts/`)

Tous les fichiers `.csv` placés dans **`export_contacts/`** commençant par `contacts` ou `autres contacts` sont fusionnés automatiquement :
* **Google Contacts (« Contacts ») :** Sur [://google.com](https://://google.com), cliquez sur **Exporter** > **Contacts** > **CSV Google** et enregistrez sous `contacts_google.csv` dans `export_contacts/`.
* **Google Contacts (« Autres contacts ») :** Ouvrez **Autres contacts**, cochez un contact, cliquez sur la flèche de sélection en haut > **Tout** > icône `⋮` > **Exporter** > **CSV Google**, et enregistrez sous `autres contacts_google.csv` dans `export_contacts/`.
* **Microsoft 365 / Outlook :** Dans **Contacts** > **Gérer les contacts** > **Exporter les contacts** (ou **Fichier** > **Importer/Exporter** > **CSV** sur Outlook Classique), enregistrez sous `contacts_outlook.csv` dans `export_contacts/`.

---

## ÉTAPE 2 : Génération et vérification de `contacts.txt`

1. **Lancer la génération** depuis la racine (avec `venv` activé) :
   ```bash
   python lancer_contacts.py
   ```
   Le script génère `contacts.txt` ainsi que `contacts_indexes.txt` et `contacts_anonymises.txt` (utilisés automatiquement pour remplacer dans tous vos documents `Prénom Nom`, `Nom Prénom` et `M. / Mme / Dr Nom` par `Prénom N.`).
2. **Vérifier `contacts.txt` :** Ajoutez si besoin vos règles manuelles (`Nom Réel = Alias`) et complétez `extra_locations` dans `config.ini` pour les communes à masquer par `[LIEU_MASQUE]`.

---

## ÉTAPE 3 : Préparation des fichiers (`fichiers sources/`)

Déposez vos documents dans **`fichiers sources/`** (sous-dossiers acceptés). Si une date figure dans le nom du fichier (ex. `2012-09-19 - Echographie.pdf`), elle est prioritaire pour le classement chronologique (`2012-09`) :
* **SMS/MMS Android :** Exportez au format **XML** via *SMS Backup & Restore* et placez le fichier dans `fichiers sources/`.
* **Formats pris en charge :** `.pdf` (natif + OCR), `.docx`, `.odt`, `.rtf`, `.xlsx`, `.pptx`, `.html`, `.txt`, `.md`, `.xml`, `.mbox`, `.eml`, `.ics`, audio (`.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.amr`, `.aup3`) et images (`.jpg`, `.png`, `.webp`, `.tif`, `.bmp`).

---

## ÉTAPE 4 : Lancement et suivi de l'anonymisation

1. **Vérifier `config.ini` :** Renseignez `main_character_name` (nom dans les SMS et appels) et personnalisez `secret_salt`.
2. **Lancer le traitement au fil de l'eau** depuis la racine :
   ```bash
   python lancer_documents.py
   ```
3. **Suivi en direct et reprise :**
   * Les moteurs lourds (Whisper et RapidOCR) se chargent uniquement si un nouvel audio ou scan est rencontré (cache local `.whisper_cache/`).
   * Les fichiers extraits apparaissent dans `transcriptions/AAAA-MM/`, les lots dans `resultats_anonymisation/lot_XX/` dès 180 Ko, et `audit_noms_residuels.txt` est actualisé à chaque lot.
   * Appuyez sur `Ctrl+C` (deux fois si un appel natif OCR/audio bloque) pour interrompre proprement avec sauvegarde de l'avancement.

---

## ÉTAPE 5 : Contrôle qualité avant envoi à une IA

1. Ouvrez **`audit_noms_residuels.txt`** : si des noms propres résiduels apparaissent, ajoutez-les dans `contacts.txt` (`Nom = Alias`), supprimez `resultats_anonymisation/` et relancez `python lancer_documents.py`.
2. Une fois l'audit propre, transmettez les fichiers de **`resultats_anonymisation/lot_01/`**, `lot_02/`, etc. à votre IA.
