# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import os
import shutil
import tempfile
import unittest
import zipfile
import pymupdf
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner


class TestWhatsAppZipAndMessengerHtml(unittest.TestCase):
    """
    Valide l'extraction des archives .zip WhatsApp (discussion + pièce jointe PDF)
    et des exports HTML Messenger (message_1.html) avec anonymisation complète.
    """

    def setUp(self) -> None:
        """Prépare un répertoire temporaire isolé."""
        self.test_dir: str = tempfile.mkdtemp(prefix="test_wazip_fbhtml_")
        self.ini_path: str = os.path.join(self.test_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f:
            f.write(
                "[files]\n"
                "first_names_file = prenoms.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "sources_dir = fichiers sources\n"
                "transcriptions_dir = transcriptions\n"
                "results_dir = resultats_anonymisation\n"
                "contacts_file = contacts.txt\n"
                "[extraction]\n"
                "enable_ocr = false\n"
                "enable_audio = false\n"
            )
        with open(os.path.join(self.test_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("jean\nclaire\nsophie\n")
        with open(os.path.join(self.test_dir, "contacts.txt"), "w", encoding="utf-8") as f:
            f.write("jean.dupont@exemple.fr = Jean D.\n")

    def tearDown(self) -> None:
        """Nettoie le répertoire temporaire."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    def test_whatsapp_zip_with_pdf_and_messenger_html(self) -> None:
        """
        Vérifie l'extraction et l'anonymisation d'un .zip WhatsApp contenant
        _chat.txt et un PDF joint, ainsi que d'un fichier message_1.html Messenger.
        """
        sources: str = os.path.join(self.test_dir, "fichiers sources")
        os.makedirs(sources, exist_ok=True)

        pdf_doc = pymupdf.open()
        page = pdf_doc.new_page()
        page.insert_text((72, 72), "Attestation médicale pour Claire Bernard.")
        pdf_bytes: bytes = pdf_doc.tobytes()
        pdf_doc.close()

        zip_path: str = os.path.join(sources, "Discussion WhatsApp avec Claire Bernard.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "_chat.txt",
                "18/09/2024, 09:15 - Claire Bernard : Voici mon attestation en PDF.\n"
                "18/09/2024, 09:20 - Jean Dupont : Merci beaucoup Claire Bernard.\n",
            )
            zf.writestr("00000001-attestation.pdf", pdf_bytes)

        fb_dir: str = os.path.join(sources, "Messenger", "inbox", "sophie_456")
        os.makedirs(fb_dir, exist_ok=True)
        html_content: str = (
            "<html><head><title>Sophie Martin</title></head><body>"
            '<div class="pam _3-95 _2pi0 _2lej uiBoxWhite noborder">'
            '<div class="_3-96 _2pio _2lek _2lel">Sophie Martin</div>'
            '<div class="_3-96 _2let"><div>On se retrouve à 15h devant la mairie.</div></div>'
            '<div class="_3-94 _2lem">12 octobre 2024 à 11:45</div>'
            "</div></body></html>"
        )
        with open(os.path.join(fb_dir, "message_1.html"), "w", encoding="utf-8") as f_html:
            f_html.write(html_content)

        config = PipelineConfig(self.ini_path)
        DocAnonymizerPipelineRunner(config=config, prevent_sleep=False).run_all()

        self.assertTrue(os.path.isdir(os.path.join(config.transcriptions_dir, "2024-09", "Chats")))
        self.assertTrue(os.path.isdir(os.path.join(config.transcriptions_dir, "2024-09", "PDF")))
        self.assertTrue(os.path.isdir(os.path.join(config.transcriptions_dir, "2024-10", "Chats")))

        result_files = [
            os.path.join(rp, fn)
            for rp, _, files in os.walk(config.results_dir)
            for fn in files
            if fn.endswith(".txt")
        ]
        self.assertTrue(result_files)
        merged: str = "\n".join(open(p, "r", encoding="utf-8").read() for p in result_files)

        self.assertIn("WHATSAPP : Claire B.", merged)
        self.assertIn("Attestation médicale pour Claire B.", merged)
        self.assertIn("MESSENGER : Sophie M.", merged)
        self.assertNotIn("Claire Bernard", merged)
        self.assertNotIn("Sophie Martin", merged)


if __name__ == "__main__":
    unittest.main()
