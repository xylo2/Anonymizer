# Chaîne d'Anonymisation Documentaire & Contacts

Ce projet permet de **convertir, structurer et anonymiser localement** l'ensemble de vos documents, messages, enregistrements vocaux et carnets d'adresses afin de générer des lots de fichiers texte propres, chronologiques et dépourvus de données personnelles. 

Les fichiers générés sont calibrés (180 Ko maximum par fichier) pour être **transmis en toute sécurité à une intelligence artificielle** (LLM, analyse médicale ou administrative, synthèse documentaire) sans jamais exposer d'informations nominatives ou sensibles.

---

## Fonctionnalités principales

* **100 % Local et Confidentiel :** Aucune donnée n'est envoyée sur Internet. L'extraction OCR, la transcription vocale (Whisper) et le masquage s'exécutent intégralement sur votre machine.
* **Fusion & Pseudonymisation d'annuaires (`projet_contacts`) :**
  * Supporte les exports CSV **Google Contacts** (« Contacts » et « Autres contacts ») et **Microsoft 365 / Outlook**.
  * Déduit les identités depuis les adresses e-mail, gère les couples et les homonymes (`Prénom N.`), et génère le référentiel partagé `contacts.txt`.
* **Extraction Multi-Formats & Traitement au Fil de l'Eau (`projet_documents`) :**
  * **Documents & Bureautique :** `.pdf` (texte natif + OCR automatique via RapidOCR sur les scans), `.docx`, `.odt`, `.rtf`, `.xlsx`, `.pptx`, `.html`, `.txt`, `.md`, `.ics`.
  * **Communications :** Sauvegardes Android SMS/MMS (`.xml`), archives e-mails (`.mbox`, `.eml` avec pièces jointes PDF).
  * **Audio & Images :** Transcription vocale locale via `faster-whisper` (`.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.amr`, projets Audacity `.aup3`) et OCR sur images (`.jpg`, `.png`, `.webp`, `.tif`, `.bmp`).
* **Masquage Avancé & Audit en Temps Réel :**
  * Remplace automatiquement les coordonnées connues par leur alias, ainsi que les noms complets déduits (`Prénom Nom`, `Nom Prénom`, `Titre Nom` -> `Prénom N.`).
  * Masque les **NIR** (`[NUM_SECU_MASQUE]`), **IBAN/BIC**, **numéros fiscaux**, **identifiants France Travail / CAF / MSA**, **adresses postales** (`[ADRESSE_MASQUEE]`) et **communes/lieux** (`[LIEU_MASQUE]`).
  * Pseudonymise de façon déterministe (SHA-256 salé) les numéros de téléphone (`TEL_XXX`) et e-mails (`EMAIL_XXX`) inconnus.
  * Génère en temps réel un rapport **`audit_noms_residuels.txt`** pour détecter d'éventuels noms propres restants avant partage.
* **Confort & Robustesse :**
  * Reprise incrémentale (seuls les nouveaux fichiers sont traités lors des relances).
  * Chargement paresseux (*Lazy Loading*) des modèles lourds (Whisper et RapidOCR) avec cache local hors-ligne.
  * Maintien en éveil du système (Windows et Linux) durant les traitements longs et arrêt propre sur `Ctrl+C`.

---

## Exemples de transformations (Avant / Après)

### 1. Extrait de compte-rendu PDF ou courrier administratif
**Texte brut extrait :**
> Compte-rendu de consultation du Dr Midieux concernant Aurélien Midieux (NIR : 1 85 05 14 118 042 19). Domicilié au 14 rue des Lilas, 14000 Caen. Contact : 06 17 17 17 17 ou aurelien.midieux@exemple.fr. Règlement par virement sur FR76 3000 6000 0112 3456 7890 189.

**Résultat anonymisé dans `lot_01/anonymise_partie_001.txt` :**
> Compte-rendu de consultation du Aurélien M. concernant Aurélien M. (NIR : [NUM_SECU_MASQUE]). Domicilié au [ADRESSE_MASQUEE], [LIEU_MASQUE]. Contact : Aurélien M. ou Aurélien M.. Règlement par virement sur [IBAN_MASQUE].

### 2. Extrait d'échange SMS (`sms.xml`)
**Résultat anonymisé :**
> `[2025-04-12 14:32:10] [ENVOYÉ par Personnage_Principal à Aurélien M.]`
> Bonjour, je vous transmets l'attestation avec mon numéro allocataire [NUM_ALLOCATAIRE_MASQUE] depuis [LIEU_MASQUE].

---

## Architecture de l'espace de travail

