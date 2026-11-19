# Méthodologie d'export : Google Chat et Microsoft Teams

> **Navigation :** [← Retour au README](../../README.md) | [Guide d'utilisation](../GUIDE_UTILISATION.md) | [Architecture technique](../ARCHITECTURE.md) | [Export Contacts, Courriels & SMS](CONTACTS_ET_EMAILS.md) | [Export Messageries (WhatsApp, Messenger, Signal)](MESSAGERIES_PERSO.md)

---

## 1. Google Chat (via Google Takeout)

1. Rendez-vous sur Google Takeout.
2. Cliquez sur **Tout désélectionner**.
3. Faites défiler la liste et cochez uniquement **Google Chat**.
4. Cliquez sur **Étape suivante**, choisissez le format `.zip` puis **Créer une exportation**.
5. Une fois l'archive téléchargée et décompressée, copiez l'intégralité du dossier **`Google Chat/Groups/`** (contenant les sous-dossiers de conversations avec `messages.json` et `group_info.json`) dans **`input_documents/`**.

> **Note :** Les fichiers techniques annexes comme `user_info.json` sont automatiquement ignorés par le pipeline.

---

## 2. Microsoft Teams (Discussions & Réunions)

### Option A : Export personnel des discussions (Compte Microsoft / RGPD)
1. Connectez-vous sur le portail de confidentialité Microsoft ou via l'interface d'export Teams.
2. Allez dans **Télécharger vos données** > **Créer une nouvelle archive**.
3. Sélectionnez votre **historique des discussions et médias Microsoft Teams**.
4. Téléchargez et décompressez l'archive reçue.
5. Placez le fichier **`messages.json`** dans **`input_documents/`** (le HTML interne et les mentions `<at>` sont nettoyés automatiquement).

### Option B : Transcriptions de réunions Teams (`.vtt`)
1. Ouvrez **Microsoft Teams** et allez dans votre **Calendrier**.
2. Cliquez sur la réunion passée dont vous souhaitez récupérer les échanges.
3. Ouvrez l'onglet **Enregistrements et transcriptions**.
4. Cliquez sur **Télécharger** à côté de la transcription et choisissez le format **`.vtt`** (WebVTT).
5. Déposez le fichier **`.vtt`** dans **`input_documents/`**.
