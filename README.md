# Anonymiseur Local & Préparation de Dossiers Confidentiels

Suite logicielle Python **100 % locale et hors-ligne** conçue pour aider les particuliers, familles, représentants du personnel, syndicats et associations à préparer leurs dossiers sensibles (santé, handicap/MDPH, prud'hommes, litiges civils ou familiaux) en toute sécurité.

Distribué sous licence libre **GNU GPL v3** (*sans garantie — relecture humaine obligatoire avant tout partage*).

---

## Deux objectifs adaptés à votre besoin

Dès l'ouverture de l'interface graphique (`python gui_anonymizer.py`), après l'écran de vigilance humaine et d'acceptation de la licence, l'application vous propose de choisir entre **deux parcours dédiés** :

### 1. Mode IA (Anonymisé — 4 étapes)
* **Pourquoi ?** Les assistants IA en ligne (ChatGPT, Claude, Mistral, etc.) ne doivent **jamais** recevoir vos données personnelles brutes.
* **Ce que fait ce mode :**
  1. **Préparer mon dossier** : création d'un espace isolé (`dossiers/<nom>/`), dépôt des pièces (`input_documents/`), import des carnets `.csv`, alerte automatique si une archive `.zip` non décompressée est détectée, et guide d'exportation intégré (*Google Takeout, Google Agenda, SMS Backup & Restore, WhatsApp, Teams, Messenger*).
  2. **Analyser & Anonymiser** : extraction multi-formats + masquage contextuel multi-passes + tableau de bord chiffré des données protégées.
  3. **Vérifier les noms** : contrôle qualité assisté avec **fenêtre dédiée Avant / Après côte à côte** et surlignage des remplacements.
  4. **Récupérer & Requêtes IA** : récupération des lots `.txt` anonymisés + **6 requêtes IA prêtes à copier** (bilan médico-social, heures supplémentaires, harcèlement, maladie professionnelle, accident du travail, faute grave employeur) demandant à l'IA la liste exacte des pièces pertinentes.

### 2. Mode Avocat / Syndicat (Nominatif — 3 étapes)
* **Pourquoi ?** Votre avocat, défenseur syndical ou juridiction a besoin des **vraies identités, dates et preuves originales** classées chronologiquement.
* **Ce que fait ce mode :**
  1. **Préparer mon dossier** : dépôt des pièces justificatives (avec alerte sur les `.zip` non décompressés).
  2. **Extraire & Classer** : extraction nominative avec **forçage OCR sur toutes les images/scans** et **transcription vocale Whisper sur tous les fichiers audio**.
  3. **Pack Avocat Nominatif** : export complet **ou filtré uniquement selon la liste de pièces retenues par l'IA**, générant :
     * `Recueil_Chronologique_Avocat.docx` (sommaire, pièces paginées par ordre chronologique et aperçu des images)
     * `Bordereau_des_Pieces.csv` (numérotation officielle `Pièce n°001`, date, type, intitulé et média original joint)
     * `Pieces_Numerotees/` contenant **côte à côte** chaque fichier média original (`_ORIGINAL.mp3/.jpg`) et sa transcription/OCR (`_TRANSCRIPTION.txt` / `_OCR.txt`)
     * `Pack_Avocat_Complet.zip`
---

## Formats pris en charge

* **Documents bureautiques & web** : `.pdf` (texte natif + OCR automatique RapidOCR sur scans), `.docx`, `.doc`, `.odt`, `.rtf`, `.xlsx`, `.xls`, `.pptx`, `.html`, `.txt`, `.md`, `.csv`.
* **E-mails** : `.mbox` (Google Takeout), `.eml` (Thunderbird, Outlook).
* **SMS & Messageries** : SMS/MMS Android (`.xml` via *SMS Backup & Restore*), WhatsApp (`.txt`), Google Chat (`.json` via *Google Takeout*), Microsoft Teams (`.json` et transcriptions `.vtt`), Messenger / Instagram (`.json`).
* **Agendas** : `.ics` (Google Agenda, Google Takeout, Outlook, Apple Calendrier).
* **Images & Audios** : `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.tiff` (OCR hors-ligne) ; `.mp3`, `.wav`, `.m4a`, `.ogg`, `.flac`, `.aup3` (transcription hors-ligne Faster-Whisper).
* *(Sécurité : les archives `.zip` ne sont jamais décompressées automatiquement ; l'application les signale explicitement afin que vous les extrayiez manuellement).*

---

## Installation et lancement rapide

```bash
# 1. Créer et activer l'environnement virtuel
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer l'interface graphique guidée
python gui_anonymizer.py
```

---

## Tests unitaires et qualité

```bash
# Exécuter l'ensemble de la suite de tests unitaires
python tests/run_all_tests.py
```

---

## Licence

Ce projet est distribué sous licence **GNU General Public License v3.0 (GPL-3.0)**.
