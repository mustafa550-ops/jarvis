"""
Wake word detection engine.
openWakeWord → Porcupine → energy-based fallback.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

import traceback

__all__ = ["WakeWordEngine", "create_wake_word_engine"]

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_config() -> dict:
    """Load wake word config from YAML with strict defaults."""
    defaults = {
        "engine": "openwakeword",
        "wake_word": "jarvis",
        "openwakeword": {"sensitivity": 0.5, "custom_model": "models/wake_word/jarvis.tflite"},
        "porcupine": {"access_key": "", "sensitivity": 0.5},
        "energy": {"threshold": 0.03, "min_duration_ms": 500, "cooldown_ms": 2000},
        "sample_rate": 16000,
        "frame_duration_ms": 30,
        "silence_timeout_ms": 5000,
        "hold_time_ms": 200,
        "require_hold": True,
    }
    try:
        import yaml
        config_path = BASE_DIR / "config" / "wake_word.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    # Deep merge
                    for k, v in loaded.items():
                        if isinstance(v, dict) and isinstance(defaults.get(k), dict):
                            defaults[k].update(v)
                        else:
                            defaults[k] = v
    except ImportError:
        print("[WakeWord] YAML destegi yok (pip install pyyaml), varsayilan config kullaniliyor")
    except Exception:
        traceback.print_exc()
    return defaults


class WakeWordEngine:
    """
    Wake word detection with automatic backend fallback.

    Backend chain: openWakeWord → Porcupine → energy threshold.
    """

    def __init__(
        self,
        config_path: str = "config/wake_word.yaml",
        on_wake_word: Optional[Callable] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        config: Optional[dict] = None,
    ):
        self.config = config if config else _load_config()
        self.on_wake_word = on_wake_word
        self.on_error = on_error
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Audio state
        self.sample_rate = self.config.get("sample_rate", 16000)
        self._energy_buffer: list[float] = []
        self._last_detection: float = 0.0

        # Backend
        self._detector = None
        self._engine_name: str = self.config.get("engine", "openwakeword")
        self._init_backend()

    # ── Backend init ──────────────────────────────────────────────────────────

    def _init_backend(self):
        """Initialize the first available detection backend."""
        if self._engine_name == "openwakeword":
            if self._init_openwakeword():
                return
            print("[WakeWord] openWakeWord kurulu degil, Porcupine deneniyor")
        if self._engine_name in ("openwakeword", "porcupine"):
            if self._init_porcupine():
                self._engine_name = "porcupine"
                return
            print("[WakeWord] Porcupine de yok, enerji tabanli moda geciliyor")
        self._engine_name = "energy"
        print(f"[WakeWord] Enerji tabanli mod aktif (wake_word={self.config.get('wake_word', 'jarvis')})")

    def _init_openwakeword(self) -> bool:
        try:
            from openwakeword import Model
            custom = self.config.get("openwakeword", {}).get("custom_model", "")
            custom_path = BASE_DIR / custom if custom else None
            if custom_path and custom_path.exists():
                self._detector = Model(wakeword_models=[str(custom_path)])
                print(f"[WakeWord] openWakeWord ozel model yuklendi: {custom_path}")
            else:
                self._detector = Model()
                print("[WakeWord] openWakeWord built-in model yuklendi")
            self._engine_name = "openwakeword"
            return True
        except ImportError:
            return False
        except Exception as exc:
            print(f"[WakeWord] openWakeWord yukleme hatasi: {exc}")
            traceback.print_exc()
            return False

    def _init_porcupine(self) -> bool:
        try:
            import pvporcupine
            access_key = self.config.get("porcupine", {}).get("access_key", "")
            if not access_key:
                print("[WakeWord] Porcupine access_key bos, atlaniyor")
                return False
            self._detector = pvporcupine.create(
                access_key=access_key,
                keywords=[self.config.get("wake_word", "jarvis").upper()],
                sensitivities=[self.config.get("porcupine", {}).get("sensitivity", 0.5)],
            )
            self._engine_name = "porcupine"
            print("[WakeWord] Porcupine yuklendi")
            return True
        except ImportError:
            return False
        except Exception as exc:
            print(f"[WakeWord] Porcupine yukleme hatasi: {exc}")
            traceback.print_exc()
            return False

    # ── Detection handlers ───────────────────────────────────────────────────

    def _detect_openwakeword(self, audio_array: np.ndarray) -> Optional[str]:
        try:
            scores = self._detector.predict(audio_array)
            for kw, score in scores.items():
                if score > self.config.get("openwakeword", {}).get("sensitivity", 0.5):
                    return kw
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
        return None

    def _detect_porcupine(self, audio_array: np.ndarray) -> bool:
        try:
            pcm = audio_array.astype(np.int16).tobytes()
            result = self._detector.process(pcm)
            return result >= 0
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
            return False

    def _detect_energy(self, audio_array: np.ndarray) -> bool:
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
        threshold = self.config.get("energy", {}).get("threshold", 0.03)
        min_duration = self.config.get("energy", {}).get("min_duration_ms", 500)
        cooldown = self.config.get("energy", {}).get("cooldown_ms", 2000) / 1000.0

        if time.time() - self._last_detection < cooldown:
            return False

        normalized = rms / 32768.0
        self._energy_buffer.append(normalized)
        if len(self._energy_buffer) > 50:
            self._energy_buffer.pop(0)

        if normalized > threshold and len(self._energy_buffer) >= 3:
            recent = self._energy_buffer[-3:]
            if all(v > threshold for v in recent):
                seg_duration = len(recent) * (self.config.get("frame_duration_ms", 30) / 1000.0)
                if seg_duration >= min_duration / 1000.0:
                    self._last_detection = time.time()
                    return True
        return False

    def feed_audio(self, audio_data: bytes) -> Optional[str]:
        """
        Feed PCM int16 audio for wake word detection.

        Returns detected keyword string or None.
        """
        if not self._running:
            return None

        try:
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
            audio_array = audio_int16.astype(np.float32) / 32768.0

            keyword = None
            if self._engine_name == "openwakeword":
                keyword = self._detect_openwakeword(audio_int16)
            elif self._engine_name == "porcupine":
                if self._detect_porcupine(audio_array):
                    keyword = self.config.get("wake_word", "jarvis")
            else:
                if self._detect_energy(audio_array):
                    keyword = self.config.get("wake_word", "jarvis")

            if keyword and self.on_wake_word:
                self.on_wake_word(keyword)

            return keyword
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
            return None

    def start(self) -> bool:
        """Start wake word detection."""
        if self._running:
            return True
        self._running = True
        print(f"[WakeWord] Baslatildi (engine={self._engine_name})")
        return True

    def stop(self):
        """Stop wake word detection."""
        self._running = False
        print("[WakeWord] Durduruldu")

    def is_active(self) -> bool:
        return self._running

    def get_stats(self) -> dict:
        return {
            "engine": self._engine_name,
            "running": self._running,
            "wake_word": self.config.get("wake_word", "jarvis"),
        }


# ── Factory ──────────────────────────────────────────────────────────────────


def create_wake_word_engine(
    on_wake_word: Optional[Callable] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    config: Optional[dict] = None,
) -> WakeWordEngine:
    """Create a wake word engine with sensible defaults."""
    return WakeWordEngine(
        on_wake_word=on_wake_word,
        on_error=on_error,
        config=config,
    )
