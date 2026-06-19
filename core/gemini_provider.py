# ── Gemini Provider ──────────────────────────────────────────
# Gemini Live API provider — bidirectional streaming audio.
# Extracted from main.py to make the provider interface concrete.
# ──────────────────────────────────────────────────────────────

"""
Gemini Provider — Google Gemini Live API ile sesli asistan.

Gemini'nin multimodal Live API'sini kullanir:
- Gercek zamanli sesli iletisim (WebSocket)
- Built-in VAD, STT, TTS (Gemini halleder)
- Tool calling (Google AI tool use)
- Kesintisiz (barge-in) destegi

API_KEY config/api_keys.json'dan okunur (gemini_api_key).
Voice model config'den secilir (voice: Charon/Puck/Aoede/Kore).

Bu provider Gemini backend secildiginde kullanilir (backend_type: "gemini").
Ollama'dan farkli olarak tum ses isleme Gemini sunucusunda yapilir.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import traceback
from typing import Any

import numpy as np

from core.provider_base import BaseProvider
from core.tool_registry import generate_gemini_declarations


# Lazy imports (genai is heavy and not always needed)
def _import_genai():
    """Lazy import: google.genai."""
    from google import genai
    return genai


def _import_types():
    """Lazy import: google.genai.types."""
    from google.genai import types
    return types


def _import_pyaudio():
    """Lazy import: pyaudio."""
    import pyaudio
    return pyaudio


# ── Constants ────────────────────────────────────────────────

LIVE_MODEL = "gemini-2.0-flash-exp"
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECV_SAMPLE_RATE = 24000
CHUNK_SIZE = 512


# ── Helpers (moved from main.py) ─────────────────────────────

from core.text_utils import clean_transcript_text as _clean_transcript_text


def _get_api_key():
    """Config'den Gemini API anahtarini alir."""
    from app_config import get_app_config_value
    return str(get_app_config_value("gemini_api_key", "") or "")


def _get_app_config_value(key: str, default: Any = None):
    """Config'den deger okur (lazy import)."""
    from app_config import get_app_config_value
    return get_app_config_value(key, default)


def _load_memory():
    """Kullanici bellegini yukler (lazy import)."""
    from memory.memory_manager import load_memory
    return load_memory()


def _format_memory_for_prompt(mem):
    """Bellegi LLM prompt'una formatlar (lazy import)."""
    from memory.memory_manager import format_memory_for_prompt
    return format_memory_for_prompt(mem)


def _load_system_prompt():
    """Sistem prompt'unu yukler (lazy import)."""
    from main import load_system_prompt
    return load_system_prompt()


# ── Gemini Provider ─────────────────────────────────────────

