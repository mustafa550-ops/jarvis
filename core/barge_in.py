"""
Barge-in — konuşma kesme tespiti.
JARVIS konuşurken kullanıcının konuşmasını algılar ve yanıtı keser.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

import numpy as np

import traceback

__all__ = ["BargeInDetector", "create_barge_in_detector"]


class BargeInDetector:
    """
    Konuşma kesme (barge-in) tespiti.

    JARVIS konuşurken mikrofonu dinler, kullanıcı konuştuğunda
    on_barge_in callback'ini tetikler.
    """

    def __init__(
        self,
        threshold_db: float = 10.0,
        min_duration_ms: int = 300,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        on_barge_in: Optional[Callable] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        self.threshold_db = threshold_db
        self.min_duration_ms = min_duration_ms
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.on_barge_in = on_barge_in
        self.on_error = on_error

        self._jarvis_speaking = False
        self._jarvis_audio_level: float = 0.0
        self._barge_detected = False

        self._consecutive_speech = 0
        self._required_frames = max(1, int(min_duration_ms / frame_duration_ms))

        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_jarvis_speaking(self, speaking: bool, audio_level: float = 0.0):
        """JARVIS konuşma durumunu ayarla."""
        with self._lock:
            self._jarvis_speaking = speaking
            self._jarvis_audio_level = audio_level
            self._barge_detected = False
            self._consecutive_speech = 0

    def process_user_audio(self, audio_data: bytes) -> bool:
        """
        Kullanıcı sesini işle ve barge-in tespit et.

        Args:
            audio_data: Kullanıcı mikrofon sesi (PCM int16, 16kHz)

        Returns:
            True: Barge-in tespit edildi
        """
        with self._lock:
            if not self._jarvis_speaking:
                return False

        try:
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            if len(audio_array) == 0:
                return False

            # Kullanıcı ses seviyesi (RMS dB)
            rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
            user_level = 20 * np.log10(max(rms, 1))

            # Basit enerji karşılaştırması
            if user_level > self._jarvis_audio_level + self.threshold_db:
                with self._lock:
                    self._consecutive_speech += 1
                    if self._consecutive_speech >= self._required_frames:
                        if not self._barge_detected:
                            self._barge_detected = True
                            if self.on_barge_in:
                                self.on_barge_in()
                        return True
            else:
                with self._lock:
                    self._consecutive_speech = max(0, self._consecutive_speech - 1)

            return False
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
            traceback.print_exc()
            return False

    def is_barge_in(self) -> bool:
        with self._lock:
            return self._barge_detected

    def is_jarvis_speaking(self) -> bool:
        with self._lock:
            return self._jarvis_speaking

    def reset(self):
        with self._lock:
            self._jarvis_speaking = False
            self._jarvis_audio_level = 0.0
            self._barge_detected = False
            self._consecutive_speech = 0

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "jarvis_speaking": self._jarvis_speaking,
                "barge_detected": self._barge_detected,
                "threshold_db": self.threshold_db,
                "consecutive_speech": self._consecutive_speech,
            }


# ── Factory ──────────────────────────────────────────────────────────────────


def create_barge_in_detector(
    on_barge_in: Optional[Callable] = None,
    threshold_db: float = 10.0,
    on_error: Optional[Callable[[Exception], None]] = None,
) -> BargeInDetector:
    """Create a barge-in detector with sensible defaults."""
    return BargeInDetector(
        threshold_db=threshold_db,
        on_barge_in=on_barge_in,
        on_error=on_error,
    )
