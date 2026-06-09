# ── Provider Base ────────────────────────────────────────────
# Abstract interface for all LLM providers (Gemini, Ollama, future)
# Each provider handles connection, audio/text I/O, and response processing.
# Shared orchestration (UI, tool dispatch, TTS, local modules) stays in main.py.
# ──────────────────────────────────────────────────────────────

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any


class BaseProvider(ABC):
    """Abstract base for LLM providers.

    Lifecycle:
        provider = ConcreteProvider()
        await provider.start(jarvis)
        try:
            await provider.run_loop()  # blocks until error/stop
        finally:
            await provider.stop()

    The provider has access to the Jarvis instance for:
      - UI updates (set_state, write_log)
      - Tool dispatch (_execute_tool)
      - Speech (_speak_response, _speak_proactive)
      - Audio pipeline (wake_word, streaming_stt, barge_in, audio_buffer)
      - Config (load_app_config)
    """

    def __init__(self) -> None:
        self.jarvis: Any = None           # set by start()
        self._loop: asyncio.AbstractEventLoop | None = None

    # ── Lifecycle ────────────────────────────────────────────

    async def start(self, jarvis: Any) -> None:
        """Store jarvis reference and initialize provider state."""
        self.jarvis = jarvis
        self._loop = asyncio.get_event_loop()

    @abstractmethod
    async def stop(self) -> None:
        """Clean up provider resources (sessions, streams, tasks)."""

    # ── I/O ──────────────────────────────────────────────────

    async def send_audio(self, data: bytes) -> None:
        """Send audio chunk to provider (voice-enabled providers override)."""
        pass  # default no-op

    @abstractmethod
    async def send_text(self, text: str) -> None:
        """Send text input to provider (from user typing or STT)."""

    # ── Main loop ─────────────────────────────────────────────

    @abstractmethod
    async def run_loop(self) -> None:
        """Main processing loop. Blocks until error or stop signal.
        Never returns normally — provider handles reconnection internally
        or raises to let main.py handle it."""

    # ── Properties ───────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'gemini', 'ollama')."""

    @property
    def supports_streaming_audio(self) -> bool:
        """Whether this provider returns audio directly (vs requiring local TTS)."""
        return False

    @property
    def supports_tool_calls(self) -> bool:
        """Whether this provider supports native tool/function calling."""
        return False

    # ── Helpers ──────────────────────────────────────────────

    def _j(self) -> Any:
        """Convenience accessor — raises if jarvis not set."""
        if self.jarvis is None:
            raise RuntimeError(f"{self.name}: jarvis not set (call start())")
        return self.jarvis
