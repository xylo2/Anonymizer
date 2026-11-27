# Instructions de génération de code (ChromeAI et watch_clipboard)

Respecte impérativement ces règles pour un assemblage fiable sans troncature ni blocage.

## 0. Communication et collaboration
* Explications légères : va directement au code ou au diagnostic court, sans théorie superflue.
* Demande explicite : indique clairement quand il faut fournir une trace, un git diff ou exécuter une commande.
* Relecture des git diff : relis systématiquement tout git diff fourni pour détecter toute régression.

## 1. Format et limites des blocs
* Encadrement obligatoire : encadre chaque fichier ou fragment dans un bloc de code Markdown (trois backticks ouvrants et fermants), avec === END_FILE === placé à l'extérieur du bloc.
* Balise en 1re ligne à l'intérieur du bloc :
  * Fichier complet (<= 65 lignes) : === FILE: chemin/relatif/fichier.ext ===
  * Fichier long (> 65 lignes, N fixe calculé avant 1/N) : === FILE_PART: chemin/relatif/fichier.ext | 1/N ===
* Chemins : chemins relatifs à la racine sans préfixe ni double point.
* Anti-virtualisation : <= 65 lignes par bloc (viser 45-62), <= 88 caractères par ligne, max 2 à 3 blocs par réponse.
* Zéro ellipse : toujours livrer le code intégral de chaque bloc.

## 2. Lisibilité humaine du code généré
* Ne jamais tasser le code : découpe un fichier long en 3/3 ou 4/4 plutôt que de compresser les lignes.
* Aération et structure : une seule instruction par ligne, indentation standard (2 ou 4 espaces), et une ligne vide entre chaque méthode.
* Nommage explicite : privilégier des noms de variables et fonctions clairs plutôt que des abréviations cryptiques.

## 3. Pièges d'affichage web et confidentialité
* Triples backticks dans le code source : construis-les dynamiquement (chr(96) * 3 en Python, String.fromCharCode(96).repeat(3) en JS), jamais en littéral dans les fichiers .py ou .js.
* URLs et fix_urls.py : concatène les URLs avec sous-domaine dans le code ("sub." + "domain.tld").
* Crochets et LaTeX : évite les index numériques entre crochets (préfère le déballage, next(iter(...)) ou .at(0)) ainsi que les symboles dollar ou antislash non échappés.
* Données abstraites : aucun nom, téléphone, e-mail ou chemin réel (Utilisateur_A, 06 00 00 00 01, test1@exemple.invalid).

## 4. Architecture, licence et qualité
* Licence GNU GPL v3 : en-tête GNU GPL v3 obligatoire sur chaque fichier source ; bibliothèques compatibles uniquement en import paresseux.
* Modularité et typage : modules légers (< 250 lignes), typage typing et validation os.path.realpath.
* Tests et couverture (tools/run_tests_clip.py) : échoue sur tout warning Python, mesure la couverture (--report-file, --coverage-file) et copie les erreurs au presse-papiers.
* Langues et docstrings : identifiants et fichiers en anglais ; commentaires, docstrings et commits en français. Chaque méthode et fonction doit obligatoirement avoir une docstring ou un commentaire en français.
