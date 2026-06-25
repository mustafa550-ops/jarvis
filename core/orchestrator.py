#!/usr/bin/env python3
"""
J.A.R.V.I.S. Unified Orchestrator v5.1
=====================================
CRITICAL FIX: RNNoise requires 48kHz native, resample to 16kHz AFTER processing.

Fixes:
  1. RNNoise: Open mic at 48kHz → RNNoise process → resample to 16kHz for STT/Gemini
  2. Unified audio pipeline — single microphone capture, shared across providers
  3. Automatic provider switching with graceful teardown
  4. Wake-word bypass option for Ollama mode (always-listen vs wake-word)
  5. Deadlock-free thread communication
  6. Proper PyAudio lifecycle management (no leaks)

Adler ASİ tarafından yapılmıştır
"""
from __future__ import annotations

import asyncio
import logging
import numpy as np
import os
import scipy.signal
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from enum import Enum, auto
from typing import Any

# PortAudio/ALSA module yüklenirken stderr'e basılan ALSA/Jack uyarılarını engelle
_save_err = os.dup(2)
_nul_fd = os.open(os.devnull, os.O_WRONLY)
os.dup2(_nul_fd, 2)
os.close(_nul_fd)
import pyaudio  # noqa: E402
os.dup2(_save_err, 2)
os.close(_save_err)

# ── Configuration ───────────────────────────────────────────
# RNNoise NATIVE rate is 48kHz! Resample to 16kHz AFTER denoising.
RNNOISE_RATE = 48000
TARGET_RATE = 16000       # STT + Gemini need 16kHz
CHUNK_DURATION_MS = 30   # 30ms frames

# Frame sizes for each rate
MAX_AUDIO_QUEUE_SIZE = 500
WAKE_WORD_COOLDOWN_SEC = 2.0

logger = logging.getLogger("orchestrator")

# ALSA/Jack uyarılarını stderr'den filtrele
@contextmanager
def _silence_alsa():
    """PyAudio ALSA/JACK init sırasında stderr'i geçici olarak sustur."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old_stderr, 2)
        os.close(old_stderr)


class ProviderState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    READY = auto()
    PROCESSING = auto()
    ERROR = auto()


class AudioPipelineState(Enum):
    STOPPED = auto()
    STARTING = auto()
    CAPTURING = auto()
    PAUSED = auto()
    ERROR = auto()


# ── Resampling Helper ───────────────────────────────────────

def resample_audio(data: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Resample PCM audio from src_rate to dst_rate."""
    if not data or src_rate == dst_rate:
        return data
    pcm = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    ratio = dst_rate / src_rate
    n_samples = int(len(pcm) * ratio)
    if n_samples == 0:
        return b""
    resampled = scipy.signal.resample(pcm, n_samples)
    return resampled.astype(np.int16).tobytes()


# ── Unified Audio Pipeline ──────────────────────────────────

