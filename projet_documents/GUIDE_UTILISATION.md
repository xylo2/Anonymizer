# Guide d'utilisation — Extraction et Anonymisation de Documents

Ce projet extrait le texte de documents hétérogènes (PDF natifs ou scannés, Word, Excel, PowerPoint, ODT, RTF, HTML, images, agendas ICS, SMS/MMS XML, e-mails `.mbox`/`.eml` et enregistrements audio) et les anonymise localement avant analyse.

---

## 1. Architecture des fichiers de contacts

Le pipeline s'appuie sur **trois fichiers de règles complémentaires** pour éviter d'écraser vos ajouts manuels lors des mises à jour d'exports :

1. **`contacts.txt`** *(généré automatiquement)* : produit par `python lancer_contacts.py` depuis vos exports CSV Google Contacts ou Outlook. Ce fichier peut être régénéré à tout moment sans perte.
2. **`contacts_emails_decouverts.txt`** *(généré automatiquement)* : alimenté après chaque extraction d'e-mails à partir du tampon `tous_emails_trouves.txt`. Il attribue un alias `Contact_Mail_XXX` aux adresses inconnues et déduit automatiquement `Prénom Nom` lorsque l'adresse est nominative. Le fichier tampon `tous_emails_trouves.txt` est purgé après transfert.
3. **`contacts_manuels.txt`** *(géré par vous, jamais écrasé)* : créé automatiquement au premier lancement. Ajoutez-y vos règles personnalisées au format `Prénom Nom = Alias` (ou laissez `Prénom Nom = ` vide pour utiliser `--complete-manual`). Elles sont appliquées en priorité sur les deux autres fichiers.

---

## 2. Exécution des pipelines depuis la racine

### Étape A : Générer l'index automatique des contacts
Placez vos exports CSV dans `export_contacts/` puis exécutez :

```bash
python lancer_contacts.py
```

### Étape B : Extraire et anonymiser les documents au fil de l'eau
Placez vos documents dans `fichiers sources/` puis exécutez :

```bash
python lancer_documents.py
```

* Les transcriptions brutes **non anonymisées** sont enregistrées dans `transcriptions/AAAA-MM/<Catégorie>/` en conservant leur nom d'origine.
* Les lots anonymisés sont écrits de façon atomique dans `resultats_anonymisation/lot_XX/anonymise_partie_XXX.txt`.
* Si de nouveaux contacts sont découverts dans `tous_emails_trouves.txt`, le pipeline déclenche automatiquement une **seconde passe complète** d'anonymisation.
## 3. Règles de masquage automatique et sécurité

En complément des noms et alias définis dans les fichiers de contacts (incluant les variantes inversées `Nom Prénom`, les titres `Dr/Mme/M.` et les noms collés sans espace comme `DUPONTAurelien`), le moteur applique les protections suivantes :

* **Adresses e-mail résiduelles** : remplacées par des jetons déterministes `EMAIL_001`, `EMAIL_002`...
* **Numéros de téléphone résiduels** : formats français et internationaux (`06...`, `+33...`, `0033...`) ainsi que les groupes MMS (`~` ou `+`), remplacés par `TEL_001`, `TEL_002`... Les horodatages compacts `AAAAMMJJHHMMSS` (ex. `20261116131514`) sont préservés pour le classement chronologique.
* **URLs et noms de domaine** : lorsque `mask_urls = true` dans `config.ini`, les liens `http://`, `https://`, `www.` et domaines sont remplacés par `[URL_MASQUEE]`.
* **Identifiants sensibles** : numéros de sécurité sociale (`[NUM_SECU_MASQUE]`), IBAN/BIC (`[IBAN_MASQUE]`), numéros fiscaux, identifiants France Travail et allocataires CAF/MSA.
* **Adresses postales et lieux** : rues, codes postaux et communes configurées remplacés par `[ADRESSE_MASQUEE]` et `[LIEU_MASQUE]`.
* **Sécurité cryptographique et écriture atomique** : si `secret_salt` n'est pas modifié dans `config.ini`, un sel aléatoire de 256 bits est généré automatiquement dans `.secret_salt`. Tous les fichiers critiques sont écrits via un fichier temporaire atomique et exclus du suivi Git via `.gitignore`.

---

## 4. Exploitation des deux rapports d'audit

À chaque lot écrit, deux fichiers d'audit sont mis à jour à la racine avec un filtrage strict des mots courants et des prénoms ambigus pour limiter les faux positifs :

* **`audit_noms_residuels.txt`** *(rapport détaillé)* : regroupe les paires `Nom Prénom` et `Prénom Nom` sous une seule entrée canonique classée par priorité (`5+ occurrences`, `2 à 4 occurrences`, `1 occurrence`), avec le nombre d'apparitions et les fichiers concernés. Lorsqu'un nom est proche orthographiquement ou phonétiquement d'un contact connu (ex. erreur de transcription vocale), l'alias est pré-rempli avec la mention `(Proche de '...')`.
* **`audit_noms_residuels_copier.txt`** *(rapport épuré pour copier-coller)* : contient uniquement les lignes au format `Prénom Nom = ` (ou `Prénom Nom = Alias_Suggéré`), sans texte superflu ni commentaire. Copiez-collez directement les lignes retenues dans `contacts_manuels.txt`.
## 5. Compléter et appliquer les contacts manuels

### Option A : Compléter automatiquement les lignes vides (`--complete-manual`)
Si vous collez des lignes `Prénom Nom = ` depuis `audit_noms_residuels_copier.txt` dans `contacts_manuels.txt` sans renseigner d'alias à droite du `=`, vous pouvez les générer automatiquement selon la convention `Prénom I.` :

```bash
# Prévisualiser les alias qui seront générés (sans modifier le fichier)
python lancer_documents.py --complete-manual --dry-run

# Enregistrer les alias générés dans contacts_manuels.txt
python lancer_documents.py --complete-manual
```

### Option B : Appliquer sur place sur les résultats existants (`--manual-only`)
Pour ré-anonymiser immédiatement les lots déjà générés dans `resultats_anonymisation/` à partir de `contacts_manuels.txt` uniquement (ou chaîner la complétion et l'application en une seule commande) :

```bash
python lancer_documents.py --complete-manual --manual-only
```

### Option C : Régénération complète depuis les transcriptions
Si vous modifiez `contacts.txt`, `excluded_words` ou les paramètres de masquage dans `config.ini` et souhaitez reconstruire intégralement les lots :

1. Supprimez le dossier `resultats_anonymisation/` (ou uniquement le fichier `resultats_anonymisation/.etat_anonymisation.json`).
2. Relancez le pipeline complet depuis la racine :

```bash
python lancer_documents.py
```

---

## 6. Générer la version PDF de ce guide

Pour exporter ce guide Markdown en document PDF paginé (ignoré par Git via `.gitignore`) :

```bash
python projet_documents/generate_pdf_guide.py projet_documents/GUIDE_UTILISATION.md
