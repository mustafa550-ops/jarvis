"""
OllamaProvider birim testleri.

Test edilenler:
- parse_local_tool_call: tool cagrisi ayristirma (pure function)
- OllamaProvider property'leri ve init state
- _get_num_ctx model adina gore context secimi
- feed_audio, send_text queue mantigi
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


# ── parse_local_tool_call tests ───────────────────────────────

class TestParseLocalToolCall(unittest.TestCase):
    """Ollama tool call parser — ce$itli formatlari ayristirma."""

    def setUp(self):
        # VALID_TOOLS'u tanimli tool'larla mock'la
        self.valid_tools_patch = patch(
            "core.ollama_provider.VALID_TOOLS",
            {"open_app", "sys_info", "shell_run", "get_weather",
             "play_media", "send_whatsapp_message", "browser_control",
             "kill_process", "set_volume", "list_processes"},
        )
        self.valid_tools_patch.start()
        self.addCleanup(self.valid_tools_patch.stop)

    def _parse(self, text: str):
        from core.ollama_provider import parse_local_tool_call
        return parse_local_tool_call(text)

    def test_plain_tool_call(self):
        """tool_name(arg) formati."""
        result = self._parse("open_app(calc)")
        self.assertIsNotNone(result)
        name, args = result
        self.assertEqual(name, "open_app")
        self.assertEqual(args, {})

    def test_json_args(self):
        """tool_name({"key": "value"}) JSON formati."""
        result = self._parse('sys_info({"query": "cpu"})')
        self.assertIsNotNone(result)
        name, args = result
        self.assertEqual(name, "sys_info")
        self.assertEqual(args, {"query": "cpu"})

    def test_key_value_args(self):
        """tool_name(key="value") key=value formati."""
        result = self._parse('play_media(query="sarki", provider="youtube")')
        self.assertIsNotNone(result)
        name, args = result
        self.assertEqual(name, "play_media")
        self.assertEqual(args, {"query": "sarki", "provider": "youtube"})

    def test_tool_prefix(self):
        """TOOL: on-ekli format."""
        result = self._parse("TOOL: get_weather(istanbul)")
        self.assertIsNotNone(result)
        name, args = result
        self.assertEqual(name, "get_weather")

    def test_invalid_tool(self):
        """Gecersiz tool adi None dondurur."""
        result = self._parse("hack_the_planet()")
        self.assertIsNone(result)

    def test_no_tool_call(self):
        """Tool cagrisi olmayan metin None dondurur."""
        result = self._parse("Bugun hava nasil?")
        self.assertIsNone(result)

    def test_empty_text(self):
        """Bos metin None dondurur."""
        result = self._parse("")
        self.assertIsNone(result)

    def test_too_long_text(self):
        """MAX_TOOL_CALL_TOTAL_LENGTH asimi None dondurur."""
        from core.ollama_provider import MAX_TOOL_CALL_TOTAL_LENGTH
        long_text = "open_app(" + "x" * MAX_TOOL_CALL_TOTAL_LENGTH + ")"
        result = self._parse(long_text)
        self.assertIsNone(result)

    def test_arg_too_long(self):
        """MAX_ARG_LENGTH asimi None dondurur."""
        from core.ollama_provider import MAX_ARG_LENGTH
        result = self._parse(f'open_app(key="{"x" * (MAX_ARG_LENGTH + 1)}")')
        self.assertIsNone(result)

    def test_case_insensitive_tool_name(self):
        """Tool adi case-insensitive eslesmeli."""
        result = self._parse("OPEN_APP(calc)")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "open_app")

    def test_mixed_args_types(self):
        """JSON icinde string disi tipler korunur."""
        result = self._parse('set_volume({"level": 75, "action": "set"})')
        self.assertIsNotNone(result)
        _, args = result
        self.assertEqual(args["level"], 75)
        self.assertEqual(args["action"], "set")

    def test_multiple_words_in_value(self):
        """Key=value formatinda bosluklu deger."""
        result = self._parse('send_whatsapp_message(recipient_name="Ahmet Yilmaz", message="Merhaba nasilsin")')
        self.assertIsNotNone(result)
        _, args = result
        self.assertEqual(args["recipient_name"], "Ahmet Yilmaz")
        self.assertEqual(args["message"], "Merhaba nasilsin")


# ── OllamaProvider property & init tests ──────────────────────

class TestOllamaProviderProperties(unittest.TestCase):
    """OllamaProvider property'leri ve temel state."""

    def setUp(self):
        patches = [
            patch("core.ollama_provider._load_app_config", return_value={}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        from core.ollama_provider import OllamaProvider
        self.provider = OllamaProvider()

    def test_name(self):
        self.assertEqual(self.provider.name, "ollama")

    def test_init_state(self):
        self.assertIsInstance(self.provider.input_queue, type(
            __import__("asyncio").Queue()))
        self.assertFalse(self.provider._running)
        self.assertFalse(self.provider._warmup_done)
        self.assertEqual(self.provider._history, [])
        self.assertIsNone(self.provider._llm)

    def test_feed_audio_no_crash(self):
        """feed_audio queue'ya data ekler, hata firlatmaz."""
        self.provider.feed_audio(b"fake audio data")
        self.assertFalse(self.provider._audio_queue.empty())

    def test_feed_audio_queue_full(self):
        """Queue doluyken feed_audio hata firlatmaz."""
        for _ in range(600):  # queue maxsize=500
            self.provider.feed_audio(b"x" * 100)
        # should not raise

    def test_send_text_queues_input(self):
        """send_text input_queue'ya ekler."""
        import asyncio
        asyncio.run(self._do_test())

    async def _do_test(self):
        from core.ollama_provider import OllamaProvider
        p = OllamaProvider()
        await p.send_text("merhaba")
        result = await p.input_queue.get()
        self.assertEqual(result, "merhaba")


# ── _get_num_ctx tests ───────────────────────────────────────

class TestGetNumCtx(unittest.TestCase):
    """_get_num_ctx context penceresi secimi."""

    def setUp(self):
        from core.ollama_provider import OllamaProvider
        self.provider = OllamaProvider()

    def _set_model(self, model_name: str):
        with patch.object(self.provider, "_get_model_name",
                          return_value=model_name):
            return self.provider._get_num_ctx()

    def test_manual_ctx(self):
        """ollama_num_ctx > 0 ise manuel deger kullanilir."""
        with patch.object(self.provider, "_get_config",
                          return_value={"ollama_num_ctx": 2048}):
            ctx = self.provider._get_num_ctx()
            self.assertEqual(ctx, 2048)

    def test_small_model(self):
        """<=3B model -> 4096."""
        ctx = self._set_model("qwen2.5:1.5b")
        self.assertEqual(ctx, 4096)

    def test_medium_model(self):
        """3B < model <= 9B -> 8192."""
        ctx = self._set_model("qwen2.5:7b")
        self.assertEqual(ctx, 8192)

    def test_large_model(self):
        """>9B model -> 16384."""
        ctx = self._set_model("qwen2.5:14b")
        self.assertEqual(ctx, 16384)

    def test_unknown_model(self):
        """Parametre tespit edilemezse varsayilan 8192."""
        ctx = self._set_model("some-custom-model")
        self.assertEqual(ctx, 8192)

    def test_no_config(self):
        """Config bos olsa da _get_num_ctx hata firlatmaz."""
        ctx = self.provider._get_num_ctx()
        self.assertIsInstance(ctx, int)


# ── _get_config cache tests ──────────────────────────────────

class TestGetConfigCache(unittest.TestCase):
    """_get_config 1 saniye cache."""

    def setUp(self):
        from core.ollama_provider import OllamaProvider
        self.provider = OllamaProvider()

    def test_cache_hit(self):
        """1 sn icinde tekrar cagrilirsa cache'den doner."""
        with patch("core.ollama_provider._load_app_config",
                   return_value={"test": "value"}) as m:
            cfg1 = self.provider._get_config()
            cfg2 = self.provider._get_config()
            self.assertEqual(cfg1, cfg2)
            m.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
