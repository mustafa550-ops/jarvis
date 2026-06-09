# ── Ollama Provider ──────────────────────────────────────────
# Ollama HTTP API provider — text-in/text-out, local STT + TTS.
# Extracted from main.py to make the provider interface concrete.
# ──────────────────────────────────────────────────────────────

from __future__ import annotations

import asyncio
import datetime
import json
import os
import re
import time
import traceback
from typing import Any

import numpy as np
import scipy.signal

from core.provider_base import BaseProvider
from core.tool_registry import VALID_TOOLS, generate_ollama_tool_help

# VAD (unified FahrettinVAD wrapper)
try:
    from core.fahrettin_vad import FahrettinVAD
    _HAS_FAHRETTIN_VAD = True
except ImportError:
    _HAS_FAHRETTIN_VAD = False
    FahrettinVAD = None  # type: ignore

# RNNoise gürültü bastırma (opsiyonel — kütüphane yoksa bypass)
try:
    from audio.noise_suppressor import NoiseSuppressor
    _HAS_RNNOISE = True
except ImportError:
    _HAS_RNNOISE = False
    NoiseSuppressor = None  # type: ignore


# ── Constants (matches main.py) ──────────────────────────────

FRAME_SIZE = 480       # 30ms @ 16kHz
MIN_SILENCE_MS = 800
SILENCE_TIMEOUT_MS = 5000
NOISE_ADAPT_FRAMES = 30
MAX_ARG_LENGTH = 500
MAX_TOOL_CALL_TOTAL_LENGTH = 2000


# ── Tool Call Parser (extracted from main.py) ────────────────

def parse_local_tool_call(text: str) -> tuple | None:
    """Parse 'tool_name(args)' from Ollama response text.

    Returns (tool_name, parsed_args_dict) or None on failure.
    Uses VALID_TOOLS from tool_registry (single source of truth).
    """
    text = text.strip()
    if len(text) > MAX_TOOL_CALL_TOTAL_LENGTH:
        return None
    match = re.search(
        r'(?:TOOL:\s*)?([a-zA-Z0-9_]+)\((.*)\)',
        text, re.DOTALL | re.IGNORECASE
    )
    if not match:
        return None

    tool_name = match.group(1).strip().lower()
    args_content = match.group(2).strip()

    if tool_name not in VALID_TOOLS:
        print(
            f"[Ollama Tool Call] Bilinmeyen araç algılandı ve reddedildi: "
            f"'{tool_name}' (yanıt: {text[:120]})"
        )
        return None

    try:
        if args_content.startswith('{') and args_content.endswith('}'):
            parsed = json.loads(args_content)
            for k, v in parsed.items():
                if isinstance(v, str) and len(v) > MAX_ARG_LENGTH:
                    return None
            return tool_name, parsed
    except Exception:
        pass

    # Fallback: key=value pairs
    try:
        args: dict[str, Any] = {}
        pairs = re.findall(r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\S+))', args_content)
        for key, v1, v2, v3 in pairs:
            val = v1 or v2 or v3
            if len(val) > MAX_ARG_LENGTH:
                return None
            args[key] = val
        return tool_name, args
    except Exception:
        pass

    return None


# ── Helpers (moved from main.py) ─────────────────────────────

def _load_app_config():
    from app_config import load_app_config
    return load_app_config()


def _load_memory():
    from memory.memory_manager import load_memory
    return load_memory()


def _format_memory_for_prompt(mem):
    from memory.memory_manager import format_memory_for_prompt
    return format_memory_for_prompt(mem)


def _load_system_prompt():
    from main import load_system_prompt
    return load_system_prompt()


# ── Ollama Provider ──────────────────────────────────────────

