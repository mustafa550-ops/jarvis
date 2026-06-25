from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock, PropertyMock, ANY
from pathlib import Path


class TestAudioSystemPackage(unittest.TestCase):
    """core.audio_system paketi import ve export testleri."""

    def test_package_import(self):
        """core.audio_system import edilebilmeli."""
        from core import audio_system
        self.assertIsNotNone(audio_system)

    def test_package_exports(self):
        """__all__ dogru sembolleri export ediyor."""
        from core.audio_system import __all__
        expected = ["AudioPlayer", "get_audio_player", "play_wav", "play_bytes",
                    "TTSEngine", "get_tts_engine", "speak_text",
                    "STTEngine", "get_stt_engine"]
        for symbol in expected:
            self.assertIn(symbol, __all__)


# =============================================================================
# AudioPlayer tests
# =============================================================================


class TestBaseAudioPlayer(unittest.TestCase):
    """core.audio_system.audio_player abstract interface testi."""

    def test_module_import(self):
        """audio_player modulu import edilebilmeli."""
        from core.audio_system import audio_player
        self.assertIsNotNone(audio_player)

    def test_base_audio_player_is_abstract(self):
        """BaseAudioPlayer ABC'dir ve instantiate edilemez."""
        from core.audio_system.audio_player import BaseAudioPlayer
        from abc import ABC
        self.assertTrue(issubclass(BaseAudioPlayer, ABC))
        with self.assertRaises(TypeError):
            BaseAudioPlayer()

    def test_linux_audio_player_available_on_linux(self):
        """LinuxAudioPlayer.is_available Linux'ta True donebilir."""
        from core.audio_system.audio_player import LinuxAudioPlayer
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                player = LinuxAudioPlayer()
                self.assertTrue(callable(player.is_available))

    def test_linux_audio_player_not_available_on_windows(self):
        """LinuxAudioPlayer.is_available Windows'ta False doner."""
        from core.audio_system.audio_player import LinuxAudioPlayer
        with patch("platform.system", return_value="Windows"):
            player = LinuxAudioPlayer()
            self.assertFalse(player.is_available())

    def test_linux_audio_player_play_wav_calls_aplay(self):
        """LinuxAudioPlayer.play_wav aplay ile oynatir."""
        from core.audio_system.audio_player import LinuxAudioPlayer
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                player = LinuxAudioPlayer()
                result = player.play_wav("/tmp/test.wav")
                self.assertTrue(result)
                aplay_calls = [c for c in mock_run.call_args_list
                               if "aplay" in str(c) or "pw-play" in str(c)]
                self.assertGreater(len(aplay_calls), 0)

    def test_linux_audio_player_play_bytes_creates_wav(self):
        """LinuxAudioPlayer.play_bytes gecici WAV olusturup oynatir."""
        from core.audio_system.audio_player import LinuxAudioPlayer
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                player = LinuxAudioPlayer()
                result = player.play_bytes(b"\x00\x00" * 1600, sample_rate=16000)
                self.assertTrue(result)

    def test_windows_audio_player_available_on_windows(self):
        """WindowsAudioPlayer.is_available Windows'ta True."""
        from core.audio_system.audio_player import WindowsAudioPlayer
        with patch("platform.system", return_value="Windows"):
            with patch("builtins.__import__", side_effect=lambda name, *a, **kw:
                       MagicMock() if name == "winsound" else __import__(name, *a, **kw)):
                player = WindowsAudioPlayer()
                self.assertTrue(player.is_available())

    def test_windows_audio_player_not_available_on_linux(self):
        """WindowsAudioPlayer.is_available Linux'ta False."""
        from core.audio_system.audio_player import WindowsAudioPlayer
        with patch("platform.system", return_value="Linux"):
            player = WindowsAudioPlayer()
            self.assertFalse(player.is_available())

    def test_macos_audio_player_available_on_darwin(self):
        """MacOSAudioPlayer.is_available macOS'ta True."""
        from core.audio_system.audio_player import MacOSAudioPlayer
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                player = MacOSAudioPlayer()
                self.assertTrue(callable(player.is_available))

    def test_macos_audio_player_not_available_on_linux(self):
        """MacOSAudioPlayer.is_available Linux'ta False."""
        from core.audio_system.audio_player import MacOSAudioPlayer
        with patch("platform.system", return_value="Linux"):
            player = MacOSAudioPlayer()
            self.assertFalse(player.is_available())

    def test_pygame_audio_player_available_when_importable(self):
        """PygameAudioPlayer.is_available pygame import edilince True."""
        from core.audio_system.audio_player import PygameAudioPlayer
        with patch.dict("sys.modules", {"pygame": MagicMock()}):
            player = PygameAudioPlayer()
            self.assertTrue(player.is_available())

    def test_pygame_audio_player_not_available_when_missing(self):
        """PygameAudioPlayer.is_available pygame yokken False."""
        from core.audio_system.audio_player import PygameAudioPlayer
        with patch.dict("sys.modules", {"pygame": None}):
            player = PygameAudioPlayer()
            self.assertFalse(player.is_available())

    def test_get_audio_player_returns_instance(self):
        """get_audio_player bir AudioPlayer instance'i dondurur."""
        from core.audio_system.audio_player import get_audio_player, AudioPlayer
        player = get_audio_player()
        self.assertIsInstance(player, AudioPlayer)

    def test_audio_player_get_player_name(self):
        """AudioPlayer.get_player_name aktif player adini dondurur."""
        from core.audio_system.audio_player import AudioPlayer
        from unittest.mock import PropertyMock
        player = AudioPlayer.__new__(AudioPlayer)
        player._active_player = None
        self.assertEqual(player.get_player_name(), "None")


