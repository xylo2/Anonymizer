# AnonVault — Pièces protégées

Application **100 % locale et hors-ligne** (Windows & Linux) permettant de rassembler,
filtrer, anonymiser ou classer chronologiquement des pièces confidentielles (documents,
images OCR, audios/vidéos transcrits, carnets de contacts, exports SMS et messageries).

Distribué sous licence libre **GNU GPL v3** (*sans garantie — relecture humaine
obligatoire avant tout partage*).

---

## 1. Installation rapide

### Sous Windows
1. Double-cliquez sur **`Lancer_Anonymiseur.bat`** (détecte automatiquement `.venv` ou
   `venv` et ouvre l'interface sans console en arrière-plan).
2. Ou en ligne de commande :
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python gui_anonymizer.py
   ```

### Sous Linux (Ubuntu, Debian, Linux Mint, Fedora)
1. Installez le paquet système Tkinter (et optionnellement Tesseract OCR / FFmpeg) :
   ```bash
   sudo apt update
   sudo apt install python3-tk tesseract-ocr tesseract-ocr-fra ffmpeg
   ```
2. Créez l'environnement virtuel et installez les dépendances Python :
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Rendez le lanceur exécutable et démarrez l'application :
   ```bash
   chmod +x Lancer_Anonymiseur.sh
   ./Lancer_Anonymiseur.sh
   ```

---

## 2. Fonctionnalités principales & Ergonomie

* **Isolation par affaire (`dossiers/<nom>/`)** : chaque dossier possède ses propres
  sources, carnets de contacts, règles d'exclusion et résultats.
* **Référencement en lecture seule (`LinkedSourcesManager`)** : ajoutez des fichiers ou
  dossiers externes (disque local, clé USB, partage réseau) sans modifier les originaux.
* **Détection des doublons (`DuplicateFilesManager`)** : écarte les fichiers binaires
  strictement identiques avec cache SHA-256.
* **Filtrage interactif** : sélectionnez contacts, numéros SMS et conversations de
  messageries (WhatsApp, Google Chat, Teams, Messenger, Signal).
* **Deux modes de sortie** :
  * **Mode IA (Anonymisé)** : remplace identités, téléphones, e-mails, adresses, NIR et
    IBAN par des alias cohérents, avec contrôle humain Avant/Après et désanonymisation.
  * **Mode Avocat (Nominatif)** : génère un recueil chronologique numéroté avec
    bordereau CSV et médias originaux côte à côte.
* **Accessibilité & Raccourcis clavier** : `Ctrl + +` / `Ctrl + -` / `Ctrl + 0` (zoom),
  `Ctrl + F` / `Échap` (recherche), `Alt + Gauche` / `Alt + Droite` (navigation) et
  mode **Lecteur d'écran** (`--screen-reader`).

---

## 3. Tests unitaires

```bash
python tests/run_all_tests.py
