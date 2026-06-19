#!/usr/bin/env python3
"""
JARVIS — orchestrator.py birim testleri.

Kapsam:
  - resample_audio() — pure function
  - UnifiedAudioPipeline — state machine, always_listen, queue ops, trigger_wake_word
  - ProviderRouter — provider selection, state transitions, retry logic
  - JarvisOrchestrator — send_text, switch_provider, lifecycle

Mock stratejisi:
  - PyAudio: tümüyle mock (gerçek mikrofonsuz çalışır)
  - scipy.signal.resample: mock'lanmaz, gerçek test
  - Provider'lar (OllamaProvider, GeminiProvider): MagicMock
"""
from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent


# ── resample_audio pure function tests ──────────────────────

class TestResampleAudio(unittest.TestCase):
    """resample_audio() pure fonksiyon testleri."""

    def setUp(self):
        from core.orchestrator import resample_audio
        self.resample = resample_audio

    def test_empty_data(self):
        """Bos data girince bos doner."""
        result = self.resample(b"", 48000, 16000)
        self.assertEqual(result, b"")

    def test_same_rate_returns_unchanged(self):
        """Kaynak ve hedef ayniysa data degismeden doner."""
        data = np.array([100, 200, -100], dtype=np.int16).tobytes()
        result = self.resample(data, 48000, 48000)
        self.assertEqual(result, data)

    def test_resample_48k_to_16k(self):
        """48kHz -> 16kHz resample dogru boyutta doner."""
        # 1 saniye 48kHz sessizlik = 48000 samples
        samples = np.zeros(48000, dtype=np.int16)
        data = samples.tobytes()
        result = self.resample(data, 48000, 16000)
        # 1 saniye 16kHz = 16000 samples * 2 byte = 32000 bytes
        self.assertEqual(len(result), 32000)

    def test_resample_16k_to_48k(self):
        """16kHz -> 48kHz resample dogru boyutta doner."""
        samples = np.zeros(16000, dtype=np.int16)
        data = samples.tobytes()
        result = self.resample(data, 16000, 48000)
        self.assertEqual(len(result), 96000)

    def test_resample_preserves_content(self):
        """Resample sonrasi sesin genligi korunur (sessiz -> sessiz)."""
        samples = np.zeros(480, dtype=np.int16)
        data = samples.tobytes()
        result = self.resample(data, 48000, 16000)
        pcm = np.frombuffer(result, dtype=np.int16)
        self.assertTrue(np.all(pcm == 0))

    def test_resample_very_short_data(self):
        """Cok kisa data (1 sample) sorunsuz islenir."""
        samples = np.array([42], dtype=np.int16)
        data = samples.tobytes()
        result = self.resample(data, 48000, 16000)
        # 1 sample resample -> ~0.33 sample -> 0'a yuvarlanir
        self.assertIsInstance(result, bytes)


# ── UnifiedAudioPipeline tests ─────────────────────────────

class MockJarvis:
    """Minimal mock jarvis nesnesi."""
    def __init__(self):
        self.audio_config = {}
        self.wake_word = None
        self.audio_buffer = None
        self.barge_in = None
        self.streaming_stt_engine = None
        self._provider = None
        self._is_speaking = False
        self._speaking_lock = threading.Lock()
        self._paused = False
        self._wake_word_triggered = False
        self._user_initiated = False
        self.ui = MagicMock()
        self.ui.muted = False


