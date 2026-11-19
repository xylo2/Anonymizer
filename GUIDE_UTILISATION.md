# Guide d'utilisation — Pipeline d'Extraction et d'Anonymisation

Ce projet local extrait, transcrit (OCR et audio) et anonymise automatiquement vos contacts, e-mails, SMS, agendas et documents bureautiques sans aucun envoi vers le cloud.

## 1. Architecture des fichiers et référentiels

* `config.ini` : Configuration centrale partagée (chemins, seuils, options OCR/audio, pseudonymisation).
* `prenoms.txt` : Référentiel des prénoms connus utilisé pour détecter les paires `Prénom Nom` et inverser `Nom Prénom`.
* `villes_masquees.txt` : Liste externe des communes, villages et lieux étrangers à remplacer par `[LIEU_MASQUE]`.
* `mots_exclus.txt` : Liste externe des mots courants, sigles et faux positifs à ignorer lors de l'audit.
* `contacts.txt` : Référentiel généré automatiquement depuis vos exports Google Contacts / Outlook (`lancer_contacts.py`).
* `contacts_emails_decouverts.txt` : Règles générées depuis les adresses et noms d'affichage (`From` / `To`) des e-mails.
* `contacts_manuels.txt` : Fichier protégé (jamais écrasé) réservé à vos exceptions spécifiques (surnoms familiers, variantes OCR).

## 2. Préparation des contacts (`lancer_contacts.py`)

Placez vos exports CSV dans `export_contacts/`, puis exécutez :

```bash
python lancer_contacts.py
```

Le script génère et trie `contacts.txt` en remplaçant les noms de famille par leurs initiales et en résolvant les homonymes.
## 3. Extraction et anonymisation des documents (`lancer_documents.py`)

Placez vos documents (`.pdf`, `.docx`, `.xlsx`, `.mbox`, `.eml`, `.xml` SMS, images, audio) dans `fichiers sources/`, puis lancez :

```bash
python lancer_documents.py
```

### Mécanismes automatiques intégrés

1. **Catalogue géographique et `villes_masquees.txt` :** Remplace les départements, régions, grandes villes et communes listées par `[LIEU_MASQUE]`.
2. **Masquage automatique des titres :** Tout nom précédé d'un titre (`Dr`, `Docteur`, `Pr`, `Mme`, `M.`, `Me`, `Famille`, `Pharmacie`) est automatiquement remplacé par son initiale (ex. `Dr Kassab` devient `Dr K.`).
3. **Découverte depuis les en-têtes MIME :** Les noms d'affichage des expéditeurs et destinataires d'e-mails sont extraits automatiquement.
4. **Données sensibles :** Les NIR, IBAN, BIC, numéros fiscaux, identifiants France Travail/CAF, téléphones, e-mails, adresses postales et URLs sont pseudonymisés ou masqués.

## 4. Traitement rapide des noms résiduels (Audit)

Pour importer automatiquement les paires `Prénom Nom` fiables de l'audit dans `contacts_manuels.txt` et ré-anonymiser immédiatement les lots déjà générés :

```bash
python lancer_documents.py --import-audit --manual-only
```

* `python lancer_documents.py --import-audit --dry-run` : Prévisualise les imports sans modifier le fichier.
* `python lancer_documents.py --complete-manual` : Génère les initiales des lignes vides (`Prénom Nom = `).
* `python lancer_documents.py --manual-only` : Ré-applique les règles sur `resultats_anonymisation/`.
* `python tests/run_all_tests.py` : Exécute toute la suite de tests unitaires.
