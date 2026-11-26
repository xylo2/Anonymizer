# Guide d'utilisation — AnonVault — Pièces protégées

Ce guide explique pas à pas comment rassembler vos pièces, préparer un lot anonymisé
pour une IA ou générer un recueil chronologique nominatif pour votre avocat,
**100 % hors-ligne** sur Windows ou Linux.

---

## 1. Démarrer l'application

* **Sous Windows** : double-cliquez sur **`Lancer_Anonymiseur.bat`**. L'interface
  s'ouvre directement sans fenêtre de commande noire en arrière-plan.
* **Sous Linux (Ubuntu, Debian, Mint, Fedora)** :
  1. Assurez-vous d'avoir installé Tkinter (`sudo apt install python3-tk`).
  2. Rendez le script exécutable (`chmod +x Lancer_Anonymiseur.sh`), puis lancez
     **`./Lancer_Anonymiseur.sh`**.

---

## 2. Parcours étape par étape

1. **Étape 0 — Accueil & Dossier** : lisez l'engagement de relecture humaine, puis
   ouvrez un dossier existant ou créez un nouveau dossier isolé (ex. `Dossier_Test_2026`).
2. **Étape 1 — Déposer mes pièces** : glissez-déposez vos fichiers ou dossiers sur la
   fenêtre (référencés **en lecture seule** ; copie proposée sur clé USB/disque externe).
3. **Étape 1 bis — Doublons détectés** : sélectionnez l'exemplaire à conserver (vert)
   et les doublons à ignorer (rouge). Vos originaux ne sont jamais supprimés.
4. **Étape 2 — Carnets & Contacts** : vérifiez les contacts détectés (`.csv` / `.vcf`)
   et basculez entre **Garder (vert)** et **Mis de côté (rouge)**.
5. **Étape 3 — Exports SMS & Numéros** : filtrez vos correspondants SMS et écartez les
   numéros courts automatiques en un clic.
6. **Étape 4 — Messageries & Chats** : sélectionnez uniquement les conversations utiles
   (WhatsApp, Google Chat, Teams, Messenger, Signal).
7. **Étape 5 — Choisir l'objectif** : **Mode IA (Anonymisé)** ou **Mode Avocat
   (Nominatif)** pour assembler un recueil chronologique Word/CSV avec médias originaux.
8. **Étape 6 — Extraction et traitement** : suivez l'avancement en pourcentage et les
   5 compteurs de protection en temps réel (transcription audio/vidéo et séparation
   des interlocuteurs assurées par la librairie externe
   [AudioTranscriber](https://github.com/xylo2/AudioTranscriber)).
9. **Étape 7 — Vérifier les noms restants (Mode IA)** : `Entrée` pour l'aperçu
   **Avant / Après**, `M` pour masquer ou `I` (`Suppr`) pour ignorer.
10. **Étape 8 — Récupérer & Désanonymiser** : copiez une requête IA prête à l'emploi,
    puis restituez les vraies identités dans un fichier suffixé `_nominatif`.

---

## 3. Paramètres du dossier, Raccourcis clavier & Accessibilité

* **Bouton `Paramètres`** : configure dates de naissance à masquer, balises numérotées
  (`[LIEU_01]`, `[DATE_01]`), OCR, transcription vocale, distinction automatique des
  interlocuteurs (`audio_transcriber`) et modèle Whisper.
* **`Ctrl + +` / `Ctrl + -` / `Ctrl + 0`** : zoom texte global mémorisé.
* **`Ctrl + F` / `Échap`** : cibler ou vider la recherche dans les tableaux.
* **`Alt + Gauche` / `Alt + Droite`** : passer à l'étape précédente ou suivante.
* **Bouton `Lecteur d'écran`** : contrôles natifs Windows Narrator, NVDA et JAWS.
