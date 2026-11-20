# Guide d'utilisation simple (Parents, Associations, Défenseurs Syndicaux)

Ce guide explique comment préparer et anonymiser un dossier confidentiel (santé d'un enfant, procédure familiale, dossier prud'homal) **en 5 minutes**, sans connaissance technique particulière.

---

## 1. Principe de sécurité et notion de « dossier »

* **Tout reste sur votre ordinateur** : le logiciel fonctionne sans Internet. Vos documents originaux (`input_documents/`) ne sont jamais modifiés ni envoyés à l'extérieur.
* **Qu'est-ce qu'un « dossier » dans ce logiciel ?**
  * C'est un **espace de travail étanche** créé sur votre ordinateur pour une affaire précise (ex. `Dossier_Enfant` ou `Dossier_Salarie`).
  * Chaque dossier possède ses propres documents, ses propres contacts et ses propres résultats : les noms d'un dossier ne se mélangent jamais avec ceux d'un autre.

---

## 2. Ouvrir le logiciel

* **Sur Windows** : double-cliquez sur le fichier **`Lancer_Anonymiseur.bat`**.
* **Sur Linux** : ouvrez un terminal dans le dossier du programme et tapez **`python3 gui_anonymizer.py`** (ou double-cliquez sur `lancer_anonymiseur.sh`).

---

## 3. Préparer son dossier (Onglet 1 : *Dossier & Documents*)

1. **Créer un espace dédié** :
   * Dans *Créer un nouveau dossier*, saisissez un nom simple sans caractères spéciaux (ex. `Dossier_Enfant` ou `Dossier_Salarie`) puis cliquez sur **Créer ce dossier**.
2. **Importer votre carnet de contacts `.csv` (fortement recommandé)** :
   * **Qu'est-ce qu'un fichier `.csv` ?** C'est un simple tableau exporté depuis votre messagerie contenant les noms, numéros de téléphone et adresses e-mail de vos contacts.
   * L'importer aide considérablement le logiciel à reconnaître immédiatement vos proches, médecins, avocats ou collègues (même en cas de faute de frappe ou de scan flou).
3. **Déposer vos pièces justificatives** :
   * Cliquez sur **1. Ouvrir le dossier où déposer mes documents** et copiez-collez vos fichiers (ou sous-dossiers entiers) à l'intérieur.

---

## 4. Comment exporter vos fichiers depuis chaque service

| Service | Format attendu | Comment récupérer le fichier |
| :--- | :--- | :--- |
| **Carnet d'adresses (Google / Outlook)** | `.csv` | • **Google Contacts** (`://google.com`) : menu de gauche -> **Exporter** -> choisir **Google CSV**.<br>• **Outlook** : *Fichier* -> *Ouvrir et exporter* -> *Importer/Exporter* -> **Exporter vers un fichier** -> **CSV**. |
| **SMS / MMS Android** | `.xml` | Installez l'application gratuite **SMS Backup & Restore** sur Android -> **Configurer une sauvegarde** -> cochez **Messages** -> récupérez le fichier `.xml` sur votre ordinateur. |
| **WhatsApp** | `.txt` | Ouvrez la conversation sur votre téléphone -> menu **(⋮)** -> **Plus** -> **Exporter la discussion** -> choisissez **Sans médias**. |
| **Google Chat / Hangouts** | `.json` | Allez sur `://google.com` -> *Tout désélectionner* -> cochez uniquement **Google Chat** -> téléchargez et décompressez l'archive `.zip`. |
| **Microsoft Teams** | `.json` ou `.vtt` | • **Discussions** : sur `://microsoft.com` -> **Télécharger vos données** -> cochez les messages Teams (format `.json`).<br>• **Transcriptions de réunions** : dans Teams -> ouvrez la réunion passée -> onglet **Enregistrement et transcription** -> **Télécharger** -> format **`.vtt`**. |
| **Facebook Messenger & Instagram** | `.json` | Dans **Espace Comptes Meta** -> **Vos informations et autorisations** -> **Télécharger vos informations** -> cochez **Messages** -> choisissez impérativement le format **JSON** (pas HTML). |
| **Signal** | *(Astuce `.txt` / `.pdf`)* | Signal ne propose pas d'export direct : sur ordinateur (**Signal Desktop**), sélectionnez et copiez-collez les échanges utiles dans un fichier `.txt` (ou imprimez en `.pdf`) avant de le déposer dans vos documents. |
| **E-mails (Gmail, Outlook, Thunderbird...)** | `.mbox` ou `.eml` | • **Gmail** : `://google.com` -> cochez **Mail** (génère un fichier `.mbox`).<br>• **Thunderbird / Outlook** : glissez-déposez les messages sur le bureau (crée des fichiers `.eml`) ou exportez le dossier en `.mbox`. |
| **Courriers, bilans, scans, audios** | `.pdf`, `.docx`, `.odt`, `.mp3`, `.m4a`, `.wav` | Copiez-collez directement vos fichiers originaux tels quels. |

---

## 5. Lancer l'anonymisation (Onglet 2 : *Lancer l'anonymisation*)

1. Cliquez sur **1er passage : Extraire et anonymiser tout**.
2. La barre de progression s'anime et le journal affiche l'avancement fichier par fichier :
   * Les documents sont convertis en texte brut dans `extracted_texts/` et classés chronologiquement par mois (`2024-05`, `2024-06`, etc.).
   * Toutes les données personnelles sont remplacées par des alias cohérents (`Camille D.`, `Dr M.`, `Contact_Mail_001`, `[ADRESSE_MASQUEE]`, `[NUM_SECU_MASQUE]`).

---

## 6. Vérifier qu'aucun nom n'a échappé (Onglet 3 : *Vérifier les noms restants*)

Après le traitement, le logiciel relit automatiquement tous les fichiers générés pour repérer d'éventuels noms propres oubliés.

1. Allez dans l'onglet **3. Vérifier les noms restants**.
2. Pour chaque ligne affichée :
   * **S'il s'agit d'un vrai nom de personne** : sélectionnez la ligne et cliquez sur **Masquer ce nom (c'est une personne)**.
   * **S'il s'agit d'un mot normal ou d'un terme médical/juridique** (ex. *Tribunal*, *Orthophoniste*) : cliquez sur **Ignorer ce mot (faux positif)**.
3. Une fois la liste vérifiée, cliquez sur **Appliquer mes corrections (2e passage rapide)** (dure quelques secondes).

---

## 7. Récupérer les fichiers prêts à partager

1. Retournez dans l'onglet **1** et cliquez sur **Ouvrir le dossier des résultats anonymisés**.
2. Vous y trouverez les dossiers `batch_01/`, `batch_02/`, etc. contenant les fichiers `.txt` anonymisés et classés par date, prêts à être lus ou confiés à un tiers / un assistant IA en toute confidentialité.
