#!/usr/bin/env python3
"""
JARVIS  — Gercek zamanli sesli yardimci cekirdegi
Adler ASİ tarafından yapılmıştır
İyilik iyidir...
"""

import sys
import logging
import traceback
import threading
import time
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "jarvis.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    filemode="w",
    level=logging.DEBUG,
    format="%(asctime)s - %(threadName)s - %(levelname)s - %(message)s"
)

logging.getLogger("httpcore").setLevel(logging.WARNING)

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Unhandled main exception", exc_info=(exc_type, exc_value, exc_traceback))
    with open(LOG_FILE, "a") as f:
        f.write("--- MAIN EXCEPTION ---\n")
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
    print(f"CRASH LOGGED TO {LOG_FILE}", file=sys.stderr)

sys.excepthook = handle_exception

def handle_thread_exception(args):
    logging.critical("Unhandled thread exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    with open(LOG_FILE, "a") as f:
        f.write("--- THREAD EXCEPTION ---\n")
        traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback, file=f)
    print(f"THREAD CRASH LOGGED TO {LOG_FILE}: {args.exc_value}", file=sys.stderr)

threading.excepthook = handle_thread_exception

import asyncio
import os
from google.genai import types

from app_config import load_app_config
from ui import JarvisUI
from memory.memory_manager import update_memory, delete_memory
from actions.open_app import open_app
from actions.sys_info  import sys_info
from actions.calendar import get_calendar_events, add_calendar_event, delete_calendar_event
from actions.reminders import get_reminders, add_reminder
from actions.browser   import browser_control
from actions.shell     import shell_run
from actions.whatsapp  import send_whatsapp_message, save_whatsapp_contact
from actions.media     import play_media
from actions.weather   import get_weather_summary
from actions.screen_vision import analyze_screen
from actions.youtube_stats import get_youtube_channel_report
from actions.system_doctor import get_system_health, cleanup_temp_files, cleanup_recycle_bin
from actions.process_manager import list_processes, kill_process, set_process_priority, find_process_by_port
from actions.file_guardian import find_large_files, find_duplicate_files, cleanup_folder, get_folder_summary
from actions.network_monitor import get_network_summary, list_connections as list_net_connections, ping_host
from actions.system_cron import add_cron_job, list_cron_jobs, remove_cron_job, start_cron_daemon
from actions.service_monitor import list_services, control_service
from core.skill_manager import get_skill_manager
from core.tool_registry import TOOL_HANDLER_MAP

# Audio yapılandırması (opsiyonel, config/audio.yaml)
def load_audio_config() -> dict:
    """'config/audio.yaml' dosyasını oku, yoksa boş dict dön."""
    audio_cfg_path = BASE_DIR / "config" / "audio.yaml"
    if not audio_cfg_path.exists():
        return {}
    try:
        import yaml
        raw = yaml.safe_load(audio_cfg_path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}

BASE_DIR        = Path(__file__).resolve().parent
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"

# ── Ses seviyesi yardımcıları ────────────────────────────────
def _set_volume(level: int) -> str:
    vol = max(0, min(100, level))
    try:
        if os.name == "nt":
            return _set_volume_windows(vol)
        elif sys.platform == "darwin":
            return _set_volume_macos(vol)
        return _set_volume_linux(vol, relative=False)
    except Exception:
        traceback.print_exc()
        return "Ses ayarlanamadi."

def _change_volume(delta: int) -> str:
    try:
        if os.name == "nt":
            return _set_volume_windows(delta, relative=True)
        elif sys.platform == "darwin":
            return _set_volume_macos(delta, relative=True)
        return _set_volume_linux(delta, relative=True)
    except Exception:
        traceback.print_exc()
        return "Ses degistirilemedi."

