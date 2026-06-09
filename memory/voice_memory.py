"""
Voice Memory — sesli konuşma geçmişi yönetimi.
Kullanıcıyla yapılan konuşmaların ses kayıtlarını ve transkriptlerini yönetir.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import traceback

__all__ = ["VoiceMemory", "create_voice_memory"]

BASE_DIR = Path(__file__).resolve().parent.parent
_MEMORY_DIR = BASE_DIR / "memory" / "conversations"


class VoiceMemory:
    """
    Sesli konuşma geçmişi yöneticisi.

    Her konuşma oturumunu JSON formatında kaydeder:
    - Zaman damgası
    - Kullanıcı transkripti
    - JARVIS yanıtı
    - Duygu durumu
    - Ses dosyası referansı (varsa)
    """

    def __init__(self, memory_dir: Optional[Path | str] = None):
        self.memory_dir = Path(memory_dir) if memory_dir else _MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._current_session: Optional[str] = None
        self._current_log: list[dict] = []

    # ── Session management ───────────────────────────────────────────────────

    def start_session(self) -> str:
        """Start a new conversation session."""
        session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        self._current_session = session_id
        self._current_log = []
        print(f"[VoiceMemory] Oturum baslatildi: {session_id}")
        return session_id

    def end_session(self) -> Optional[str]:
        """End current session and save to disk."""
        if not self._current_session:
            return None
        result = self.save()
        print(f"[VoiceMemory] Oturum sonlandirildi: {self._current_session}")
        self._current_session = None
        self._current_log = []
        return result

    @property
    def is_active(self) -> bool:
        return self._current_session is not None

    # ── Logging ──────────────────────────────────────────────────────────────

    def log_user(self, text: str, emotion: str = "neutral", audio_ref: Optional[str] = None):
        """Log user utterance."""
        if not self._current_session:
            self.start_session()
        self._current_log.append({
            "role": "user",
            "text": text,
            "emotion": emotion,
            "audio_ref": audio_ref,
            "timestamp": time.time(),
        })

    def log_jarvis(self, text: str, emotion: str = "neutral", audio_ref: Optional[str] = None):
        """Log JARVIS response."""
        if not self._current_session:
            self.start_session()
        self._current_log.append({
            "role": "jarvis",
            "text": text,
            "emotion": emotion,
            "audio_ref": audio_ref,
            "timestamp": time.time(),
        })

    # ── Save / Load ──────────────────────────────────────────────────────────

    def save(self) -> Optional[str]:
        """Save current session to disk. Returns file path or None."""
        if not self._current_session or not self._current_log:
            return None
        file_path = self.memory_dir / f"{self._current_session}.json"
        data = {
            "session_id": self._current_session,
            "created_at": self._current_log[0].get("timestamp", time.time()) if self._current_log else time.time(),
            "updated_at": time.time(),
            "turn_count": len(self._current_log),
            "conversation": self._current_log,
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return str(file_path)
        except Exception:
            traceback.print_exc()
            return None

    def load_session(self, session_id: str) -> Optional[list[dict]]:
        """Load a specific session by ID."""
        file_path = self.memory_dir / f"{session_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("conversation", [])
        except Exception:
            traceback.print_exc()
            return None

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """List recent sessions with metadata."""
        if not self.memory_dir.exists():
            return []
        sessions = []
        try:
            for f in sorted(self.memory_dir.glob("session_*.json"), reverse=True)[:limit]:
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    sessions.append({
                        "session_id": data.get("session_id", f.stem),
                        "created_at": data.get("created_at", 0),
                        "turn_count": data.get("turn_count", 0),
                        "file_size": f.stat().st_size,
                    })
                except Exception:
                    continue
        except Exception:
            traceback.print_exc()
        return sessions

    def get_recent_context(self, n_turns: int = 5) -> str:
        """Get recent conversation context as formatted string."""
        if not self._current_log:
            sessions = self.list_sessions(limit=1)
            if sessions:
                session_id = sessions[0]["session_id"]
                log = self.load_session(session_id)
                if log:
                    turns = log[-n_turns:]
                else:
                    return ""
            else:
                return ""
        else:
            turns = self._current_log[-n_turns:]

        lines = ["[SON KONUSMALAR]"]
        for entry in turns:
            prefix = "Kullanici" if entry.get("role") == "user" else "JARVIS"
            text = entry.get("text", "").strip()
            if text:
                lines.append(f"  {prefix}: {text}")
        return "\n".join(lines)

    def clear(self):
        """Clear current session without saving."""
        self._current_session = None
        self._current_log = []

    def get_stats(self) -> dict:
        return {
            "active": self.is_active,
            "current_session": self._current_session,
            "current_turns": len(self._current_log),
            "total_sessions": len(list(self.memory_dir.glob("session_*.json"))),
            "storage_dir": str(self.memory_dir),
        }


# ── Factory ──────────────────────────────────────────────────────────────────


def create_voice_memory(memory_dir: Optional[Path] = None) -> VoiceMemory:
    """Create a VoiceMemory with sensible defaults."""
    return VoiceMemory(memory_dir=memory_dir)