class UnifiedAudioPipeline:
    """
    SINGLE microphone capture thread at 48kHz → RNNoise → resample to 16kHz → distribute.

    Flow:
      Mic (48kHz) → RNNoise (48kHz) → Resample → 16kHz → Consumers

    Consumers:
      - Wake word engine (16kHz)
      - Streaming STT (16kHz)
      - Gemini real-time input (16kHz) — Gemini Live API handles VAD server-side
      - Audio buffer (16kHz)
      - Barge-in detector (16kHz)
    """

    def __init__(self, jarvis: Any):
        """UnifiedAudioPipeline baslatir."""
        self.jarvis = jarvis
        self._state = AudioPipelineState.STOPPED
        self._state_lock = threading.Lock()

        # PyAudio
        self._pa: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None

        # Cihaz önbelleği — ilk başarılı açılışta kaydedilir
        self._cached_device_index: int | None = None

        # Capture thread
        self._capture_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Audio distribution queues (16kHz, thread-safe)
        self._gemini_queue: deque[bytes] = deque(maxlen=MAX_AUDIO_QUEUE_SIZE)
        self._stt_queue: deque[bytes] = deque(maxlen=200)

        # Wake word
        self._wake_word_triggered = False
        self._last_wake_time = 0.0
        self._always_listen = False  # True = no wake word needed (Ollama mode)

        # RNNoise (48kHz native)
        self._rnnoise = None
        self._has_rnnoise = False
        self._init_rnnoise()

    def _init_rnnoise(self):
        """Initialize noise suppressor using configured library."""
        try:
            from core.audio_system import create_noise_suppressor

            _lib = "rnnoise"
            try:
                _ac = getattr(self.jarvis, "audio_config", {})
                _lib = _ac.get("audio", {}).get("noise_suppression", {}).get("library", "rnnoise")
            except Exception:
                pass

            self._rnnoise = create_noise_suppressor(sample_rate=48000, library=_lib)
            self._has_rnnoise = self._rnnoise is not None
            if self._has_rnnoise:
                logger.info("[NoiseSuppressor] Initialized (library=%s)", _lib)
        except Exception as e:
            logger.warning("[NoiseSuppressor] Not available: %s", e)
            self._has_rnnoise = False

    @property
    def state(self) -> AudioPipelineState:
        """AudioPipeline'in mevcut durumu."""
        with self._state_lock:
            return self._state

    def set_always_listen(self, value: bool):
        """Ollama mode: True = no wake word needed."""
        self._always_listen = value
        logger.info("[AudioPipeline] Always-listen mode: %s", value)

    def start(self) -> bool:
        """Start the unified capture pipeline at 48kHz. Returns success."""
        with self._state_lock:
            if self._state in (AudioPipelineState.STARTING, AudioPipelineState.CAPTURING):
                return True
            self._state = AudioPipelineState.STARTING

        self._stop_event.clear()

        # Initialize PyAudio (ALSA/Jack stderr sessize alındı)
        try:
            with _silence_alsa():
                self._pa = pyaudio.PyAudio()
        except Exception as e:
            logger.error("[AudioPipeline] PyAudio init failed: %s", e)
            self._set_state(AudioPipelineState.ERROR)
            return False

        # Open stream at 48kHz (RNNoise native)
        self._stream = self._open_stream_48k()
        if self._stream is None:
            logger.error("[AudioPipeline] No microphone available at 48kHz")
            self._set_state(AudioPipelineState.ERROR)
            return False

        logger.info("[AudioPipeline] Stream opened at 48kHz → RNNoise → 16kHz")

        # Start capture thread
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            name="audio-capture",
            daemon=True
        )
        self._capture_thread.start()
        self._set_state(AudioPipelineState.CAPTURING)
        return True

    def _open_stream_48k(self) -> pyaudio.Stream | None:
        """Tüm ses giriş cihazlarını tara, dene ve ilk çalışanı seç."""
        # 1. Önce önbellekteki cihazı dene
        if self._cached_device_index is not None:
            stream = self._try_device(self._cached_device_index, "önbellek")
            if stream:
                return stream

        # 2. Sistem varsayılanını dene (index'siz open — PortAudio en iyi bunu bilir)
        try:
            frames = int(48000 * CHUNK_DURATION_MS / 1000)
            stream = self._pa.open(
                format=pyaudio.paInt16, channels=1, rate=48000,
                input=True, frames_per_buffer=frames,
            )
            logger.info("[AudioPipeline] ✅ Varsayılan cihaz açıldı @ 48kHz")
            self._cached_device_index = -1  # default
            return stream
        except Exception:
            pass

        # 3. Tüm giriş cihazlarını enumerate et
        devices = []
        for i in range(self._pa.get_device_count()):
            try:
                info = self._pa.get_device_info_by_index(i)
                ch = int(info.get("maxInputChannels", 0) or 0)
                if ch > 0:
                    devices.append({
                        "index": i,
                        "name": info["name"],
                        "channels": ch,
                        "rate": int(info.get("defaultSampleRate", 0) or 0),
                    })
            except Exception:
                continue

        if not devices:
            logger.error("[AudioPipeline] ❌ Giriş cihazı bulunamadı")
            return None

        # 4. Öncelik sırası: default > Analog/ALC > pulse > pipewire > sysdefault > diğer
        def _priority(d):
            """Cihaz secim onceligini hesaplar (default/Analog/pulse/pipewire/sysdefault)."""
            n = d["name"].lower()
            if self._cached_device_index is not None and d["index"] == self._cached_device_index:
                return 0
            if "default" in n:
                return 1
            if "analog" in n or "alc" in n or "alc" in n:
                return 2
            if "pulse" in n:
                return 3
            if "pipewire" in n:
                return 4
            if "sysdefault" in n:
                return 5
            return 10

        devices.sort(key=_priority)

        # 5. Sırayla dene
        tried = []
        for dev in devices:
            stream = self._try_device(dev["index"], dev["name"])
            if stream:
                logger.info("[AudioPipeline] ✅ Seçilen mikrofon: [%d] %s @ 48kHz",
                           dev["index"], dev["name"])
                return stream
            tried.append(f"[{dev['index']}] {dev['name']}")

        logger.error("[AudioPipeline] ❌ Tüm cihazlar denendi — hiçbiri açılamadı:\n  %s",
                     "\n  ".join(tried))
        return None

    def _try_device(self, device_index: int, label: str = "") -> pyaudio.Stream | None:
        """Bir cihazı 48kHz'de açmayı dene, olmazsa 44.1kHz dene."""
        for rate in [48000, 44100]:
            try:
                frames = int(rate * CHUNK_DURATION_MS / 1000)
                stream = self._pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=rate,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=frames,
                )
                self._cached_device_index = device_index
                logger.info("[AudioPipeline] Açıldı: [%d] %s @ %dHz",
                           device_index, label or device_index, rate)
                return stream
            except Exception:
                continue
        return None

    def _set_state(self, state: AudioPipelineState):
        """AudioPipeline durumunu atomik olarak gunceller."""
        with self._state_lock:
            self._state = state

    def stop(self):
        """Gracefully stop capture and release resources."""
        logger.info("[AudioPipeline] Stopping...")
        self._stop_event.set()

        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)

        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

        self._set_state(AudioPipelineState.STOPPED)
        logger.info("[AudioPipeline] Stopped")

    def _capture_loop(self):
        """Main capture thread — reads mic at 48kHz → RNNoise → resample to 16kHz → distribute."""
        logger.info("[AudioPipeline] Capture thread started")

        while not self._stop_event.is_set():
            try:
                # Read raw audio at 48kHz
                raw_48k = self._stream.read(
                    self._stream._frames_per_buffer,
                    exception_on_overflow=False
                )
            except Exception as e:
                logger.error("[AudioPipeline] Read error: %s", e)
                time.sleep(0.1)
                continue

            # Step 1: Apply RNNoise at 48kHz (native)
            denoised_48k = raw_48k
            if self._has_rnnoise and self._rnnoise:
                try:
                    # Convert bytes (int16 PCM) → float32 numpy array → process → back to bytes
                    pcm_float = np.frombuffer(raw_48k, dtype=np.int16).astype(np.float32) / 32768.0
                    clean_float = self._rnnoise.process_stream(pcm_float, 48000)
                    denoised_48k = (clean_float * 32768.0).astype(np.int16).tobytes()
                except Exception as e:
                    logger.debug("[RNNoise] Process error: %s", e)
                    denoised_48k = raw_48k  # Fallback to raw

            # Step 2: Resample to 16kHz for all consumers
            data_16k = resample_audio(denoised_48k, 48000, TARGET_RATE)

            # Step 3: Distribute 16kHz audio to all consumers
            self._distribute(data_16k)

        logger.info("[AudioPipeline] Capture thread exited")

    def _distribute(self, data: bytes):
        """Distribute 16kHz audio to shared modules + active provider."""
        j = self.jarvis

        # 1. Always feed wake word (16kHz)
        ww = getattr(j, "wake_word", None)
        if ww is not None:
            try:
                ww.feed_audio(data)
            except Exception as e:
                logger.debug("[AudioPipeline] Wake word feed error: %s", e)

        # 2. Always feed audio buffer (16kHz)
        buf = getattr(j, "audio_buffer", None)
        if buf is not None:
            try:
                buf.write(data)
            except Exception as e:
                logger.debug("[AudioPipeline] Buffer write error: %s", e)

        # 3. Check if JARVIS is speaking → barge-in detection
        barge = getattr(j, "barge_in", None)
        jarvis_speaking = False
        try:
            with j._speaking_lock:
                jarvis_speaking = j._is_speaking
        except Exception as e:
            logger.debug("[AudioPipeline] Speaking lock error: %s", e)

        if jarvis_speaking and barge is not None:
            try:
                barge.process_user_audio(data)
            except Exception as e:
                logger.debug("[AudioPipeline] Barge-in error: %s", e)
            return  # Don't process as user speech while JARVIS is speaking

        # 4. Check muted
        try:
            if j.ui.muted:
                return
        except Exception as e:
            logger.debug("[AudioPipeline] Muted check error: %s", e)

        # 5. Check paused
        try:
            if j._paused:
                return
        except Exception as e:
            logger.debug("[AudioPipeline] Paused check error: %s", e)

        # 6. Feed streaming STT (16kHz)
        sstt = getattr(j, "streaming_stt_engine", None)
        if sstt is not None:
            try:
                sstt.feed_audio(data)
            except Exception as e:
                logger.debug("[AudioPipeline] STT feed error: %s", e)

        # 7. Feed the active provider's audio pipeline (16kHz)
        provider = getattr(j, "_provider", None)
        if provider is not None and hasattr(provider, "feed_audio"):
            try:
                provider.feed_audio(data)
            except Exception as e:
                logger.debug("[AudioPipeline] Provider feed error: %s", e)

    def get_gemini_queue_size(self) -> int:
        """Gemini kuyrugundaki bekleyen ses parcacigi sayisi."""
        return len(self._gemini_queue)

    def clear_gemini_queue(self):
        """Gemini kuyrugunu temizler."""
        self._gemini_queue.clear()

    def trigger_wake_word(self):
        """Called by wake word engine when detected."""
        now = time.time()
        if now - self._last_wake_time < WAKE_WORD_COOLDOWN_SEC:
            return
        self._last_wake_time = now
        self._wake_word_triggered = True
        try:
            self.jarvis._wake_word_triggered = True
            self.jarvis._user_initiated = True
            self.jarvis.ui.mark_user_activity(True)
        except Exception:
            pass