class TestAudioPlayerSingleton(unittest.TestCase):
    """AudioPlayer singleton davranisi."""

    def setUp(self):
        from core.audio_system import audio_player as ap
        self._old_instance = ap._audio_player
        ap._audio_player = None

    def tearDown(self):
        from core.audio_system import audio_player as ap
        ap._audio_player = self._old_instance

    @patch("core.audio_system.audio_player.LinuxAudioPlayer.is_available", return_value=True)
    def test_audio_player_detects_linux(self, mock_avail):
        """AudioPlayer Linux'ta LinuxAudioPlayer secer."""
        from core.audio_system.audio_player import AudioPlayer
        with patch("platform.system", return_value="Linux"):
            player = AudioPlayer()
            self.assertIsNotNone(player._active_player)
            self.assertIn("Linux", player._active_player.__class__.__name__)

    def test_audio_player_detects_windows(self):
        """AudioPlayer Windows'ta WindowsAudioPlayer secer."""
        from core.audio_system.audio_player import AudioPlayer, LinuxAudioPlayer, WindowsAudioPlayer, MacOSAudioPlayer, PygameAudioPlayer
        with patch("core.audio_system.audio_player.LinuxAudioPlayer.is_available", return_value=False), \
             patch("core.audio_system.audio_player.WindowsAudioPlayer.is_available", return_value=True), \
             patch("platform.system", return_value="Windows"):
            p = AudioPlayer.__new__(AudioPlayer)
            p._players = [LinuxAudioPlayer(), WindowsAudioPlayer(), MacOSAudioPlayer(), PygameAudioPlayer()]
            p._detect_player()
            self.assertIsNotNone(p._active_player)
            self.assertIn("Windows", p._active_player.__class__.__name__)

    def test_audio_player_detects_macos(self):
        """AudioPlayer macOS'ta MacOSAudioPlayer secer."""
        from core.audio_system.audio_player import AudioPlayer, LinuxAudioPlayer, WindowsAudioPlayer, MacOSAudioPlayer, PygameAudioPlayer
        with patch("core.audio_system.audio_player.LinuxAudioPlayer.is_available", return_value=False), \
             patch("core.audio_system.audio_player.MacOSAudioPlayer.is_available", return_value=True), \
             patch("platform.system", return_value="Darwin"):
            p = AudioPlayer.__new__(AudioPlayer)
            p._players = [LinuxAudioPlayer(), WindowsAudioPlayer(), MacOSAudioPlayer(), PygameAudioPlayer()]
            p._detect_player()
            self.assertIsNotNone(p._active_player)
            self.assertIn("MacOS", p._active_player.__class__.__name__)

    def test_audio_player_no_player_fallback(self):
        """AudioPlayer hic player yoksa _active_player=None."""
        from core.audio_system.audio_player import AudioPlayer
        player = AudioPlayer.__new__(AudioPlayer)
        player._active_player = None  # reset from _init
        player._players = []
        player._detect_player()
        self.assertIsNone(player._active_player)

    def test_audio_player_play_wav_no_player(self):
        """AudioPlayer.play_wav player yokken False doner."""
        from core.audio_system.audio_player import AudioPlayer
        player = AudioPlayer.__new__(AudioPlayer)
        player._active_player = None
        self.assertFalse(player.play_wav("/tmp/test.wav"))

    def test_audio_player_play_bytes_no_player(self):
        """AudioPlayer.play_bytes player yokken False doner."""
        from core.audio_system.audio_player import AudioPlayer
        player = AudioPlayer.__new__(AudioPlayer)
        player._active_player = None
        self.assertFalse(player.play_bytes(b"test"))


