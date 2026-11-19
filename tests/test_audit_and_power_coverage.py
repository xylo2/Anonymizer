# Commandes pip à exécuter : Aucune dépendance externe requise (bibliothèque standard uniquement)

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from doc_anonymizer.audit_state_manager import AuditAndStateManager
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.contact_rules_loader import ContactRulesLoader
from doc_anonymizer.power_manager import SystemSleepInhibitor


class TestAuditAndPowerCoverage(unittest.TestCase):
    """
    Couvre en profondeur AuditAndStateManager (phonétique, suggestions floues,
    filtrage des faux positifs, sauvegarde/chargement JSON) et SystemSleepInhibitor
    (Windows fallback, Linux systemd-inhibit, mode désactivé).
    """

    def setUp(self) -> None:
        """Prépare un environnement temporaire isolé avant chargement de la config."""
        self.test_dir: str = tempfile.mkdtemp(prefix="test_audit_pow_")
        self.ini_path: str = os.path.join(self.test_dir, "config.ini")
        with open(self.ini_path, "w", encoding="utf-8") as f:
            f.write(
                "[files]\n"
                "first_names_file = prenoms.txt\n"
                "[paths]\n"
                "root_dir = .\n"
                "results_dir = resultats_anonymisation\n"
                "contacts_file = contacts.txt\n"
                "manual_contacts_file = contacts_manuels.txt\n"
                "audit_report_file = audit_noms_residuels.txt\n"
                "audit_copy_file = audit_noms_residuels_copier.txt\n"
                "[anonymization]\n"
                "min_audit_occurrences = 1\n"
            )
        with open(os.path.join(self.test_dir, "prenoms.txt"), "w", encoding="utf-8") as f:
            f.write("jean\nsophie\nclaire\nrose\npierre\nmarc\naudrey\n")
        with open(os.path.join(self.test_dir, "contacts.txt"), "w", encoding="utf-8") as f:
            f.write("Jean Dupont = Jean D.\nSophie Martin = Sophie M.\n")

        self.config: PipelineConfig = PipelineConfig(self.ini_path)
        self.rules: ContactRulesLoader = ContactRulesLoader(self.config)
        self.rules.load_all()

    def tearDown(self) -> None:
        """Nettoie le répertoire temporaire."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_audit_phonetic_fuzzy_and_false_positives_filtering(self) -> None:
        """
        Vérifie le calcul phonétique français, les suggestions d'alias proches,
        le rejet des prénoms ambigus/toponymes tronqués et la persistance JSON.
        """
        audit = AuditAndStateManager(self.config, self.rules)

        self.assertEqual(AuditAndStateManager._phonetic_french_key(""), "")
        self.assertEqual(
            AuditAndStateManager._phonetic_french_key("Dupont"),
            AuditAndStateManager._phonetic_french_key("Dubunt"),
        )

        suggestion = audit._suggest_alias_from_fuzzy_last_name("Audrey Dupond")
        self.assertIsNotNone(suggestion)
        assert suggestion is not None
        self.assertEqual(suggestion, ("Audrey D.", "Dupont"))
        self.assertIsNone(audit._suggest_alias_from_fuzzy_last_name("Audrey Sophie"))
        self.assertIsNone(audit._suggest_alias_from_fuzzy_last_name("Audrey Xyz"))

        # Faux positifs : prénom ambigu + mot courant, toponyme tronqué, sigles majuscules
        self.assertFalse(audit._is_plausible_pair("Rose", "Blanche"))
        self.assertFalse(audit._is_plausible_pair("Saint-Martin-De", "Fontenay"))
        self.assertFalse(audit._is_plausible_pair("URSSAF", "CPAM"))
        self.assertFalse(audit._is_valid_word("TEL_001"))
        self.assertFalse(audit._is_valid_word("Code123"))

        # Noms valides avec inversion et titres + niveaux de priorité (5+, 2-4, 1)
        sample_text: str = (
            "Rencontre avec Valmont Audrey et Audrey Valmont.\n"
            "Audrey Valmont confirme avec Audrey Valmont et Audrey Valmont.\n"
            "Suivi de Dr Delacroix et Docteur Delacroix.\n"
            "Note unique pour Audrey Dupond.\n"
        )
        audit.scan_residual_names(sample_text, "dossier/doc1.txt")
        audit.scan_residual_names("Audrey Valmont", "dossier/doc2.txt")
        audit.scan_residual_names("Audrey Valmont", "dossier/doc3.txt")
        audit.scan_residual_names("Audrey Valmont", "dossier/doc4.txt")

        count: int = audit.write_report()
        self.assertGreaterEqual(count, 3)

        with open(self.config.audit_report_file, "r", encoding="utf-8") as f_rep:
            rep_txt: str = f_rep.read()
        self.assertIn("PRIORITÉ HAUTE", rep_txt)
        self.assertIn("PRIORITÉ MOYENNE", rep_txt)
        self.assertIn("OCCURRENCES UNIQUES", rep_txt)
        self.assertIn("Proche de 'Dupont'", rep_txt)
        self.assertIn("autre(s))", rep_txt)

        # Sauvegarde et rechargement JSON avec filtrage d'une entrée invalide
        audit.save()
        with open(self.config.resume_state_file, "r", encoding="utf-8") as f_st:
            state_data = json.load(f_st)
        state_data["compteur_paires"]["Sophie"] = 99
        with open(self.config.resume_state_file, "w", encoding="utf-8") as f_st:
            json.dump(state_data, f_st)

        reloaded = AuditAndStateManager(self.config, self.rules)
        reloaded.load()
        self.assertIn("audrey valmont", reloaded.pair_counter)
        self.assertNotIn("sophie", reloaded.pair_counter)
    def test_power_manager_disabled_linux_and_error_paths(self) -> None:
        """
        Vérifie le mode désactivé (enabled=False), les branches Linux
        (systemd-inhibit présent, absent ou en erreur) et les exceptions Windows
        de SystemSleepInhibitor.
        """
        disabled_inh = SystemSleepInhibitor(enabled=False)
        with disabled_inh:
            self.assertFalse(disabled_inh._win_active)
            self.assertIsNone(disabled_inh._linux_proc)

        fake_proc = MagicMock()
        with patch.object(os, "name", "posix"), patch.object(
            sys, "platform", "linux"
        ), patch("shutil.which", return_value="/usr/bin/systemd-inhibit"), patch(
            "subprocess.Popen", return_value=fake_proc
        ) as mock_popen:
            linux_inh = SystemSleepInhibitor(enabled=True)
            with linux_inh:
                self.assertIs(linux_inh._linux_proc, fake_proc)
                mock_popen.assert_called_once()
            fake_proc.terminate.assert_called_once()
            fake_proc.wait.assert_called_once()
            self.assertIsNone(linux_inh._linux_proc)

        with patch.object(os, "name", "posix"), patch.object(
            sys, "platform", "linux"
        ), patch("shutil.which", return_value="/usr/bin/systemd-inhibit"), patch(
            "subprocess.Popen", side_effect=OSError("Permission denied")
        ):
            err_linux_inh = SystemSleepInhibitor(enabled=True)
            with err_linux_inh:
                self.assertIsNone(err_linux_inh._linux_proc)

        with patch.object(os, "name", "posix"), patch.object(
            sys, "platform", "linux"
        ), patch("shutil.which", return_value=None):
            no_bin_inh = SystemSleepInhibitor(enabled=True)
            with no_bin_inh:
                self.assertIsNone(no_bin_inh._linux_proc)

        with patch.object(os, "name", "nt"), patch.object(
            SystemSleepInhibitor,
            "_apply_windows_state",
            side_effect=RuntimeError("Win32 indisponible"),
        ):
            err_win_inh = SystemSleepInhibitor(enabled=True)
            with err_win_inh:
                self.assertFalse(err_win_inh._win_active)


if __name__ == "__main__":
    unittest.main()
