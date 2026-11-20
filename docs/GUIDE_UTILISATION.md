# Guide d'utilisation — Extraction et Anonymisation de Documents

> **Navigation :** [← Retour au README](../README.md) | [Guide pas-à-pas](../GUIDE_UTILISATION.md) | [Architecture technique](ARCHITECTURE.md) | **Guides d'export :** [Contacts & E-mails](exports/CONTACTS_ET_EMAILS.md) • [Google Chat & Teams](exports/MESSAGERIES_PRO.md) • [WhatsApp, Messenger & Signal](exports/MESSAGERIES_PERSO.md)

Ce projet extrait le texte de documents hétérogènes (PDF natifs ou scannés, Word, Excel, PowerPoint, ODT, RTF, HTML, images, agendas ICS, SMS/MMS XML, e-mails `.mbox`/`.eml`, messageries instantanées et enregistrements audio) et les anonymise localement avant analyse.

---

## 1. Préparation des données et méthodologies d'export

1. **[Contacts, Courriels & SMS](exports/CONTACTS_ET_EMAILS.md)** :
   * Déposez les CSV **Google Contacts** ou **Microsoft Outlook** dans **`input_contacts/`**.
   * Déposez les archives **Gmail (`.mbox`)**, courriels **`.eml`** et sauvegardes **SMS Android (`.xml`)** dans **`input_documents/`**.
2. **[Messageries Professionnelles (Google Chat & Microsoft Teams)](exports/MESSAGERIES_PRO.md)** :
   * Déposez le dossier **`Google Chat/Groups/`** (`messages.json`) dans **`input_documents/`**.
   * Déposez les exports personnels **Microsoft Teams (`messages.json`)** ou les transcriptions **`.vtt`** dans **`input_documents/`**.
3. **[Messageries Personnelles (WhatsApp, Messenger & Signal)](exports/MESSAGERIES_PERSO.md)** :
   * Dézippez manuellement vos archives **WhatsApp**, puis déposez le dossier obtenu (ou `.txt`), les dossiers **Messenger (`messages/inbox/`)** et exports **Signal (`.json`)** dans **`input_documents/`**.

---

## 2. Architecture unifiée des fichiers de contacts (`output_contacts/`)

Le pipeline s'appuie sur **quatre fichiers de règles complémentaires** au format unifié **`Identifiant_Brut = Alias`** regroupés dans **`output_contacts/`** :

1. **`output_contacts/contacts.txt`** *(généré automatiquement)* : produit par `python run_contacts.py` depuis vos exports CSV (ex. `camille.dupont@exemple.fr=Camille D.`), enrichi par le pré-scan des chats et e-mails. Les étapes intermédiaires sont conservées dans `output_contacts/.intermediates/` (`indexed_contacts.txt`, `anonymized_contacts.txt`, `deduplicated_contacts.txt`, `contact_surnames.txt`, `suggested_first_names.txt`).
2. **`output_contacts/discovered_email_contacts.txt`** *(généré automatiquement)* : alimenté depuis les en-têtes de courriels et `audits/all_found_emails.txt`.
3. **`output_contacts/discovered_chat_contacts.txt`** *(généré automatiquement)* : alimenté à partir des participants détectés dans les messageries instantanées.
4. **`output_contacts/manual_contacts.txt`** *(géré par vous, jamais écrasé)* : créé automatiquement au premier lancement. Ajoutez-y vos règles personnalisées au format `Prénom Nom = Alias` (ou `Prénom Nom = ` pour utiliser `--complete-manual`), vos variantes OCR collées (`DUPONTCAMILLE = Camille D.`) ainsi que les dates sensibles (`14/07/1985 = [DATE_MASQUEE]`).

---

## 3. Exécution des pipelines depuis la racine

