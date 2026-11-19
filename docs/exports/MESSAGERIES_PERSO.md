# Méthodologie d'export : WhatsApp, Messenger et Signal

> **Navigation :** [← Retour au README](../../README.md) | [Guide d'utilisation](../GUIDE_UTILISATION.md) | [Architecture technique](../ARCHITECTURE.md) | [Export Contacts, Courriels & SMS](CONTACTS_ET_EMAILS.md) | [Export Messageries (Google Chat, Teams)](MESSAGERIES_PRO.md)

---

## 1. WhatsApp (Android & iPhone)

1. Ouvrez **WhatsApp** et entrez dans la discussion individuelle ou de groupe à exporter.
2. Ouvrez le menu de la conversation :
   * **Sur Android** : appuyez sur **⋮** (en haut à droite) > **Plus** > **Exporter la discussion**.
   * **Sur iPhone** : appuyez sur le nom du contact ou du groupe en haut > faites défiler vers le bas > **Exporter la discussion**.
3. Choisissez le mode d'export :
   * **Joindre les médias** : génère une archive `.zip` contenant `_chat.txt` ainsi que les documents PDF, images et notes vocales joints.
   * **Sans média** : génère uniquement un fichier texte `.txt`.
4. **Dézippez manuellement l'archive `.zip`** dans un sous-dossier dédié (ex. `input_documents/WhatsApp_Claire/`), puis lancez l'extraction : la discussion et tous les médias extraits seront traités automatiquement.

> **Important :** Les archives `.zip` non décompressées sont ignorées par l'application avec un avertissement consigné dans `audits/extraction_report.txt`.

---

## 2. Messenger (Facebook / Meta)

1. Ouvrez **Facebook** et allez dans **Paramètres et confidentialité** > **Paramètres**.
2. Ouvrez l'**Espace Comptes** (en haut à gauche) > **Vos informations et autorisations**.
3. Cliquez sur **Télécharger vos informations** > **Télécharger ou transférer des informations**.
4. Sélectionnez votre profil Facebook, puis choisissez **Types d'informations spécifiques**.
5. Cochez uniquement **Messages**, puis cliquez sur **Suivant**.
6. Choisissez **Télécharger sur l'appareil**, sélectionnez la plage de dates et réglez le format sur **JSON** *(recommandé)* ou **HTML**.
7. Une fois l'archive décompressée, copiez le dossier **`messages/inbox/`** (contenant `message_1.json` ou `message_1.html`) dans **`input_documents/`**.

---

## 3. Signal

1. **Depuis Android (sauvegarde chiffrée convertie localement)** :
   * Activez les sauvegardes locales dans Signal (**Paramètres** > **Discussions** > **Sauvegardes des discussions**).
   * Convertissez le fichier `.backup` localement à l'aide d'un outil hors-ligne tel que `signal-back` ou `sigtop` vers le format **JSON** (`signal_backup.json`).
2. **Depuis Signal Desktop** :
   * Exportez l'historique des messages au format **JSON** (contenant `source`, `sourceName`, `timestamp`, `body`).
3. Déposez le ou les fichiers **`.json`** dans **`input_documents/`**.
