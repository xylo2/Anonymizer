# Règles du dépôt pour les assistants IA

Consulter et appliquer impérativement l'ensemble des règles définies dans `INSTRUCTIONS_IA.md` à la racine du projet :

1. **Concision & relecture `git diff`** : aller droit au but ; relire systématiquement tout `git diff` fourni pour détecter régressions, suppressions involontaires ou **URLs / sous-domaines réécrits à tort**.
2. **Données abstraites uniquement** : aucune donnée réelle dans le code, les commentaires, les tests ou la documentation (`Utilisateur_A`, `Contact_Test_1`, `Dossier_Test_2026`).
3. **Isolation & lecture seule** : chaque dossier est isolé dans `dossiers/<nom>/` ; ne jamais modifier ni déplacer les fichiers externes référencés (`LinkedSourcesManager`).
4. **Architecture & tests** : modules Python sous ~250-300 lignes, typage (`typing`) et validation systématique via `python tests/run_all_tests.py` (ou `python tools/run_tests_clip.py`).
5. **Liens & sous-domaines** : formater en `[Nom du service](https://domaine.tld)` en Markdown et reconstruire dynamiquement les URLs en Python (`_u("sub", "domain.tld")`) pour éviter la troncature DOM.
6. **Formatage `watch_clipboard`** : balises `=== FILE: ... ===` ou `=== FILE_PART: ... | i/N ===`, ≤ 65 lignes par bloc, ≤ 88 caractères par ligne et zéro ellipse.
