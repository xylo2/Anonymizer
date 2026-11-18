# Suite Locale d'Anonymisation de Contacts et Documents

Outil Python modulaire et 100 % local permettant d'indexer vos contacts (Google Contacts / Outlook), d'extraire le texte de tous vos documents (PDF, Office, images OCR, SMS/MMS XML, e-mails `.mbox`/`.eml`, enregistrements audio Whisper) et d'anonymiser les données personnelles par lots avant analyse.

---

## Arborescence du projet

```text
.
├── config.ini                         # Configuration unifiée des deux pipelines
├── lancer_contacts.py                 # Lanceur racine : génération de contacts.txt
├── lancer_documents.py                # Lanceur racine : extraction, anonymisation et options manuelles
├── prenoms.txt                        # Référentiel partagé des prénoms
├── contacts.txt                       # Règles générées automatiquement depuis les CSV
├── contacts_emails_decouverts.txt     # Règles déduites depuis les en-têtes d'e-mails
├── contacts_manuels.txt               # Règles manuelles prioritaires (jamais écrasées)
├── audit_noms_residuels.txt           # Audit détaillé des noms résiduels (occurrences et sources)
├── audit_noms_residuels_copier.txt    # Audit épuré ('Prénom Nom = ') prêt à copier-coller
├── projet_contacts/                   # Module de parsing et d'anonymisation des exports CSV
└── projet_documents/                  # Module d'extraction multi-formats, d'anonymisation et d'audit
## Démarrage rapide

### 1. Préparer les règles de contacts
Placez vos exports CSV dans `export_contacts/` puis lancez :

```bash
python lancer_contacts.py
```

### 2. Extraire et anonymiser vos documents
Placez vos fichiers dans `fichiers sources/` puis lancez :

```bash
python lancer_documents.py
```

* Les transcriptions brutes sont conservées intactes dans `transcriptions/`.
* Les lots anonymisés sont générés de manière atomique dans `resultats_anonymisation/lot_XX/`.
* Toute adresse e-mail inconnue découverte dans vos `.mbox`/`.eml` enrichit `contacts_emails_decouverts.txt` et déclenche automatiquement une seconde passe complète d'anonymisation.

### 3. Compléter et appliquer vos règles manuelles
Après avoir copié des lignes depuis `audit_noms_residuels_copier.txt` vers `contacts_manuels.txt` :

* **Prévisualiser la génération automatique des alias manquants (`Prénom Nom = `) :**
  ```bash
  python lancer_documents.py --complete-manual --dry-run
  ```
* **Compléter `contacts_manuels.txt` et ré-anonymiser immédiatement les lots existants :**
  ```bash
  python lancer_documents.py --complete-manual --manual-only
  ```

Pour consulter le guide détaillé complet, ouvrez `projet_documents/GUIDE_UTILISATION.md` ou générez sa version PDF via `python projet_documents/generate_pdf_guide.py projet_documents/GUIDE_UTILISATION.md`.