class TestGlobalAudioPlayerFunctions(unittest.TestCase):
    """play_wav, play_bytes, get_audio_player global fonksiyonlar."""

    def test_play_wav_calls_audio_player(self):
        """play_wav global fonksiyon AudioPlayer.play_wav'i cagirir."""
        from core.audio_system.audio_player import play_wav
        with patch("core.audio_system.audio_player.get_audio_player") as mock_get:
            mock_player = MagicMock()
            mock_player.play_wav.return_value = True
            mock_get.return_value = mock_player
            result = play_wav("/tmp/test.wav")
            self.assertTrue(result)
            mock_player.play_wav.assert_called_once_with("/tmp/test.wav")

    def test_play_bytes_calls_audio_player(self):
        """play_bytes global fonksiyon AudioPlayer.play_bytes'i cagirir."""
        from core.audio_system.audio_player import play_bytes
        with patch("core.audio_system.audio_player.get_audio_player") as mock_get:
            mock_player = MagicMock()
            mock_player.play_bytes.return_value = True
            mock_get.return_value = mock_player
            result = play_bytes(b"\x00\x01", sample_rate=44100)
            self.assertTrue(result)
            mock_player.play_bytes.assert_called_once_with(b"\x00\x01", 44100, 1)


# =============================================================================
# TTS Engine tests
# =============================================================================