class TestUnifiedAudioPipeline(unittest.TestCase):
    """UnifiedAudioPipeline state ve pure logic testleri."""

    def setUp(self):
        self.jarvis = MockJarvis()
        # PyAudio'yu tamamen mock'la
        pa_patcher = patch("core.orchestrator.pyaudio")
        self.mock_pa = pa_patcher.start()
        self.addCleanup(pa_patcher.stop)

        # scipy.signal.resample'ı mock'la (hizli test icin)
        resample_patcher = patch("core.orchestrator.scipy.signal.resample")
        self.mock_resample = resample_patcher.start()
        self.addCleanup(resample_patcher.stop)
        self.mock_resample.side_effect = lambda data, n: data[:n] if len(data) > n else np.pad(data, (0, max(0, n - len(data))), 'constant')

        from core.orchestrator import UnifiedAudioPipeline
        self.pipeline = UnifiedAudioPipeline(self.jarvis)

    def test_initial_state(self):
        """Baslangic durumu STOPPED olmali."""
        from core.orchestrator import AudioPipelineState
        self.assertEqual(self.pipeline.state, AudioPipelineState.STOPPED)

    def test_always_listen_default_false(self):
        """Varsayilan always_listen False olmali."""
        self.assertFalse(self.pipeline._always_listen)

    def test_set_always_listen(self):
        """set_always_listen durumu guncellemeli."""
        self.pipeline.set_always_listen(True)
        self.assertTrue(self.pipeline._always_listen)
        self.pipeline.set_always_listen(False)
        self.assertFalse(self.pipeline._always_listen)

    def test_start_when_already_capturing(self):
        """Zaten calisiyorken start cagrilirsa tekrar baslatmaz."""
        from core.orchestrator import AudioPipelineState
        self.pipeline._state = AudioPipelineState.CAPTURING
        self.pipeline._stream = MagicMock()
        result = self.pipeline.start()
        self.assertTrue(result)

    def test_start_without_microphone_returns_false(self):
        """Mikrofon yoksa start False doner."""
        self.mock_pa.PyAudio.return_value.open.side_effect = Exception("No mic")
        result = self.pipeline.start()
        self.assertFalse(result)

    def test_stop_cleans_up(self):
        """stop() kaynaklari temizler ve state STOPPED yapar."""
        from core.orchestrator import AudioPipelineState
        self.pipeline._stream = MagicMock()
        self.pipeline._pa = MagicMock()
        self.pipeline._capture_thread = threading.Thread(target=lambda: None)
        self.pipeline._capture_thread.start()
        self.pipeline._capture_thread.join(timeout=1)

        self.pipeline.stop()
        self.assertEqual(self.pipeline.state, AudioPipelineState.STOPPED)

    def test_get_gemini_queue_size(self):
        """get_gemini_queue_size dogru sayi doner."""
        self.pipeline._gemini_queue.append(b"data1")
        self.pipeline._gemini_queue.append(b"data2")
        self.assertEqual(self.pipeline.get_gemini_queue_size(), 2)

    def test_clear_gemini_queue(self):
        """clear_gemini_queue kuyrugu temizler."""
        self.pipeline._gemini_queue.append(b"data")
        self.pipeline.clear_gemini_queue()
        self.assertEqual(len(self.pipeline._gemini_queue), 0)

    def test_trigger_wake_word_updates_jarvis(self):
        """trigger_wake_word jarvis state'ini gunceller."""
        self.pipeline.trigger_wake_word()
        self.assertTrue(self.jarvis._wake_word_triggered)
        self.assertTrue(self.jarvis._user_initiated)

    def test_trigger_wake_word_cooldown(self):
        """trigger_wake_word cooldown süresince tekrar tetiklenmez."""
        self.pipeline._last_wake_time = time.time()
        self.pipeline.trigger_wake_word()  # cooldown icinde
        self.assertFalse(self.pipeline._wake_word_triggered)

    def test_state_property_thread_safe(self):
        """state property thread-safe ve dogru degeri doner."""
        from core.orchestrator import AudioPipelineState
        self.pipeline._state = AudioPipelineState.CAPTURING
        self.assertEqual(self.pipeline.state, AudioPipelineState.CAPTURING)

    def test_distribute_without_consumers(self):
        """distribute tüketici yokken sorunsuz calisir."""
        try:
            self.pipeline._distribute(b"\x00" * 480)
        except Exception as e:
            self.fail(f"_distribute raised {e}")

    def test_distribute_feeds_wake_word(self):
        """distribute wake_word.feed_audio'yu cagirir."""
        mock_ww = MagicMock()
        self.jarvis.wake_word = mock_ww
        self.pipeline._distribute(b"\x00" * 480)
        mock_ww.feed_audio.assert_called_once()

    def test_distribute_feeds_audio_buffer(self):
        """distribute audio_buffer.write'i cagirir."""
        mock_buf = MagicMock()
        self.jarvis.audio_buffer = mock_buf
        self.pipeline._distribute(b"\x00" * 480)
        mock_buf.write.assert_called_once()

    def test_distribute_skips_stt_when_jarvis_speaking(self):
        """JARVIS konusuyorken (barge-in varken) STT beslenmez."""
        mock_sstt = MagicMock()
        mock_barge = MagicMock()
        self.jarvis.streaming_stt_engine = mock_sstt
        self.jarvis.barge_in = mock_barge
        self.jarvis._is_speaking = True
        self.pipeline._distribute(b"\x00" * 480)
        mock_sstt.feed_audio.assert_not_called()
        mock_barge.process_user_audio.assert_called_once()

    def test_distribute_feeds_barge_in_when_speaking(self):
        """JARVIS konusuyorken barge-in beslenir."""
        mock_barge = MagicMock()
        self.jarvis.barge_in = mock_barge
        self.jarvis._is_speaking = True
        self.pipeline._distribute(b"\x00" * 480)
        mock_barge.process_user_audio.assert_called_once()

    def test_distribute_skips_when_muted(self):
        """Muted durumunda ses dagitilmaz."""
        mock_sstt = MagicMock()
        self.jarvis.streaming_stt_engine = mock_sstt
        self.jarvis.ui.muted = True
        self.pipeline._distribute(b"\x00" * 480)
        mock_sstt.feed_audio.assert_not_called()

    def test_distribute_skips_when_paused(self):
        """Paused durumunda ses dagitilmaz."""
        mock_sstt = MagicMock()
        self.jarvis.streaming_stt_engine = mock_sstt
        self.jarvis._paused = True
        self.pipeline._distribute(b"\x00" * 480)
        mock_sstt.feed_audio.assert_not_called()

    def test_distribute_feeds_provider(self):
        """distribute provider.feed_audio'yu cagirir."""
        mock_provider = MagicMock()
        self.jarvis._provider = mock_provider
        self.pipeline._distribute(b"\x00" * 480)
        mock_provider.feed_audio.assert_called_once()


