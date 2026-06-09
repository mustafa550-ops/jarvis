"""
Multimodal Motor — görüntü işleme ve çoklu mod algılama.
Ekran görüntüsü + kamera + dosya analizi.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import traceback

__all__ = ["MultimodalEngine", "create_multimodal_engine"]

BASE_DIR = Path(__file__).resolve().parent.parent


class MultimodalEngine:
    """
    Multimodal algılama motoru.

    Mevcut yetenekleri birleştirir:
    - actions.screen_vision: Ekran görüntüsü analizi
    - vision.camera_capture: Kamera ile fotoğraf
    - Dosya görüntüleme (resim/pdf)
    """

    def __init__(self):
        self._screen_vision = None
        self._camera = None

    # ── Screen analysis ──────────────────────────────────────────────────────

    def analyze_screen(self, query: Optional[str] = None) -> Optional[str]:
        """
        Capture and analyze screen content.

        Args:
            query: Optional question about the screen content

        Returns:
            Analysis text or None on failure.
        """
        try:
            from actions.screen_vision import analyze_screen
            return analyze_screen(query=query or "Ekranda ne var?")
        except ImportError:
            print("[Multimodal] screen_vision yuklenemedi")
            return None
        except Exception:
            traceback.print_exc()
            return None

    # ── Camera capture ───────────────────────────────────────────────────────

    def capture_photo(self) -> Optional[bytes]:
        """
        Take a photo with camera.

        Returns:
            JPEG bytes or None.
        """
        try:
            if self._camera is None:
                from vision.camera_capture import CameraCapture
                self._camera = CameraCapture()
            return self._camera.capture()
        except Exception:
            traceback.print_exc()
            return None

    def analyze_camera(self, query: Optional[str] = None) -> Optional[str]:
        """
        Take photo and analyze with Gemini/Ollama vision.

        Args:
            query: Optional question about the image

        Returns:
            Analysis text or None.
        """
        try:
            img_bytes = self.capture_photo()
            if img_bytes is None:
                return "Kamera goruntusu alinamadi."

            # Try Gemini vision first
            try:
                from google import genai
                from app_config import get_app_config_value
                from google.genai import types

                api_key = get_app_config_value("gemini_api_key", "")
                if api_key:
                    client = genai.Client(api_key=api_key)
                    import PIL.Image
                    import io
                    img = PIL.Image.open(io.BytesIO(img_bytes))
                    prompt = query or "Bu resimde ne goruyorsun? Turkce cevap ver."
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=[prompt, img],
                    )
                    if response and response.text:
                        return response.text
            except Exception:
                traceback.print_exc()

            return "Goruntu alindi fakat analiz edilemedi (Gemini API anahtari gerekli)."
        except Exception:
            traceback.print_exc()
            return None

    # ── Image file analysis ─────────────────────────────────────────────────

    def analyze_image_file(self, file_path: str, query: Optional[str] = None) -> Optional[str]:
        """
        Analyze an image file.

        Args:
            file_path: Path to image file
            query: Optional question about the image

        Returns:
            Analysis text or None.
        """
        path = Path(file_path)
        if not path.exists():
            return f"Dosya bulunamadi: {file_path}"

        try:
            from google import genai
            from app_config import get_app_config_value

            api_key = get_app_config_value("gemini_api_key", "")
            if not api_key:
                return "Gemini API anahtari gerekli."

            client = genai.Client(api_key=api_key)

            import PIL.Image
            img = PIL.Image.open(path)
            prompt = query or "Bu resimde ne goruyorsun? Turkce cevap ver."
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[prompt, img],
            )
            if response and response.text:
                return response.text
            return "Analiz sonucu alinamadi."
        except ImportError:
            return "PIL veya genai kutuphanesi gerekli."
        except Exception:
            traceback.print_exc()
            return None

    # ── Info ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        return {
            "screen_vision_available": self._check_screen_vision(),
            "camera_available": self._camera is not None,
        }

    def _check_screen_vision(self) -> bool:
        try:
            from actions.screen_vision import analyze_screen
            return True
        except Exception:
            return False


# ── Factory ──────────────────────────────────────────────────────────────────


def create_multimodal_engine() -> MultimodalEngine:
    """Create a MultimodalEngine."""
    return MultimodalEngine()