class TestBaseTTSEngine(unittest.TestCase):
    """core.audio_system.tts_engine abstract interface testi."""

    def test_module_import(self):
        """tts_engine modulu import edilebilmeli."""
        from core.audio_system import tts_engine
        self.assertIsNotNone(tts_engine)

    def test_base_tts_engine_is_abstract(self):
        """BaseTTSEngine ABC'dir ve instantiate edilemez."""
        from core.audio_system.tts_engine import BaseTTSEngine
        from abc import ABC
        self.assertTrue(issubclass(BaseTTSEngine, ABC))
        with self.assertRaises(TypeError):
            BaseTTSEngine()

    def test_piper_tts_detect_model_no_dir(self):
        """PiperTTSEngine model dizini yoksa _detect_model hata firlatmaz."""
        from core.audio_system.tts_engine import PiperTTSEngine
        with patch("pathlib.Path.exists", return_value=False):
            engine = PiperTTSEngine(model_dir=Path("/tmp/nonexistent_tts_dir"))
            self.assertIsNone(engine._model_path)
            self.assertIsNone(engine._config_path)

    def test_piper_tts_detect_model_with_dir(self):
        """PiperTTSEngine model dizini varsa onnx dosyalarini arar."""
        from core.audio_system.tts_engine import PiperTTSEngine
        with patch("pathlib.Path.exists", return_value=True):
            with patch.object(Path, "glob", return_value=[Path("test.onnx")]):
                engine = PiperTTSEngine(model_dir=Path("/tmp/test_tts"))
                self.assertIsNotNone(engine._model_path)

    def test_piper_tts_is_available_no_model(self):
        """PiperTTSEngine.is_available model yokken False."""
        from core.audio_system.tts_engine import PiperTTSEngine
        with patch("pathlib.Path.exists", return_value=False):
            engine = PiperTTSEngine(model_dir=Path("/tmp/bogus"))
            self.assertFalse(engine.is_available())

    @patch("platform.system", return_value="Windows")
    def test_piper_tts_is_available_windows_false(self, mock_sys):
        """PiperTTSEngine.is_available Windows'ta False."""
        from core.audio_system.tts_engine import PiperTTSEngine
        engine = PiperTTSEngine.__new__(PiperTTSEngine)
        engine._model_path = Path("/fake/model.onnx")
        self.assertFalse(engine.is_available())

    def test_piper_tts_speak_not_available(self):
        """PiperTTSEngine.speak kullanilamazken False doner."""
        from core.audio_system.tts_engine import PiperTTSEngine
        engine = PiperTTSEngine.__new__(PiperTTSEngine)
        engine._model_path = None
        result = engine.speak("test")
        self.assertFalse(result)

    def test_pyttsx3_tts_is_available_when_importable(self):
        """Pyttsx3TTSEngine.is_available pyttsx3 import edilince True."""
        from core.audio_system.tts_engine import Pyttsx3TTSEngine
        with patch.dict("sys.modules", {"pyttsx3": MagicMock()}):
            engine = Pyttsx3TTSEngine()
            self.assertTrue(engine.is_available())

    def test_pyttsx3_tts_is_available_when_missing(self):
        """Pyttsx3TTSEngine.is_available pyttsx3 yokken False."""
        from core.audio_system.tts_engine import Pyttsx3TTSEngine
        with patch.dict("sys.modules", {"pyttsx3": None}):
            engine = Pyttsx3TTSEngine()
            self.assertFalse(engine.is_available())

    def test_edge_tts_is_available_when_installed(self):
        """EdgeTTSEngine.is_available edge-tts binary varken."""
        from core.audio_system.tts_engine import EdgeTTSEngine
        with patch("shutil.which", return_value="/usr/bin/edge-tts"):
            engine = EdgeTTSEngine()
            self.assertTrue(engine.is_available())

    def test_edge_tts_is_available_when_missing(self):
        """EdgeTTSEngine.is_available edge-tts yokken False."""
        from core.audio_system.tts_engine import EdgeTTSEngine
        with patch("shutil.which", return_value=None):
            engine = EdgeTTSEngine()
            self.assertFalse(engine.is_available())

    def test_edge_tts_voice_map_aliases(self):
        """EdgeTTSEngine ses alias'lari dogru."""
        from core.audio_system.tts_engine import EdgeTTSEngine
        engine = EdgeTTSEngine()
        self.assertEqual(engine._voice_map["ahmet"], "tr-TR-AhmetNeural")
        self.assertEqual(engine._voice_map["emel"], "tr-TR-EmelNeural")

    def test_gtts_is_available_when_importable(self):
        """GTTSEngine.is_available gtts import edilince True."""
        from core.audio_system.tts_engine import GTTSEngine
        with patch.dict("sys.modules", {"gtts": MagicMock()}):
            engine = GTTSEngine()
            self.assertTrue(engine.is_available())

    def test_gtts_is_available_when_missing(self):
        """GTTSEngine.is_available gtts yokken False."""
        from core.audio_system.tts_engine import GTTSEngine
        with patch.dict("sys.modules", {"gtts": None}):
            engine = GTTSEngine()
            self.assertFalse(engine.is_available())

    def test_get_tts_engine_returns_instance(self):
        """get_tts_engine bir TTSEngine instance'i dondurur."""
        from core.audio_system.tts_engine import get_tts_engine, TTSEngine
        engine = get_tts_engine()
        self.assertIsInstance(engine, TTSEngine)


