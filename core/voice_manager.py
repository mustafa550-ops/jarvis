"""
Voice Manager — çoklu ses tonu yönetimi.
Farklı durumlar için farklı ses profilleri kullanır.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

import traceback

__all__ = ["VoiceManager", "create_voice_manager"]

BASE_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "voices.yaml"


def _load_voices_config(config_path: Optional[Path] = None) -> dict:
    """Load voices config from YAML."""
    config_path = config_path or _DEFAULT_CONFIG_PATH
    defaults: dict = {
        "voices": {},
        "default_voice": "fahrettin",
        "default_emotion": "neutral",
        "auto_voice_selection": True,
        "context_voice_mapping": {},
    }
    if not config_path.exists():
        return defaults
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        if isinstance(loaded, dict):
            for k, v in loaded.items():
                if v is not None:
                    defaults[k] = v
    except Exception as e:
        print(f"[VoiceManager] Config load error: {e}")
        traceback.print_exc()
    return defaults


class VoiceManager:
    """
    Çoklu ses tonu yöneticisi.

    Farklı konuşma bağlamlarına göre otomatik ses seçimi yapar.
    Emotion TTS ile entegre çalışır.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config = _load_voices_config(config_path)
        self._voices: dict = self.config.get("voices", {})
        self._mapping: dict = self.config.get("context_voice_mapping", {})
        self._auto_select: bool = self.config.get("auto_voice_selection", True)

        self._current_voice_id: str = self.config.get("default_voice", "fahrettin")
        self._current_emotion: str = self.config.get("default_emotion", "neutral")

        self._emotion_tts = None  # Lazy import

    # ── Voice selection ──────────────────────────────────────────────────────

    def get_voice(self, context: Optional[str] = None) -> str:
        """
        Get voice ID for given context.

        Args:
            context: Konuşma bağlamı (greeting, information, warning, error, casual)

        Returns:
            Ses ID'si (ör: piper-fahrettin, edge-ahmet)
        """
        if context and self._auto_select:
            mapped = self._mapping.get(context)
            if mapped and mapped in self._voices:
                voice_id = self._voices[mapped].get("id", "")
                if voice_id:
                    return voice_id

        # Fallback: current voice
        voice_data = self._voices.get(self._current_voice_id, {})
        return voice_data.get("id", "piper-fahrettin")

    def set_voice(self, voice_name: str) -> bool:
        """Switch to a different voice by its config name."""
        if voice_name in self._voices:
            self._current_voice_id = voice_name
            # Sync with emotion TTS if loaded
            if self._emotion_tts:
                voice_data = self._voices[voice_name]
                self._emotion_tts.set_voice(voice_data.get("id", "piper-fahrettin"))
            return True
        return False

    def set_emotion(self, emotion: str):
        """Set current emotion."""
        self._current_emotion = emotion
        if self._emotion_tts:
            self._emotion_tts.set_emotion(emotion)

    def get_emotion(self) -> str:
        return self._current_emotion

    # ── Speaking ─────────────────────────────────────────────────────────────

    def speak(self, text: str, context: Optional[str] = None, emotion: Optional[str] = None):
        """Speak with context-aware voice and emotion."""
        try:
            if self._emotion_tts is None:
                from core.emotion_tts import EmotionTTS
                self._emotion_tts = EmotionTTS(
                    default_voice=self.get_voice(),
                    default_emotion=emotion or self._current_emotion,
                )

            voice_id = self.get_voice(context)
            self._emotion_tts.set_voice(voice_id)
            self._emotion_tts.speak(text, emotion=emotion or self._current_emotion)
        except Exception:
            traceback.print_exc()

    # ── Info ──────────────────────────────────────────────────────────────────

    def list_voices(self) -> list[dict]:
        """List available voices with metadata."""
        result = []
        for name, data in self._voices.items():
            result.append({
                "name": name,
                "id": data.get("id", ""),
                "engine": data.get("engine", ""),
                "gender": data.get("gender", "unspecified"),
                "description": data.get("description", ""),
            })
        return result

    def get_current_voice_info(self) -> Optional[dict]:
        voice_data = self._voices.get(self._current_voice_id)
        if voice_data:
            return {
                "name": self._current_voice_id,
                "id": voice_data.get("id", ""),
                "engine": voice_data.get("engine", ""),
                "gender": voice_data.get("gender", "unspecified"),
                "emotion": self._current_emotion,
            }
        return None

    def get_stats(self) -> dict:
        return {
            "current_voice": self._current_voice_id,
            "current_emotion": self._current_emotion,
            "auto_select": self._auto_select,
            "available_voices": len(self._voices),
        }


# ── Factory ──────────────────────────────────────────────────────────────────


def create_voice_manager(config_path: Optional[Path] = None) -> VoiceManager:
    """Create a VoiceManager with sensible defaults."""
    return VoiceManager(config_path=config_path)
