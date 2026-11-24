# Méthodologie d'export : WhatsApp, Messenger et Signal

> **Navigation :** [← Retour au README](../../README.md) | [Guide d'utilisation](../GUIDE_UTILISATION.md) | [Architecture technique](../ARCHITECTURE.md) | [Contacts, Courriels & SMS](CONTACTS_ET_EMAILS.md) | [Google Chat & Teams](MESSAGERIES_PRO.md)

---

## 1. [WhatsApp](https://www.whatsapp.com) (Android, iPhone & Ordinateur)

### Sur Android
1. Ouvrez **WhatsApp** et entrez dans la discussion individuelle ou de groupe.
2. Appuyez sur **⋮** (les trois points en haut à droite) > **Plus** > **Exporter discussion**.
3. Choisissez l'option adaptée à votre besoin :
   * **Sans média** *(rapide)* : génère uniquement le fichier texte de la discussion
     (jusqu'aux 40 000 derniers messages).
   * **Joindre les médias** *(complet)* : génère une archive **`.zip`** contenant
     `_chat.txt` ainsi que les photos, PDF et notes vocales (`.opus` / `.m4a`).
4. Transférez le fichier sur votre PC (e-mail, câble USB, Bluetooth ou Drive).
5. **Si vous avez un `.zip`, décompressez-le impérativement** (clic droit > *Extraire tout*)
   dans un dossier nommé d'après le contact (ex. `WhatsApp_Claire/`), puis référencez
   ce dossier dans **AnonVault**.

### Sur iPhone / iPad (iOS)
1. Ouvrez **WhatsApp** et entrez dans la conversation souhaitée.
2. Touchez le **nom du contact ou du groupe** tout en haut de l'écran.
3. Faites défiler tout en bas et touchez **Exporter la discussion**.
4. Choisissez **Joindre les médias** ou **Sans média**, puis touchez **Enregistrer
   dans Fichiers** (ou envoyez-le vers votre ordinateur).
5. Décompressez l'archive `.zip` obtenue sur votre ordinateur avant de la référencer
   dans **AnonVault**.

> **Important :** Par sécurité, les archives `.zip` non décompressées sont ignorées
> avec une alerte visuelle à l'étape 1 et dans `audits/extraction_report.txt`.
---

## 2. [Facebook Messenger](https://www.facebook.com) (Meta)

### Étapes détaillées depuis l'Espace Comptes Meta
1. Ouvrez [Facebook](https://www.facebook.com) sur ordinateur et cliquez sur votre **photo
   de profil** (en haut à droite) > **Paramètres et confidentialité** > **Paramètres**.
2. Dans le panneau gauche, cliquez sur **Espace Comptes** (ou ouvrez directement le
   [Centre de comptes Meta](https://accountscenter.facebook.com/info_and_permissions))
   > **Vos informations et autorisations**.
3. Cliquez sur **Télécharger vos informations** > **Télécharger ou transférer des
   informations**.
4. Sélectionnez votre profil Facebook, puis choisissez **Types d'informations spécifiques**.
5. Cochez uniquement **Messages**, puis cliquez sur **Suivant**.
6. Choisissez **Télécharger sur l'appareil**, puis réglez ces 3 paramètres clés :
   * **Plage de dates** : sélectionnez la période utile au dossier.
   * **Format** : choisissez impérativement **JSON** *(plus fidèle et complet que HTML ;
     les deux formats sont toutefois pris en charge par AnonVault)*.
   * **Qualité des médias** : *Moyenne* ou *Élevée* si vous joignez des captures.
7. Cliquez sur **Créer des fichiers**, téléchargez le `.zip` une fois prêt,
   **décompressez-le**, puis référencez le dossier **`messages/inbox/`** (ou le
   sous-dossier précis de l'interlocuteur contenant `message_1.json`).

---

## 3. [Signal](https://signal.org) (Desktop & Android)

### Option A : Depuis [Signal Desktop](https://signal.org/download/) (Windows, macOS, Linux)
1. Si vos messages sont sur téléphone, liez d'abord **Signal Desktop** sur ordinateur
   (les messages récents se synchronisent ; pour l'historique complet Android, voir
   l'Option B ci-dessous).
2. Utilisez l'outil local hors-ligne open-source [sigtop](https://github.com/tbvdm/sigtop)
   (Windows/macOS/Linux) pour exporter la base locale Signal Desktop en fichiers **JSON** :
   ```bash
   sigtop export-messages --format json dossier_export_signal/
   ```
3. Référencez le dossier `dossier_export_signal/` dans **AnonVault**.

### Option B : Depuis Android (Sauvegarde chiffrée convertie hors-ligne)
1. Dans Signal Android : **Paramètres** > **Discussions** > **Sauvegardes des
   discussions** > **Activer**.
2. **Notez précieusement la phrase de récupération à 30 chiffres** affichée à l'écran.
3. Appuyez sur **Créer une sauvegarde**, puis copiez le fichier `.backup` sur votre PC.
4. Convertissez localement le fichier `.backup` vers le format **JSON** à l'aide de
   l'outil hors-ligne [signal-back](https://github.com/xeals/signal-back)
   (`signal-back format -f JSON ...`), puis référencez le `.json` obtenu dans
   **AnonVault** (les champs `source`, `sourceName`, `timestamp` et `body` sont
   extraits et classés par mois automatiquement).
