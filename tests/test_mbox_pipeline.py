# Commandes pip à exécuter : Aucune dépendance externe requise

from email.message import EmailMessage
import mailbox
import os
import sys
import tempfile
from typing import List

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.pipeline_runner import DocAnonymizerPipelineRunner


class MboxPipelineTester:
    """
    Exécute un test d'intégration isolé sur un fichier .mbox factice afin de
    valider l'extraction, la découverte d'e-mails et noms d'affichage MIME,
    le masquage des URLs/téléphones et la seconde passe d'anonymisation.
    """

    def __init__(self, work_dir: str) -> None:
        """
        Initialise les chemins de test dans un répertoire temporaire.

        :param work_dir: Chemin du dossier temporaire isolé.
        """
        self.work_dir: str = work_dir
        self.config_path: str = os.path.join(work_dir, "config.ini")
        self.contacts_path: str = os.path.join(work_dir, "contacts.txt")
        self.first_names_path: str = os.path.join(work_dir, "prenoms.txt")
        self.sources_dir: str = os.path.join(work_dir, "fichiers sources")
        self.mbox_path: str = os.path.join(self.sources_dir, "test_echantillon.mbox")

    def setup_environment(self) -> None:
        """
        Crée les fichiers config.ini, prenoms.txt, contacts.txt et le .mbox de test.
        """
        os.makedirs(self.sources_dir, exist_ok=True)
        with open(self.first_names_path, "w", encoding="utf-8") as f_fn:
            f_fn.write("jean\nsophie\nmarc\n")
        with open(self.contacts_path, "w", encoding="utf-8") as f_ct:
            f_ct.write("jean.dupont@exemple.fr = Jean D.\n")
        with open(self.config_path, "w", encoding="utf-8") as f_cfg:
            f_cfg.write(
                "[files]\nfirst_names_file = prenoms.txt\ninverted_output_file = contacts.txt\n"
                "[paths]\nroot_dir = .\ncontacts_file = contacts.txt\n"
                "manual_contacts_file = contacts_manuels.txt\ndiscovered_contacts_file = contacts_emails_decouverts.txt\n"
                "all_emails_file = tous_emails_trouves.txt\nsources_dir = fichiers sources\n"
                "transcriptions_dir = transcriptions\nresults_dir = resultats_anonymisation\n"
                "audit_report_file = audit_noms_residuels.txt\n"
                "[extraction]\nenable_ocr = false\nenable_audio = false\n"
                "[anonymization]\nmain_character_name = Personnage_Principal\nmask_urls = true\n"
            )
        mbox = mailbox.mbox(self.mbox_path)
        try:
            msg = EmailMessage()
            msg["From"] = "Jean Dupont <jean.dupont@exemple.fr>"
            msg["To"] = "Sophie Leroy <sophie.leroy@cabinet-exemple.fr>"
            msg["Cc"] = "Marc Delacroix <accueil@cabinet-exemple.fr>"
            msg["Date"] = "Wed, 15 May 2024 10:30:00 +0200"
            msg["Subject"] = "Suivi dossier"
            msg.set_content(
                "Bonjour Sophie Leroy et Marc Delacroix,\n"
                "Veuillez consulter https://cabinet-exemple.fr "
                "ou me joindre au +33 6 12 34 56 78.\n"
                "Cordialement, Jean Dupont."
            )
            mbox.add(msg)
            mbox.flush()
        finally:
            mbox.close()

    def run_and_assert(self) -> None:
        """
        Lance le pipeline complet et vérifie toutes les assertions attendues.
        """
        self.setup_environment()
        config: PipelineConfig = PipelineConfig(config_path=self.config_path)
        runner: DocAnonymizerPipelineRunner = DocAnonymizerPipelineRunner(config=config, prevent_sleep=False)
        runner.run_all()

        assert os.path.exists(config.discovered_contacts_file)
        with open(config.discovered_contacts_file, "r", encoding="utf-8") as f_disc:
            disc_content: str = f_disc.read()
        assert "accueil@cabinet-exemple.fr = Contact_Mail_001" in disc_content
        assert "Marc Delacroix = Contact_Mail_001" in disc_content
        assert "sophie.leroy@cabinet-exemple.fr = Contact_Mail_002" in disc_content
        assert "Sophie Leroy = Contact_Mail_002" in disc_content

        result_files: List[str] = [
            os.path.join(rp, fn)
            for rp, _, files in os.walk(config.results_dir)
            for fn in files
            if fn.endswith(".txt")
        ]
        assert result_files
        chunks: List[str] = []
        for p in result_files:
            with open(p, "r", encoding="utf-8") as f_res:
                chunks.append(f_res.read())
        merged: str = "\n".join(chunks)
        assert "Sophie Leroy" not in merged
        assert "Marc Delacroix" not in merged
        assert "Contact_Mail_001" in merged
        assert "Contact_Mail_002" in merged
        assert "[URL_MASQUEE]" in merged
        assert "TEL_001" in merged
        print("\n[SUCCÈS] Toutes les vérifications .mbox ont réussi !", flush=True)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="test_mbox_anon_") as tmp_dir:
        MboxPipelineTester(work_dir=tmp_dir).run_and_assert()