```text
mon_espace_anonymisation/
├── venv/                              # Environnement virtuel Python isolé
├── .gitignore                         # Exclusions Git des données sensibles et de config.ini
├── requirements.txt                   # Dépendances Python du projet
├── config.example.ini                 # Modèle de configuration versionné
├── config.ini                         # Configuration personnelle active (ignorée par Git)
├── prenoms.txt                        # Référentiel UNIQUE des prénoms partagé
├── lancer_contacts.py                 # Lanceur racine : génération de contacts.txt
├── lancer_documents.py                # Lanceur racine : extraction et anonymisation
│
├── export_contacts/                   # <-- Déposez ici vos exports CSV Google & Outlook
├── fichiers sources/                  # <-- Déposez ici TOUS vos documents à anonymiser
│
├── contacts.txt                       # Annuaire pseudonymisé généré (Alias = coordonnée)
├── audit_noms_residuels.txt           # Rapport d'audit actualisé en temps réel
├── transcriptions/                    # Extractions intermédiaires classées par AAAA-MM
├── resultats_anonymisation/           # <-- Lots anonymisés prêts pour l'IA (lot_XX/*.txt)
│
├── projet_contacts/                   # Code source du parseur de contacts
└── projet_documents/                  # Code source de l'extracteur et anonymiseur
    ├── GUIDE_UTILISATION.md           # Guide détaillé pas à pas
    ├── ARCHITECTURE.md                # Documentation technique complète
    └── generate_pdf_guide.py          # Utilitaire de génération des guides en PDF
```

---

## Installation rapide

1. **Créer et activer l'environnement virtuel Python :**
   * **Windows (PowerShell) :**
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   * **Linux / macOS :**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

2. **Installer les dépendances :**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialiser votre configuration personnelle :**
   Copiez le modèle `config.example.ini` vers `config.ini` (ignoré par Git), puis personnalisez `main_character_name`, `secret_salt` et `extra_locations` :
   * **Windows (PowerShell) :** `Copy-Item config.example.ini config.ini`
   * **Linux / macOS :** `cp config.example.ini config.ini`

---

## Utilisation

### 1. Générer l'annuaire anonymisé (`contacts.txt`)
Placez vos exports CSV (Google Contacts et/ou Outlook) dans le dossier **`export_contacts/`**, puis lancez :
```bash
python lancer_contacts.py
```

### 2. Extraire et anonymiser vos documents
Placez vos documents (PDF, Word, SMS XML, e-mails, enregistrements audio...) dans **`fichiers sources/`**, vérifiez votre `config.ini`, puis lancez :
```bash
python lancer_documents.py
```

### 3. Contrôler avant envoi à une IA
1. Consultez **`audit_noms_residuels.txt`** à la racine : si un nom propre résiduel apparaît, ajoutez-le dans `contacts.txt` (`Nom Réel = Alias`), supprimez `resultats_anonymisation/` et relancez `python lancer_documents.py`.
2. Transmettez les fichiers générés dans **`resultats_anonymisation/lot_01/`**, `lot_02/`, etc. à votre intelligence artificielle.

---

## Guide de dépannage (FAQ)

* **`ModuleNotFoundError: No module named 'docx'` (ou `odf`, `pymupdf`...) :**
  Vérifiez que votre environnement virtuel `venv` est bien activé dans votre terminal (`(venv)` affiché en début de ligne), puis lancez `pip install -r requirements.txt`.
* **Le dossier `resultats_anonymisation/` reste vide pendant l'exécution :**
  C'est normal dans deux cas : soit le script parcourt des fichiers déjà extraits lors d'un passage précédent (le rattrapage d'anonymisation s'exécute juste après la fin de l'inventaire), soit le volume cumulé en mémoire n'a pas encore atteint le seuil d'écriture de **180 Ko** (`max_batch_bytes` dans `config.ini`).
* **Comment relancer uniquement l'anonymisation après avoir ajouté un nom dans `contacts.txt` ?**
  Supprimez le dossier `resultats_anonymisation/` (tout en conservant `transcriptions/`) et relancez `python lancer_documents.py`. L'extraction OCR/Whisper ne sera pas refaite et seule l'anonymisation s'exécutera en quelques secondes.
* **Le premier lancement semble long :**
  La reconnaissance optique (RapidOCR sur les PDF scannés) et la transcription vocale (Whisper) s'exécutent sur processeur (CPU). Une fois ce premier passage terminé, les relances suivantes n'analysent que les nouveaux documents ajoutés.
* **Arrêter le script proprement en cours de route :**
  Appuyez sur `Ctrl+C` (une seconde fois si un appel natif OCR ou Whisper est en cours). Les transcriptions terminées, les lots écrits et `audit_noms_residuels.txt` sont sauvegardés sur le disque.

---

## Documentation complémentaire

* **Guide complet d'utilisation :** `projet_documents/GUIDE_UTILISATION.md`
* **Architecture technique :** `projet_documents/ARCHITECTURE.md`
* **Génération des guides au format PDF paginé :**
  ```bash
  python projet_documents/generate_pdf_guide.py projet_documents/GUIDE_UTILISATION.md
  python projet_documents/generate_pdf_guide.py projet_documents/ARCHITECTURE.md
  ```

---

## Licence & Confidentialité

Ce projet est distribué sous licence **MIT**. Il est conçu pour un usage personnel et local : grâce au fichier `.gitignore` fourni, vos données personnelles (`export_contacts/`, `fichiers sources/`, `transcriptions/`, `resultats_anonymisation/`, `contacts.txt`, `audit_noms_residuels.txt`) ainsi que votre `config.ini` personnel ne seront jamais envoyés sur un dépôt Git.