# ── ProviderRouter tests ───────────────────────────────────

class TestProviderRouter(unittest.TestCase):
    """ProviderRouter state ve logic testleri."""

    def setUp(self):
        self.jarvis = MockJarvis()
        self.jarvis.app_config = {"backend_type": "ollama"}

        from core.orchestrator import ProviderRouter
        self.router = ProviderRouter(self.jarvis)

    def test_initial_state(self):
        """Baslangic durumu DISCONNECTED."""
        from core.orchestrator import ProviderState
        self.assertEqual(self.router.state, ProviderState.DISCONNECTED)
        self.assertIsNone(self.router.current_provider)
        self.assertEqual(self.router.current_name, "")

    def test_initial_config(self):
        """Varsayilan retry degerleri dogru."""
        self.assertEqual(self.router._max_retries, 5)
        self.assertEqual(self.router._retry_delay, 3.0)
        self.assertEqual(self.router._retry_count, 0)
        self.assertFalse(self.router._shutdown)

    def test_get_provider_instance_ollama(self):
        """_get_provider_instance ollama instance'i olusturur."""
        with patch("core.ollama_provider.OllamaProvider") as mock_ollama:
            inst = self.router._get_provider_instance("ollama")
            self.assertEqual(inst, mock_ollama.return_value)

    def test_get_provider_instance_gemini(self):
        """_get_provider_instance gemini instance'i olusturur."""
        with patch("core.gemini_provider.GeminiProvider") as mock_gemini:
            inst = self.router._get_provider_instance("gemini")
            self.assertEqual(inst, mock_gemini.return_value)

    def test_get_provider_instance_unknown(self):
        """Bilinmeyen provider ValueError firlatir."""
        with self.assertRaises(ValueError):
            self.router._get_provider_instance("invalid")

    def test_get_provider_instance_caches(self):
        """Provider instance'lari cache'lenir, tekrar olusturulmaz."""
        with patch("core.ollama_provider.OllamaProvider") as mock_ollama:
            inst1 = self.router._get_provider_instance("ollama")
            inst2 = self.router._get_provider_instance("ollama")
            self.assertIs(inst1, inst2)
            mock_ollama.assert_called_once()

    def test_select_provider_ollama_preferred(self):
        """Ollama varsayilan olarak tercih edilir."""
        with patch.object(self.router, "_check_ollama_available", return_value=True):
            name = self.router._select_provider()
            self.assertEqual(name, "ollama")

    def test_select_provider_fallback_to_gemini(self):
        """Ollama yoksa Gemini fallback."""
        with patch.object(self.router, "_check_ollama_available", return_value=False):
            name = self.router._select_provider()
            self.assertEqual(name, "gemini")

    def test_select_provider_preferred_param(self):
        """_select_provider(preferred) ile override edilebilir."""
        name = self.router._select_provider("gemini")
        self.assertEqual(name, "gemini")

    def test_state_transition_connecting(self):
        """state CONNECTING'e gecince dogru deger doner."""
        from core.orchestrator import ProviderState
        self.router._set_state(ProviderState.CONNECTING)
        self.assertEqual(self.router.state, ProviderState.CONNECTING)

    def test_state_transition_error(self):
        """state ERROR'a gecince dogru deger doner."""
        from core.orchestrator import ProviderState
        self.router._set_state(ProviderState.ERROR)
        self.assertEqual(self.router.state, ProviderState.ERROR)

    def test_shutdown_sets_flag(self):
        """shutdown() flag'i true yapar."""
        self.router.shutdown()
        self.assertTrue(self.router._shutdown)

    def test_shutdown_prevents_start(self):
        """shutdown sonrasi start() hicbir sey yapmaz."""
        self.router.shutdown()
        import asyncio
        asyncio.run(self.router.start())
        self.assertIsNone(self.router.current_provider)

    @patch("core.ollama_provider.OllamaProvider")
    def test_start_ollama_success(self, mock_ollama_cls):
        """start() Ollama basarili olursa state READY olur."""
        mock_provider = AsyncMock()
        mock_ollama_cls.return_value = mock_provider

        import asyncio
        asyncio.run(self.router.start("ollama"))

        self.assertEqual(self.router.current_name, "ollama")
        self.assertIsNotNone(self.router.current_provider)
        from core.orchestrator import ProviderState
        self.assertEqual(self.router.state, ProviderState.READY)

    @patch("core.ollama_provider.OllamaProvider")
    def test_start_ollama_failure_sets_error(self, mock_ollama_cls):
        """start() basarisiz olursa state ERROR olur."""
        mock_provider = AsyncMock()
        mock_provider.start.side_effect = Exception("Connection failed")
        mock_ollama_cls.return_value = mock_provider

        from core.orchestrator import ProviderState
        import asyncio
        with self.assertRaises(Exception):
            asyncio.run(self.router.start("ollama"))

        self.assertEqual(self.router.state, ProviderState.ERROR)

    @patch("core.ollama_provider.OllamaProvider")
    def test_stop_cleans_up(self, mock_ollama_cls):
        """stop() provider'i durdurur ve reference'lari temizler."""
        from core.orchestrator import ProviderState
        import asyncio

        mock_provider = AsyncMock()
        mock_ollama_cls.return_value = mock_provider

        asyncio.run(self.router.start("ollama"))
        self.assertIsNotNone(self.router.current_provider)

        asyncio.run(self.router.stop())
        self.assertIsNone(self.router.current_provider)
        self.assertEqual(self.router.current_name, "")
        self.assertEqual(self.router.state, ProviderState.DISCONNECTED)

    @patch("core.ollama_provider.OllamaProvider")
    def test_switch_changes_provider(self, mock_ollama_cls):
        """switch() provider degistirir."""
        from core.orchestrator import ProviderState
        import asyncio

        mock_provider = AsyncMock()
        mock_ollama_cls.return_value = mock_provider

        asyncio.run(self.router.start("ollama"))
        self.assertEqual(self.router.current_name, "ollama")

        # Gemini'e gec
        with patch("core.gemini_provider.GeminiProvider") as mock_gemini_cls:
            mock_gemini = AsyncMock()
            mock_gemini_cls.return_value = mock_gemini
            asyncio.run(self.router.switch("gemini"))
            self.assertEqual(self.router.current_name, "gemini")
            self.assertEqual(self.router.state, ProviderState.READY)

    def test_check_ollama_available_httpx(self):
        """_check_ollama_available httpx ile kontrol eder."""
        with patch("httpx.get") as mock_get, \
             patch("core.local_llm.LocalLLM") as mock_llm:
            mock_llm.side_effect = ImportError("no local_llm")
            mock_get.return_value.status_code = 200
            result = self.router._check_ollama_available()
            self.assertTrue(result)

    def test_check_ollama_not_available(self):
        """_check_ollama_available baglanti yoksa False doner."""
        with patch("httpx.get") as mock_get, \
             patch("core.local_llm.LocalLLM") as mock_llm:
            mock_llm.side_effect = ImportError("no local_llm")
            mock_get.side_effect = Exception("Connection refused")
            result = self.router._check_ollama_available()
            self.assertFalse(result)


