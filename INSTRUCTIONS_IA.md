# Instructions de génération de code (ChromeAI & `watch_clipboard`)

Respecte **impérativement** ces règles afin que l'extension navigateur et `watch_clipboard` assemblent les fichiers sans troncature ni blocage.

---

## 0. Style de communication & collaboration

* **Concision stricte** : pas d'explications détaillées ni de théorie superflue ; va directement au code ou au diagnostic court.
* **Actions utilisateur** : indique explicitement quand une action manuelle de l'utilisateur aide la recherche (ex. : exécuter une commande `unittest` ciblée, coller la trace d'erreur brute, ou réexporter le projet).
* **Relecture systématique des `git diff`** : lorsqu'un `git diff` est fourni en contexte, relis-le systématiquement afin de détecter toute incohérence ou régression (code, options CLI, dépendances, règles de masquage, tests supprimés, ou **URLs / sous-domaines réécrits ou tronqués à tort** comme `://google.com` ou suppression de sous-domaine) avant de proposer un commit ou d'autres modifications.

---

## 1. Balises d'en-tête & stabilité du découpage

* **Placement obligatoire** : la balise `=== FILE: ... ===` ou `=== FILE_PART: ... ===` doit toujours être placée **à l'intérieur** du bloc de code (en première ligne juste après ```` ``` ````), jamais à l'extérieur.
* **Fichier complet (≤ 65 lignes)** :
  `=== FILE: médical/chemin/relatif/du/fichier.py ===`
* **Fichier long (> 65 lignes), découpé en `N` parties** :
  `=== FILE_PART: médical/chemin/relatif/du/fichier.py | 1/N ===`

### Règles strictes
* Utilise uniquement des **chemins relatifs** préfixés par `médical/` avec `/`.
* **Stabilité de `N`** : calcule le nombre total `N` **avant** d'écrire la partie `1/N`. Ne change jamais `N` en cours de livraison (si `N` change, renvoie toutes les parties `1/N` à `N/N`).
* **Zéro note après un bloc** : n'écris jamais de commentaire ou parenthèse juste sous la fermeture d'un bloc de code.
* **Zéro indexation par crochets dans le texte** : évite d'écrire un nom suivi de crochets (supprimés par le parseur Markdown). Préfère `next(iter(seq))`, `next(reversed(pair))` ou le déballage (`a, b = pair`).

---

## 2. Liens Markdown, URLs et préservation des sous-domaines

* **Dans les fichiers Markdown (`.md`)** : utilise toujours un lien explicite `[Nom du service](https://domaine.tld)` sans backticks ni crochets imbriqués dans le libellé. N'écris jamais d'URL brute avec sous-domaine, car le filtre DOM la tronque en `://domaine.tld`.
* **Dans le code Python (`.py`)** : ne mets jamais d'URL littérale contenant un sous-domaine (`"https://domain.tld"`) dans une chaîne statique ; construis-la dynamiquement via un helper (ex. `_u("contacts", "google.com")`) afin que le filtre DOM ne réécrive pas la chaîne littérale.
---

## 3. Limites anti-virtualisation & anti-blocage

* **≤ 65 lignes par bloc** (viser 45–62 lignes) et **≤ 88 caractères par ligne** pour éviter la virtualisation DOM et les retours à la ligne forcés.
* **Maximum 2 à 3 blocs `FILE_PART` par réponse** pour éviter tout coupe-circuit du générateur.
* Coupe toujours proprement entre deux fonctions, méthodes ou paragraphes.

---

## 4. Cache `.watch_clipboard` & intégrité (Zéro ellipse)

* **Première génération** : fournis **toutes les parties (`1/N` à `N/N`)** d'un fichier créé ou modifié pour alimenter le cache `.watch_clipboard`.
* **Mises à jour suivantes** : renvoie uniquement la ou les parties modifiées si `N` reste identique.
* **Strictement interdit** : `# ... reste du code inchangé ...`, `...`, ou de simples *diffs* (`+` / `-`).

---

## 5. Confidentialité & identifiants abstraits

* **Interdiction stricte** : aucun nom réel, prénom réel, téléphone, e-mail, adresse ou identifiant réel dans le code, les commentaires, les tests (`tests/`) ou la documentation.
* **Identifiants abstraits recommandés** : privilégie des libellés abstraits (`Utilisateur_A`, `Contact_Test_1`, `Exemple_Un`, `06 00 00 00 01`, `contact1@exemple.test`, `Dossier_Test_2026`) afin d'éviter tout faux positif des filtres PII.

---

## 6. Architecture modulaire, typage et tests

* **Dépendances** : indiquer en première ligne de code la commande `pip` requise ou `# Commandes pip à exécuter : Aucune dépendance externe requise`.
* **Taille des modules** : maintenir chaque module Python sous ~250-300 lignes (`GuiPagesMixin`, `GuiSecondaryPagesMixin`, `GuiTablesMixin`, `GuiChatTableMixin`).
* **Rétrocompatibilité & lecture seule** : préserver les façades existantes et ne jamais modifier les fichiers externes référencés (`LinkedSourcesManager`).
* **Typage & tests** : annoter avec `typing` et couvrir chaque ajout par un test unitaire dans `médical/tests/` (`tempfile.mkdtemp`), validé via `python médical/tests/run_all_tests.py`.