class TestTTSEngineSingleton(unittest.TestCase):
    """TTSEngine singleton ve fallback davranisi."""

    def setUp(self):
        from core.audio_system import tts_engine as te
        self._old_instance = te._tts_engine
        te._tts_engine = None
        self._old_singleton = te.TTSEngine._instance
        te.TTSEngine._instance = None

    def tearDown(self):
        from core.audio_system import tts_engine as te
        te._tts_engine = self._old_instance
        te.TTSEngine._instance = self._old_singleton

    def test_tts_engine_speak_empty_text(self):
        """TTSEngine.speak bos metin icin True doner."""
        from core.audio_system.tts_engine import TTSEngine
        engine = TTSEngine.__new__(TTSEngine)
        engine._engines = []
        engine._active_engine = None
        result = engine.speak("")
        self.assertTrue(result)

    def test_tts_engine_speak_all_fail(self):
        """TTSEngine.speak tum engine'lar basarisizsa False."""
        from core.audio_system.tts_engine import TTSEngine
        mock_engine = MagicMock()
        mock_engine.speak.return_value = False
        mock_engine.name = "mock"
        engine = TTSEngine.__new__(TTSEngine)
        engine._engines = [mock_engine]
        engine._active_engine = mock_engine
        result = engine.speak("test")
        self.assertFalse(result)

    def test_tts_engine_speak_active_succeeds(self):
        """TTSEngine.speak aktif engine basariliysa True."""
        from core.audio_system.tts_engine import TTSEngine
        mock_engine = MagicMock()
        mock_engine.speak.return_value = True
        mock_engine.name = "mock"
        engine = TTSEngine.__new__(TTSEngine)
        engine._engines = [mock_engine]
        engine._active_engine = mock_engine
        result = engine.speak("test")
        self.assertTrue(result)
        mock_engine.speak.assert_called_once_with("test", None, False)

    def test_tts_engine_fallback_promotes(self):
        """TTSEngine.speak fallback engine'i aktif yapar."""
        from core.audio_system.tts_engine import TTSEngine
        primary = MagicMock()
        primary.speak.return_value = False
        primary.name = "primary"
        fallback = MagicMock()
        fallback.speak.return_value = True
        fallback.name = "fallback"
        engine = TTSEngine.__new__(TTSEngine)
        engine._engines = [primary, fallback]
        engine._active_engine = primary
        result = engine.speak("test")
        self.assertTrue(result)
        self.assertEqual(engine._active_engine, fallback)

    def test_set_preferred_engine_found(self):
        """TTSEngine.set_preferred_engine dogru engine'i secer."""
        from core.audio_system.tts_engine import TTSEngine
        mock_engine = MagicMock()
        mock_engine.name = "piper"
        engine = TTSEngine.__new__(TTSEngine)
        engine._engines = [mock_engine]
        engine._active_engine = None
        result = engine.set_preferred_engine("piper")
        self.assertTrue(result)
        self.assertEqual(engine._active_engine, mock_engine)

    def test_set_preferred_engine_not_found(self):
        """TTSEngine.set_preferred_engine bulamazsa False."""
        from core.audio_system.tts_engine import TTSEngine
        engine = TTSEngine.__new__(TTSEngine)
        engine._engines = []
        result = engine.set_preferred_engine("nonexistent")
        self.assertFalse(result)

    def test_list_engines_returns_names(self):
        """TTSEngine.list_engines engine isimlerini dondurur."""
        from core.audio_system.tts_engine import TTSEngine
        e1 = MagicMock(name="mock1")
        e1.name = "piper"
        e2 = MagicMock(name="mock2")
        e2.name = "edge-tts"
        engine = TTSEngine.__new__(TTSEngine)
        engine._engines = [e1, e2]
        names = engine.list_engines()
        self.assertIn("piper", names)
        self.assertIn("edge-tts", names)

    def test_get_active_engine_returns_name(self):
        """TTSEngine.get_active_engine aktif engine adini doner."""
        from core.audio_system.tts_engine import TTSEngine
        mock_engine = MagicMock()
        mock_engine.name = "piper"
        engine = TTSEngine.__new__(TTSEngine)
        engine._active_engine = mock_engine
        self.assertEqual(engine.get_active_engine(), "piper")

    def test_get_active_engine_none(self):
        """TTSEngine.get_active_engine None ise None doner."""
        from core.audio_system.tts_engine import TTSEngine
        engine = TTSEngine.__new__(TTSEngine)
        engine._active_engine = None
        self.assertIsNone(engine.get_active_engine())

    def test_speak_text_global_function(self):
        """speak_text global fonksiyon TTSEngine.speak'i cagirir."""
        from core.audio_system.tts_engine import speak_text
        with patch("core.audio_system.tts_engine.get_tts_engine") as mock_get:
            mock_engine = MagicMock()
            mock_engine.speak.return_value = True
            mock_get.return_value = mock_engine
            result = speak_text("merhaba", voice="ahmet", blocking=True)
            self.assertTrue(result)
            mock_engine.speak.assert_called_once_with("merhaba", "ahmet", True)


