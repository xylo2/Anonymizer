# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import os
import sys
import tempfile
import unittest

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from google_contacts_parser.config_manager import ContactsConfig
from google_contacts_parser.csv_reader import GoogleContactsReader


class TestExtractorsAndEdgeCases(unittest.TestCase):
    """
    Valide l'extraction bureautique (HTML, ICS, cellules numériques)
    et les cas limites du lecteur CSV (couples, inversions, e-mails collés).
    """

    def test_html_and_ics_extractors(self) -> None:
        """
        Vérifie le nettoyage HTML (suppression scripts/styles) et l'extraction ICS.
        """
        extractor = OfficeAndDocumentExtractor(enable_ocr=False)
        self.assertEqual(extractor._format_excel_cell(12345678.0), "12345678")
        self.assertEqual(extractor._format_excel_cell(None), "")

        with tempfile.TemporaryDirectory(prefix="test_ext_") as tmp_dir:
            html_path: str = os.path.join(tmp_dir, "page.html")
            with open(html_path, "w", encoding="utf-8") as f_h:
                f_h.write(
                    "<html><head><style>body{color:red}</style></head>"
                    "<body><h1>Compte rendu</h1><p>Patient&nbsp;: Jean Dupont</p></body></html>"
                )
            txt_h, err_h = extractor.extract_html(html_path)
            self.assertIsNone(err_h)
            assert txt_h is not None
            self.assertIn("Compte rendu", txt_h)
            self.assertIn("Jean Dupont", txt_h)
            self.assertNotIn("color:red", txt_h)

            ics_path: str = os.path.join(tmp_dir, "rdv.ics")
            with open(ics_path, "w", encoding="utf-8") as f_i:
                f_i.write(
                    "BEGIN:VCALENDAR\nBEGIN:VEVENT\n"
                    "DTSTART:20240615T090000Z\n"
                    "SUMMARY:Consultation Dr Martin\n"
                    "END:VEVENT\nEND:VCALENDAR\n"
                )
            txt_i, err_i = extractor.extract_ics(ics_path)
            self.assertIsNone(err_i)
            assert txt_i is not None
            self.assertIn("Consultation Dr Martin", txt_i)
    def test_csv_reader_inversions_and_couples(self) -> None:
        """
        Vérifie la correction automatique Nom/Prénom inversés et les contacts couples.
        """
        with tempfile.TemporaryDirectory(prefix="test_csv_edge_") as tmp_dir:
            prenoms_path: str = os.path.join(tmp_dir, "prenoms.txt")
            with open(prenoms_path, "w", encoding="utf-8") as f_fn:
                f_fn.write("jean\nmarie\nsophie\n")

            csv_path: str = os.path.join(tmp_dir, "contacts.csv")
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f_csv:
                f_csv.write(
                    "First Name;Last Name;E-mail 1 - Value\n"
                    "Dupont;Jean;jean.dupont@exemple.fr\n"
                    "Jean - Marie;Dupont - Martin;famille@exemple.fr\n"
                    ";;sophie.leroy@exemple.fr\n"
                )

            cfg_path: str = os.path.join(tmp_dir, "config.ini")
            with open(cfg_path, "w", encoding="utf-8") as f_cfg:
                f_cfg.write("[files]\nfirst_names_file = prenoms.txt\n")

            reader = GoogleContactsReader(ContactsConfig(cfg_path))
            pairs = dict(reader.parse_file(csv_path))

            self.assertEqual(pairs.get("jean.dupont@exemple.fr"), "Jean Dupont")
            self.assertEqual(pairs.get("famille@exemple.fr"), "Jean Dupont et Marie Martin")
            self.assertEqual(pairs.get("sophie.leroy@exemple.fr"), "Sophie Leroy")


if __name__ == "__main__":
    unittest.main()
