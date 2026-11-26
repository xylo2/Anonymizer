import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock
import wave
import numpy as np

ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from doc_anonymizer.comm_extractors import CommunicationExtractor
from doc_anonymizer.config_manager import PipelineConfig
from doc_anonymizer.gui_controller import AnonymizerGuiController
from doc_anonymizer.office_extractors import OfficeAndDocumentExtractor
from doc_anonymizer.workspace_settings_dialog import WorkspaceSettingsManager


class TestAudioTranscriberIntegration(unittest.TestCase):
    """Vérifie l'intégration de audio_transcriber dans AnonVault (diarisation & paramètres)."""

    def setUp(self) -> None:
        self.tmp_root: str = tempfile.mkdtemp(prefix="test_at_anonvault_")
        os.makedirs(os.path.join(self.tmp_root, "data"), exist_ok=True)
        for fn in ("mots_exclus.txt", "prenoms.txt", "collisions_noms.txt", "villes_masquees.txt"):
            with open(os.path.join(self.tmp_root, "data", fn), "w", encoding="utf-8") as f_d:
                f_d.write("# Data\n")
        self.ctrl = AnonymizerGuiController(self.tmp_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_stereo_multi_speaker_transcription_and_settings(self) -> None:
        ini_path: str = self.ctrl.create_workspace("Dossier_Audio_Diarization")
        defaults = WorkspaceSettingsManager.load_settings(ini_path)
        self.assertTrue(defaults["enable_diarization"])

        sr: int = 16000
        t = np.linspace(0.0, 1.0, sr, endpoint=False)
        left = np.concatenate([np.sin(2 * np.pi * 220 * t) * 0.6, np.zeros(sr)])
        right = np.concatenate([np.zeros(sr), np.sin(2 * np.pi * 440 * t) * 0.6])
        stereo_wav: str = os.path.join(self.tmp_root, "appel_0612345678.wav")
        pcm = np.clip(np.column_stack([left, right]) * 32767.0, -32768, 32767).astype(np.int16)
        with wave.open(stereo_wav, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm.tobytes())

        cfg = PipelineConfig(ini_path)
        office_ext = OfficeAndDocumentExtractor(config=cfg, enable_ocr=False)
        comm_ext = CommunicationExtractor(config=cfg, doc_extractor=office_ext)

        fake_segs = [
            SimpleNamespace(start=0.0, end=1.0, text="Bonjour docteur."),
            SimpleNamespace(start=1.0, end=2.0, text="Bonjour, je vous écoute."),
        ]
        fake_model = MagicMock()
        fake_model.transcribe.return_value = (fake_segs, SimpleNamespace(language="fr", duration=2.0))
        comm_ext._whisper_model = fake_model

        txt, err = comm_ext.extract_audio(stereo_wav)
        self.assertIsNone(err)
        assert txt is not None
        self.assertIn("[00:00] Interlocuteur_1 : Bonjour docteur.", txt)
        self.assertIn("[00:01] Interlocuteur_2 : Bonjour, je vous écoute.", txt)

        WorkspaceSettingsManager.save_settings(ini_path, {**defaults, "enable_diarization": False})
        cfg_no_diar = PipelineConfig(ini_path)
        self.assertFalse(cfg_no_diar.enable_diarization)


if __name__ == "__main__":
    unittest.main()