class OllamaProvider(BaseProvider):

    @property
    def name(self) -> str:
        return "ollama"

    def __init__(self):
        super().__init__()
        self.input_queue: asyncio.Queue = asyncio.Queue()
        self._stt_task: asyncio.Task | None = None
        self._history: list[dict[str, str]] = []
        self._ollama_warned_quality = False
        self._running = False

    async def start(self, jarvis: Any) -> None:
        await super().start(jarvis)
        self._history = []
        self._ollama_warned_quality = False
        self._running = True

    async def stop(self):
        self._running = False
        if self._stt_task is not None and not self._stt_task.done():
            self._stt_task.cancel()
            try:
                await self._stt_task
            except (asyncio.CancelledError, Exception):
                pass
            self._stt_task = None

    async def send_text(self, text: str) -> None:
        """Put text into the Ollama processing queue."""
        await self.input_queue.put(text)

    # ── Main processing loop ─────────────────────────────────

    async def run_loop(self):
        """Main Ollama loop — STT + HTTP chat + TTS."""
        j = self._j()
        import httpx

        # ── Start STT listener ──
        if self._stt_task is None or self._stt_task.done():
            self._stt_task = asyncio.create_task(self._stt_listen_loop())

        if not self._history:
            self._history = []

        # ── Model Warm-up ──
        cfg = _load_app_config()
        warmup_model = cfg.get("ollama_model", "")
        if warmup_model:
            j.ui.write_log(f"SYS: Model yükleniyor ({warmup_model})...")
            j.ui.set_state("THINKING")
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    await client.post(
                        "http://localhost:11434/api/chat",
                        json={"model": warmup_model, "messages": [], "keep_alive": "30m"},
                    )
                print(f"[Ollama] Warm-up tamamlandı: {warmup_model}")
            except Exception as e:
                print(f"[Ollama] Warm-up hata (önemsiz): {e}")

        # ── Proactive voice start ──
        pv = getattr(j, "proactive_voice", None)
        if pv is not None:
            try:
                pv.start()
            except Exception:
                pass

        if getattr(j.ui, "_jarvis_state", "") not in ("THINKING", "SPEAKING"): j.ui.set_state("LISTENING")
        j.ui.write_log("SYS: JARVIS yerel modda hazır. Dinliyorum...")

        while self._running:
            cfg = _load_app_config()
            if cfg.get("backend_type", "gemini") != "ollama":
                break

            if j._paused:
                await asyncio.sleep(0.5)
                continue

            try:
                text = await asyncio.wait_for(self.input_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            # Voice memory log
            vm = getattr(j, "voice_memory", None)
            if vm is not None:
                try:
                    vm.log_user(text)
                except Exception:
                    pass

            j.ui.set_state("THINKING")

            # Thinking aloud
            ta = getattr(j, "thinking_aloud", None)
            if ta is not None:
                try:
                    ta.start("processing")
                except Exception:
                    pass

            # ── Build system prompt ──
            mem_data = _load_memory()
            mem_str = _format_memory_for_prompt(mem_data)
            sys_p = _load_system_prompt()
            now = datetime.datetime.now()
            time_ctx = f"[ŞU ANKİ ZAMAN]\n{now.strftime('%A, %d %B %Y — %H:%M')}\n\n"

            transcript_str = ""
            tr = getattr(j, "transcript", None)
            if tr is not None:
                try:
                    transcript_str = tr.get_formatted(n=5)
                except Exception:
                    pass

            parts = [time_ctx]
            if mem_str:
                parts.append(mem_str + "\n\n")
            if transcript_str:
                parts.append(transcript_str + "\n\n")
            parts.append(sys_p)
            system_instruction = "\n".join(parts)

            # Use tool_registry for Ollama tool help (single source of truth)
            system_instruction += generate_ollama_tool_help()

            messages = [{"role": "system", "content": system_instruction}]
            messages.extend(self._history[-20:])
            messages.append({"role": "user", "content": text})

            ollama_model = cfg.get("ollama_model", "")
            if not ollama_model:
                j.ui.write_log("ERR: Ollama modeli secilmemis.")
                j.ui.set_state("ERROR")
                continue

            print(f"[Ollama] Model: {ollama_model}")

            # ── Send to Ollama API ──
            response_text = ""
            try:
                response_text = await self._ollama_chat(
                    ollama_model, messages, j
                )
            except Exception as e:
                err_detail = f"{type(e).__name__}: {e}"
                print(f"[Ollama] Hata: {err_detail}")
                j.ui.write_log(f"ERR: Ollama yanit veremiyor — {err_detail[:120]}")
                j.ui.set_state("ERROR")
                continue

            print(f"[Ollama] Yanit uzunlugu: {len(response_text)} chars")

            # Clean <think> blocks from reasoning models
            response_text = re.sub(
                r"<think>[\s\S]*?</think>", "", response_text,
                flags=re.IGNORECASE
            ).strip()

            if not response_text:
                j.ui.write_log("WARN: Model bos yanit verdi, tekrar bekliyorum.")
                if getattr(j.ui, "_jarvis_state", "") not in ("THINKING", "SPEAKING"): j.ui.set_state("LISTENING")
                continue

            # ── Check for tool calls ──
            tool_call = parse_local_tool_call(response_text)
            if tool_call:
                tool_name, tool_args = tool_call
                print(f"[Ollama Tool Call] detected: {tool_name} with {tool_args}")
                j.ui.write_log(f"SYS: Araç çalıştırılıyor — {tool_name}")

                # LocalFunctionCall adapter → _execute_tool
                class LocalFunctionCall:
                    def __init__(self, name, args):
                        self.id = "local_call"
                        self.name = name
                        self.args = args

                try:
                    result_response = await j._execute_tool(
                        LocalFunctionCall(tool_name, tool_args)
                    )
                    result_text = result_response.response.get("result", "Tamamlandı.")
                except Exception as e:
                    result_text = f"Hata: {e}"

                self._history.append({"role": "user", "content": text})
                self._history.append({"role": "assistant", "content": response_text})
                tool_result_prompt = (
                    f"[ARAÇ SONUCU] {result_text}\n"
                    f"Lütfen kullanıcıya bunu Türkçe olarak açıkla."
                )
                self._history.append({"role": "user", "content": tool_result_prompt})

                messages = [{"role": "system", "content": system_instruction}]
                messages.extend(self._history[-20:])

                response_text = ""
                try:
                    j.ui.set_state("THINKING")
                    response_text = await self._ollama_chat(
                        ollama_model, messages, j
                    )
                    # Clean <think> blocks
                    response_text = re.sub(
                        r"<think>[\s\S]*?</think>", "", response_text,
                        flags=re.IGNORECASE
                    ).strip()
                except Exception as e:
                    err_detail = f"{type(e).__name__}: {e}"
                    print(f"[Ollama Tool Follow-up] Hata: {err_detail}")
                    j.ui.write_log(
                        f"ERR: Ollama arac sonrasi yanit veremiyor — {err_detail[:120]}"
                    )
                    j.ui.set_state("ERROR")
                    continue

                j.ui.write_log(f"JARVIS: {response_text}")
                await j._speak_response(response_text)

            else:
                self._history.append({"role": "user", "content": text})
                self._history.append({"role": "assistant", "content": response_text})
                j.ui.write_log(f"JARVIS: {response_text}")
                await j._speak_response(response_text)

    # ── Ollama HTTP Chat ─────────────────────────────────────

    async def _ollama_chat(
        self, model: str, messages: list, j: Any
    ) -> str:
        """Send messages to Ollama API, return response text."""
        import httpx

        response_text = ""
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST", "http://localhost:11434/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "keep_alive": "30m",
                },
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise Exception(
                        f"HTTP {resp.status_code}: {body.decode()[:200]}"
                    )

                # Chunked NDJSON reading
                buf = b""
                async for raw_bytes in resp.aiter_bytes():
                    buf += raw_bytes
                    while b"\n" in buf:
                        line_b, buf = buf.split(b"\n", 1)
                        line = line_b.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                response_text += content
                                # Quality warning for small models
                                if any(
                                    w in content.lower()
                                    for w in ["probability", "threshold", "confidence"]
                                ):
                                    if not self._ollama_warned_quality:
                                        self._ollama_warned_quality = True
                                        j.ui.write_log(
                                            "WARN: Mevcut Ollama modeli bazi isteklerde "
                                            "yetersiz kaliyor. Ayarlardan daha buyuk "
                                            "bir model secin (7B+)."
                                        )
                            done = data.get("done", False)
                            if done:
                                done_reason = data.get("done_reason", "")
                                if done_reason and done_reason not in ("stop", ""):
                                    j.ui.write_debug(
                                        f"Ollama done_reason: {done_reason}",
                                        level="WARN",
                                    )
                        except Exception:
                            pass
        return response_text

    # ── STT Listen Loop ──────────────────────────────────────

    async def _stt_listen_loop(self):
        """Main STT loop: PyAudio → STTEngine → input_queue."""
        j = self._j()
        import pyaudio
        from core.audio_system.stt_engine import get_stt_engine
        
        stt_engine = get_stt_engine()
        if not stt_engine.list_engines():
            print("[Ollama STT] UYARI: STT motoru hazir degil!")
            
        print("[Ollama STT] PyAudio baslatiliyor...")
        p = pyaudio.PyAudio()
        stream = None
        target_rate = 16000
        device_rate = 16000
        
        # Sudo altinda PulseAudio reddedilirse hw dogrudan 44100 veya 48000 Hz isteyebilir.
        for rate in [16000, 48000, 44100]:
            try:
                stream = p.open(
                    format=pyaudio.paInt16, channels=1, rate=rate,
                    input=True, frames_per_buffer=2048,
                )
                device_rate = rate
                print(f"[Ollama STT] PyAudio stream opened at {rate}Hz")
                break
            except Exception as e:
                print(f"[Ollama STT] PyAudio {rate}Hz failed: {e}")
                
        if stream is None:
            print("[Ollama STT] FATAL: Mikrofon baslatilamadi.")
            p.terminate()
            j.ui.write_log("ERR: Mikrofon baslatilamadi. Sesli komut calismayacak.")
            return

        # ── FahrettinVAD (unified VAD wrapper) ──
        self._fahrettin_vad: FahrettinVAD | None = None
        if _HAS_FAHRETTIN_VAD:
            try:
                from app_config import load_app_config
                cfg = load_app_config()
                audio_cfg = cfg.get("audio", {})
                self._fahrettin_vad = FahrettinVAD(
                    config=audio_cfg,
                    engine="energy",
                    energy_threshold=50.0,
                    debug_log=False,
                )
                print("[Ollama STT] FahrettinVAD etkin")
            except Exception:
                traceback.print_exc()
                print("[Ollama STT] FahrettinVAD baslatilamadi, energy VAD kullanilacak")

        FRAME_SIZE = 2048
        
        print("[Ollama STT] Dinleme başladı...")
        _speech_buf = bytearray()
        _pre_roll = []
        _silence_start = None
        _is_awake = False
        
        try:
            print(f"[Ollama STT DEBUG] Before while. running={self._running}", flush=True)
            while self._running:
                cfg = _load_app_config()
                is_paused = getattr(j, "_paused", False)
                backend = cfg.get("backend_type", "gemini")
                
                print(f"[Ollama STT DEBUG] loop tick. paused={is_paused}, backend={backend}", flush=True)
                
                if is_paused or backend != "ollama":
                    await asyncio.sleep(0.1)
                    continue

                barge = getattr(j, "barge_in", None)
                try:
                    # Non-blocking read attempts to avoid deadlocks
                    # DO NOT use run_in_executor here, PortAudio ALSA backend hangs when read from a ThreadPool worker!
                    print("[Ollama STT DEBUG] Before stream.read", flush=True)
                    data = stream.read(FRAME_SIZE, exception_on_overflow=False)
                    print("[Ollama STT DEBUG] After stream.read", flush=True)
                    await asyncio.sleep(0.001)  # yield control to asyncio loop
                    
                    # ── Downsample if needed ──
                    if device_rate != target_rate:
                        pcm = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                        samples = int(len(pcm) * target_rate / device_rate)
                        resampled = scipy.signal.resample(pcm, samples)
                        data = resampled.astype(np.int16).tobytes()
                    
                    # ── Feed shared modules ──
                    ww = getattr(j, "wake_word", None)
                    if ww is not None:
                        ww.feed_audio(data)
                    buf = getattr(j, "audio_buffer", None)
                    if buf is not None:
                        buf.write(data)
                        
                    with j._speaking_lock:
                        # Watchdog: If speaking state is stuck for more than 15 seconds, force unlock
                        if j._is_speaking and getattr(j, "_last_speech_start", 0) > 0:
                            if time.monotonic() - j._last_speech_start > 15.0:
                                j._is_speaking = False
                                j._last_speech_end = time.monotonic()
                                print("[Ollama STT] Watchdog triggered: Forcing _is_speaking to False", flush=True)
                                if barge is not None:
                                    barge.set_jarvis_speaking(False)

                    if barge is not None and barge.is_jarvis_speaking():
                        barge.process_user_audio(data)
                        continue

                    with j._speaking_lock:
                        js = j._is_speaking
                        sc = time.monotonic() - j._last_speech_end < j._speaking_cooldown
                        
                    if js or sc or j.ui.muted:
                        print(f"[Ollama STT DEBUG] Skipping RMS. js={js}, sc={sc}, muted={j.ui.muted}", flush=True)
                        continue
                        
                    # Wake word — gate STT until triggered
                    if ww is not None:
                        if j._wake_word_triggered:
                            _is_awake = True
                            j._wake_word_triggered = False
                        
                        if not _is_awake:
                            continue
                            
                    if getattr(j.ui, "_jarvis_state", "") not in ("THINKING", "SPEAKING"): j.ui.set_state("LISTENING")
                    
                    # VAD — unified FahrettinVAD wrapper
                    if self._fahrettin_vad is not None:
                        is_speech, _ = self._fahrettin_vad.is_speech(data, target_rate)
                    else:
                        # Fallback: simple energy threshold (no noise adaptation)
                        arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                        rms = float(np.sqrt(np.mean(arr ** 2)))
                        is_speech = rms > 400.0
                        
                    if is_speech:
                        if not _speech_buf:
                            # Prepend the last few frames to catch unvoiced starts of words
                            for f in _pre_roll:
                                _speech_buf.extend(f)
                        _speech_buf.extend(data)
                        _silence_start = None
                    else:
                        _pre_roll.append(data)
                        if len(_pre_roll) > 5:
                            _pre_roll.pop(0)
                            
                        if _speech_buf:
                            _speech_buf.extend(data)
                            if _silence_start is None:
                                _silence_start = time.time()
                            elif (time.time() - _silence_start) * 1000 > 700: # 700ms silence
                                audio_bytes = bytes(_speech_buf)
                                _speech_buf = bytearray()
                                _silence_start = None
                                _is_awake = False
                                
                                if len(audio_bytes) < 8000: # at least 0.5 sec
                                    continue
                                    
                                j.ui.set_state("THINKING")
                                text = ""
                                try:
                                    text = await asyncio.to_thread(
                                        stt_engine.transcribe, audio_bytes, target_rate
                                    )
                                except Exception as e:
                                    print(f"[Ollama STT] Transcription error: {e}")
                                    
                                if text and text.strip():
                                    text = text.strip()
                                    j._user_initiated = True
                                    j.ui.write_log(f"Siz: {text}")
                                    j.ui.mark_user_activity(True)
                                    print(f"[Ollama STT] {text}")
                                    await self.input_queue.put(text)
                                else:
                                    if getattr(j.ui, "_jarvis_state", "") not in ("THINKING", "SPEAKING"): j.ui.set_state("LISTENING")
                                    
                except OSError as e:
                    await asyncio.sleep(0.01)
                except Exception as e:
                    print(f"[Ollama STT] Loop error: {e}")
                    traceback.print_exc()
                    await asyncio.sleep(0.5)
        except Exception:
            traceback.print_exc()
        finally:
            try:
                if stream:
                    stream.close()
                p.terminate()
            except Exception:
                pass
