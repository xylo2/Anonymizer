# Guide d'utilisation — Extraction et Anonymisation de Documents

> **Navigation :** [← Retour au README](README.md) | [Architecture technique](ARCHITECTURE.md) | **Guides d'export :** [Contacts & E-mails](docs/exports/CONTACTS_ET_EMAILS.md) • [Google Chat & Teams](docs/exports/MESSAGERIES_PRO.md) • [WhatsApp, Messenger & Signal](docs/exports/MESSAGERIES_PERSO.md)

Ce projet extrait le texte de documents hétérogènes (PDF natifs ou scannés, Word, Excel, PowerPoint, ODT, RTF, HTML, images, agendas ICS, SMS/MMS XML, e-mails `.mbox`/`.eml`, messageries instantanées et enregistrements audio) et les anonymise localement avant analyse.

---

## 1. Préparation des données et méthodologies d'export

Avant de lancer les scripts, exportez vos archives depuis vos différentes plateformes en suivant nos fiches détaillées :

1. **[Contacts, Courriels & SMS](docs/exports/CONTACTS_ET_EMAILS.md)** :
   * Déposez les CSV **Google Contacts** ou **Microsoft Outlook** dans **`export_contacts/`**.
   * Déposez les archives **Gmail (`.mbox`)**, courriels **`.eml`** et sauvegardes **SMS Android (`.xml`)** dans **`fichiers sources/`**.
2. **[Messageries Professionnelles (Google Chat & Microsoft Teams)](docs/exports/MESSAGERIES_PRO.md)** :
   * Déposez le dossier **`Google Chat/Groups/`** (`messages.json`) issu de Google Takeout dans **`fichiers sources/`**.
   * Déposez les exports personnels **Microsoft Teams (`messages.json`)** ou les transcriptions de réunions **`.vtt`** dans **`fichiers sources/`**.
3. **[Messageries Personnelles (WhatsApp, Messenger & Signal)](docs/exports/MESSAGERIES_PERSO.md)** :
   * Déposez les archives **WhatsApp (`.zip` avec médias ou `.txt`)**, dossiers **Messenger (`messages/inbox/`)** et exports **Signal (`.json`)** dans **`fichiers sources/`**.

---

## 2. Architecture des fichiers de contacts

Le pipeline s'appuie sur **trois fichiers de règles complémentaires** pour éviter d'écraser vos ajouts manuels lors des mises à jour d'exports (voir aussi l'[architecture technique](ARCHITECTURE.md)) :

1. **`contacts.txt`** *(généré automatiquement)* : produit par `python lancer_contacts.py` depuis vos exports CSV Google Contacts ou Outlook. Ce fichier peut être régénéré à tout moment sans perte.
2. **`contacts_emails_decouverts.txt`** *(généré automatiquement)* : alimenté après chaque extraction d'e-mails ou de messageries à partir du tampon `tous_emails_trouves.txt`. Il attribue un alias `Contact_Mail_XXX` aux adresses inconnues et déduit automatiquement `Prénom Nom` lorsque l'adresse ou l'en-tête est nominatif. Le fichier tampon `tous_emails_trouves.txt` est purgé après transfert.
3. **`contacts_manuels.txt`** *(géré par vous, jamais écrasé)* : créé automatiquement au premier lancement. Ajoutez-y vos règles personnalisées au format `Prénom Nom = Alias` (ou laissez `Prénom Nom = ` vide pour utiliser `--complete-manual`). Elles sont appliquées en priorité sur les deux autres fichiers.
---

## 3. Exécution des pipelines depuis la racine

### Étape A : Générer l'index automatique des contacts
```bash
python lancer_contacts.py
```

### Étape B : Extraire et anonymiser les documents au fil de l'eau
```bash
python lancer_documents.py
```

* Les transcriptions brutes **non anonymisées** sont enregistrées dans `transcriptions/AAAA-MM/<Catégorie>/` (dont `Chats/` pour toutes les messageries instantanées).
* Les lots anonymisés sont écrits de façon atomique dans `resultats_anonymisation/lot_XX/anonymise_partie_XXX.txt`.
* Si de nouveaux contacts sont découverts dans `tous_emails_trouves.txt`, le pipeline déclenche automatiquement une **seconde passe complète** d'anonymisation.

