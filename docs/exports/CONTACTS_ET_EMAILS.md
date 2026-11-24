# Méthodologie d'export : Contacts, Courriels, SMS et Agendas

> **Navigation :** [← Retour au README](../../README.md) | [Guide d'utilisation](../GUIDE_UTILISATION.md) | [Architecture technique](../ARCHITECTURE.md) | [Google Chat & Teams](MESSAGERIES_PRO.md) | [WhatsApp, Messenger & Signal](MESSAGERIES_PERSO.md)

---

## 1. Carnets de contacts (`.csv` et vCard `.vcf`)

Déposez vos exports directement dans **AnonVault** (Étape 1) ou dans `input_contacts/`.
Ils sont indexés automatiquement pour masquer les noms de famille en initiales (`Prénom N.`).

### Google Contacts, Microsoft 365 / Outlook & Thunderbird
* **[Google Contacts](https://contacts.google.com)** : menu gauche > **Exporter** >
  **Tous les contacts** > choisissez impérativement **CSV Google** *(préserve les accents)*.
* **[Outlook Web](https://outlook.live.com) / [Microsoft 365](https://outlook.office.com)** :
  icône **Personnes** > **Gérer les contacts** > **Exporter les contacts** > **Tous les
  contacts** (`.csv`).
* **Outlook Classique (client lourd Windows)** : **Fichier** > **Ouvrir et exporter** >
  **Importer/Exporter** > **Exporter des données vers un fichier** > **Valeurs séparées
  par des virgules (CSV)** > sélectionnez **Contacts**.
* **Apple iPhone / iPad (iOS 16+) & [iCloud Contacts](https://www.icloud.com/contacts)** :
  * *iPhone* : **Contacts** > **`< Listes`** > appui long sur **Tous les contacts** >
    **Exporter** (`.vcf`).
  * *iCloud Web* : ouvrez [iCloud Contacts](https://www.icloud.com/contacts) >
    **`Ctrl + A`** > roue dentée > **Exporter vCard**.
* **Android & [Mozilla Thunderbird](https://www.thunderbird.net)** :
  * *Android* : **Contacts** > **Corriger et gérer** > **Exporter vers un fichier** (`.vcf`).
  * *Thunderbird* : **Carnet d'adresses** > clic droit sur le carnet > **Exporter** (`.vcf`).
---

## 2. Courriels : Exporter tout ou une sélection filtrée par fournisseur

Les pièces jointes PDF incluses dans les courriels sont extraites automatiquement.

### A. Client lourd Microsoft Outlook Classique (Windows / Mac)
* **Méthode 1 — Archive Outlook directe (`.pst` ou `.ost`, recommandé et natif)** :
  1. Dans Outlook Classique : **Fichier** > **Ouvrir et exporter** > **Importer/Exporter**
     > **Exporter des données vers un fichier** > **Fichier de données Outlook (`.pst`)**.
  2. Sélectionnez le dossier voulu (ex. *Boîte de réception* ou *Éléments envoyés*) et
     cliquez sur **Filtrer...** pour restreindre par expéditeur, mots-clés ou dates.
  3. Référencez directement le fichier **`.pst`** (ou votre cache local **`.ost`**) dans
     **AnonVault** : tous les sous-dossiers, courriels et PDF joints sont lus nativement.
* **Méthode 2 — Messages unitaires ciblés (`.msg`)** :
  1. Filtrez via la recherche Outlook (ex. `de:nom@domaine.fr` ou `reçu:01/01/2024..31/12/2024`).
  2. Sélectionnez les e-mails utiles (`Ctrl + Clic` ou `Ctrl + A`), puis glissez-les
     vers un dossier PC : les fichiers **`.msg`** créés sont lus directement par AnonVault.

### B. Gmail (via [Google Takeout](https://takeout.google.com) — `.mbox`)
1. Rendez-vous sur [Google Takeout](https://takeout.google.com) > **Tout désélectionner**
   > cochez **Messagerie**.
2. *Pour exporter uniquement une partie* : créez d'abord un libellé Gmail (ex. `Dossier_Litige`)
   via un filtre de recherche, puis dans Takeout cliquez sur **Toutes les données des
   messages incluses** et ne cochez que ce libellé.
3. Téléchargez et décompressez le `.zip`, puis référencez le **`.mbox`** dans `Takeout/Mail/`.

### C. [Outlook.com](https://outlook.live.com) / [Microsoft 365 Web](https://outlook.office.com) (`.eml` ou `.pst`)
* **Sélection filtrée (`.eml`)** : ouvrez chaque courriel utile > **`...`** > **Télécharger**.
* **Boîte complète (`.pst`)** : **Engrenage** > **Général** > **Confidentialité et données**
  > **Exporter la boîte aux lettres** *(le `.pst` obtenu est directement lu par AnonVault)*.

### D. Autres fournisseurs (Yahoo, Orange, Free, SFR, La Poste, Proton, iCloud, Infomaniak)
* Installez [Mozilla Thunderbird](https://www.thunderbird.net), connectez votre compte en
  **IMAP** ([Yahoo Mail](https://mail.yahoo.com), [Orange](https://messagerie.orange.fr),
  [Free Zimbra](https://zimbra.free.fr), [SFR Mail](https://webmail.sfr.fr),
  [La Poste](https://www.laposte.net), [iCloud Mail](https://www.icloud.com/mail),
  [Infomaniak](https://mail.infomaniak.com), [Proton Mail](https://mail.proton.me)),
  filtrez vos messages et faites **Enregistrer sous...** (`.eml`) ou récupérez le `.mbox`.

---

## 3. SMS & MMS & Agendas (`.xml` / `.ics`)

* **SMS Android** : [SMS Backup & Restore](https://play.google.com/store/apps/details?id=com.riteshsahu.SMSBackupRestore) > **Sauvegarder maintenant** (`.xml`).
* **SMS iPhone** : [iMazing](https://imazing.com) ou [CopyTrans Contacts](https://www.copytrans.fr/copytranscontacts/) > **Exporter en CSV/PDF**.
* **Agendas (`.ics`)** : [Google Agenda](https://calendar.google.com) > **Paramètres** > **Importer et exporter** > **Exporter** (dézipper le `.ics`).