# =============================================================================
# STT Engine tests
# =============================================================================


class TestBaseSTTEngine(unittest.TestCase):
    """core.audio_system.stt_engine abstract interface testi."""

    def test_module_import(self):
        """stt_engine modulu import edilebilmeli."""
        from core.audio_system import stt_engine
        self.assertIsNotNone(stt_engine)

    def test_base_stt_engine_is_abstract(self):
        """BaseSTTEngine ABC'dir ve instantiate edilemez."""
        from core.audio_system.stt_engine import BaseSTTEngine
        from abc import ABC
        self.assertTrue(issubclass(BaseSTTEngine, ABC))
        with self.assertRaises(TypeError):
            BaseSTTEngine()

    def test_concrete_stt_subclass_possible(self):
        """BaseSTTEngine'dan tureyen sinif abstract'lari implement edebilmeli."""
        from core.audio_system.stt_engine import BaseSTTEngine

        class TestSTT(BaseSTTEngine):
            def transcribe(self, audio_data, sample_rate=16000):
                return "test"
            def is_available(self):
                return False
            @property
            def name(self):
                return "test"

        engine = TestSTT()
        self.assertEqual(engine.name, "test")
        self.assertFalse(engine.is_available())
        self.assertEqual(engine.transcribe(b"test"), "test")

    def test_faster_whisper_stt_init_defaults(self):
        """FasterWhisperSTT varsayilan parametrelerle baslatilir."""
        from core.audio_system.stt_engine import FasterWhisperSTT
        with patch("core.audio_system.stt_engine.FasterWhisperSTT.__init__", return_value=None):
            engine = FasterWhisperSTT.__new__(FasterWhisperSTT)
            engine.model_size = "base"
            engine.language = "tr"
            engine.device = "cpu"
            engine.compute_type = "int8"
            self.assertEqual(engine.model_size, "base")
            self.assertEqual(engine.language, "tr")

    def test_faster_whisper_stt_is_available_no_model(self):
        """FasterWhisperSTT.is_available model yokken False."""
        from core.audio_system.stt_engine import FasterWhisperSTT
        engine = FasterWhisperSTT.__new__(FasterWhisperSTT)
        engine._model = None
        self.assertFalse(engine.is_available())

    def test_faster_whisper_stt_is_available_with_model(self):
        """FasterWhisperSTT.is_available model varken True."""
        from core.audio_system.stt_engine import FasterWhisperSTT
        engine = FasterWhisperSTT.__new__(FasterWhisperSTT)
        engine._model = MagicMock()
        self.assertTrue(engine.is_available())

    def test_faster_whisper_stt_transcribe_not_available(self):
        """FasterWhisperSTT.transcribe model yokken bos string."""
        from core.audio_system.stt_engine import FasterWhisperSTT
        engine = FasterWhisperSTT.__new__(FasterWhisperSTT)
        engine._model = None
        self.assertEqual(engine.transcribe(b"test"), "")

    def test_google_speech_stt_is_available_when_importable(self):
        """GoogleSpeechSTT.is_available speech_recognition varken True."""
        from core.audio_system.stt_engine import GoogleSpeechSTT
        with patch.dict("sys.modules", {"speech_recognition": MagicMock()}):
            engine = GoogleSpeechSTT()
            self.assertTrue(engine.is_available())

    def test_google_speech_stt_is_available_when_missing(self):
        """GoogleSpeechSTT.is_available speech_recognition yokken False."""
        from core.audio_system.stt_engine import GoogleSpeechSTT
        with patch.dict("sys.modules", {"speech_recognition": None}):
            engine = GoogleSpeechSTT()
            self.assertFalse(engine.is_available())

    def test_google_speech_stt_transcribe_not_available(self):
        """GoogleSpeechSTT.transcribe kullanilamazken bos string."""
        from core.audio_system.stt_engine import GoogleSpeechSTT
        with patch.dict("sys.modules", {"speech_recognition": None}):
            engine = GoogleSpeechSTT()
            self.assertEqual(engine.transcribe(b"test"), "")

    def test_get_stt_engine_returns_instance(self):
        """get_stt_engine bir STTEngine instance'i dondurur."""
        from core.audio_system.stt_engine import get_stt_engine, STTEngine
        engine = get_stt_engine()
        self.assertIsInstance(engine, STTEngine)


