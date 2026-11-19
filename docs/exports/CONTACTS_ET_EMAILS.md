# Méthodologie d'export : Contacts, Courriels et SMS

> **Navigation :** [← Retour au README](../../README.md) | [Guide d'utilisation](../../GUIDE_UTILISATION.md) | [Architecture technique](../../ARCHITECTURE.md) | [Export Messageries (Google Chat, Teams)](MESSAGERIES_PRO.md) | [Export Messageries (WhatsApp, Messenger, Signal)](MESSAGERIES_PERSO.md)

---

## 1. Contacts (Google Contacts & Microsoft Outlook)

Les fichiers CSV de contacts doivent être placés dans le dossier **`export_contacts/`** à la racine du projet.

### Google Contacts
1. Ouvrez [://google.com](https://://google.com).
2. Cliquez sur l'icône **Exporter** (en haut à droite) ou dans le menu latéral gauche.
3. Sélectionnez **Tous les contacts** (ou un libellé précis) et choisissez le format **CSV Google**.
4. Enregistrez le fichier `.csv` dans **`export_contacts/`**.

### Microsoft Outlook / Microsoft 365
1. Ouvrez **Outlook** (Web ou Bureau) et accédez à l'onglet **Contacts** (icône personnes).
2. Cliquez sur **Gérer les contacts** > **Exporter les contacts**.
3. Choisissez **Tous les contacts** au format **CSV** (séparateur virgule ou point-virgule).
4. Enregistrez le fichier `.csv` dans **`export_contacts/`**.

---

## 2. Courriels Gmail & Fichiers `.eml`

Les archives de messagerie doivent être placées dans le dossier **`fichiers sources/`**.

### Gmail (via Google Takeout)
1. Rendez-vous sur [://google.com](https://://google.com).
2. Cliquez sur **Tout désélectionner**.
3. Cochez uniquement **Messagerie** (Gmail). Vous pouvez cliquer sur *Toutes les données des messages incluses* pour filtrer certains libellés.
4. Cliquez sur **Étape suivante** > **Créer une exportation**.
5. Téléchargez et décompressez l'archive, puis placez le fichier **`.mbox`** dans **`fichiers sources/`**.

### Messages individuels `.eml`
* Depuis Thunderbird, Outlook ou Apple Mail, glissez-déposez simplement vos courriels enregistrés au format **`.eml`** dans **`fichiers sources/`** (les pièces jointes PDF incluses seront extraites automatiquement).

---

## 3. SMS & MMS Android

1. Installez et ouvrez l'application **SMS Backup & Restore** sur votre téléphone Android.
2. Appuyez sur **Configurer une sauvegarde** (ou **Sauvegarder maintenant**).
3. Activez **Messages** (cochez l'inclusion des MMS si souhaité) et choisissez un emplacement local ou Google Drive.
4. Récupérez le fichier **`.xml`** généré et déposez-le dans **`fichiers sources/`**.
