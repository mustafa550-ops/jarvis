"""
audio/microphone.py
JARVIS mikrofon stream'i. RNNoise gürültü bastırma katmanı içerir.

sounddevice tabanlıdır. Mevcut PyAudio tabanlı pipeline'a alternatif
olarak kullanılabilir veya RNNoise ön işleme katmanı olarak entegre
edilebilir.
"""

from __future__ import annotations

import logging
import traceback
from typing import Callable, Optional

import numpy as np

from audio.noise_suppressor import NoiseSuppressor

logger = logging.getLogger(__name__)


class MicrophoneStream:
    """sounddevice tabanlı mikrofon stream'i + RNNoise gürültü bastırma.

    Kullanım:
        def on_audio(clean_audio: np.ndarray):
            # wake-word + STT pipeline'ı
            pass

        with MicrophoneStream(
            sample_rate=48000,
            block_size=480,
            on_audio=on_audio,
        ) as mic:
            input()  # beklet
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        block_size: int = 480,
        channels: int = 1,
        noise_suppression_enabled: bool = True,
        on_audio: Optional[Callable[[np.ndarray], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.channels = channels
        self.on_audio = on_audio
        self._stream: Optional["sd.InputStream"] = None  # noqa: F821

        # RNNoise suppressor initialize
        self.suppressor: Optional[NoiseSuppressor] = None
        if noise_suppression_enabled:
            try:
                self.suppressor = NoiseSuppressor(
                    sample_rate=sample_rate,
                    enabled=True,
                )
            except Exception as exc:
                logger.error(
                    "[Microphone] Suppressor başlatılamadı: %s", exc
                )

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: "sd.CallbackFlags",  # noqa: F821
    ) -> None:
        """sounddevice callback — gerçek zamanlı çalışır."""
        if status:
            logger.debug("[Microphone] Stream status: %s", status)

        # Mono'ya zorla (stereo gelirse ilk kanalı al)
        if indata.shape[1] > 1:
            mono = indata[:, 0].copy()
        else:
            mono = indata[:, 0]

        # Gürültü bastırma
        if self.suppressor and self.suppressor.enabled:
            try:
                clean = self.suppressor.process_stream(
                    mono, original_rate=self.sample_rate
                )
                mono = clean
            except Exception as exc:
                logger.error(
                    "[Microphone] Gürültü bastırma hatası: %s", exc
                )

        # Pipeline'a devam et (wake-word, STT, vb.)
        if self.on_audio:
            self.on_audio(mono)

    def start(self) -> None:
        """Mikrofon stream'ini başlat."""
        if self._stream is not None:
            return

        try:
            import sounddevice as sd

            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                channels=self.channels,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
            logger.info(
                "[Microphone] Stream başladı. SR=%d, Block=%d, RNNoise=%s",
                self.sample_rate,
                self.block_size,
                "Aktif"
                if (self.suppressor and self.suppressor.enabled)
                else "Devre dışı",
            )
        except Exception as exc:
            logger.error("[Microphone] Stream başlatılamadı: %s", exc)
            traceback.print_exc()

    def stop(self) -> None:
        """Mikrofon stream'ini durdur."""
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:
                logger.error("[Microphone] Stream durdurma hatası: %s", exc)
            self._stream = None
            logger.info("[Microphone] Stream durduruldu.")

        if self.suppressor:
            self.suppressor._cleanup()
            self.suppressor = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
