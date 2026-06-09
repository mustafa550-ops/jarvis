"""
Voice Activity Detection Engine 2.0
Silero VAD → WebRTC VAD → energy-based fallback.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Optional, Tuple

import numpy as np

import traceback

__all__ = ["VADEngine", "create_vad_engine"]


class VADEngine:
    """
    Voice Activity Detection with automatic backend fallback.

    Backend chain: silero (PyTorch) → webrtc (webrtcvad) → energy (numpy).
    Includes adaptive noise profiling and speech state machine.

    Supports automatic downsampling: if process_frame() receives audio at
    a sample_rate different from the internal rate, it downsamples to 16kHz
    (the native rate for Silero/WebRTC VAD models).
    """

    # Default energy threshold for speech (RMS value, 16-bit audio)
    # 50 = normal conversation, 400+ = very loud / close mic
    ENERGY_THRESHOLD: float = 50.0

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        aggressiveness: int = 2,
        engine: str = "silero",
        on_speech_start: Optional[Callable] = None,
        on_speech_end: Optional[Callable] = None,
        speech_pad_ms: int = 300,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 500,
        energy_threshold: Optional[float] = None,
    ):
        self.sample_rate = int(sample_rate)
        self.frame_duration_ms = frame_duration_ms
        self.aggressiveness = aggressiveness
        self.engine_name = engine
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end
        self.speech_pad_ms = speech_pad_ms
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self.energy_threshold = energy_threshold if energy_threshold is not None else self.ENERGY_THRESHOLD

        self.frame_size = int(self.sample_rate * frame_duration_ms / 1000)

        # State machine
        self._is_speaking = False
        self._speech_start_time: Optional[float] = None
        self._last_speech_time: Optional[float] = None
        self._silence_start_time: Optional[float] = None

        # Buffers
        self._audio_buffer = deque(maxlen=int(self.sample_rate * 10))
        self._speech_buffer = bytearray()

        # Noise profile
        self._noise_floor: Optional[float] = None
        self._noise_samples = deque(maxlen=100)

        # Thread safety
        self._lock = threading.Lock()

        # Stats
        self._speech_count = 0
        self._total_frames = 0

        # Backend
        self._engine = None
        self._init_engine()

    # ── Backend init ──────────────────────────────────────────────────────────

    def _init_engine(self):
        if self.engine_name == "silero":
            self._init_silero()
        elif self.engine_name == "webrtc":
            self._init_webrtc()
        else:
            self._engine = "energy"
            print("[VAD] Enerji tabanli VAD aktif (fallback)")

    def _init_silero(self):
        try:
            import torch
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
            )
            (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils
            self._engine = {
                "model": model,
                "utils": utils,
                "vad_iterator": VADIterator(model),
            }
            print("[VAD] Silero VAD yuklendi")
        except ImportError:
            print("[VAD] PyTorch kurulu degil, WebRTC VAD'a geciliyor")
            self._init_webrtc()
        except Exception as exc:
            print(f"[VAD] Silero VAD hatasi: {exc}")
            traceback.print_exc()
            self._init_webrtc()

    def _init_webrtc(self):
        try:
            import webrtcvad
            self._engine = webrtcvad.Vad(self.aggressiveness)
            self.engine_name = "webrtc"
            print("[VAD] WebRTC VAD yuklendi")
        except ImportError:
            print("[VAD] webrtcvad kurulu degil, enerji tabanli VAD'a geciliyor")
            self._engine = "energy"
            self.engine_name = "energy"

    # ── Frame processing ──────────────────────────────────────────────────────

    def _downsample(
        self, audio_data: np.ndarray, from_rate: int, to_rate: int = 16000
    ) -> np.ndarray:
        """Downsample audio to target rate.

        Uses integer decimation for exact ratios (48→16, 44.1→16) and
        linear interpolation for non-integer ratios.  Both are fast enough
        for VAD purposes without pulling in scipy.
        """
        if from_rate <= to_rate:
            return audio_data
        if from_rate % to_rate == 0:
            step = from_rate // to_rate
            return audio_data[::step]
        n_samples = int(len(audio_data) * to_rate / from_rate)
        return np.interp(
            np.linspace(0, len(audio_data) - 1, n_samples),
            np.arange(len(audio_data)),
            audio_data,
        ).astype(audio_data.dtype)

    def process_frame(
        self, audio_frame: bytes, sample_rate: Optional[int] = None
    ) -> Tuple[bool, float]:
        """Process one audio frame. Returns (is_speech, confidence).

        If *sample_rate* is given and differs from the engine's internal
        sample rate the frame is automatically downsampled so that the
        underlying VAD backends (all native 16 kHz) work correctly.
        """
        if sample_rate is not None and sample_rate != self.sample_rate:
            audio_array = np.frombuffer(audio_frame, dtype=np.int16)
            audio_array = self._downsample(audio_array, sample_rate, self.sample_rate)
            audio_frame = audio_array.astype(np.int16).tobytes()

        self._total_frames += 1
        audio_array = np.frombuffer(audio_frame, dtype=np.int16)

        if not self._is_speaking:
            self._update_noise_profile(audio_array)

        if self.engine_name == "silero" and isinstance(self._engine, dict):
            is_speech, confidence = self._process_silero(audio_array)
        elif self.engine_name == "webrtc" and hasattr(self._engine, "is_speech"):
            is_speech, confidence = self._process_webrtc(audio_frame)
        else:
            is_speech, confidence = self._process_energy(audio_array)

        self._update_state(is_speech, confidence)
        return is_speech, confidence

    def _process_silero(self, audio_array: np.ndarray) -> Tuple[bool, float]:
        try:
            import torch
            tensor = torch.from_numpy(audio_array.astype(np.float32) / 32768.0)
            if not isinstance(self._engine, dict):
                return False, 0.0
            vad_iterator = self._engine["vad_iterator"]
            result = vad_iterator(tensor, return_seconds=False)
            if result:
                return True, 0.9
            return False, 0.1
        except Exception:
            return False, 0.0

    def _process_webrtc(self, audio_frame: bytes) -> Tuple[bool, float]:
        try:
            if not hasattr(self._engine, "is_speech"):
                return False, 0.0
            is_speech = self._engine.is_speech(audio_frame, self.sample_rate)
            return is_speech, 0.8 if is_speech else 0.2
        except Exception:
            return False, 0.0

    def _process_energy(self, audio_array: np.ndarray) -> Tuple[bool, float]:
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
        if self._noise_floor is not None:
            threshold = max(self.energy_threshold, self._noise_floor * 3.0)
        else:
            threshold = self.energy_threshold * 10
        is_speech = rms > threshold
        confidence = min(1.0, (rms - threshold) / threshold) if is_speech else 0.0
        return is_speech, confidence

    def _update_noise_profile(self, audio_array: np.ndarray):
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
        self._noise_samples.append(rms)
        if len(self._noise_samples) >= 10:
            self._noise_floor = float(np.median(list(self._noise_samples)))

    # ── State machine ─────────────────────────────────────────────────────────

    def _update_state(self, is_speech: bool, confidence: float):
        now = time.time()
        if is_speech:
            self._last_speech_time = now
            if not self._is_speaking:
                if self._speech_start_time is None:
                    self._speech_start_time = now
                speech_duration = (now - self._speech_start_time) * 1000
                if speech_duration >= self.min_speech_duration_ms:
                    self._is_speaking = True
                    self._speech_count += 1
                    if self.on_speech_start:
                        self.on_speech_start()
        else:
            if self._is_speaking:
                if self._silence_start_time is None:
                    self._silence_start_time = now
                silence_duration = (now - self._silence_start_time) * 1000
                if silence_duration >= self.min_silence_duration_ms:
                    self._is_speaking = False
                    self._speech_start_time = None
                    self._silence_start_time = None
                    if self.on_speech_end:
                        self.on_speech_end()
            else:
                self._speech_start_time = None
                self._silence_start_time = None

    # ── Stream processing ─────────────────────────────────────────────────────

    def process_stream(self, audio_data: bytes) -> Optional[bytes]:
        """Process audio stream, return completed speech segment or None."""
        self._audio_buffer.extend(np.frombuffer(audio_data, dtype=np.int16))
        while len(self._audio_buffer) >= self.frame_size:
            frame = np.array([self._audio_buffer.popleft() for _ in range(self.frame_size)])
            frame_bytes = frame.astype(np.int16).tobytes()
            is_speech, _ = self.process_frame(frame_bytes)
            if is_speech:
                self._speech_buffer.extend(frame_bytes)
            else:
                if len(self._speech_buffer) > 0 and not self._is_speaking:
                    segment = bytes(self._speech_buffer)
                    self._speech_buffer = bytearray()
                    return segment
        return None

    def get_speech_segment(self) -> Optional[bytes]:
        """Get current speech segment if speech ended."""
        if len(self._speech_buffer) > 0 and not self._is_speaking:
            segment = bytes(self._speech_buffer)
            self._speech_buffer = bytearray()
            return segment
        return None

    # ── Control ───────────────────────────────────────────────────────────────

    def reset(self):
        self._is_speaking = False
        self._speech_start_time = None
        self._last_speech_time = None
        self._silence_start_time = None
        self._audio_buffer.clear()
        self._speech_buffer = bytearray()
        if self.engine_name == "silero" and isinstance(self._engine, dict):
            try:
                self._engine["vad_iterator"].reset_states()
            except Exception:
                traceback.print_exc()

    def is_speaking(self) -> bool:
        return self._is_speaking

    def get_stats(self) -> dict:
        return {
            "engine": self.engine_name,
            "is_speaking": self._is_speaking,
            "speech_count": self._speech_count,
            "total_frames": self._total_frames,
            "noise_floor": self._noise_floor,
            "buffer_size": len(self._audio_buffer),
        }


# ── Factory ──────────────────────────────────────────────────────────────────


def create_vad_engine(
    engine: str = "silero",
    on_speech_start: Optional[Callable] = None,
    on_speech_end: Optional[Callable] = None,
    energy_threshold: Optional[float] = None,
) -> VADEngine:
    """Create a VAD engine with sensible defaults."""
    return VADEngine(
        engine=engine,
        on_speech_start=on_speech_start,
        on_speech_end=on_speech_end,
        energy_threshold=energy_threshold,
    )