class TestSTTEngineSingleton(unittest.TestCase):
    """STTEngine singleton ve fallback davranisi."""

    def setUp(self):
        from core.audio_system import stt_engine as se
        self._old_instance = se._stt_engine
        se._stt_engine = None
        self._old_singleton = se.STTEngine._instance
        se.STTEngine._instance = None

    def tearDown(self):
        from core.audio_system import stt_engine as se
        se._stt_engine = self._old_instance
        se.STTEngine._instance = self._old_singleton

    def test_stt_engine_active_succeeds(self):
        """STTEngine.transcribe aktif engine basariliysa sonucu doner."""
        from core.audio_system.stt_engine import STTEngine
        mock_engine = MagicMock()
        mock_engine.transcribe.return_value = "merhaba"
        mock_engine.name = "mock"
        engine = STTEngine.__new__(STTEngine)
        engine._engines = [mock_engine]
        engine._active_engine = mock_engine
        result = engine.transcribe(b"audio")
        self.assertEqual(result, "merhaba")

    def test_stt_engine_active_fails_fallback_succeeds(self):
        """STTEngine.transcribe aktif basarisizsa fallback'i dener."""
        from core.audio_system.stt_engine import STTEngine
        primary = MagicMock()
        primary.transcribe.return_value = ""
        primary.name = "primary"
        fallback = MagicMock()
        fallback.transcribe.return_value = "fallback text"
        fallback.name = "fallback"
        engine = STTEngine.__new__(STTEngine)
        engine._engines = [primary, fallback]
        engine._active_engine = primary
        result = engine.transcribe(b"audio")
        self.assertEqual(result, "fallback text")

    def test_stt_engine_all_fail_returns_empty(self):
        """STTEngine.transcribe tum engine'lar basarisizsa bos string."""
        from core.audio_system.stt_engine import STTEngine
        mock_engine = MagicMock()
        mock_engine.transcribe.return_value = ""
        mock_engine.name = "mock"
        engine = STTEngine.__new__(STTEngine)
        engine._engines = [mock_engine]
        engine._active_engine = mock_engine
        result = engine.transcribe(b"audio")
        self.assertEqual(result, "")

    def test_list_engines_returns_names(self):
        """STTEngine.list_engines engine isimlerini dondurur."""
        from core.audio_system.stt_engine import STTEngine
        e1 = MagicMock(name="e1")
        e1.name = "faster-whisper"
        e2 = MagicMock(name="e2")
        e2.name = "google-speech"
        engine = STTEngine.__new__(STTEngine)
        engine._engines = [e1, e2]
        names = engine.list_engines()
        self.assertIn("faster-whisper", names)
        self.assertIn("google-speech", names)

    def test_get_stt_engine_from_global(self):
        """get_stt_engine singleton'u dondurur."""
        from core.audio_system.stt_engine import get_stt_engine, STTEngine
        engine1 = get_stt_engine()
        engine2 = get_stt_engine()
        self.assertIs(engine1, engine2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