def _set_volume_linux(level: int, relative: bool = False) -> str:
    try:
        import subprocess as sp
        sinks = sp.run(
            ["pactl", "list", "sinks", "short"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip().split("\n")
        if not sinks or not sinks[0].strip():
            return "Ses cihazi bulunamadi."
        sink = sinks[0].split()[1] if len(sinks) > 1 else sinks[0].split()[0]
        op = "+" if relative and level >= 0 else ("-" if relative and level < 0 else "")
        sp.run(
            ["pactl", "set-sink-volume", sink, f"{op}{abs(level)}%"],
            capture_output=True, timeout=5
        )
        return f"Ses {'%+d' % level if relative else '%d' % level} olarak ayarlandi."
    except Exception:
        traceback.print_exc()
        return "Linux ses ayari yapilamadi."

def _set_volume_macos(level: int, relative: bool = False) -> str:
    try:
        import subprocess as sp
        if relative:
            sp.run(["osascript", "-e", f"set volume output volume (output volume of (get volume settings)) + {level}"],
                    capture_output=True, timeout=5)
        else:
            sp.run(["osascript", "-e", f"set volume output volume {level}"],
                    capture_output=True, timeout=5)
        return f"Ses {'%+d' % level if relative else '%d' % level} olarak ayarlandi."
    except Exception:
        traceback.print_exc()
        return "macOS ses ayari yapilamadi."

def _set_volume_windows(level: int, relative: bool = False) -> str:
    try:
        import subprocess as sp
        nircmd = Path(__file__).resolve().parent / "helpers" / "bin" / "nircmd.exe"
        if not nircmd.exists():
            return "nircmd.exe bulunamadi."
        if relative:
            op = "changesysvolume" if level >= 0 else "changesysvolume"
            sp.run([str(nircmd), op, str(int(level * 655.35))], capture_output=True, timeout=5)
        else:
            sp.run([str(nircmd), "setsysvolume", str(int(level * 655.35))], capture_output=True, timeout=5)
        return f"Ses {'%+d' % level if relative else '%d' % level} olarak ayarlandi."
    except Exception:
        traceback.print_exc()
        return "Windows ses ayari yapilamadi."

def load_system_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return ""

# ── Ana Jarvis sinifi ─────────────────────────────────────────
class JarvisLive:
    """JARVIS main controller — orchestrates UI, providers, tools, and local modules."""

    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        self._loop          = None
        self._provider      = None
        self._is_speaking     = False
        self._speaking_lock   = threading.Lock()
        self._speaking_cooldown = 2.0
        self._last_speech_end = 0.0
        self._shutdown_event   = threading.Event()

        self.ui.on_text_command  = self._on_text_command
        self.ui.on_pause_toggle  = self._on_pause_toggle
        self.ui.on_effects_state_change = self._on_effects_state_change
        self._paused             = False
        self._user_initiated     = False
        self._effects_enabled    = True
        self._wake_word_triggered = False

        # ── Audio yapılandırması (RNNoise, mikrofon, vb.) ──
        self.audio_config = load_audio_config()

        # ── Skill Manager ──
        self.skill_manager = get_skill_manager()

        # ── Assimilated modules ──
        self._asimilasyon_init()

    def _asimilasyon_init(self):
        """Initialize all assimilated modules (graceful fallback on all)."""
        try:
            from core.local_llm import LocalLLM
            self.local_llm = LocalLLM()
        except Exception:
            self.local_llm = None

        try:
            from memory.voice_memory import VoiceMemory
            self.voice_memory = VoiceMemory()
            self.voice_memory.start_session()
        except Exception:
            self.voice_memory = None

        try:
            from memory.conversation_transcript import ConversationTranscript
            self.transcript = ConversationTranscript()
        except Exception:
            self.transcript = None

        try:
            from core.streaming_tts import StreamingTTS
            self.streaming_tts = StreamingTTS(
                on_error=lambda exc: self.ui.write_log(f"[TTS] Hata: {exc}"),
            )
        except Exception:
            self.streaming_tts = None

        try:
            from core.voice_manager import VoiceManager
            self.voice_manager = VoiceManager()
        except Exception:
            self.voice_manager = None

        try:
            from core.multimodal import create_multimodal_engine
            self.multimodal = create_multimodal_engine()
        except Exception:
            self.multimodal = None

        try:
            from core.thinking_aloud import create_thinking_aloud
            self.thinking_aloud = create_thinking_aloud(
                on_phrase=lambda phrase: self._speak_thinking_phrase(phrase)
            )
        except Exception:
            self.thinking_aloud = None

        try:
            from core.proactive_voice import create_proactive_voice
            self.proactive_voice = create_proactive_voice(
                on_speak=lambda msg: self._speak_proactive(msg)
            )
        except Exception:
            self.proactive_voice = None

        try:
            from core.wake_word import create_wake_word_engine
            self.wake_word = create_wake_word_engine(
                on_wake_word=lambda kw: self._on_wake_word(kw),
                on_error=lambda exc: self.ui.write_log(f"[WakeWord] Hata: {exc}"),
                config=self.app_config.get("audio", {}).get("wake_word"),
            )
            self.wake_word.start()
            self._wake_word_triggered = False
        except Exception:
            self.wake_word = None
            self._wake_word_triggered = False

        try:
            # Pull VAD config from audio.yaml (with sensible defaults)
            vad_cfg = self.app_config.get("audio", {}).get("vad", {})
            fc = vad_cfg.get("fahrettin", {})
            vad_engine_name = fc.get("engine", "energy")
            vad_energy_threshold = float(fc.get("energy_threshold", 50.0))

            from core.vad_engine import create_vad_engine
            self.vad_engine = create_vad_engine(
                engine=vad_engine_name,
                on_speech_start=self._on_vad_speech_start,
                on_speech_end=self._on_vad_speech_end,
                energy_threshold=vad_energy_threshold,
            )
        except Exception:
            self.vad_engine = None

        try:
            from core.streaming_stt import create_streaming_stt
            self.streaming_stt_engine = create_streaming_stt(
                on_text=lambda text: self._on_stt_text(text)
            )
            self.streaming_stt_engine.start()
        except Exception:
            self.streaming_stt_engine = None

        try:
            from core.audio_buffer import AudioBuffer
            self.audio_buffer = AudioBuffer()
        except Exception:
            self.audio_buffer = None

        try:
            from core.emotion_tts import EmotionTTS
            self.emotion_tts = EmotionTTS()
        except Exception:
            self.emotion_tts = None

        try:
            from core.barge_in import create_barge_in_detector
            self.barge_in = create_barge_in_detector(
                on_barge_in=lambda: self._on_barge_in(),
                on_error=lambda exc: self.ui.write_log(f"[BargeIn] Hata: {exc}"),
            )
        except Exception:
            self.barge_in = None

        try:
            from vision.camera_capture import CameraCapture
            self.camera = CameraCapture()
        except Exception:
            self.camera = None

    def _speak_proactive(self, text: str):
        self.set_speaking(True)
        try:
            from actions.tts import speak_text
            speak_text(text, blocking=False)
        except Exception:
            traceback.print_exc()
        finally:
            self.set_speaking(False)

    def _speak_thinking_phrase(self, phrase: str):
        self.set_speaking(True)
        try:
            from actions.tts import speak_text
            speak_text(phrase, blocking=True)
        except Exception:
            pass
        finally:
            self.set_speaking(False)

    def _on_stt_text(self, text: str):
        """StreamingSTT callback — route transcribed text to active provider."""
        if not text or not text.strip():
            return
        text = text.strip()
        self._user_initiated = True
        self.ui.write_log(f"Siz: {text}")
        self.ui.mark_user_activity(True)
        if self._provider is not None and hasattr(self._provider, 'input_queue'):
            self._provider.input_queue.put_nowait(text)

    def _on_barge_in(self):
        self.set_speaking(False)
        if hasattr(self, "streaming_tts") and self.streaming_tts:
            try:
                self.streaming_tts.stop()
            except Exception:
                pass
        self.ui.write_log("SYS: Kullanici araya girdi, yanit kesildi.")

    def _on_wake_word(self, keyword: str):
        self.ui.write_log(f"[WakeWord] '{keyword}' algilandi")
        self._wake_word_triggered = True
        self._user_initiated = True
        self.ui.mark_user_activity(True)

    def _on_vad_speech_start(self):
        self.ui.write_log("[VAD] Konusma basladi")
        self.ui.mark_user_activity(True)

    def _on_vad_speech_end(self):
        self.ui.write_log("[VAD] Konusma sona erdi")

    async def _speak_response(self, response_text: str):
        if hasattr(self, "thinking_aloud") and self.thinking_aloud:
            try:
                self.thinking_aloud.stop()
            except Exception:
                pass
        if hasattr(self, "transcript") and self.transcript:
            try:
                last_user = self._last_user_text if hasattr(self, "_last_user_text") else ""
                self.transcript.add_turn(user_text=last_user, jarvis_text=response_text)
            except Exception:
                pass
        if hasattr(self, "voice_memory") and self.voice_memory:
            try:
                self.voice_memory.log_jarvis(response_text)
            except Exception:
                pass
        self.set_speaking(True)
        try:
            if hasattr(self, "emotion_tts") and self.emotion_tts:
                try:
                    from core.emotion_tts import _detect_emotion
                    emotion = _detect_emotion(response_text)
                    vm = getattr(self, "voice_manager", None)
                    if vm is not None:
                        vm.set_emotion(emotion)
                    self.emotion_tts.speak(response_text, emotion=emotion, blocking=True)
                except Exception:
                    from actions.tts import speak_text
                    speak_text(response_text, blocking=True)
            elif hasattr(self, "streaming_tts") and self.streaming_tts:
                await asyncio.to_thread(self.streaming_tts.speak, response_text, True)
            else:
                from actions.tts import speak_text
                await asyncio.to_thread(speak_text, response_text, blocking=True)
        except Exception:
            traceback.print_exc()
        finally:
            self.set_speaking(False)

    def _on_pause_toggle(self, paused: bool):
        self._paused = paused

    def _on_effects_state_change(self, enabled: bool):
        self._effects_enabled = enabled
        logging.info("Effects state changed: enabled=%s", enabled)

    def _focus_ui_section_for_tool(self, tool_name: str, args: dict):
        if tool_name == "sys_info":
            query = str(args.get("query", "")).strip().lower()
            if query in {"time", "saat", "zaman", "date", "tarih"}:
                self.ui.focus_panel("time", duration_ms=5200)
            else:
                self.ui.focus_panel("system", duration_ms=5200)
        elif tool_name == "get_weather":
            self.ui.focus_panel("weather", duration_ms=5600)
        elif tool_name in {
            "get_system_health", "cleanup_temp_files", "cleanup_recycle_bin",
            "list_processes", "kill_process", "set_process_priority",
            "find_large_files", "find_duplicate_files", "cleanup_folder", "get_folder_summary",
            "get_network_summary", "list_net_connections", "ping_host",
            "add_cron_job", "list_cron_jobs", "remove_cron_job",
            "list_services", "control_service",
        }:
            self.ui.focus_panel("system", duration_ms=8000)

    def _on_text_command(self, text: str):
        if self._paused:
            return
        if not text or len(text) > 10000:
            return
        self._user_initiated = True

        skill_result = self.skill_manager.route(text)
        if skill_result is not None:
            self.ui.write_log(f"JARVIS: {skill_result}")
            return

        self.ui.write_log(f"Siz: {text}")
        if self._provider is not None:
            asyncio.run_coroutine_threadsafe(
                self._provider.send_text(text),
                self._loop
            )
        else:
            self.ui.write_log("ERR: JARVIS baglantisi henuz hazir degil.")

    async def _interrupt_audio(self):
        self.set_speaking(False)

    def set_speaking(self, value: bool, audio_level: float = 30.0):
        with self._speaking_lock:
            self._is_speaking = value
            if not value:
                self._last_speech_end = time.monotonic()
            else:
                self._last_speech_start = time.monotonic()
        if value:
            self.ui.set_state("SPEAKING")
            if hasattr(self, "barge_in") and self.barge_in:
                self.barge_in.set_jarvis_speaking(True, audio_level)
        else:
            self.ui.set_state("LISTENING")
            if hasattr(self, "barge_in") and self.barge_in:
                self.barge_in.set_jarvis_speaking(False)

    def shutdown(self):
        """Signal the asyncio run loop to exit cleanly."""
        self._shutdown_event.set()

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.ui.write_debug(f"{tool_name}: {short}", level="ERROR")
        self.ui.set_state("ERROR")

    @staticmethod
    def _result_looks_like_error(result) -> bool:
        text = str(result or "").strip().lower()
        if not text:
            return False
        error_markers = (
            "hata", "error", "alinamadi", "alınamadı",
            "bulunamadi", "bulunamadı", "acilamadi", "açılamadı",
            "tamamlanamadi", "tamamlanamadı", "gecersiz", "geçersiz",
            "izin gerekiyor", "izin gerekli", "baglanti", "bağlantı", "gerekli.",
        )
        return any(marker in text for marker in error_markers)

    @staticmethod
    def _should_play_success_sfx(tool_name: str, args: dict, result) -> bool:
        action_tools = {
            "open_app", "add_calendar_event", "add_reminder",
            "delete_calendar_event", "remove_calendar_event",
        }
        if tool_name in action_tools:
            return True
        if tool_name == "send_whatsapp_message":
            text = str(result or "").lower()
            if bool(args.get("send_now", False)):
                return "gönderildi" in text or "gonderildi" in text
            return False
        return False

    # ── Tool dispatch map ─────────────────────────────────────
    _TOOL_HANDLERS: dict[str, str] = {}

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})
        print(f"[JARVIS] 🔧 {name} {args}")
        self.ui.set_state("THINKING")

        loop   = asyncio.get_event_loop()
        result = "Tamam."
        had_exception = False

        if not self._TOOL_HANDLERS:
            self._build_tool_handler_map()

        method_name = self._TOOL_HANDLERS.get(name)
        if method_name:
            method = getattr(self, method_name, None)
            if method:
                try:
                    result = await method(args, loop)
                except Exception as e:
                    result = f"Hata: {e}"
                    had_exception = True
                    traceback.print_exc()
                    self.speak_error(name, e)
            else:
                result = f"Bilinmeyen araç: {name}"
        else:
            result = f"Bilinmeyen araç: {name}"

        tool_failed = self._result_looks_like_error(result)
        if tool_failed:
            if not had_exception:
                self.ui.set_state("ERROR")
        elif self._should_play_success_sfx(name, args, result):
            self.ui.play_success_sfx()

        if not tool_failed and not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    def _build_tool_handler_map(self):
        self._TOOL_HANDLERS = dict(TOOL_HANDLER_MAP)

    async def run(self):
        """Main entry point — delegates to the active provider."""
        from core.gemini_provider import GeminiProvider
        from core.ollama_provider import OllamaProvider

        self._loop = asyncio.get_event_loop()

        while not self._shutdown_event.is_set():
            if self._paused:
                await asyncio.sleep(1)
                continue

            cfg = load_app_config()
            backend = cfg.get("backend_type", "gemini")
            print(f"[DEBUG] Loaded config: {cfg}")
            print(f"[DEBUG] Selected backend: {backend}")

            if backend == "ollama":
                provider = OllamaProvider()
            else:
                provider = GeminiProvider()

            try:
                self._provider = provider
                await provider.start(self)
                await provider.run_loop()
            except Exception as e:
                print(f"[JARVIS] ⚠️ {backend}: {e}")
                traceback.print_exc()
                self.set_speaking(False)
                self.ui.write_log(f"ERR: JARVIS baglantisi kesildi — {e}")
                self.ui.set_state("ERROR")
                print(f"[JARVIS] 🔄 3 saniyede yeniden {backend} baglaniyor...")
                await asyncio.sleep(3)
            finally:
                self._provider = None
                try:
                    await provider.stop()
                except Exception:
                    pass

    # ── Tool handlers ─────────────────────────────────────────

    async def _handle_get_current_location(self, args, loop) -> str:
        from actions.location import get_current_location
        loc = await loop.run_in_executor(None, get_current_location)
        if loc:
            try:
                from memory.memory_manager import update_memory
                await loop.run_in_executor(None, update_memory, "weather_location", loc.get("city", ""))
            except Exception:
                pass
            city = loc.get("city", "bilinmiyor")
            region = loc.get("region", "")
            country = loc.get("country", "")
            return f"Konum: {city}, {region}, {country}"
        return "Konum alinamadi."

    async def _handle_save_memory(self, args, loop) -> str:
        category = args.get("category", "notes")
        key      = args.get("key", "")
        value    = args.get("value", "")
        if not key or not value:
            return "Eksik parametre: key ve value gerekli."
        await loop.run_in_executor(None, update_memory, key, value, category)
        return f"Hafizaya kaydedildi: {key}={value}"

    async def _handle_delete_memory(self, args, loop) -> str:
        match_text = args.get("match_text", "")
        category   = args.get("category", "")
        key        = args.get("key", "")
        await loop.run_in_executor(None, delete_memory, category, key, match_text)
        return "Hafizadan silindi."

    async def _handle_open_app(self, args, loop) -> str:
        name = args.get("app_name", "")
        if not name:
            return "Uygulama adi gerekli."
        result = await loop.run_in_executor(None, open_app, name)
        return str(result)

    async def _handle_sys_info(self, args, loop) -> str:
        query = args.get("query", "all")
        result = await loop.run_in_executor(None, sys_info, query)
        return str(result)

    async def _handle_get_weather(self, args, loop) -> str:
        location = args.get("location", "")
        result = await loop.run_in_executor(None, get_weather_summary, location)
        return str(result)

    async def _handle_get_calendar_events(self, args, loop) -> str:
        query = args.get("query", "today")
        limit = args.get("limit", 10)
        result = await loop.run_in_executor(None, get_calendar_events, query, limit)
        return str(result)

    async def _handle_add_calendar_event(self, args, loop) -> str:
        title = args.get("title", "")
        start_iso = args.get("start_iso", "")
        end_iso = args.get("end_iso", "")
        location = args.get("location", "")
        notes = args.get("notes", "")
        calendar_name = args.get("calendar_name", "")
        all_day = args.get("all_day", False)
        if not title or not start_iso:
            return "Baslik ve baslangic tarihi gerekli."
        result = await loop.run_in_executor(
            None, add_calendar_event,
            title, start_iso, end_iso, location, notes, calendar_name, all_day
        )
        return str(result)

    async def _handle_delete_calendar_event(self, args, loop) -> str:
        title = args.get("title", "")
        start_iso = args.get("start_iso", "")
        calendar_name = args.get("calendar_name", "")
        delete_all_matches = args.get("delete_all_matches", False)
        if not title:
            return "Etkinlik basligi gerekli."
        result = await loop.run_in_executor(
            None, delete_calendar_event,
            title, start_iso, calendar_name, delete_all_matches
        )
        return str(result)

    async def _handle_get_reminders(self, args, loop) -> str:
        query = args.get("query", "today")
        limit = args.get("limit", 10)
        list_name = args.get("list_name", "")
        result = await loop.run_in_executor(None, get_reminders, query, limit, list_name)
        return str(result)

    async def _handle_add_reminder(self, args, loop) -> str:
        title = args.get("title", "")
        due_iso = args.get("due_iso", "")
        notes = args.get("notes", "")
        list_name = args.get("list_name", "")
        priority = args.get("priority", "medium")
        all_day = args.get("all_day", False)
        if not title:
            return "Hatirlatma basligi gerekli."
        result = await loop.run_in_executor(
            None, add_reminder,
            title, due_iso, notes, list_name, priority, all_day
        )
        return str(result)

    async def _handle_browser_control(self, args, loop) -> str:
        action = args.get("action", "")
        url    = args.get("url", "")
        query  = args.get("query", "")
        result = await loop.run_in_executor(None, browser_control, action, url, query)
        return str(result)

    async def _handle_browser_skill(self, args, loop) -> str:
        action = args.get("action", "open_url")
        target = args.get("target", "")
        if action == "open_url":
            result = await loop.run_in_executor(None, browser_control, "open_url", target, "")
        elif action == "search":
            result = await loop.run_in_executor(None, browser_control, "search", "", target)
        elif action == "play_youtube":
            result = await loop.run_in_executor(None, browser_control, "play_youtube", "", target)
        else:
            result = f"Bilinmeyen browser action: {action}"
        return str(result)

    async def _handle_shell_run(self, args, loop) -> str:
        command = args.get("command", "")
        if not command:
            return "Komut gerekli."
        result = await loop.run_in_executor(None, shell_run, command)
        return str(result)

    async def _handle_play_media(self, args, loop) -> str:
        query = args.get("query", "")
        provider = args.get("provider", "auto")
        autoplay = args.get("autoplay", False)
        if not query:
            return "Sarki adi gerekli."
        result = await loop.run_in_executor(None, play_media, query, provider, autoplay)
        return str(result)

    async def _handle_get_youtube_channel_report(self, args, loop) -> str:
        query = args.get("query", "")
        handle = args.get("handle", "")
        video_limit = args.get("video_limit", 6)
        result = await loop.run_in_executor(None, get_youtube_channel_report, query, handle, video_limit)
        return str(result)

    async def _handle_analyze_screen(self, args, loop) -> str:
        query = args.get("query", "")
        target = args.get("target", "active_window")
        result = await loop.run_in_executor(None, analyze_screen, query, target)
        return str(result)

    async def _handle_capture_camera(self, args, loop) -> str:
        query = args.get("query", "Bu nedir?")
        multimodal = getattr(self, "multimodal", None)
        if multimodal is None:
            return "Kamera modulu aktif degil."
        try:
            result = await loop.run_in_executor(None, multimodal.analyze_camera, query)
            return str(result)
        except Exception as e:
            return f"Kamera hatasi: {e}"

    async def _handle_send_whatsapp_message(self, args, loop) -> str:
        recipient_name = args.get("recipient_name", "")
        phone_number = args.get("phone_number", "")
        message = args.get("message", "")
        app_target = args.get("app_target", "auto")
        send_now = args.get("send_now", False)
        if not message:
            return "Mesaj gerekli."
        if not recipient_name and not phone_number:
            return "Alici adi veya telefon numarasi gerekli."
        try:
            result = await loop.run_in_executor(
                None, send_whatsapp_message,
                recipient_name, phone_number, message, app_target, send_now
            )
            return str(result)
        except Exception as e:
            return f"Whatsapp hatasi: {e}"

    async def _handle_save_whatsapp_contact(self, args, loop) -> str:
        display_name = args.get("display_name", "")
        phone_number = args.get("phone_number", "")
        aliases = args.get("aliases", "")
        if not display_name or not phone_number:
            return "Isim ve telefon numarasi gerekli."
        try:
            result = await loop.run_in_executor(None, save_whatsapp_contact, display_name, phone_number, aliases)
            return str(result)
        except Exception as e:
            return f"Kisi kayit hatasi: {e}"

    async def _handle_get_system_health(self, args, loop) -> str:
        query = args.get("query", "all")
        result = await loop.run_in_executor(None, get_system_health, query)
        return str(result)

    async def _handle_cleanup_temp_files(self, args, loop) -> str:
        result = await loop.run_in_executor(None, cleanup_temp_files)
        return str(result)

    async def _handle_cleanup_recycle_bin(self, args, loop) -> str:
        result = await loop.run_in_executor(None, cleanup_recycle_bin)
        return str(result)

    async def _handle_list_processes(self, args, loop) -> str:
        sort_by = args.get("sort_by", "cpu")
        limit   = args.get("limit", 10)
        result = await loop.run_in_executor(None, list_processes, sort_by, limit)
        return str(result)

    async def _handle_kill_process(self, args, loop) -> str:
        identifier = args.get("identifier", "")
        force      = args.get("force", False)
        if not identifier:
            return "Surec adi veya PID gerekli."
        result = await loop.run_in_executor(None, kill_process, identifier, force)
        return str(result)

    async def _handle_set_process_priority(self, args, loop) -> str:
        identifier = args.get("identifier", "")
        priority   = args.get("priority", "normal")
        result = await loop.run_in_executor(None, set_process_priority, identifier, priority)
        return str(result)

    async def _handle_find_process_by_port(self, args, loop) -> str:
        port = args.get("port", 0)
        try:
            port = int(port)
        except (ValueError, TypeError):
            return "Gecerli bir port numarasi girin."
        result = await loop.run_in_executor(None, find_process_by_port, port)
        return str(result)

    async def _handle_find_large_files(self, args, loop) -> str:
        path = args.get("path", "")
        min_size_mb = args.get("min_size_mb", 100)
        limit       = args.get("limit", 20)
        result = await loop.run_in_executor(None, find_large_files, path, min_size_mb, limit)
        return str(result)

    async def _handle_find_duplicate_files(self, args, loop) -> str:
        path  = args.get("path", "")
        limit = args.get("limit", 10)
        result = await loop.run_in_executor(None, find_duplicate_files, path, limit)
        return str(result)

    async def _handle_cleanup_folder(self, args, loop) -> str:
        path   = args.get("path", "")
        pattern = args.get("pattern", "*")
        dry_run = args.get("dry_run", True)
        if not path:
            return "Klasor yolu gerekli."
        result = await loop.run_in_executor(None, cleanup_folder, path, pattern, dry_run)
        return str(result)

    async def _handle_get_folder_summary(self, args, loop) -> str:
        path = args.get("path", "")
        result = await loop.run_in_executor(None, get_folder_summary, path)
        return str(result)

    async def _handle_get_network_summary(self, args, loop) -> str:
        result = await loop.run_in_executor(None, get_network_summary)
        return str(result)

    async def _handle_list_net_connections(self, args, loop) -> str:
        state = args.get("state", "all")
        limit = args.get("limit", 20)
        result = await loop.run_in_executor(None, list_net_connections, state, limit)
        return str(result)

    async def _handle_ping_host(self, args, loop) -> str:
        host  = args.get("host", "google.com")
        count = args.get("count", 4)
        result = await loop.run_in_executor(None, ping_host, host, count)
        return str(result)

    async def _handle_add_cron_job(self, args, loop) -> str:
        name          = args.get("name", "")
        command       = args.get("command", "")
        schedule_type = args.get("schedule_type", "daily")
        schedule_value = args.get("schedule_value", "")
        if not name or not command:
            return "Isim ve komut gerekli."
        result = await loop.run_in_executor(
            None, add_cron_job,
            name, command, schedule_type, schedule_value
        )
        return str(result)

    async def _handle_list_cron_jobs(self, args, loop) -> str:
        enabled_only = args.get("enabled_only", False)
        result = await loop.run_in_executor(None, list_cron_jobs, enabled_only)
        return str(result)

    async def _handle_remove_cron_job(self, args, loop) -> str:
        job_id = args.get("job_id", 0)
        try:
            job_id = int(job_id)
        except (ValueError, TypeError):
            return "Gecerli bir gorev ID'si girin."
        result = await loop.run_in_executor(None, remove_cron_job, job_id)
        return str(result)

    async def _handle_list_services(self, args, loop) -> str:
        status_filter = args.get("status_filter", "all")
        limit         = args.get("limit", 20)
        result = await loop.run_in_executor(None, list_services, status_filter, limit)
        return str(result)

    async def _handle_control_service(self, args, loop) -> str:
        service_name = args.get("service_name", "")
        action       = args.get("action", "")
        if not service_name or not action:
            return "Servis adi ve aksiyon gerekli."
        result = await loop.run_in_executor(None, control_service, service_name, action)
        return str(result)

    async def _handle_set_volume(self, args, loop) -> str:
        level  = args.get("level", 50)
        action = args.get("action", "set")
        try:
            level = int(level)
        except (ValueError, TypeError):
            return "Gecerli bir ses seviyesi girin."
        if action == "set":
            return _set_volume(level)
        elif action == "up":
            return _change_volume(abs(level))
        elif action == "down":
            return _change_volume(-abs(level))
        elif action == "mute":
            return _set_volume(0)
        elif action == "unmute":
            return _set_volume(50)
        return "Bilinmeyen aksiyon."


# ── Entry point ───────────────────────────────────────────────
def _run_async(app: JarvisLive) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(app.run())
    except Exception:
        traceback.print_exc()
    finally:
        loop.close()


def main():
    if os.environ.get("TERM_PROGRAM") == "vscode":
        print("[JARVIS] VS Code icinden baslatildi.")

    ui = JarvisUI()
    app = JarvisLive(ui)

    # ── asyncio event loop in background thread ──
    # Tkinter is NOT thread-safe; root.mainloop() MUST run in the main thread.
    # The asyncio event loop runs in a daemon thread so it won't block exit.
    async_thread = threading.Thread(
        target=_run_async,
        args=(app,),
        daemon=True,
        name="asyncio-runner",
    )
    async_thread.start()

    try:
        # Tkinter mainloop in MAIN thread — processes UI events, after() callbacks,
        # user input, and canvas redraws. Blocks until the window is closed.
        ui.root.mainloop()
    except KeyboardInterrupt:
        print("\n[JARVIS] Kapatiliyor...")
    except Exception:
        traceback.print_exc()
    finally:
        app.shutdown()
        async_thread.join(timeout=3.0)
        ui.destroy()
        print("[JARVIS] Gorusmek uzere.")


if __name__ == "__main__":
    main()
