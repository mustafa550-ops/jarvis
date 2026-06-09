"""
Cross-Platform STT Engine
faster-whisper (local) → Google Speech Recognition (internet fallback)
"""

from __future__ import annotations

import queue
import threading
import time
import wave
from abc import ABC, abstractmethod
from collections import deque
from pathlib import Path
from typing import Callable, Optional

import numpy as np


class BaseSTTEngine(ABC):
    """Abstract STT engine."""

    @abstractmethod
    def transcribe(self, audio_data: np.ndarray | bytes, sample_rate: int = 16000) -> str:
        """Transcribe audio to text."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine is available."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine name."""
        pass


class FasterWhisperSTT(BaseSTTEngine):
    """faster-whisper STT - Local, fast, supports Turkish."""

    def __init__(
        self,
        model_size: str = "base",
        language: str = "tr",
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        self.model_size = model_size
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._load_model()

    @property
    def name(self) -> str:
        return "faster-whisper"

    def is_available(self) -> bool:
        return self._model is not None

    def _load_model(self):
        try:
            from faster_whisper import WhisperModel
            print(f"[FasterWhisperSTT] Loading model: {self.model_size}")
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=4,
            )
            print("[FasterWhisperSTT] Model loaded")
        except ImportError:
            print("[FasterWhisperSTT] faster-whisper not installed. pip install faster-whisper")
            self._model = None
        except Exception as e:
            print(f"[FasterWhisperSTT] Load error: {e}")
            self._model = None

    def transcribe(self, audio_data: np.ndarray | bytes, sample_rate: int = 16000) -> str:
        if not self.is_available():
            return ""

        try:
            # Convert to float32 if needed
            if isinstance(audio_data, bytes):
                audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio_array = audio_data.astype(np.float32)
                if audio_array.max() > 1.0:
                    audio_array = audio_array / 32768.0

            segments, info = self._model.transcribe(
                audio_array,
                language=self.language,
                beam_size=1,
                best_of=1,
                temperature=0,
                condition_on_previous_text=False,
                vad_filter=True,
                vad_parameters={
                    "threshold": 0.3,
                    "min_speech_duration_ms": 300,
                    "min_silence_duration_ms": 500,
                },
            )

            text_parts = [segment.text.strip() for segment in segments]
            return " ".join(text_parts).strip()

        except Exception as e:
            print(f"[FasterWhisperSTT] Transcribe error: {e}")
            return ""


class GoogleSpeechSTT(BaseSTTEngine):
    """Google Speech Recognition - Internet required, fallback."""

    def __init__(self, language: str = "tr-TR"):
        self.language = language

    @property
    def name(self) -> str:
        return "google-speech"

    def is_available(self) -> bool:
        try:
            import speech_recognition as sr
            return True
        except ImportError:
            return False

    def transcribe(self, audio_data: np.ndarray | bytes, sample_rate: int = 16000) -> str:
        if not self.is_available():
            return ""

        try:
            import speech_recognition as sr
            import tempfile
            import wave

            # Save to temporary WAV
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name

                if isinstance(audio_data, bytes):
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                else:
                    audio_array = (audio_data * 32768).astype(np.int16)

                with wave.open(f, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_array.tobytes())

            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio = recognizer.record(source)

            text = recognizer.recognize_google(audio, language=self.language)

            Path(wav_path).unlink(missing_ok=True)
            return text

        except Exception as e:
            print(f"[GoogleSpeechSTT] Error: {e}")
            return ""


class STTEngine:
    """Universal STT - auto-selects best engine with fallback."""

    _instance: Optional[STTEngine] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._engines: list[BaseSTTEngine] = []
        self._active_engine: Optional[BaseSTTEngine] = None

        # Try faster-whisper first
        try:
            fw = FasterWhisperSTT()
            if fw.is_available():
                self._engines.append(fw)
                self._active_engine = fw
        except Exception as e:
            print(f"[STTEngine] faster-whisper init failed: {e}")

        # Fallback to Google
        try:
            gs = GoogleSpeechSTT()
            if gs.is_available():
                self._engines.append(gs)
                if self._active_engine is None:
                    self._active_engine = gs
        except Exception as e:
            print(f"[STTEngine] Google Speech init failed: {e}")

        if self._active_engine:
            print(f"[STTEngine] Active: {self._active_engine.name}")
        else:
            print("[STTEngine] ⚠️ No STT engine available!")

    def transcribe(self, audio_data: np.ndarray | bytes, sample_rate: int = 16000) -> str:
        """Transcribe with fallback chain."""
        if self._active_engine:
            try:
                result = self._active_engine.transcribe(audio_data, sample_rate)
                if result:
                    return result
            except Exception as e:
                print(f"[STTEngine] {self._active_engine.name} failed: {e}")

        for engine in self._engines:
            if engine is self._active_engine:
                continue
            try:
                print(f"[STTEngine] Fallback to {engine.name}")
                result = engine.transcribe(audio_data, sample_rate)
                if result:
                    return result
            except Exception as e:
                print(f"[STTEngine] {engine.name} failed: {e}")

        return ""

    def list_engines(self) -> list[str]:
        return [e.name for e in self._engines]


# Global instance
_stt_engine: Optional[STTEngine] = None

def get_stt_engine() -> STTEngine:
    global _stt_engine
    if _stt_engine is None:
        _stt_engine = STTEngine()
    return _stt_engine
