# Guide d'utilisation — AnonVault — Pièces protégées

> **Navigation :** [← Retour au README](../README.md) | [Guide pas-à-pas](../GUIDE_UTILISATION.md) | [Architecture technique](ARCHITECTURE.md) | **Guides d'export :** [Contacts & E-mails](exports/CONTACTS_ET_EMAILS.md) • [Google Chat & Teams](exports/MESSAGERIES_PRO.md) • [WhatsApp, Messenger & Signal](exports/MESSAGERIES_PERSO.md)

**AnonVault — Pièces protégées** extrait le texte de documents hétérogènes (PDF natifs
ou scannés, Word, Excel, PowerPoint, ODT, RTF, HTML, images OCR, agendas ICS, SMS/MMS
XML, e-mails `.mbox`/`.eml`, archives Outlook `.pst`/`.ost`/`.msg`, messageries
instantanées et enregistrements audio/vidéo) et les anonymise **100 % localement**.

---

## 1. Tableau récapitulatif des exports par service

| Service / Source | Format attendu | Où l'obtenir |
| :--- | :--- | :--- |
| **Google Contacts** | `.csv` *(CSV Google)* | [Google Contacts](https://contacts.google.com) > **Exporter** > **CSV Google** |
| **Apple / iPhone / Mac** | `.vcf` *(vCard)* | App Contacts > **Listes** > appui long **Tous les contacts** > **Exporter** |
| **Outlook / Thunderbird** | `.csv` ou `.vcf` | Contacts > **Gérer les contacts** > **Exporter** |
| **Gmail** | `.mbox` *(dézippé)* | [Google Takeout](https://takeout.google.com) > cocher uniquement **Messagerie** |
| **Outlook Classique (Client lourd)** | `.pst`, `.ost` ou `.msg` | **Fichier** > **Ouvrir et exporter** > **Importer/Exporter** > **`.pst`** *(ou glisser-déposer `.msg`)* |
| **Outlook Web / Apple Mail** | `.eml` | Ouvrir le mail > **`...`** > **Télécharger** |
| **SMS Android** | `.xml` | App **SMS Backup & Restore** > **Sauvegarder** > **Messages** |
| **SMS iPhone** | `.csv` ou `.pdf` | Logiciel local **iMazing** ou **CopyTrans Contacts** |
| **WhatsApp** | `.txt` ou dossier dézippé | Discussion > **Plus** > **Exporter discussion** *(dézipper le `.zip`)* |
| **Google Chat** | `messages.json` | [Google Takeout](https://takeout.google.com) > **Google Chat** > dossier `Groups/` |
| **Microsoft Teams** | `messages.json` ou `.vtt` | Portail confidentialité Microsoft (`.json`) ou réunion > **Télécharger `.vtt`** |
| **Facebook Messenger** | `message_1.json` *(ou `.html`)* | Facebook > **Espace Comptes** > **Télécharger vos informations** > **Messages** |
| **Signal** | `.json` | Signal Desktop via `sigtop` ou sauvegarde Android via `signal-back` |
| **Agendas** | `.ics` | [Google Agenda](https://calendar.google.com) > **Paramètres** > **Importer et exporter** > **Exporter** |

> **Règle d'or pour les archives `.zip` :** par sécurité, **AnonVault** ne décompresse
> jamais automatiquement les fichiers `.zip`. Faites un clic droit > **Extraire tout**
> avant de référencer le dossier obtenu à l'étape 1.
## 2. Préparation des données et guides détaillés

1. **[Contacts, Courriels, SMS & Agendas](exports/CONTACTS_ET_EMAILS.md)** :
   * Déposez les carnets (`.csv`, `.vcf`) directement dans l'interface (Étape 1) ou dans
     `input_contacts/`.
   * Déposez les archives Gmail (`.mbox`), archives Outlook (`.pst`, `.ost`, `.msg`),
     courriels (`.eml`), SMS Android (`.xml`) et agendas (`.ics`) dans vos pièces.
2. **[Messageries Professionnelles (Google Chat & Teams)](exports/MESSAGERIES_PRO.md)** :
   * Référencez le dossier **`Takeout/Google Chat/Groups/`** ou vos exports Teams
     (`messages.json` et transcriptions `.vtt`).
3. **[Messageries Personnelles (WhatsApp, Messenger & Signal)](exports/MESSAGERIES_PERSO.md)** :
   * Dézippez vos exports **WhatsApp** ou **Messenger (`messages/inbox/`)** et
     référencez le dossier extrait à l'étape 1.

---

## 3. Architecture unifiée des contacts et filtres (`output_contacts/` / `contacts/`)

Le pipeline s'appuie sur **quatre fichiers de règles complémentaires** au format unifié
**`Identifiant_Brut = Alias`** :

1. **`contacts.txt`** *(généré automatiquement)* : produit depuis vos exports CSV/vCard
   (ex. `camille.dupont@exemple.test=Camille D.`), enrichi par le pré-scan des chats et
   e-mails. Les étapes intermédiaires sont conservées dans `.intermediates/`.
2. **`discovered_email_contacts.txt`** *(généré automatiquement)* : alimenté depuis les
   en-têtes de courriels et `audits/all_found_emails.txt`.
3. **`discovered_chat_contacts.txt`** *(généré automatiquement)* : alimenté à partir des
   participants détectés dans les messageries instantanées.
4. **`manual_contacts.txt` / `contacts_manuels.txt`** *(géré par vous, jamais écrasé)* :
   recevant vos règles manuelles (`Prénom Nom = Alias`), vos variantes OCR collées
   (`DUPONTCAMILLE = Camille D.`) ainsi que vos dates sensibles (`14/07/1985 = [DATE_MASQUEE]`).
5. **Listes de sélection GUI (`whitelist_contacts.json` et `whitelist_chats.json`)** :
   enregistrent les contacts, numéros SMS et conversations retenus aux étapes 2, 3 et 4.

---

## 4. Exécution depuis l'interface graphique ou en ligne de commande

```bash
# Interface graphique complète (recommandée)
python gui_anonymizer.py

# Ou en ligne de commande (après copie de config.example.ini vers config.ini) :
python run_contacts.py --config config.ini
python run_documents.py --config config.ini

# Ré-anonymiser uniquement depuis extracted_texts/ (ou après modification de règles)
python run_documents.py --config config.ini --anonymize-only
python run_documents.py --config config.ini --anonymize-only --reset-results

# Extraction nominative seule (OCR + Audio forcés, sans anonymisation)
python run_documents.py --config config.ini --extract-only
```

---

## 5. Exploitation des audits, réversibilité et génération PDF

* **`audits/residual_names_audit.txt` & `residual_names_copy.txt`** : listent les noms
  propres résiduels classés par fréquence (`5+`, `2 à 4`, `1`) avec aperçu Avant/Après.
* **`audits/deanon_vault.json`** : coffre local de réversibilité permettant de restituer
  les vraies identités dans les synthèses retournées par l'IA (fichiers `_nominatif`).
* **`audits/source_files_mapping.json`** : relie chaque lot anonymisé au fichier extrait
  (`extracted_texts/`) et à la pièce originale (utilisé par `--copy-unmasked` et le
  **Pack Avocat Nominatif**).
* **Générer la version PDF des guides** :
  ```bash
  python tools/generate_pdf_guide.py docs/GUIDE_UTILISATION.md -o docs/GUIDE_UTILISATION.pdf
  python tools/generate_pdf_guide.py docs/ARCHITECTURE.md -o docs/ARCHITECTURE.pdf
