# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import re
import unicodedata
from typing import Set, Tuple


class FrenchGeoCatalog:
    """
    Référentiel des départements français, régions et grandes villes de France,
    permettant de filtrer les mentions géographiques lors de l'anonymisation.
    """

    DEPARTMENTS: Tuple[str, ...] = (
        "ain", "aisne", "allier", "alpes-de-haute-provence", "hautes-alpes",
        "alpes-maritimes", "ardèche", "ardennes", "ariège", "aube", "aude",
        "aveyron", "bouches-du-rhône", "calvados", "cantal", "charente",
        "charente-maritime", "cher", "corrèze", "corse-du-sud", "haute-corse",
        "côte-d'or", "côtes-d'armor", "creuse", "dordogne", "doubs", "drôme",
        "eure", "eure-et-loir", "finistère", "gard", "haute-garonne", "gers",
        "gironde", "hérault", "ille-et-vilaine", "indre", "indre-et-loire",
        "isère", "jura", "landes", "loir-et-cher", "loire", "haute-loire",
        "loire-atlantique", "loiret", "lot", "lot-et-garonne", "lozère",
        "maine-et-loire", "manche", "marne", "haute-marne", "mayenne",
        "meurthe-et-moselle", "meuse", "morbihan", "moselle", "nièvre", "nord",
        "oise", "orne", "pas-de-calais", "puy-de-dôme", "pyrénées-atlantiques",
        "hautes-pyrénées", "pyrénées-orientales", "bas-rhin", "haut-rhin",
        "rhône", "haute-saône", "saône-et-loire", "sarthe", "savoie",
        "haute-savoie", "paris", "seine-maritime", "seine-et-marne",
        "yvelines", "deux-sèvres", "somme", "tarn", "tarn-et-garonne", "var",
        "vaucluse", "vendée", "vienne", "haute-vienne", "vosges", "yonne",
        "territoire de belfort", "essonne", "hauts-de-seine",
        "seine-saint-denis", "val-de-marne", "val-d'oise", "guadeloupe",
        "martinique", "guyane", "la réunion", "réunion", "mayotte",
    )

    REGIONS: Tuple[str, ...] = (
        "auvergne-rhône-alpes", "bourgogne-franche-comté", "bretagne",
        "centre-val de loire", "corse", "grand est", "hauts-de-france",
        "île-de-france", "normandie", "nouvelle-aquitaine", "occitanie",
        "pays de la loire", "provence-alpes-côte d'azur", "paca",
        "alsace", "aquitaine", "auvergne", "basse-normandie", "bourgogne",
        "centre", "champagne-ardenne", "franche-comté", "haute-normandie",
        "languedoc-roussillon", "limousin", "lorraine", "midi-pyrénées",
        "nord-pas-de-calais", "picardie", "poitou-charentes", "rhône-alpes",
    )
    MAJOR_CITIES: Tuple[str, ...] = (
        "paris", "marseille", "lyon", "toulouse", "nice", "nantes",
        "montpellier", "strasbourg", "bordeaux", "lille", "rennes", "reims",
        "toulon", "saint-étienne", "le havre", "grenoble", "dijon", "angers",
        "villeurbanne", "saint-denis", "nîmes", "clermont-ferrand", "le mans",
        "aix-en-provence", "brest", "tours", "amiens", "limoges", "annecy",
        "boulogne-billancourt", "perpignan", "besançon", "metz", "orléans",
        "argenteuil", "rouen", "mulhouse", "montreuil", "caen",
        "saint-paul", "nancy", "nouméa", "tourcoing", "roubaix", "nanterre",
        "vitry-sur-seine", "créteil", "avignon", "poitiers", "aubervilliers",
        "asnières-sur-seine", "colombes", "aulnay-sous-bois", "versailles",
        "courbevoie", "cherbourg-en-cotentin", "cherbourg",
        "rueil-malmaison", "béziers", "pau", "la rochelle", "saint-maur-des-fossés",
        "calais", "cannes", "antibes", "dunkerque", "saint-nazaire", "colmar",
        "mérignac", "drancy", "issy-les-moulineaux", "noisy-le-grand",
        "évry-courcouronnes", "évry", "cergy", "pessac", "vénissieux",
        "clichy", "la seyne-sur-mer", "ivry-sur-seine", "quimper", "valence",
        "antony", "troyes", "montauban", "neuilly-sur-seine", "pantin",
        "niort", "chambéry", "sarcelles", "le blanc-mesnil", "lorient",
        "beauvais", "maisons-alfort", "meaux", "narbonne", "villejuif",
        "hyères", "la roche-sur-yon", "chemnitz", "cholet", "bondy",
        "bobigny", "clamart", "vannes", "épinay-sur-seine", "sartrouville",
        "corbeil-essonnes", "bayonne", "cagnes-sur-mer", "saint-ouen",
        "seine-saint-denis", "massy", "vincennes", "montrouge", "suresnes",
        "martigues", "albi", "laval", "belfort", "évreux", "charleville-mézières",
        "brive-la-gaillarde", "saint-malo", "blois", "chalon-sur-saône",
        "carcassonne", "saint-brieuc", "châteauroux", "tarbes", "angoulême",
        "arras", "boulogne-sur-mer", "gap", "auxerre", "nevers", "lisieux",
        "bayeux", "vire", "falaise", "honfleur", "deauville", "trouville",
        "granville", "saint-lô", "alençon", "flers", "argentan", "hérouville-saint-clair",
    )
    @staticmethod
    def normalize_geo_token(text: str) -> str:
        """
        Normalise un nom géographique (minuscules, sans accents, espaces ni tirets)
        afin d'uniformiser les comparaisons (ex: 'Thury Harcourt' == 'thury-harcourt').

        :param text: Libellé géographique brut.
        :return: Chaîne normalisée compacte.
        """
        nfkd: str = unicodedata.normalize("NFKD", text.strip().lower())
        without_accents: str = "".join(c for c in nfkd if not unicodedata.combining(c))
        return re.sub(r"[\s\-']", "", without_accents)

    @classmethod
    def build_normalized_set(cls, extra_locations: Set[str]) -> Set[str]:
        """
        Construit l'ensemble complet des noms géographiques normalisés (départements,
        régions, grandes villes et communes supplémentaires configurées).

        :param extra_locations: Ensemble de communes ou lieux personnalisés issus de config.ini.
        :return: Ensemble unifié des identifiants géographiques normalisés.
        """
        all_raw: Set[str] = (
            set(cls.DEPARTMENTS)
            | set(cls.REGIONS)
            | set(cls.MAJOR_CITIES)
            | set(extra_locations)
        )
        return {cls.normalize_geo_token(item) for item in all_raw if item.strip()}
