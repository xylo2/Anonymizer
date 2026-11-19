# Guide d'utilisation — Extraction et anonymisation locale

Ce dépôt fournit une suite complète d'outils Python fonctionnant **100 % en local** (sans envoi de données vers le cloud) pour préparer un corpus documentaire avant analyse.

Il repose sur deux pipelines complémentaires pilotés par un fichier `config.ini` partagé :

1. **`lancer_contacts.py` (`google_contacts_parser`)** : extrait, nettoie, anonymise et dédoublonne les exports Google Contacts et Microsoft Outlook (`.csv`) afin de générer les référentiels d'alias (`contacts.txt` et `noms_famille_contacts.txt`).
2. **`lancer_documents.py` (`doc_anonymizer`)** : extrait le texte de documents multi-formats (PDF natifs ou scannés, Word, Excel, PowerPoint, LibreOffice, e-mails, SMS/MMS, audio, images, agendas) et anonymise l'ensemble des données personnelles, médicales et administratives.

---

## 1. Installation et prérequis

### Environnement Python

Le projet nécessite **Python 3.10 ou supérieur**. Il est recommandé d'utiliser un environnement virtuel dédié :

```bash
python -m venv .venv
# Activation sous Windows (PowerShell) :
.venv\Scripts\Activate.ps1
# Activation sous Linux / macOS :
source .venv/bin/activate
```

### Dépendances externes

L'installation des bibliothèques d'extraction bureautique, d'OCR et de transcription vocale s'effectue via `requirements.txt` :

```bash
pip install -r requirements.txt
```

*Note : le pipeline de contacts (`lancer_contacts.py`) ainsi que l'utilitaire `watch_clipboard.py` n'utilisent que la bibliothèque standard Python et ne requièrent aucune installation supplémentaire.*

---

## 2. Architecture du projet