# ── Provider Router ───────────────────────────────────────

class ProviderRouter:
    """
    Manages provider lifecycle:
      - Auto-detect best provider (Ollama first, fallback to Gemini)
      - Graceful switch with resource cleanup
      - Health checks and reconnection
    """

    def __init__(self, jarvis: Any):
        """ProviderRouter baslatir."""
        self.jarvis = jarvis
        self._current_provider: Any = None
        self._current_name: str = ""
        self._state = ProviderState.DISCONNECTED
        self._state_lock = threading.Lock()
        self._shutdown = False

        # Provider instances (lazy init)
        self._providers: dict[str, Any] = {}

        # Reconnection
        self._retry_count = 0
        self._max_retries = 5
        self._retry_delay = 3.0

    @property
    def state(self) -> ProviderState:
        """Provider'in mevcut durumu."""
        with self._state_lock:
            return self._state

    def _set_state(self, state: ProviderState):
        """Provider durumunu atomik olarak gunceller."""
        with self._state_lock:
            old = self._state
            self._state = state
            if old != state:
                logger.info("[ProviderRouter] State: %s → %s", old.name, state.name)

    def _get_provider_instance(self, name: str) -> Any:
        """Lazy-load provider class."""
        if name in self._providers:
            return self._providers[name]

        if name == "ollama":
            from core.ollama_provider import OllamaProvider
            inst = OllamaProvider()
        elif name == "gemini":
            from core.gemini_provider import GeminiProvider
            inst = GeminiProvider()
        else:
            raise ValueError(f"Unknown provider: {name}")

        self._providers[name] = inst
        return inst

    def _check_ollama_available(self) -> bool:
        """Quick check if Ollama is running (uses LocalLLM if available)."""
        try:
            from core.local_llm import LocalLLM
            return LocalLLM().is_ollama_running()
        except Exception:
            try:
                import httpx
                r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
                return r.status_code == 200
            except Exception:
                return False

    def _select_provider(self, preferred: str | None = None) -> str:
        """Select best available provider."""
        cfg = self.jarvis.app_config if hasattr(self.jarvis, "app_config") else {}
        backend = preferred or cfg.get("backend_type", "ollama")

        if backend == "ollama":
            if self._check_ollama_available():
                return "ollama"
            logger.warning("[ProviderRouter] Ollama not available, falling back to Gemini")
            return "gemini"
        return backend

    async def start(self, preferred: str | None = None):
        """Start the selected provider."""
        if self._shutdown:
            return

        name = self._select_provider(preferred)
        self._set_state(ProviderState.CONNECTING)

        try:
            provider = self._get_provider_instance(name)
            await provider.start(self.jarvis)

            self._current_provider = provider
            self._current_name = name
            self._retry_count = 0
            self._set_state(ProviderState.READY)

            # Expose to jarvis so the audio pipeline can route captured audio
            self.jarvis._provider = provider

            # Configure audio pipeline based on provider
            pipeline = getattr(self.jarvis, "audio_pipeline", None)
            if pipeline:
                pipeline.set_always_listen(name == "ollama")

            logger.info("[ProviderRouter] Started: %s", name)

        except Exception as e:
            logger.error("[ProviderRouter] Failed to start %s: %s", name, e)
            self._set_state(ProviderState.ERROR)
            raise

    async def stop(self):
        """Stop current provider and cleanup."""
        self._set_state(ProviderState.DISCONNECTED)

        if self._current_provider:
            try:
                await self._current_provider.stop()
            except Exception as e:
                logger.error("[ProviderRouter] Stop error: %s", e)
            self._current_provider = None
            self._current_name = ""
            self.jarvis._provider = None

    async def switch(self, new_name: str):
        """Switch to a different provider gracefully."""
        logger.info("[ProviderRouter] Switching to %s...", new_name)
        await self.stop()
        await self.start(new_name)

    async def run(self):
        """Main loop — run current provider, reconnect on failure."""
        while not self._shutdown:
            try:
                if self._current_provider is None:
                    await self.start()

                self._set_state(ProviderState.PROCESSING)
                await self._current_provider.run_loop()

            except Exception as e:
                logger.error("[ProviderRouter] Provider error: %s", e)
                self._set_state(ProviderState.ERROR)

                # Notify UI
                try:
                    self.jarvis.ui.safe_call(
                        self.jarvis.ui.write_log,
                        f"ERR: {self._current_name} bağlantısı kesildi — {e}"
                    )
                except Exception:
                    pass

                # Retry logic
                self._retry_count += 1
                if self._retry_count > self._max_retries:
                    logger.error("[ProviderRouter] Max retries exceeded")
                    try:
                        self.jarvis.ui.safe_call(
                            self.jarvis.ui.write_log,
                            "ERR: Maksimum yeniden bağlanma sayısına ulaşıldı."
                        )
                    except Exception:
                        pass
                    break

                delay = self._retry_delay * min(self._retry_count, 5)
                logger.info("[ProviderRouter] Retrying in %.0f seconds...", delay)
                await asyncio.sleep(delay)

                # Try alternate provider on repeated failures
                if self._retry_count >= 3 and self._current_name == "ollama":
                    logger.info("[ProviderRouter] Trying Gemini fallback...")
                    try:
                        await self.switch("gemini")
                        continue
                    except Exception:
                        pass

                await self.start()

    def shutdown(self):
        """Signal shutdown."""
        self._shutdown = True

    @property
    def current_provider(self) -> Any:
        """Aktif provider instance'i."""
        return self._current_provider

    @property
    def current_name(self) -> str:
        """Aktif provider adi ('gemini' veya 'ollama')."""
        return self._current_name


