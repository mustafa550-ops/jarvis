"""
Cross-Platform Audio Player
Windows: winsound, simpleaudio, pygame
Linux: aplay, pulseaudio, paplay
macOS: afplay, say
"""

from __future__ import annotations

import platform
import subprocess
import tempfile
import threading
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import numpy as np


class BaseAudioPlayer(ABC):
    """Abstract base for platform-specific audio playback."""

    @abstractmethod
    def play_wav(self, wav_path: str | Path) -> bool:
        """Play WAV file. Returns True on success."""
        pass

    @abstractmethod
    def play_bytes(self, audio_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bool:
        """Play raw PCM audio bytes."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this player is available on current system."""
        pass


class LinuxAudioPlayer(BaseAudioPlayer):
    """Linux audio playback using aplay or paplay."""

    def is_available(self) -> bool:
        return platform.system() == "Linux" and (
            self._cmd_exists("aplay") or self._cmd_exists("paplay")
        )

    def play_wav(self, wav_path: str | Path) -> bool:
        try:
            import os
            # Sudo delegation for PipeWire/PulseAudio
            if os.geteuid() == 0:
                sudo_user = os.environ.get("SUDO_USER")
                if sudo_user:
                    try:
                        import pwd
                        uid = pwd.getpwnam(sudo_user).pw_uid
                        gid = pwd.getpwnam(sudo_user).pw_gid
                        os.chown(str(wav_path), uid, gid)
                        if self._cmd_exists("pw-play"):
                            subprocess.run(
                                ["sudo", "-u", sudo_user, "env", f"XDG_RUNTIME_DIR=/run/user/{uid}", "pw-play", str(wav_path)],
                                capture_output=True, timeout=60, check=True
                            )
                            return True
                    except Exception as e:
                        print(f"[LinuxAudioPlayer] Sudo delegation failed: {e}")

            # Try pw-play first (PipeWire)
            if self._cmd_exists("pw-play"):
                subprocess.run(
                    ["pw-play", str(wav_path)],
                    capture_output=True, timeout=60, check=True
                )
                return True
            # Try aplay second (ALSA)
            elif self._cmd_exists("aplay"):
                subprocess.run(
                    ["aplay", "-q", str(wav_path)],
                    capture_output=True, timeout=60, check=True
                )
                return True
            # Fallback to paplay (PulseAudio)
            elif self._cmd_exists("paplay"):
                subprocess.run(
                    ["paplay", str(wav_path)],
                    capture_output=True, timeout=60, check=True
                )
                return True
        except Exception as e:
            print(f"[LinuxAudioPlayer] Error: {e}")
        return False

    def play_bytes(self, audio_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bool:
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name
                with wave.open(f, "wb") as wf:
                    wf.setnchannels(channels)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_bytes)

            result = self.play_wav(wav_path)
            Path(wav_path).unlink(missing_ok=True)
            return result
        except Exception as e:
            print(f"[LinuxAudioPlayer] Bytes error: {e}")
            return False

    @staticmethod
    def _cmd_exists(cmd: str) -> bool:
        return subprocess.run(
            ["which", cmd], capture_output=True
        ).returncode == 0


class WindowsAudioPlayer(BaseAudioPlayer):
    """Windows audio playback using winsound or simpleaudio."""

    def is_available(self) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            import winsound
            return True
        except ImportError:
            try:
                import simpleaudio
                return True
            except ImportError:
                return False

    def play_wav(self, wav_path: str | Path) -> bool:
        try:
            import winsound
            winsound.PlaySound(str(wav_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            return True
        except ImportError:
            pass

        try:
            import simpleaudio as sa
            wave_obj = sa.WaveObject.from_wave_file(str(wav_path))
            wave_obj.play()
            return True
        except Exception as e:
            print(f"[WindowsAudioPlayer] Error: {e}")
        return False

    def play_bytes(self, audio_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bool:
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name
                with wave.open(f, "wb") as wf:
                    wf.setnchannels(channels)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_bytes)

            result = self.play_wav(wav_path)
            # Windows async olduğu için hemen silme
            threading.Timer(5.0, lambda: Path(wav_path).unlink(missing_ok=True)).start()
            return result
        except Exception as e:
            print(f"[WindowsAudioPlayer] Bytes error: {e}")
            return False


class MacOSAudioPlayer(BaseAudioPlayer):
    """macOS audio playback using afplay or say."""

    def is_available(self) -> bool:
        return platform.system() == "Darwin" and (
            self._cmd_exists("afplay") or self._cmd_exists("say")
        )

    def play_wav(self, wav_path: str | Path) -> bool:
        try:
            if self._cmd_exists("afplay"):
                subprocess.run(
                    ["afplay", str(wav_path)],
                    capture_output=True, timeout=60, check=True
                )
                return True
        except Exception as e:
            print(f"[MacOSAudioPlayer] Error: {e}")
        return False

    def play_bytes(self, audio_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bool:
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name
                with wave.open(f, "wb") as wf:
                    wf.setnchannels(channels)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_bytes)

            result = self.play_wav(wav_path)
            Path(wav_path).unlink(missing_ok=True)
            return result
        except Exception as e:
            print(f"[MacOSAudioPlayer] Bytes error: {e}")
            return False

    @staticmethod
    def _cmd_exists(cmd: str) -> bool:
        return subprocess.run(
            ["which", cmd], capture_output=True
        ).returncode == 0


class PygameAudioPlayer(BaseAudioPlayer):
    """Fallback using pygame (cross-platform if installed)."""

    def is_available(self) -> bool:
        try:
            import pygame
            return True
        except ImportError:
            return False

    def play_wav(self, wav_path: str | Path) -> bool:
        try:
            import pygame
            pygame.mixer.init()
            sound = pygame.mixer.Sound(str(wav_path))
            sound.play()
            return True
        except Exception as e:
            print(f"[PygameAudioPlayer] Error: {e}")
            return False

    def play_bytes(self, audio_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bool:
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name
                with wave.open(f, "wb") as wf:
                    wf.setnchannels(channels)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_bytes)

            result = self.play_wav(wav_path)
            Path(wav_path).unlink(missing_ok=True)
            return result
        except Exception as e:
            print(f"[PygameAudioPlayer] Bytes error: {e}")
            return False


class AudioPlayer:
    """Universal audio player - auto-selects best backend."""

    _instance: Optional[AudioPlayer] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._players: list[BaseAudioPlayer] = [
            LinuxAudioPlayer(),
            WindowsAudioPlayer(),
            MacOSAudioPlayer(),
            PygameAudioPlayer(),
        ]
        self._active_player: Optional[BaseAudioPlayer] = None
        self._detect_player()

    def _detect_player(self):
        """Auto-detect best available player."""
        for player in self._players:
            if player.is_available():
                self._active_player = player
                print(f"[AudioPlayer] Selected: {player.__class__.__name__}")
                return
        print("[AudioPlayer] ⚠️ No audio player available!")

    def play_wav(self, wav_path: str | Path) -> bool:
        if self._active_player is None:
            print("[AudioPlayer] ❌ No player available")
            return False
        return self._active_player.play_wav(wav_path)

    def play_bytes(self, audio_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bool:
        if self._active_player is None:
            print("[AudioPlayer] ❌ No player available")
            return False
        return self._active_player.play_bytes(audio_bytes, sample_rate, channels)

    def get_player_name(self) -> str:
        if self._active_player:
            return self._active_player.__class__.__name__
        return "None"


# Global instance
_audio_player: Optional[AudioPlayer] = None

def get_audio_player() -> AudioPlayer:
    global _audio_player
    if _audio_player is None:
        _audio_player = AudioPlayer()
    return _audio_player


def play_wav(wav_path: str | Path) -> bool:
    return get_audio_player().play_wav(wav_path)


def play_bytes(audio_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bool:
    return get_audio_player().play_bytes(audio_bytes, sample_rate, channels)