```bash
# Interface graphique complète (recommandée)
python gui_anonymizer.py

# Ou en ligne de commande :
# Étape A : Générer l'index unifié des contacts (Identifiant_Brut = Alias)
python run_contacts.py

# Étape B : Extraire et anonymiser les documents au fil de l'eau
python run_documents.py

# Étape C : Exécuter uniquement l'anonymisation complète depuis extracted_texts/
python run_documents.py --anonymize-only
python run_documents.py --anonymize-only --reset-results

# Étape D : Extraction nominative seule (OCR + Audio forcés, sans anonymisation)
python run_documents.py --extract-only
```

* Les transcriptions brutes sont enregistrées dans `extracted_texts/AAAA-MM/<Catégorie>/` (suivies par `.extraction_state.txt`, `.sms_state.txt` et `.email_state.txt`).
* Les lots anonymisés sont écrits dans `anonymized_results/batch_XX/anonymized_part_XXX.txt` (suivies par `.anonymization_state.json`).

---

## 4. Exploitation des rapports d'audit et correspondances (`audits/`)

À chaque lot écrit dans **`anonymized_results/`**, les rapports sont mis à jour dans **`audits/`** avec filtrage strict des référentiels situés dans **`data/`** (`mots_exclus.txt`, `collisions_noms.txt`, `villes_masquees.txt`, `prenoms.txt`) :

* **`audits/residual_names_audit.txt`** *(rapport détaillé)* : regroupe les paires `Nom Prénom` et `Prénom Nom` sous une entrée canonique classée par priorité (`5+ occurrences`, `2 à 4 occurrences`, `1 occurrence`), avec suggestion phonétique `(Proche de '...')`.
* **`audits/residual_names_copy.txt`** *(rapport épuré)* : contient uniquement les lignes au format `Prénom Nom = ` prêtes à coller dans `output_contacts/manual_contacts.txt`.
* **`audits/source_files_mapping.json`** *(dictionnaire de traçabilité)* : relie chaque chemin anonymisé (`# SOURCE TRANSCRIPTION : ...`) au fichier extrait brut (`extracted_file` dans `extracted_texts/`), au fichier source initial (`original_source_file` dans `input_documents/`) et au lot final (`batch_file`).
* **`audits/extraction_report.txt`** : liste les éventuels fichiers illisibles ou archives `.zip` ignorées lors de l'extraction.
* **`audits/all_found_emails.txt` et `audits/all_sms_numbers.txt`** : recensent respectivement les adresses e-mail et numéros de téléphone détectés lors de l'extraction.

---

## 5. Retrouver et copier les transcriptions brutes (`--copy-unmasked`)

Lorsqu'un lot anonymisé révèle un fichier à vérifier, vous pouvez copier automatiquement les transcriptions `.txt` non anonymisées correspondantes dans un dossier dédié à partir d'un fichier liste (`.txt` ou `.md`, acceptant des chemins bruts, puces `- ...`, backticks `` `...` `` ou en-têtes `# SOURCE TRANSCRIPTION : ...`) :

```bash
# Via le lanceur principal (dossier de sortie par défaut : transcriptions_non_anonymisees)
python run_documents.py --copy-unmasked liste_fichiers_a_revoir.md --unmasked-dir fichiers_a_revoir

# Ou directement via l'utilitaire dédié (avec chemins passés en arguments ou fichier liste)
python tools/copy_unmasked_transcriptions.py --list-file liste_fichiers_a_revoir.md -o fichiers_a_revoir
```

---

## 6. Compléter et appliquer les contacts manuels

```bash
# Prévisualiser ou compléter les lignes vides dans output_contacts/manual_contacts.txt
python run_documents.py --complete-manual --dry-run
python run_documents.py --complete-manual

# Appliquer sur place sur les lots existants dans anonymized_results/
python run_documents.py --complete-manual --manual-only
```

---

## 7. Générer la version PDF des guides

```bash
# Générer le PDF paginé du guide d'utilisation
python tools/generate_pdf_guide.py docs/GUIDE_UTILISATION.md -o docs/GUIDE_UTILISATION.pdf

# Générer également le PDF paginé de l'architecture technique
python tools/generate_pdf_guide.py docs/ARCHITECTURE.md -o docs/ARCHITECTURE.pdf