# ── JarvisOrchestrator tests ───────────────────────────────

class TestJarvisOrchestrator(unittest.TestCase):
    """JarvisOrchestrator lifecycle ve delegasyon testleri."""

    def setUp(self):
        self.jarvis = MockJarvis()
        self.jarvis._loop = None

        pa_patcher = patch("core.orchestrator.pyaudio")
        self.mock_pa = pa_patcher.start()
        self.addCleanup(pa_patcher.stop)

        resample_patcher = patch("core.orchestrator.scipy.signal.resample")
        self.mock_resample = resample_patcher.start()
        self.addCleanup(resample_patcher.stop)

        from core.orchestrator import JarvisOrchestrator
        self.orch = JarvisOrchestrator(self.jarvis)

    def test_init_creates_components(self):
        """__init__ pipeline ve router'i olusturur."""
        self.assertIsNotNone(self.orch.audio_pipeline)
        self.assertIsNotNone(self.orch.provider_router)
        self.assertIsNotNone(self.orch._executor)
        self.assertFalse(self.orch._running)

    def test_send_text_no_provider(self):
        """send_text provider yokken hata mesaji yazar."""
        self.jarvis.ui.write_log = MagicMock()
        self.orch.send_text("test")
        self.jarvis.ui.write_log.assert_called_with("ERR: Provider hazır değil.")

    @patch("core.ollama_provider.OllamaProvider")
    def test_switch_provider(self, mock_ollama_cls):
        """switch_provider provider degisikligi baslatir."""
        import asyncio

        mock_provider = AsyncMock()
        mock_ollama_cls.return_value = mock_provider

        self.jarvis._loop = asyncio.new_event_loop()
        asyncio.run(self.orch.provider_router.start("ollama"))
        self.orch._loop = self.jarvis._loop

        self.orch.switch_provider("gemini")

    @patch("core.ollama_provider.OllamaProvider")
    def test_stop_cleans_providers_and_pipeline(self, mock_ollama_cls):
        """stop() pipeline, router ve executor'u temizler."""
        import asyncio

        mock_provider = AsyncMock()
        mock_ollama_cls.return_value = mock_provider

        self.jarvis._loop = asyncio.new_event_loop()
        asyncio.run(self.orch.provider_router.start("ollama"))
        self.orch._running = True

        asyncio.run(self.orch.stop())
        self.assertFalse(self.orch._running)


if __name__ == "__main__":
    unittest.main(verbosity=2)
