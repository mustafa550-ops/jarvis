# ── Gemini Provider ──────────────────────────────────────────
# Gemini Live API provider — bidirectional streaming audio.
# Extracted from main.py to make the provider interface concrete.
# ──────────────────────────────────────────────────────────────

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import traceback
from typing import Any

from core.provider_base import BaseProvider
from core.tool_registry import generate_gemini_declarations


# Lazy imports (genai is heavy and not always needed)
def _import_genai():
    from google import genai
    return genai


def _import_types():
    from google.genai import types
    return types


def _import_pyaudio():
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
    from app_config import get_app_config_value
    return str(get_app_config_value("gemini_api_key", "") or "")


def _get_app_config_value(key: str, default: Any = None):
    from app_config import get_app_config_value
    return get_app_config_value(key, default)


def _load_memory():
    from memory.memory_manager import load_memory
    return load_memory()


def _format_memory_for_prompt(mem):
    from memory.memory_manager import format_memory_for_prompt
    return format_memory_for_prompt(mem)


def _load_system_prompt():
    from main import load_system_prompt
    return load_system_prompt()


# ── Gemini Provider ─────────────────────────────────────────

class GeminiProvider(BaseProvider):

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def supports_streaming_audio(self) -> bool:
        return True

    @property
    def supports_tool_calls(self) -> bool:
        return True

    def __init__(self):
        super().__init__()
        self.session: Any = None
        self.audio_in_queue: asyncio.Queue | None = None
        self.out_queue: asyncio.Queue | None = None

    async def stop(self):
        self.session = None
        self.audio_in_queue = None
        self.out_queue = None

    async def send_audio(self, data: bytes) -> None:
        """Called from main.py's shared audio capture pipeline."""
        q = self.out_queue
        if q is not None:
            await q.put({"data": data, "mime_type": "audio/pcm"})

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

    async def _listen_audio(self, stream):
        """Read microphone, feed local modules, forward audio to Gemini."""
        j = self._j()
        print("[JARVIS] 🎤 Mikrofon başladı")
        try:
            while True:
                data = await asyncio.to_thread(
                    stream.read, CHUNK_SIZE, exception_on_overflow=False)

                # ── Feed ALL local audio modules (shared pipeline) ──
                ww = getattr(j, "wake_word", None)
                if ww is not None:
                    ww.feed_audio(data)
                buf = getattr(j, "audio_buffer", None)
                if buf is not None:
                    buf.write(data)
                sstt = getattr(j, "streaming_stt_engine", None)
                if sstt is not None:
                    sstt.feed_audio(data)
                barge = getattr(j, "barge_in", None)
                if barge is not None and barge.is_jarvis_speaking():
                    barge.process_user_audio(data)

                # ── Forward to Gemini if not speaking/paused/muted ──
                with j._speaking_lock:
                    jarvis_speaking = j._is_speaking
                if not jarvis_speaking and not j.ui.muted and not j._paused:
                    await self.out_queue.put({
                        "data": data,
                        "mime_type": "audio/pcm"
                    })
        except Exception as e:
            print(f"[JARVIS] ❌ Mikrofon: {e}")
            raise

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
                        self.audio_in_queue.put_nowait(response.data)

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
                                j.ui.mark_user_activity(True)

                        if sc.turn_complete:
                            j.set_speaking(False)

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                j.ui.write_log(f"Siz: {full_in}")
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                j.ui.write_log(f"JARVIS: {full_out}")
                                if output_noise_samples:
                                    j.ui.write_debug(
                                        "Kısmen filtrelenen ses transcripti: " + " | ".join(output_noise_samples),
                                        level="WARN",
                                    )
                            elif output_noise:
                                j.ui.write_log("ERR: JARVIS sesli yanıtını çözümlerken bir hata oluştu.")
                                if output_noise_samples:
                                    j.ui.write_debug(
                                        "Filtrelenen ham transcript: " + " | ".join(output_noise_samples),
                                        level="WARN",
                                    )
                                j.ui.set_state("ERROR")
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

        while True:
            # ── Pause check ──
            if j._paused:
                await asyncio.sleep(1)
                continue

            print("[JARVIS] 🔌 Bağlanıyor...")
            j.ui.set_state("THINKING")
            config = self.build_config()

            client = genai.Client(
                api_key=_get_api_key(),
                http_options={"api_version": "v1alpha"}
            )

            async with client.aio.live.connect(
                model=LIVE_MODEL, config=config
            ) as session:
                self.session = session
                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=10)

                print("[JARVIS] ✅ Bağlandı.")

                # ── Proactive voice ──
                pv = getattr(j, "proactive_voice", None)
                if pv is not None:
                    try:
                        pv.start()
                    except Exception:
                        pass

                j.ui.set_state("LISTENING")
                logging.debug("[RUNNER] UI state set to LISTENING")
                j.ui.write_log("SYS: JARVIS hazır. Dinliyorum...")
                logging.debug("[RUNNER] write_log called")

                # Open audio streams sequentially (avoid PortAudio/ALSA segfaults)
                print("[JARVIS] 🎤 Giriş akışı açılıyor...")
                logging.debug("[RUNNER] Opening input stream")
                input_stream = await asyncio.to_thread(
                    pa_instance.open,
                    format=fmt, channels=CHANNELS,
                    rate=SEND_SAMPLE_RATE, input=True,
                    frames_per_buffer=CHUNK_SIZE,
                )
                logging.debug("[RUNNER] Input stream opened successfully")

                try:
                    print("[JARVIS] 🔊 Çıkış akışı açılıyor...")
                    logging.debug("[RUNNER] Opening output stream")
                    output_stream = await asyncio.to_thread(
                        pa_instance.open,
                        format=fmt, channels=CHANNELS,
                        rate=RECV_SAMPLE_RATE, output=True,
                    )
                    logging.debug("[RUNNER] Output stream opened successfully")
                    try:
                        async with asyncio.TaskGroup() as tg:
                            tg.create_task(self._send_realtime())
                            tg.create_task(self._listen_audio(input_stream))
                            tg.create_task(self._receive_audio())
                            tg.create_task(self._play_audio(output_stream))
                    finally:
                        print("[JARVIS] 🔊 Çıkış akışı kapatılıyor...")
                        try:
                            output_stream.close()
                        except Exception:
                            traceback.print_exc()
                finally:
                    print("[JARVIS] 🎤 Giriş akışı kapatılıyor...")
                    try:
                        input_stream.close()
                    except Exception:
                        traceback.print_exc()
