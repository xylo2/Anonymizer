# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import shutil
import tempfile
import unittest
from doc_anonymizer.anonymization_runner import DocumentAnonymizationRunner
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.extraction_runner import DocumentExtractionRunner


class TestFalsePositiveGuards(unittest.TestCase):
    """
    Vérifie les garde-fous contre les faux positifs d'anonymisation
    au format unifié Identifiant_Brut = Alias (données strictement fictives).
    """

    def setUp(self) -> None:
        """Prépare un environnement temporaire fictif au format Identifiant = Alias."""
        self.tmp_dir: str = tempfile.mkdtemp(prefix="test_fp_guards_")
        self.cfg_path: str = os.path.join(self.tmp_dir, "config.ini")
        self.contacts_path: str = os.path.join(self.tmp_dir, "contacts.txt")
        self.manual_path: str = os.path.join(self.tmp_dir, "manual_contacts.txt")
        self.places_path: str = os.path.join(self.tmp_dir, "villes_masquees.txt")
        self.first_names_path: str = os.path.join(self.tmp_dir, "prenoms.txt")

        with open(self.first_names_path, "w", encoding="utf-8") as f_fn:
            f_fn.write("camille\nleo\nnathalie\nclaire\n")

        with open(self.contacts_path, "w", encoding="utf-8") as f_c:
            f_c.write("camille.dupont@exemple.fr = Camille D.\n")
            f_c.write("06 12 34 56 78 = Camille D.\n")
            f_c.write("blog.orne@exemple.fr = Orne\n")
            f_c.write("blog.chou@exemple.fr = Chou\n")
            f_c.write("mairie.village@exemple.fr = - Le Maire\n")

        with open(self.manual_path, "w", encoding="utf-8") as f_m:
            f_m.write("DUPONTCAMILLE = Camille D.\n")
            f_m.write("DUPONTLEO = Léo D.\n")
            f_m.write("14/07/1985 = [DATE_MASQUEE]\n")
            f_m.write("01/09/2018 = [DATE_MASQUEE]\n")
            f_m.write("15/09/2018 = [DATE_MASQUEE]\n")

        with open(self.places_path, "w", encoding="utf-8") as f_p:
            f_p.write("Saint-Exemple-sur-Orne\n")
            f_p.write("Ville-Fictive\n")

        with open(self.cfg_path, "w", encoding="utf-8") as f_cfg:
            f_cfg.write(
                "[files]\n"
                "first_names_file = prenoms.txt\n"
                "locations_file = villes_masquees.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = input_documents\n"
                "transcriptions_dir = extracted_texts\n"
                "results_dir = anonymized_results\n"
                "contacts_file = contacts.txt\n"
                "manual_contacts_file = manual_contacts.txt\n"
            )

        self.config: PipelineConfig = PipelineConfig(self.cfg_path)
        self.runner: DocumentAnonymizationRunner = DocumentAnonymizationRunner(self.config)
        self.runner.initialize()

    def tearDown(self) -> None:
        """Nettoie le répertoire temporaire après chaque test."""
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_glued_timestamp_before_email_domain(self) -> None:
        """Vérifie qu'un horaire collé (11:57) n'est pas fusionné dans un e-mail."""
        sample: str = "Le 29/01/2020 11:57claire@exemple.fr a écrit : Bonjour."
        masked: str = self.runner.anonymize_text(sample)
        self.assertIn("11:57", masked)
        self.assertNotIn("11:[ADRESSE_MASQUEE]", masked)
        self.assertIn("EMAIL_001", masked)
    def test_css_styles_and_past_participle_allee_preserved(self) -> None:
        """Vérifie que les styles CSS (0.75rem) et le verbe 'est allée' restent intacts."""
        sample: str = (
            '<div style="margin:0.5rem; padding:0.75rem;">'
            "Nathalie est allée chez elle au 12 rue des Lilas, 14000 Ville-Fictive."
            "</div>"
        )
        masked: str = self.runner.anonymize_text(sample)
        self.assertIn('style="margin:0.5rem; padding:0.75rem;"', masked)
        self.assertIn("est allée chez elle", masked)
        self.assertIn("[ADRESSE_MASQUEE]", masked)
        self.assertNotIn("12 rue des Lilas", masked)

    def test_common_words_and_departments_not_replaced_by_contact_pseudos(self) -> None:
        """Vérifie que 'Orne', 'chou' et 'maire' ne sont pas remplacés par des pseudos de contacts.txt."""
        sample: str = (
            "Le maire habite près de l'Orne et prépare un chou-fleur au marché."
        )
        masked: str = self.runner.anonymize_text(sample)
        self.assertIn("maire", masked)
        self.assertIn("Orne", masked)
        self.assertIn("chou-fleur", masked)

    def test_compact_dates_and_glued_ocr_compounds(self) -> None:
        """Vérifie le masquage des dates (14071985, 01/09/2018) et des noms collés en OCR."""
        sample: str = (
            "DATEDENAISS: 14071985 - Titulaire : MMEDUPONTCAMILLE - "
            "EnfantDUPONTLEO né le 01/09/2018 (ou 15/09/2018)."
        )
        masked: str = self.runner.anonymize_text(sample)
        self.assertNotIn("14071985", masked)
        self.assertNotIn("01/09/2018", masked)
        self.assertNotIn("15/09/2018", masked)
        self.assertIn("MME Camille D.", masked)
        self.assertIn("Enfant Léo D.", masked)

    def test_skip_already_anonymized_source_files(self) -> None:
        """Vérifie que les fichiers préfixés par anonymise_ ou anonymized_ sont ignorés."""
        src_dir: str = self.config.sources_dir
        os.makedirs(src_dir, exist_ok=True)
        already_anon: str = os.path.join(src_dir, "anonymized_export.txt")
        valid_src: str = os.path.join(src_dir, "notes_brutes.txt")
        with open(already_anon, "w", encoding="utf-8") as f_a:
            f_a.write("Camille D. test")
        with open(valid_src, "w", encoding="utf-8") as f_v:
            f_v.write("Contenu brut à extraire")

        extractor: DocumentExtractionRunner = DocumentExtractionRunner(self.config)
        collected = extractor.collect_source_files()
        basenames = [os.path.basename(p) for p in collected]
        self.assertIn("notes_brutes.txt", basenames)
        self.assertNotIn("anonymized_export.txt", basenames)


if __name__ == "__main__":
    unittest.main()