```text
.
├── config.ini                         # Configuration centralisée des deux pipelines
├── lancer_contacts.py                 # Point d'entrée : traitement des contacts CSV
├── lancer_documents.py                # Point d'entrée : extraction et anonymisation des documents
├── prenoms.txt                        # Référentiel partagé des prénoms connus
├── villes_masquees.txt                # Communes et lieux-dits supplémentaires à masquer
├── mots_exclus.txt                    # Sigles et mots courants ignorés par l'audit
├── collisions_noms.txt                # Noms de famille homographes de mots courants
├── common/                            # Utilitaires partagés (Unicode, écriture atomique, durées)
├── google_contacts_parser/            # Module d'extraction et d'anonymisation des contacts
├── doc_anonymizer/                    # Module d'extraction multi-formats et de masquage
├── tools/                             # Outils annexes (complétion manuelle, sync, export PDF)
└── tests/                             # Suite de tests unitaires et d'intégration
## 3. Étape 1 : Préparer le référentiel des contacts

Avant d'anonymiser des documents, il est conseillé de générer la table de correspondance des contacts à partir de vos exports CSV (Google Contacts ou Outlook).

### 3.1 Placer les fichiers CSV

Déposez vos fichiers `.csv` (préfixés par `contacts` ou `autres contacts` selon `config.ini`) dans le dossier `export_contacts/`.

### 3.2 Lancer le pipeline contacts

```bash
python lancer_contacts.py
```

Option disponible :
* `-c CHEMIN` / `--config CHEMIN` : spécifie un fichier de configuration alternatif (défaut : `config.ini`).

### 3.3 Fichiers générés

Le pipeline exécute 4 étapes séquentielles et produit les fichiers suivants :

* **`contacts_indexes.txt`** : extraction brute `coordonnée = Identité`.
* **`contacts_anonymises.txt`** : remplacement des noms de famille par leur initiale (`Jean Dupont` -> `Jean D.`), conservation des noms d'enseignes/sociétés et différenciation automatique des homonymes (`Jean Du.`, `Jean Du-2`).
* **`contacts_dedoublonnes.txt`** : suppression des alias `+...` d'e-mails et fusion des libellés partageant une même coordonnée.
* **`contacts.txt`** : fichier final inversé et trié alphabétiquement (`Jean D. = 0601020304`), utilisé directement par l'anonymiseur de documents.
* **`noms_famille_contacts.txt`** : liste des noms de famille isolés extraits des contacts physiques (hors collisions lexicales).
* **`prenoms_suggeres.txt`** : créé uniquement si des prénoms inédits sont détectés dans les CSV afin de vous permettre d'enrichir `prenoms.txt`.

---

## 4. Étape 2 : Extraire et anonymiser les documents

### 4.1 Formats pris en charge

Placez tous vos fichiers bruts dans le dossier `fichiers sources/`. Le pipeline prend en charge :

* **Documents bureautiques et texte** : `.pdf` (texte natif et pages scannées via RapidOCR), `.docx`, `.odt`, `.rtf`, `.xlsx`, `.pptx`, `.txt`, `.md`, `.html`, `.htm`.
* **Communications et agendas** : exports SMS/MMS `.xml` (avec protection anti-XXE), archives e-mails `.mbox` et `.eml` (pièces jointes PDF incluses), calendriers `.ics`.
* **Audio et images** : `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.amr`, projets Audacity `.aup3` (transcrits localement via `faster-whisper`), ainsi que les images `.jpg`, `.png`, `.webp`, `.tiff`, `.bmp` (via RapidOCR).
### 4.2 Lancer le pipeline documents

```bash
python lancer_documents.py
```

Le traitement s'exécute en **parallèle au fil de l'eau** : les threads d'extraction alimentent `transcriptions/` (classé par période `AAAA-MM` et par catégorie) tandis que le thread principal anonymise et écrit les lots dans `resultats_anonymisation/lot_XX/`. La mise en veille du système (Windows et Linux) est automatiquement inhibée pendant l'exécution.

### 4.3 Options de ligne de commande (`lancer_documents.py`)

* `-c CHEMIN`, `--config CHEMIN` : chemin vers `config.ini`.
* `--sync-contacts CHEMIN` : fusionne et copie un fichier `contacts.txt` externe avant le lancement.
* `--overwrite-contacts` : réinitialise la protection des règles manuelles lors d'une synchronisation.
* `--allow-sleep` : autorise la mise en veille de l'ordinateur pendant le traitement.
* `--complete-manual` : remplit automatiquement les lignes incomplètes (`Prénom Nom = `) dans `contacts_manuels.txt`.
* `--dry-run` : prévisualise les complétions de `contacts_manuels.txt` sans modifier le disque.
* `--manual-only` : réapplique uniquement `contacts_manuels.txt` sur les lots déjà générés dans `resultats_anonymisation/` sans relancer l'extraction.

---

## 5. Couverture d'anonymisation et limites

### 5.1 Données systématiquement masquées

* **Identités des personnes** :
  * Contacts issus de `contacts.txt`, `contacts_manuels.txt` et `contacts_emails_decouverts.txt` (y compris en ordre inversé `Nom Prénom` et formes collées OCR).
  * Paires `Prénom Nom` et `NOM Prénom`, prénoms composés (`Jean-Eudes L.`, `Jean Eudes M.`, `J.-Marc A.`) et noms précédés d'une civilité ou d'un titre médical/juridique (`Dr`, `Docteur`, `Mme`, `M.`, `Pr`, `Me`, `Famille`), y compris sans espace OCR (`DrLAMOTTE` -> `Dr L.`, `MMEAlice` -> `MME Alice`).
  * Destinataires d'en-têtes MIME (`"EMAIL_068 B."`) et pseudonymes sur plateformes de vente/colis (`Vinted (pseudo)`).
  * Les mots courants homographes (`fois`, `bois`, `fiers`, `mis`, `créé`, `cousin`, `barrière`, `garage`, `courant`, `cerisier`, `commande`, `colis`) sont protégés pour éviter les faux positifs d'abréviation.
* **Coordonnées numériques** :
  * Numéros de téléphone français et internationaux remplacés par des pseudonymes déterministes (`TEL_001` via empreinte SHA-256 salée), sans confusion avec les nombres décimaux (`0.008...`) ou les horodatages (`10.15:57`).
  * Adresses e-mail (`EMAIL_001`) et liens hypertextes (`[URL_MASQUEE]`).
* **Dates et état civil** :
  * Dates de naissance exactes déclarées dans `masked_birth_dates` (`config.ini`), automatiquement masquées sous tous les formats (`JJ/MM/AAAA`, `JJ.MM.AA`, `AAAA-MM-JJ`, `AAAAMMJJ`, `2 mai 2013` et confusions OCR `0`/`O`, `5`/`S`) par `[DATE_MASQUEE]`.
  * Autres dates de naissance contextuelles (`né(e) le`, `ddn`, `enfant`, `patient`) masquées au niveau du jour et du mois (`[JOUR_MOIS_MASQUES]/2015`).
  * Dates de délivrance et d'expiration de pièces d'identité (`[DATE_TITRE_MASQUEE]`).
* **Identifiants administratifs, médicaux et financiers** :
  * Numéros de Sécurité sociale (`[NUM_SECU_MASQUE]`), y compris collés ou altérés par l'OCR.
  * Coordonnées bancaires (`[IBAN_MASQUE]`, `[BIC_MASQUE]`), numéros de carte tronqués, transactions et commandes (`[REF_BANCAIRE_TX_MASQUEE]`).
  * Identifiants fiscaux (`[NUM_FISCAL_MASQUE]`), France Travail (`[ID_FRANCE_TRAVAIL_MASQUE]`), CAF (`[NUM_ALLOCATAIRE_MASQUE]`), RPPS/AM/FINESS/IPP (`[ID_ADMIN_MASQUE]`), titres d'identité à 12 chiffres (`[ID_CNI_PERMIS_MASQUE]`) et bandes MRZ (`[MRZ_IDENTITE_MASQUEE]`).
  * Codes d'accès, digicodes, mots de passe (`[CODE_ACCES_MASQUE]`), identifiants de visioconférence (`[ID_REUNION_MASQUE]`), références de dossiers (`[REF_ADMIN_MASQUEE]`) et plaques d'immatriculation (`[PLAQUE_IMMAT_MASQUEE]`).
* **Localisations et établissements** :
  * Adresses postales (`[ADRESSE_MASQUEE]`), y compris collées par l'OCR (`RuedelaCabottiere`, `23Rve...`), codes postaux et communes (`[LIEU_MASQUE]`, y compris `14031Caencedex9`) ainsi qu'établissements hospitaliers et zones d'activité (`[ETABLISSEMENT_LIEU_MASQUE]`).

### 5.2 Données sensibles pouvant subsister (vigilance manuelle)

1. **Prénoms seuls et surnoms familiers** :
   * Les prénoms employés sans nom de famille (`Maël`, `Aloïs`, `Lilou`, `Steph`) sont conservés par conception pour maintenir la lisibilité des échanges. Pour les remplacer par des pseudonymes (`Enfant_1`, `Conjoint`), ajoutez-les explicitement dans `contacts_manuels.txt`.
2. **Noms de famille isolés ou hors carnet d'adresses** :
   * Un nom de famille isolé (sans prénom ni titre) absent de `contacts.txt` et `contacts_manuels.txt` reste visible, mais est signalé dans `audit_noms_residuels.txt`.
3. **Employeurs, écoles et associations spécifiques** :
   * Les noms propres d'entreprises, d'écoles ou d'associations non listés dans les contacts ne sont pas masqués automatiquement afin de préserver les enseignes et organismes courants (`Ikea`, `Decathlon`, `CPAM`).
4. **Identifiants numériques libres sans mot-clé** :
   * Les numéros de client, d'adhérent, identifiants internes d'échographie ou identifiants séparés de leur libellé par un saut de ligne ne sont pas interceptés par les motifs génériques.
5. **Contenu médical et biographique narratif** :
   * Les diagnostics, traitements et récits cliniques sont conservés intacts pour l'analyse et peuvent permettre une ré-identification indirecte si les noms d'établissements ou de proches n'ont pas été ajoutés dans `contacts_manuels.txt`.
### 5.3 Boucle d'audit des noms résiduels

À l'issue de chaque passe, deux fichiers sont mis à jour à la racine :

1. **`audit_noms_residuels.txt`** : liste triée par fréquence des noms propres potentiels encore présents dans les lots, accompagnée des fichiers concernés et d'une suggestion orthographique/phonétique si un nom proche existe dans les contacts.
2. **`audit_noms_residuels_copier.txt`** : liste épurée prête à être copiée dans `contacts_manuels.txt`.

Workflow recommandé pour affiner l'anonymisation :

```bash
# 1. Copiez les lignes pertinentes depuis audit_noms_residuels_copier.txt vers contacts_manuels.txt
# 2. Complétez automatiquement les alias manquants :
python lancer_documents.py --complete-manual
# 3. Appliquez les nouvelles règles directement sur les résultats existants :
python lancer_documents.py --manual-only
```

---

## 6. Outils complémentaires et tests

### 6.1 Scripts utilitaires (`tools/`)

* **`tools/completer_contacts_manuels.py`** : génère les alias manquants dans `contacts_manuels.txt` (supporte `--dry-run`).
* **`tools/sync_contacts.py`** : synchronise `contacts.txt` et initialise `contacts_manuels.txt` s'il est absent.
* **`tools/restaurer_noms_transcriptions.py`** : restaure les noms bruts des fichiers dans `transcriptions/` et les reclasse par période `AAAA-MM` (utiliser `--apply` pour exécuter réellement les déplacements).
* **`tools/generate_pdf_guide.py`** : convertit ce guide Markdown en PDF paginé :

```bash
python tools/generate_pdf_guide.py GUIDE_UTILISATION.md -o GUIDE_UTILISATION.pdf
```

### 6.2 Exécuter la suite de tests

La suite de tests vérifie la normalisation, l'extraction bureautique, la sécurité XML (anti-XXE), l'anonymisation OCR et le traitement complet d'une archive `.mbox` :

```bash
python tests/run_all_tests.py