class GeminiProvider(BaseProvider):

    @property
    def name(self) -> str:
        """Provider adi: 'gemini'."""
        return "gemini"

    @property
    def supports_streaming_audio(self) -> bool:
        """Gemini, sesli streaming destekler."""
        return True

    @property
    def supports_tool_calls(self) -> bool:
        """Gemini, function calling destekler."""
        return True

    def __init__(self):
        """GeminiProvider baslatir."""
        super().__init__()
        self.session: Any = None
        self.audio_in_queue: asyncio.Queue | None = None
        self.out_queue: asyncio.Queue | None = None
        self._min_energy: float = 200.0

    async def stop(self):
        """Provider'i durdurur, kaynaklari temizler."""
        self.session = None
        self.audio_in_queue = None
        self.out_queue = None

    def feed_audio(self, data: bytes) -> None:
        """Called from the orchestrator's audio capture pipeline (16kHz PCM)."""
        q = self.out_queue
        if q is not None:
            # Energy-based VAD: skip silence
            arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(arr ** 2)))
            if rms >= self._min_energy:
                try:
                    q.put_nowait({"data": data, "mime_type": "audio/pcm"})
                except asyncio.QueueFull:
                    pass

    async def send_text(self, text: str) -> None:
        """Send text input to Gemini."""
        j = self._j()
        if not self.session:
            return
        await self.session.send_client_content(
            turns={"parts": [{"text": text}]},
            turn_complete=True
        )

    def build_config(self) -> Any:
        """Build Gemini LiveConnectConfig (replaces _build_config in main.py)."""
        import datetime
        types = _import_types()

        memory = _load_memory()
        mem_str = _format_memory_for_prompt(memory)
        sys_p = _load_system_prompt()
        now = datetime.datetime.now()

        if os.name == "nt":
            os_info = "Windows"
        elif sys.platform == "darwin":
            os_info = "macOS"
        else:
            os_info = "Linux"
        time_ctx = f"[ŞU ANKİ ZAMAN]\n{now.strftime('%A, %d %B %Y — %H:%M')}\n\n"
        sys_ctx = f"[SISTEM BILGISI]\nİşletim sistemi: {os_info}\nKabuk: {'PowerShell/cmd' if os.name == 'nt' else 'bash'}\nDosya yolu ayracı: {'\\\\' if os.name == 'nt' else '/'}\n\n"

        parts = [time_ctx, sys_ctx]
        if mem_str:
            parts.append(mem_str + "\n\n")
        parts.append(sys_p)

        # Use the tool registry as single source of truth
        tool_declarations = generate_gemini_declarations()

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": tool_declarations}],
            speech_config=types.SpeechConfig(
                voice_config=types.PrebuiltVoiceConfig(
                    voice_name=str(_get_app_config_value("voice", "Charon") or "Charon")
                )
            ),
        )

    async def _send_realtime(self):
        """Send audio chunks from out_queue to Gemini session."""
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _receive_audio(self):
        """Receive audio + transcriptions + tool calls from Gemini."""
        j = self._j()
        types = _import_types()

        print("[JARVIS] 👂 Alım başladı")
        out_buf, in_buf = [], []
        output_noise = False
        output_noise_samples = []
        try:
            while True:
                async for response in self.session.receive():
                    if response.data:
                        try:
                            self.audio_in_queue.put_nowait(response.data)
                        except asyncio.QueueFull:
                            # Kuyruk dolu → en yeni chunk atlanir
                            # Bu, baglantinin kopmasi yerine tercih edilir
                            print("[JARVIS] ⚠️ Ses kuyrugu doldu, chunk atlandi")

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            j.set_speaking(True)
                            raw_txt = sc.output_transcription.text.strip()
                            if raw_txt:
                                txt, had_noise = _clean_transcript_text(raw_txt)
                                if had_noise:
                                    output_noise = True
                                    if len(output_noise_samples) < 4:
                                        output_noise_samples.append(raw_txt)
                                if txt:
                                    out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = sc.input_transcription.text.strip()
                            if txt:
                                in_buf.append(txt)
                                j._user_initiated = True
                                j.ui.safe_call(j.ui.mark_user_activity, True)

                        if sc.turn_complete:
                            j.set_speaking(False)

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                j.ui.safe_call(j.ui.write_log, f"Siz: {full_in}")
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                j.ui.safe_call(j.ui.write_log, f"JARVIS: {full_out}")
                                if output_noise_samples:
                                    j.ui.safe_call(j.ui.write_debug, "Kısmen filtrelenen ses transcripti: " + " | ".join(output_noise_samples), level="WARN")
                            elif output_noise:
                                j.ui.safe_call(j.ui.write_log, "ERR: JARVIS sesli yanıtını çözümlerken bir hata oluştu.")
                                if output_noise_samples:
                                    j.ui.safe_call(j.ui.write_debug, "Filtrelenen ham transcript: " + " | ".join(output_noise_samples), level="WARN")
                                j.set_state("ERROR")
                            out_buf = []
                            output_noise = False
                            output_noise_samples = []

                    if response.tool_call:
                        fn_responses = []
                        for fc in (response.tool_call.function_calls or []):
                            print(f"[JARVIS] 📞 {fc.name}")
                            fr = await j._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses)

        except Exception as e:
            print(f"[JARVIS] ❌ Alım: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self, stream):
        """Play audio chunks from Gemini to speakers."""
        j = self._j()
        print("[JARVIS] 🔊 Ses çalma başladı")
        try:
            while True:
                chunk = await self.audio_in_queue.get()
                j.set_speaking(True)
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            print(f"[JARVIS] ❌ Ses: {e}")
            raise
        finally:
            j.set_speaking(False)

    async def run_loop(self):
        """Main Gemini loop — connect, open streams, process until error."""
        j = self._j()
        types = _import_types()
        pyaudio = _import_pyaudio()
        genai = _import_genai()

        pa_instance = pyaudio.PyAudio()
        fmt = pyaudio.paInt16

        # ── Check output devices for audio playback ──
        output_devices = 0
        try:
            from core.hardware_detector import HardwareDetector
            hw_out = HardwareDetector.check_audio_output()
            output_devices = len(hw_out.devices)
        except ImportError:
            try:
                cnt = pa_instance.get_device_count()
                for i in range(cnt):
                    info = pa_instance.get_device_info_by_index(i)
                    if int(info.get("maxOutputChannels", 0) or 0) > 0:
                        output_devices += 1
            except Exception:
                pass

        if output_devices == 0:
            print("[Gemini Provider] ⚠️ Hoparlör bulunamadı — ses çıkışı olmadan çalışılıyor.")

        while True:
            # ── Pause check ──
            if j._paused:
                await asyncio.sleep(1)
                continue

            print("[JARVIS] 🔌 Bağlanıyor...")
            j.set_state("THINKING")
            config = self.build_config()
            client = genai.Client(
                api_key=_get_api_key(),
                http_options={"api_version": "v1alpha"}
            )

            async with client.aio.live.connect(
                model=LIVE_MODEL, config=config
            ) as session:
                self.session = session
                self.audio_in_queue = asyncio.Queue(maxsize=200)
                self.out_queue = asyncio.Queue(maxsize=10)

                print("[JARVIS] ✅ Bağlandı.")

                # ── Proactive voice ──
                pv = getattr(j, "proactive_voice", None)
                if pv is not None:
                    try:
                        pv.start()
                    except Exception:
                        pass

                j.set_state("LISTENING")
                logging.debug("[RUNNER] UI state set to LISTENING")
                j.ui.safe_call(j.ui.write_log, "SYS: JARVIS hazır. Dinliyorum...")
                logging.debug("[RUNNER] write_log called")

                # ── Open audio output stream (input comes from orchestrator pipeline) ──
                output_stream = None
                try:
                    if output_devices > 0:
                        print("[JARVIS] 🔊 Çıkış akışı açılıyor...")
                        logging.debug("[RUNNER] Opening output stream")
                        output_stream = await asyncio.to_thread(
                            pa_instance.open,
                            format=fmt, channels=CHANNELS,
                            rate=RECV_SAMPLE_RATE, output=True,
                        )
                        logging.debug("[RUNNER] Output stream opened successfully")
                    else:
                        print("[JARVIS] ⚠️ Hoparlör bulunamadı — ses çıkışı olmadan çalışılıyor.")
                        j.ui.safe_call(j.ui.write_log, "WARN: Hoparlör bulunamadı. Sadece yazılı yanıt verilecek.")

                    # Start tasks: send realtime audio from queue, receive from API, play output
                    tasks = [
                        self._send_realtime(),
                        self._receive_audio(),
                    ]
                    if output_stream is not None:
                        tasks.append(self._play_audio(output_stream))

                    if tasks:
                        async with asyncio.TaskGroup() as tg:
                            for t in tasks:
                                tg.create_task(t)
                finally:
                    if output_stream is not None:
                        print("[JARVIS] 🔊 Çıkış akışı kapatılıyor...")
                        try:
                            output_stream.close()
                        except Exception:
                            traceback.print_exc()
