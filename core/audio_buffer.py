"""
Circular audio buffer — thread-safe PCM int16 ring buffer.
"""

from __future__ import annotations

import collections
import time
from typing import Optional

import numpy as np

import traceback

__all__ = ["AudioBuffer"]


class AudioBuffer:
    """
    Ring buffer for PCM int16 audio data.

    Stores up to `max_duration` seconds at `sample_rate` Hz.
    Supports frame extraction, overlapping reads, and stats tracking.
    """

    def __init__(self, sample_rate: int = 16000, max_duration: float = 30.0):
        self.sample_rate = sample_rate
        max_samples = int(sample_rate * max_duration)
        self._buffer: collections.deque = collections.deque(maxlen=max_samples)
        self._total_written: int = 0
        self._write_count: int = 0
        self._created_at: float = time.time()

    # ── Write ─────────────────────────────────────────────────────────────────

    def write(self, audio_data: bytes) -> None:
        """Append PCM int16 audio data to the buffer."""
        try:
            samples = np.frombuffer(audio_data, dtype=np.int16)
            self._buffer.extend(samples.tolist())
            self._total_written += len(samples)
            self._write_count += 1
        except Exception:
            traceback.print_exc()

    # ── Read ──────────────────────────────────────────────────────────────────

    def read(self, duration_ms: int) -> Optional[bytes]:
        """
        Read last `duration_ms` milliseconds as PCM int16 bytes.

        Returns None if buffer is empty, truncates if buffer is shorter.
        """
        if not self._buffer:
            return None
        n_samples = int(self.sample_rate * duration_ms / 1000)
        n_samples = min(n_samples, len(self._buffer))
        samples = list(self._buffer)[-n_samples:]
        return np.array(samples, dtype=np.int16).tobytes()

    def read_frame(self, frame_size: int) -> Optional[bytes]:
        """
        Pop one frame of `frame_size` samples from the front.

        Returns None if fewer than frame_size samples available.
        """
        if len(self._buffer) < frame_size:
            return None
        samples = [self._buffer.popleft() for _ in range(frame_size)]
        return np.array(samples, dtype=np.int16).tobytes()

    def peek(self, n_samples: int) -> Optional[bytes]:
        """Peek at the last `n_samples` without removing them."""
        if not self._buffer or n_samples <= 0:
            return None
        n = min(n_samples, len(self._buffer))
        samples = list(self._buffer)[-n:]
        return np.array(samples, dtype=np.int16).tobytes()

    # ── State ─────────────────────────────────────────────────────────────────

    def clear(self) -> None:
        """Reset the buffer."""
        self._buffer.clear()

    @property
    def duration_ms(self) -> float:
        """Audio duration in milliseconds."""
        return len(self._buffer) / self.sample_rate * 1000

    def __len__(self) -> int:
        return len(self._buffer)

    def get_stats(self) -> dict:
        return {
            "sample_rate": self.sample_rate,
            "current_samples": len(self._buffer),
            "current_duration_ms": round(self.duration_ms, 1),
            "max_samples": self._buffer.maxlen,
            "total_written": self._total_written,
            "write_count": self._write_count,
            "age_seconds": round(time.time() - self._created_at, 1),
        }
