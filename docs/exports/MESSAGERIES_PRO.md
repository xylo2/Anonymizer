# Méthodologie d'export : Google Chat et Microsoft Teams

> **Navigation :** [← Retour au README](../../README.md) | [Guide d'utilisation](../GUIDE_UTILISATION.md) | [Architecture technique](../ARCHITECTURE.md) | [Contacts, Courriels & SMS](CONTACTS_ET_EMAILS.md) | [WhatsApp, Messenger & Signal](MESSAGERIES_PERSO.md)

---

## 1. Google Chat (via [Google Takeout](takeout.google.com))

### Étapes détaillées sur Google Takeout
1. Connectez-vous sur [Google Takeout](takeout.google.com) avec votre compte Google.
2. Cliquez sur **Tout désélectionner** en haut de la page.
3. Faites défiler la liste jusqu'à **Google Chat** et cochez uniquement cette case.
4. Cliquez sur **Étape suivante** en bas de page.
5. Choisissez **Envoyer le lien de téléchargement par e-mail**, format **`.zip`**, puis
   cliquez sur **Créer une exportation**.
6. Une fois l'archive téléchargée, faites un clic droit > **Extraire tout** *(les
   archives `.zip` ne sont jamais décompressées automatiquement par sécurité)*.
7. Dans **AnonVault** (Étape 1), référencez le dossier **`Takeout/Google Chat/Groups/`**
   (ou uniquement les sous-dossiers `DM_...` / `Space_...` utiles).

### Contenu reconnu automatiquement
* **`messages.json`** et **`group_info.json`** : chaque fil est classé par mois
  (`AAAA-MM/Chats/`), avec les expéditeurs, dates et noms des pièces jointes.
* **`user_info.json`** et les images miniatures internes de Google Chat sont
  automatiquement ignorés pour éviter le bruit.
---

## 2. Microsoft Teams (Discussions & Réunions)

### Option A : Export personnel des discussions (`messages.json`)
1. Rendez-vous sur le [Portail de confidentialité Microsoft](https://account.microsoft.com/privacy)
   (ou sur [Mon Compte Microsoft 365](https://myaccount.microsoft.com) pour un compte
   professionnel ou scolaire).
2. Ouvrez la rubrique **Télécharger vos données** (ou **Exporter les données**).
3. Sélectionnez **Historique des discussions et médias Microsoft Teams** (et décochez
   les autres services pour accélérer la génération).
4. Cliquez sur **Envoyer une demande** / **Créer une nouvelle archive**.
5. Téléchargez le fichier `.zip` dès qu'il est prêt, **décompressez-le** (`Extraire tout`),
   puis référencez le fichier **`messages.json`** dans **AnonVault**.
6. *Traitement automatique* : les balises HTML internes, mentions `<at>` et noms de
   pièces jointes sont convertis en texte clair et classés par mois (`AAAA-MM/Chats/`).

### Option B : Transcriptions de réunions Teams (`.vtt` WebVTT)
1. Ouvrez [Microsoft Teams](https://teams.microsoft.com) et cliquez sur **Calendrier**
   dans le menu de gauche.
2. Double-cliquez sur la réunion passée concernée (ou ouvrez son fil de discussion).
3. Cliquez sur l'onglet **Enregistrements et transcriptions** (ou **Récapitulatif**).
4. Cliquez sur **Télécharger** à côté de la transcription et choisissez **`.vtt`**
   *(format WebVTT — bien plus fiable et rapide qu'un `.docx`)*.
5. Déposez le fichier **`.vtt`** dans **AnonVault** : chaque prise de parole est
   horodatée et attribuée à son intervenant (`[HH:MM:SS] Intervenant : ...`).

### Option C : Messages individuels ou captures (Compte Pro sans droit d'export)
* Si votre administrateur informatique bloque l'export global Teams :
  * Copiez-collez le fil dans un fichier `.txt` ou `.docx`, ou imprimez la conversation
    en **PDF** (`Ctrl + P` > *Enregistrer au format PDF*).
  * Pour un appel enregistré en `.mp4`, déposez directement la vidéo : **AnonVault**
    transcrira automatiquement la piste vocale hors-ligne via Whisper.