# ── Orchestrator ────────────────────────────────────────────

class JarvisOrchestrator:
    """
    Central orchestrator that coordinates:
      - AudioPipeline (microphone → RNNoise 48kHz → 16kHz → consumers)
      - ProviderRouter (Ollama/Gemini lifecycle)
      - State machine
      - Thread-safe UI communication
    """

    def __init__(self, jarvis: Any):
        """JarvisOrchestrator baslatir."""
        self.jarvis = jarvis
        self.audio_pipeline = UnifiedAudioPipeline(jarvis)
        self.provider_router = ProviderRouter(jarvis)

        # Thread pool for blocking operations
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="orch")

        # State
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None

        # (No pipeline callbacks — each provider handles its own VAD/STT)

    async def start(self):
        """Start orchestrator: audio pipeline + provider router."""
        self._running = True
        self._loop = asyncio.get_running_loop()

        # Start audio pipeline
        if not self.audio_pipeline.start():
            logger.error("[Orchestrator] Audio pipeline failed to start")
            self.jarvis.ui.safe_call(
                self.jarvis.ui.write_log,
                "ERR: Mikrofon başlatılamadı. Sesli komut çalışmayacak."
            )

        # Start provider router
        await self.provider_router.start()

    async def run(self):
        """Main loop — runs provider and monitors health."""
        await self.provider_router.run()

    async def stop(self):
        """Graceful shutdown."""
        self._running = False
        self.provider_router.shutdown()
        await self.provider_router.stop()
        self.audio_pipeline.stop()
        self._executor.shutdown(wait=False)

    def send_text(self, text: str):
        """Send text command to current provider (from UI)."""
        provider = self.provider_router.current_provider
        if provider is None:
            self.jarvis.ui.write_log("ERR: Provider hazır değil.")
            return

        asyncio.run_coroutine_threadsafe(
            provider.send_text(text),
            self.jarvis._loop
        )

    def switch_provider(self, name: str):
        """Switch provider (called from UI/config change)."""
        asyncio.run_coroutine_threadsafe(
            self.provider_router.switch(name),
            self.jarvis._loop
        )
