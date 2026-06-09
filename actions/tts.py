"""
actions/tts.py
JARVIS TTS arayüzü - tüm sesli yanıtlar buradan geçer.
"""

from __future__ import annotations

from typing import Optional

from core.audio_system.tts_engine import get_tts_engine, speak_text

__all__ = ["speak_text", "get_tts_engine"]
