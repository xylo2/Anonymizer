# Commandes pip à exécuter : Aucune dépendance externe requise

import unittest

try:
    from project_exporter.config import ExporterConfig  # type: ignore[import-not-found]
except ModuleNotFoundError as exc:
    raise unittest.SkipTest("Module optionnel project_exporter absent") from exc
