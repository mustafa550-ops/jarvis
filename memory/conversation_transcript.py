"""
Conversation Transcript — gerçek zamanlı konuşma transkripti.
Son N konuşmayı hafızada tutar, isteğe bağlı ses kaydı referanslarını saklar.
"""

from __future__ import annotations

import json
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

import traceback

__all__ = ["ConversationTranscript", "create_transcript"]

BASE_DIR = Path(__file__).resolve().parent.parent
_TRANSCRIPT_DIR = BASE_DIR / "memory" / "transcripts"


class ConversationTranscript:
    """
    Gerçek zamanlı konuşma transkripti.

    Son N konuşma turunu deque'te tutar, periyodik olarak diske kaydeder.
    prompt.txt'e eklenmek üzere formatlı çıktı üretir.
    """

    def __init__(
        self,
        max_turns: int = 50,
        auto_save: bool = True,
        transcript_dir: Optional[Path] = None,
    ):
        self.max_turns = max_turns
        self.auto_save = auto_save
        self.transcript_dir = transcript_dir or _TRANSCRIPT_DIR

        self._turns: deque = deque(maxlen=max_turns)
        self._session_id: str = datetime.now().strftime("transcript_%Y%m%d_%H%M%S")
        self._turn_count: int = 0

        if auto_save:
            self.transcript_dir.mkdir(parents=True, exist_ok=True)

    # ── Logging ──────────────────────────────────────────────────────────────

    def add_turn(
        self,
        user_text: str,
        jarvis_text: str,
        user_emotion: str = "neutral",
        jarvis_emotion: str = "neutral",
        metadata: Optional[dict] = None,
    ):
        """Add a conversation turn."""
        turn = {
            "turn_id": self._turn_count,
            "timestamp": time.time(),
            "user": {
                "text": user_text,
                "emotion": user_emotion,
            },
            "jarvis": {
                "text": jarvis_text,
                "emotion": jarvis_emotion,
            },
            "metadata": metadata or {},
        }
        self._turns.append(turn)
        self._turn_count += 1

        if self.auto_save and self._turn_count % 5 == 0:
            self.save()

    # ── Query ────────────────────────────────────────────────────────────────

    def get_recent(self, n: int = 5) -> list[dict]:
        """Get last N turns."""
        return list(self._turns)[-n:]

    def get_formatted(self, n: int = 5) -> str:
        """
        Get recent turns as formatted string for prompt injection.

        Returns:
            Örnek:
            [SON KONUSMALAR]
            Kullanici: merhaba
            JARVIS: merhaba, nasil yardimci olabilirim?
        """
        recent = self.get_recent(n)
        if not recent:
            return ""

        lines = ["[SON KONUSMALAR]"]
        for turn in recent:
            user_text = turn.get("user", {}).get("text", "").strip()
            jarvis_text = turn.get("jarvis", {}).get("text", "").strip()
            if user_text:
                lines.append(f"  Kullanici: {user_text}")
            if jarvis_text:
                lines.append(f"  JARVIS: {jarvis_text}")
        return "\n".join(lines)

    def search(self, query: str) -> list[dict]:
        """Search through transcript for matching text."""
        query_lower = query.lower()
        results = []
        for turn in self._turns:
            user_text = turn.get("user", {}).get("text", "").lower()
            jarvis_text = turn.get("jarvis", {}).get("text", "").lower()
            if query_lower in user_text or query_lower in jarvis_text:
                results.append(turn)
        return results

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self) -> Optional[str]:
        """Save transcript to disk."""
        if not self._turns:
            return None
        file_path = self.transcript_dir / f"{self._session_id}.json"
        data = {
            "session_id": self._session_id,
            "updated_at": time.time(),
            "total_turns": self._turn_count,
            "max_turns": self.max_turns,
            "conversation": list(self._turns),
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return str(file_path)
        except Exception:
            traceback.print_exc()
            return None

    def load(self, session_id: str) -> bool:
        """Load a saved transcript."""
        file_path = self.transcript_dir / f"{session_id}.json"
        if not file_path.exists():
            return False
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._turns = deque(data.get("conversation", []), maxlen=self.max_turns)
            self._turn_count = data.get("total_turns", len(self._turns))
            self._session_id = data.get("session_id", session_id)
            return True
        except Exception:
            traceback.print_exc()
            return False

    # ── State ────────────────────────────────────────────────────────────────

    def clear(self):
        self._turns.clear()
        self._turn_count = 0
        self._session_id = datetime.now().strftime("transcript_%Y%m%d_%H%M%S")

    def new_session(self):
        """Start a new transcript session (saves old one first)."""
        if self.auto_save:
            self.save()
        self.clear()

    @property
    def turn_count(self) -> int:
        return self._turn_count

    def get_stats(self) -> dict:
        return {
            "session_id": self._session_id,
            "total_turns": self._turn_count,
            "current_turns": len(self._turns),
            "max_turns": self.max_turns,
            "auto_save": self.auto_save,
        }


# ── Factory ──────────────────────────────────────────────────────────────────


def create_transcript(max_turns: int = 50, auto_save: bool = True) -> ConversationTranscript:
    """Create a ConversationTranscript with sensible defaults."""
    return ConversationTranscript(max_turns=max_turns, auto_save=auto_save)
