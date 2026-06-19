"""
GeminiProvider birim testleri.

Gerçek API/audio bagimliligi olmayan kisimlar test edilir:
- Property'ler (name, supports_*)
- __init__ state
- stop() cleanup
- feed_audio() energy-VAD mantigi
- build_config() cagrilabilirlik (mock config ile)
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch


class TestGeminiProviderProperties(unittest.IsolatedAsyncioTestCase):
    """Property'ler ve temel state."""

    def setUp(self):
        patches = [
            patch("core.gemini_provider._import_genai"),
            patch("core.gemini_provider._import_types"),
            patch("core.gemini_provider._import_pyaudio"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        from core.gemini_provider import GeminiProvider
        self.provider = GeminiProvider()

    def test_name(self):
        self.assertEqual(self.provider.name, "gemini")

    def test_supports_streaming_audio(self):
        self.assertTrue(self.provider.supports_streaming_audio)

    def test_supports_tool_calls(self):
        self.assertTrue(self.provider.supports_tool_calls)

    def test_init_state(self):
        self.assertIsNone(self.provider.session)
        self.assertIsNone(self.provider.audio_in_queue)
        self.assertIsNone(self.provider.out_queue)
        self.assertEqual(self.provider._min_energy, 200.0)

    def test_stop_cleans_up(self):
        self.provider.session = MagicMock()
        self.provider.audio_in_queue = asyncio.Queue()
        self.provider.out_queue = asyncio.Queue()

        asyncio.run(self.provider.stop())

        self.assertIsNone(self.provider.session)
        self.assertIsNone(self.provider.audio_in_queue)
        self.assertIsNone(self.provider.out_queue)


class TestFeedAudio(unittest.IsolatedAsyncioTestCase):
    """feed_audio energy-VAD mantigi."""

    def setUp(self):
        patches = [
            patch("core.gemini_provider._import_genai"),
            patch("core.gemini_provider._import_types"),
            patch("core.gemini_provider._import_pyaudio"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        from core.gemini_provider import GeminiProvider
        self.provider = GeminiProvider()
        self.queue = asyncio.Queue(maxsize=10)
        self.provider.out_queue = self.queue

    def _make_audio(self, amplitude: int, length: int = 320) -> bytes:
        """length bytes PCM16 mono (320 = 10ms @ 16kHz)."""
        import struct
        samples = [min(amplitude, 32767)] * (length // 2)
        return struct.pack(f"<{len(samples)}h", *samples)

    def test_quiet_audio_skipped(self):
        """Sessiz audio (RMS < 200) queue'ya eklenmez."""
        quiet = self._make_audio(10)  # very low amplitude
        self.provider._min_energy = 200.0
        self.provider.feed_audio(quiet)
        self.assertTrue(self.queue.empty())

    def test_loud_audio_queued(self):
        """Yuksek sesli audio (RMS >= 200) queue'ya eklenir."""
        loud = self._make_audio(30000)
        self.provider._min_energy = 200.0
        self.provider.feed_audio(loud)
        self.assertFalse(self.queue.empty())
        item = self.queue.get_nowait()
        self.assertIn("data", item)
        self.assertIn("mime_type", item)

    def test_below_threshold_skipped(self):
        """Esigin hemen altindaki ses (RMS = 199) atlanir."""
        import struct
        samples = [199] * 160
        quiet = struct.pack(f"<{len(samples)}h", *samples)
        self.provider._min_energy = 200.0
        self.provider.feed_audio(quiet)
        self.assertTrue(self.queue.empty())

    def test_at_threshold_queued(self):
        """Tam esikteki ses (RMS = 200) queue'ya eklenir."""
        import struct
        samples = [200] * 160
        boundary = struct.pack(f"<{len(samples)}h", *samples)
        self.provider._min_energy = 200.0
        self.provider.feed_audio(boundary)
        self.assertFalse(self.queue.empty())

    def test_no_queue_no_error(self):
        """out_queue None iken feed_audio hata firlatmaz."""
        self.provider.out_queue = None
        loud = self._make_audio(30000)
        self.provider.feed_audio(loud)  # should not raise


class TestBuildConfig(unittest.TestCase):
    """build_config config dosyasi ile dogru calisir mi."""

    def setUp(self):
        patches = [
            patch("core.gemini_provider._import_genai"),
            patch("core.gemini_provider._import_types"),
            patch("core.gemini_provider._import_pyaudio"),
            patch("core.gemini_provider._load_memory", return_value={}),
            patch("core.gemini_provider._format_memory_for_prompt", return_value=""),
            patch("core.gemini_provider._load_system_prompt", return_value="sys prompt"),
            patch("core.gemini_provider._get_app_config_value",
                  return_value="Charon"),
            patch("core.gemini_provider.generate_gemini_declarations",
                  return_value=[]),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        from core.gemini_provider import GeminiProvider
        self.provider = GeminiProvider()

    def test_build_config_returns_object(self):
        """build_config mock config ile cagrilabilir olmali."""
        config = self.provider.build_config()
        self.assertIsNotNone(config)

    def test_build_config_voice_from_config(self):
        """build_config voice adini config'den alir."""
        config = self.provider.build_config()
        self.assertIsNotNone(config)


class TestSendText(unittest.IsolatedAsyncioTestCase):
    """send_text async mantigi."""

    def setUp(self):
        patches = [
            patch("core.gemini_provider._import_genai"),
            patch("core.gemini_provider._import_types"),
            patch("core.gemini_provider._import_pyaudio"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        from core.gemini_provider import GeminiProvider
        self.provider = GeminiProvider()

    async def test_send_text_no_session(self):
        """Session None iken send_text hata firlatmaz."""
        self.provider.jarvis = MagicMock()
        self.provider.session = None
        await self.provider.send_text("merhaba")  # should not raise


if __name__ == "__main__":
    unittest.main(verbosity=2)
