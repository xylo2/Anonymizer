# Guide d'Utilisation Pas-à-Pas

> **Voir aussi :** [Documentation technique détaillée (`docs/GUIDE_UTILISATION.md`)](docs/GUIDE_UTILISATION.md) • [Architecture technique](docs/ARCHITECTURE.md)

Ce guide accompagne pas à pas toute personne souhaitant constituer un dossier clair, chronologique et sécurisé (parcours médical/MDPH, prud'hommes, litige civil ou administratif) sans aucune compétence technique requise.

---

## ÉTAPE 0 : Écran de vigilance et choix de votre objectif

1. **Engagement de relecture & Licence libre (GNU GPL v3)** :
   * Au démarrage de `python gui_anonymizer.py`, un écran rappelle qu'**aucune machine n'est infaillible** : vous devez toujours relire (au moins par sondage) vos exports avant de les transmettre à un tiers.
   * Cliquez sur **« J'ai compris et j'accepte de relire mes exports -> Continuer »** pour accéder à l'application (ou sur *« Refuser et quitter poliment »* pour fermer le logiciel).
2. **Choisir votre objectif** :
   * **Option A — Mode IA (Anonymisé)** : si vous voulez analyser votre dossier avec une IA en ligne (ChatGPT, Claude, Mistral...) sans exposer votre vie privée.
   * **Option B — Mode Avocat / Syndicat (Nominatif)** : si vous préparez le dossier final avec les vrais noms pour votre avocat, votre défenseur syndical ou le tribunal.
   * *Astuce : vous pouvez basculer d'un mode à l'autre à tout moment via le badge en haut de la fenêtre.*

---

## ÉTAPE 1 : Préparer votre dossier et exporter vos pièces

1. **Créer un espace de travail isolé (`1A`)** : saisissez un nom de dossier (ex. `Dossier_MDPH_2026` ou `Prudhommes_Employeur`) et cliquez sur **Créer**.
2. **Exporter vos sources (`Aide & Exports ?` ou `Exporter un agenda (.ics) ?`)** :
   * **Google Takeout (`https://google.com`)** : permet d'exporter d'un coup vos **e-mails Gmail (`.mbox`)**, vos **discussions Google Chat (`.json`)**, votre **Google Agenda (`.ics`)** et vos **Contacts (`.csv`)**. Pensez à **décompresser le `.zip`** téléchargé avant de copier les fichiers dans `input_documents/`.
   * **Google Agenda direct (`https://google.com`)** : *Paramètres (roue dentée) -> Importer et exporter -> Exporter* (`.ics`).
   * **SMS / MMS Android** : utilisez l'application gratuite **SMS Backup & Restore** pour générer un fichier `.xml`.
   * **WhatsApp** : ouvrez la discussion -> *Menu -> Plus -> Exporter la discussion -> Sans médias* (`.txt`).
   * **Documents, images et audios** : copiez directement vos PDF, Word, captures d'écran (`.jpg`, `.png`) et enregistrements vocaux (`.mp3`, `.m4a`, `.wav`) dans `input_documents/`.
3. **Importer vos carnets de contacts `.csv` (`1C` — Mode IA uniquement)** : ajoutez vos exports Google Contacts ou Outlook `.csv` pour masquer automatiquement vos proches et praticiens.

---

## ÉTAPE 2 : Extraction, classement et tableau de bord

1. Cliquez sur le bouton principal de lancement :
   * **En Mode IA** : extrait tous les formats, applique les règles d'anonymisation, découvre automatiquement les contacts dans vos e-mails/chats et affiche le **tableau de bord** (nombre de documents traités, identités, coordonnées, identifiants sensibles et lieux/dates masqués).
   * **En Mode Avocat** : extrait tous les documents en **conservant les vrais noms**, force la reconnaissance **OCR sur toutes les images** et la **transcription vocale sur tous les audios**.
2. Si une archive `.zip` est présente dans `input_documents/`, un bandeau d'avertissement vous indique de la décompresser manuellement (clic droit -> *Extraire tout*).

---

## ÉTAPE 3 (Mode IA) : Contrôle qualité Avant / Après

1. L'écran **« 4. Vérifier les noms »** liste les noms propres potentiels encore présents (issus de `audits/residual_names_copy.txt`).
2. Sélectionnez une ligne et cliquez sur **« Voir dans le document (Avant / Après) »** (ou double-cliquez sur la ligne) :
   * Une fenêtre dédiée affiche côte à côte l'extrait original (surligné en jaune) et le texte anonymisé (masquages en vert, candidat restant en rouge).
   * Vous pouvez naviguer entre toutes les occurrences du nom et choisir en un clic de le **masquer** (ajout dans `output_contacts/manual_contacts.txt`) ou de l'**ignorer** (ajout dans `data/mots_exclus.txt`).
3. Cliquez sur **« Appliquer et passer à l'étape 4 -> »** pour régénérer les lots propres.

---

## ÉTAPE FINALE : Récupération & Passerelle IA -> Avocat

### Parcours IA (Étape 5)
* Récupérez vos fichiers `.txt` anonymisés dans `anonymized_results/batch_01/`, etc.
* Utilisez le sélecteur **« Exemples de requêtes IA prêtes à copier »** (bilan médico-social, heures supplémentaires, harcèlement, maladie professionnelle, accident du travail, faute grave employeur) et cliquez sur **« Copier cette requête »**.
* Chaque requête demande à l'IA de vous fournir en conclusion **la liste exacte des fichiers pertinents** (`# SOURCE TRANSCRIPTION : ...`).

### Parcours Avocat (Étape 4)
* Choisissez entre :
  * **Exporter l'intégralité des pièces du dossier**
  * **Filtrer uniquement les pièces recommandées par l'IA** (collez simplement la liste des chemins retournée par l'IA)
* Cliquez sur **« Générer le Pack Avocat »** pour obtenir :
  * `Recueil_Chronologique_Avocat.docx`
  * `Bordereau_des_Pieces.csv`
  * `Pieces_Numerotees/` (avec **l'audio ou l'image originale + sa transcription/OCR numérotés côte à côte**)
  * `Pack_Avocat_Complet.zip`
