# Guide d'utilisation simple (Parents, Associations, Défenseurs Syndicaux)

Ce guide explique comment préparer et anonymiser un dossier confidentiel (santé d'un enfant, procédure familiale, dossier prud'homal) **en 5 minutes**, sans connaissance technique particulière.

---

## 1. Principe de sécurité

* **Tout reste sur votre ordinateur** : le logiciel fonctionne sans Internet. Vos documents originaux (`input_documents/`) ne sont jamais modifiés ni envoyés à l'extérieur.
* **Dossiers séparés** : vous pouvez créer un espace totalement étanche par personne ou par affaire (les contacts d'un dossier ne se mélangent jamais avec ceux d'un autre).

---

## 2. Ouvrir le logiciel

* **Sur Windows** : double-cliquez sur le fichier **`Lancer_Anonymiseur.bat`**.
* **Sur Linux** : ouvrez un terminal dans le dossier du programme et tapez **`python3 gui_anonymizer.py`** (ou double-cliquez sur `lancer_anonymiseur.sh`).

---

## 3. Préparer son dossier (Onglet 1 : *Dossier & Documents*)

1. **Créer un espace dédié** :
   * Dans *Nouveau dossier*, saisissez un nom clair sans espaces spéciaux (ex. `Garde_Leo` ou `Prudhommes_Dupont`) puis cliquez sur **Créer ce dossier**.
2. **Déposer les pièces du dossier** :
   * Cliquez sur **Ouvrir le dossier des documents sources**.
   * Copiez-collez à l'intérieur tous vos fichiers : comptes rendus médicaux PDF, scans, courriers, exports d'e-mails (`.mbox`), sauvegardes SMS (`.xml`), discussions WhatsApp/Teams/Google Chat, ou enregistrements vocaux (`.mp3`, `.m4a`, `.wav`).
   * *Astuce* : vous pouvez conserver vos sous-dossiers, le logiciel explore tout automatiquement.
3. **Importer vos contacts (facultatif mais recommandé)** :
   * Si vous avez un export `.csv` de vos contacts (Google Contacts ou Outlook), cliquez sur **Importer un fichier de contacts (.csv)**. Les noms et numéros de vos interlocuteurs seront ainsi reconnus dès le premier passage.

---

## 4. Lancer l'anonymisation (Onglet 2 : *Extraction & Anonymisation*)

1. Cliquez sur **Lancer l'extraction et l'anonymisation**.
2. La barre de progression s'anime et le journal affiche l'avancement fichier par fichier :
   * Les documents sont d'abord convertis en texte brut dans `extracted_texts/` et classés par mois (`2024-05`, `2024-06`, etc.).
   * Toutes les données personnelles sont ensuite remplacées par des alias cohérents (`Aurélie S.`, `Dr M.`, `Contact_Mail_001`, `[ADRESSE_MASQUEE]`, `[NUM_SECU_MASQUE]`).
3. À la fin, le message **`[OK] Traitement terminé.`** s'affiche.

---

## 5. Vérifier qu'aucun nom n'a échappé (Onglet 3 : *Vérification des noms restants*)

Après le traitement, le logiciel relit automatiquement tous les fichiers générés pour repérer d'éventuels noms propres oubliés (fautes de frappe, noms rares, mauvaise qualité de scan).

1. Allez dans l'onglet **3. Vérification des noms restants**.
2. Pour chaque ligne affichée :
   * **S'il s'agit d'un vrai nom de personne** : sélectionnez la ligne et cliquez sur **Masquer ce nom (ajouter aux règles)**.
   * **S'il s'agit d'un mot normal ou d'un terme médical/juridique** (ex. *Tribunal*, *Ophtalmologiste*) : cliquez sur **Ignorer (mot courant / faux positif)**.
3. Une fois la liste vérifiée, cliquez sur **Appliquer les corrections (Ré-anonymiser)**.
   * Cette seconde passe est **très rapide** (quelques secondes) car elle ne relit pas les PDF ni les audios.

---

## 6. Récupérer les fichiers prêts à partager

1. Retournez dans l'onglet **1** et cliquez sur **Ouvrir le dossier des lots anonymisés (`anonymized_results`)**.
2. Vous y trouverez les dossiers `batch_01/`, `batch_02/`, etc. contenant les fichiers `.txt` anonymisés et classés chronologiquement, prêts à être lus ou confiés à un tiers / un assistant IA en toute confidentialité.
