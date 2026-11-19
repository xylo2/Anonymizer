# Guide d'utilisation — Extraction et Anonymisation de Documents

> **Navigation :** [← Retour au README](../README.md) | [Architecture technique](ARCHITECTURE.md) | **Guides d'export :** [Contacts & E-mails](exports/CONTACTS_ET_EMAILS.md) • [Google Chat & Teams](exports/MESSAGERIES_PRO.md) • [WhatsApp, Messenger & Signal](exports/MESSAGERIES_PERSO.md)

Ce projet extrait le texte de documents hétérogènes (PDF natifs ou scannés, Word, Excel, PowerPoint, ODT, RTF, HTML, images, agendas ICS, SMS/MMS XML, e-mails `.mbox`/`.eml`, messageries instantanées et enregistrements audio) et les anonymise localement avant analyse.

---

## 1. Préparation des données et méthodologies d'export

1. **[Contacts, Courriels & SMS](exports/CONTACTS_ET_EMAILS.md)** :
   * Déposez les CSV **Google Contacts** ou **Microsoft Outlook** dans **`export_contacts/`**.
   * Déposez les archives **Gmail (`.mbox`)**, courriels **`.eml`** et sauvegardes **SMS Android (`.xml`)** dans **`fichiers sources/`**.
2. **[Messageries Professionnelles (Google Chat & Microsoft Teams)](exports/MESSAGERIES_PRO.md)** :
   * Déposez le dossier **`Google Chat/Groups/`** (`messages.json`) dans **`fichiers sources/`**.
   * Déposez les exports personnels **Microsoft Teams (`messages.json`)** ou les transcriptions **`.vtt`** dans **`fichiers sources/`**.
3. **[Messageries Personnelles (WhatsApp, Messenger & Signal)](exports/MESSAGERIES_PERSO.md)** :
   * Dézippez manuellement vos archives **WhatsApp**, puis déposez le dossier obtenu (ou `.txt`), les dossiers **Messenger (`messages/inbox/`)** et exports **Signal (`.json`)** dans **`fichiers sources/`**.

---

## 2. Architecture des fichiers de contacts (`output_contacts/`)

Le pipeline s'appuie sur **trois fichiers de règles complémentaires** regroupés dans **`output_contacts/`** :

1. **`output_contacts/contacts.txt`** *(généré automatiquement)* : produit par `python lancer_contacts.py` depuis vos exports CSV. Les étapes intermédiaires sont conservées dans `output_contacts/.intermediaires/`.
2. **`output_contacts/contacts_emails_decouverts.txt`** *(généré automatiquement)* : alimenté après chaque extraction à partir du tampon `audits/tous_emails_trouves.txt`.
3. **`output_contacts/contacts_manuels.txt`** *(géré par vous, jamais écrasé)* : créé automatiquement au premier lancement. Ajoutez-y vos règles personnalisées au format `Prénom Nom = Alias` (ou `Prénom Nom = ` pour utiliser `--complete-manual`).

---

## 3. Exécution des pipelines depuis la racine

```bash
# Étape A : Générer l'index automatique des contacts
python lancer_contacts.py

# Étape B : Extraire et anonymiser les documents au fil de l'eau
python lancer_documents.py

# Étape C : Exécuter uniquement l'anonymisation complète depuis transcriptions/
python lancer_documents.py --anonymize-only
python lancer_documents.py --anonymize-only --reset-results
```

---

## 4. Exploitation des rapports d'audit (`audits/`)

À chaque lot écrit, deux fichiers d'audit sont mis à jour dans **`audits/`** avec filtrage strict des référentiels situés dans **`data/`** (`mots_exclus.txt`, `collisions_noms.txt`, `villes_masquees.txt`, `prenoms.txt`) :

* **`audits/audit_noms_residuels.txt`** *(rapport détaillé)* : regroupe les paires `Nom Prénom` et `Prénom Nom` sous une entrée canonique classée par priorité (`5+ occurrences`, `2 à 4 occurrences`, `1 occurrence`), avec suggestion phonétique `(Proche de '...')`.
* **`audits/audit_noms_residuels_copier.txt`** *(rapport épuré)* : contient uniquement les lignes au format `Prénom Nom = ` prêtes à coller dans `output_contacts/contacts_manuels.txt`.

---

## 5. Compléter et appliquer les contacts manuels

```bash
# Prévisualiser ou compléter les lignes vides dans output_contacts/contacts_manuels.txt
python lancer_documents.py --complete-manual --dry-run
python lancer_documents.py --complete-manual

# Appliquer sur place sur les lots existants
python lancer_documents.py --complete-manual --manual-only
```

---

## 6. Générer la version PDF de ce guide

```bash
python tools/generate_pdf_guide.py docs/GUIDE_UTILISATION.md -o docs/GUIDE_UTILISATION.pdf