---

## 4. Règles de masquage automatique et sécurité

En complément des noms et alias définis dans les fichiers de contacts (incluant les variantes inversées `Nom Prénom`, les titres `Dr/Mme/M.` et les noms collés sans espace comme `DUPONTAurelien`), le moteur applique les protections suivantes :

* **Adresses e-mail résiduelles** : remplacées par des jetons déterministes `EMAIL_001`, `EMAIL_002`...
* **Numéros de téléphone résiduels** : formats français et internationaux (`06...`, `+33...`, `0033...`) ainsi que les groupes MMS (`~` ou `+`), remplacés par `TEL_001`, `TEL_002`... Les horodatages compacts `AAAAMMJJHHMMSS` sont préservés pour le classement chronologique.
* **URLs et noms de domaine** : lorsque `mask_urls = true` dans `config.ini`, les liens `http://`, `https://`, `www.` et domaines sont remplacés par `[URL_MASQUEE]`.
* **Identifiants sensibles** : numéros de sécurité sociale (`[NUM_SECU_MASQUE]`), IBAN/BIC (`[IBAN_MASQUE]`), numéros fiscaux, identifiants France Travail, allocataires CAF/MSA, RPPS/CNI/MRZ (`[MRZ_IDENTITE_MASQUEE]`), digicodes (`[CODE_ACCES_MASQUE]`) et plaques d'immatriculation (`[PLAQUE_IMMAT_MASQUEE]`).
* **Adresses postales, dates et lieux** : dates déclarées dans `masked_birth_dates` (`[DATE_MASQUEE]`), dates de naissance contextuelles (`[JOUR_MOIS_MASQUES]/AAAA`), rues, codes postaux, communes et établissements remplacés par `[ADRESSE_MASQUEE]`, `[LIEU_MASQUE]` et `[ETABLISSEMENT_LIEU_MASQUE]`.
* **Sécurité et écriture atomique** : protection anti-XXE sur les fichiers XML, protection anti-ZipSlip sur les archives `.zip` WhatsApp, écriture atomique sur disque et exclusion des données sensibles via `.gitignore`.
---

## 5. Exploitation des deux rapports d'audit

À chaque lot écrit, deux fichiers d'audit sont mis à jour à la racine avec un filtrage strict des mots courants (`mots_exclus.txt`, `collisions_noms.txt`) et des prénoms ambigus pour limiter les faux positifs :

* **`audit_noms_residuels.txt`** *(rapport détaillé)* : regroupe les paires `Nom Prénom` et `Prénom Nom` sous une seule entrée canonique classée par priorité (`5+ occurrences`, `2 à 4 occurrences`, `1 occurrence`), avec le nombre d'apparitions et les fichiers concernés. Lorsqu'un nom est proche orthographiquement ou phonétiquement d'un contact connu (ex. erreur de transcription vocale), l'alias est pré-rempli avec la mention `(Proche de '...')`.
* **`audit_noms_residuels_copier.txt`** *(rapport épuré pour copier-coller)* : contient uniquement les lignes au format `Prénom Nom = ` (ou `Prénom Nom = Alias_Suggéré`), sans texte superflu ni commentaire. Copiez-collez directement les lignes retenues dans `contacts_manuels.txt`.

---

## 6. Compléter et appliquer les contacts manuels

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
Si vous modifiez `contacts.txt`, `mots_exclus.txt` ou les paramètres de masquage dans `config.ini` et souhaitez reconstruire intégralement les lots :

1. Supprimez le dossier `resultats_anonymisation/` (ou uniquement le fichier `resultats_anonymisation/.etat_anonymisation.json`).
2. Relancez le pipeline complet depuis la racine :

```bash
python lancer_documents.py
```

---

## 7. Générer la version PDF de ce guide

Pour exporter ce guide Markdown en document PDF paginé (ignoré par Git via `.gitignore`) :

```bash
python tools/generate_pdf_guide.py GUIDE_UTILISATION.md -o GUIDE_UTILISATION.pdf
