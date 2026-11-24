# Commandes pip à exécuter : Aucune dépendance externe requise

from typing import FrozenSet


class AuditLexicons:
    """Listes lexicales de mots-outils, particules et prénoms ambigus pour l'audit."""

    COMPOUND_PLACE_PARTICLES: FrozenSet[str] = frozenset({
        "de", "du", "des", "d", "sur", "sous", "en", "les", "la", "le", "aux", "au",
    })

    COMMON_FRENCH_STOPWORDS: FrozenSet[str] = frozenset({
        "le", "la", "les", "un", "une", "des", "du", "de", "au", "aux",
        "ce", "cet", "cette", "ces", "mon", "ton", "son", "ma", "ta", "sa",
        "mes", "tes", "ses", "notre", "votre", "leur", "nos", "vos", "leurs",
        "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
        "qui", "que", "quoi", "dont", "ou", "et", "mais", "donc", "or", "ni",
        "car", "pour", "par", "avec", "sans", "sous", "sur", "dans", "vers",
        "chez", "entre", "apres", "avant", "depuis", "pendant", "selon",
        "tres", "plus", "moins", "bien", "mal", "tout", "tous", "toute",
        "toutes", "autre", "autres", "meme", "memes", "aucun", "aucune",
        "chaque", "quel", "quelle", "quels", "quelles", "ici", "la", "oui",
        "non", "pas", "ne", "en", "y", "est", "sont", "etait", "etaient",
        "etre", "avoir", "fait", "faire", "dit", "dire", "voir", "vu",
        "bonjour", "bonsoir", "salut", "merci", "cordialement", "sinceres",
        "salutations", "objet", "sujet", "date", "heure", "lieu", "page",
        "pages", "total", "montant", "numero", "reference", "dossier",
        "document", "documents", "fichier", "fichiers", "piece", "jointe",
        "annexe", "copie", "original", "version", "note", "notes", "avis",
        "compte", "rendu", "bilan", "rapport", "synthese", "resume",
        "contrat", "facture", "devis", "commande", "paiement", "reglement",
        "attestation", "certificat", "ordonnance", "prescription", "courrier",
        "lettre", "message", "mail", "email", "telephone", "adresse", "code",
        "postal", "ville", "pays", "france", "europe", "region", "departement",
        "mairie", "prefecture", "tribunal", "ministere", "service", "services",
        "direction", "directeur", "directrice", "president", "presidente",
        "general", "generale", "secretaire", "responsable", "chef", "agent",
        "docteur", "professeur", "madame", "monsieur", "mademoiselle", "maitre",
        "cabinet", "clinique", "hopital", "centre", "laboratoire", "pharmacie",
        "banque", "assurance", "mutuelle", "caisse", "allocations", "impots",
        "article", "chapitre", "section", "titre", "point", "liste", "tableau",
        "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
        "lun", "mar", "mer", "jeu", "ven", "sam", "dim",
        "janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
        "aout", "septembre", "octobre", "novembre", "decembre", "janv", "fevr",
        "avr", "juil", "sept", "oct", "nov", "dec", "nord", "sud", "est",
        "ouest", "saint", "sainte", "rue", "avenue", "boulevard", "place",
        "delivery", "carte", "recap", "parking", "nouveau", "arbitrage",
        "backlog", "daily", "coord", "donne", "enf", "finalement", "origine",
        "passe", "signature", "signez", "tome", "visualiser", "voici",
        "apparemment", "besoin", "bises", "coordination", "dessins", "dsn",
        "demo", "demonstration", "developpement", "epic", "examens", "fax",
        "fourmi", "gazette", "genre", "gestion", "lorsque", "mascarade",
        "mondial", "plein", "preparation", "puree", "quant", "respire",
        "retour", "reorganisation", "reunions", "taper", "trancher", "union",
        "unite", "appart",
    })

    AMBIGUOUS_FIRST_NAMES: FrozenSet[str] = frozenset({
        "aime", "aimee", "ange", "aube", "aurore", "blanc", "blanche",
        "bon", "cerise", "clair", "claire", "clement", "constance", "desire",
        "douce", "esperance", "fidele", "fleur", "flore", "france", "gai",
        "grace", "guy", "honore", "iris", "jean", "joie", "joli", "joy",
        "juste", "laurier", "loup", "luce", "lumiere", "marc", "marine",
        "max", "may", "modeste", "noel", "olive", "paix", "parfait",
        "patience", "pierre", "premier", "prime", "prudence", "rose",
        "sage", "sauveur", "solange", "soleil", "victoire", "violette",
    })
