from __future__ import annotations

import io
import mimetypes
import time
from pathlib import Path

from google import genai
from google.genai import errors, types
from PIL import Image, ImageStat

from app_config import get_app_config_value
from actions.windows_utils import capture_active_window


import traceback
VISION_MODELS = (
    "models/gemini-2.0-flash",
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.5-flash",
)
VISION_MAX_DIMENSION = 1800
VISION_MAX_INLINE_BYTES = 5_500_000


def _screen_permission_message() -> str:
    return (
        "Ekran goruntusu alinamadi. Windows oturumunun kilitli olmadigindan, "
        "pencerenin gorunur oldugundan ve ekran yakalamayi engelleyen bir uygulama "
        "acik olmadigindan emin ol."
    )


def _image_looks_blank(image_path: Path) -> bool:
    try:
        with Image.open(image_path) as img:
            sample = img.convert("RGB")
            stat = ImageStat.Stat(sample)
            means = stat.mean
            extrema = stat.extrema
            max_seen = max(channel[1] for channel in extrema)
            mean_total = sum(means) / max(1, len(means))
            return max_seen <= 8 or mean_total <= 3
    except Exception:
        return False


def _build_image_part(image_path: Path) -> types.Part:
    mime_type, _ = mimetypes.guess_type(str(image_path))
    if not mime_type:
        mime_type = "image/png"

    try:
        with Image.open(image_path) as img:
            work = img.copy()
        if work.mode not in {"RGB", "L"}:
            work = work.convert("RGB")
        if max(work.size) > VISION_MAX_DIMENSION:
            work.thumbnail((VISION_MAX_DIMENSION, VISION_MAX_DIMENSION), Image.Resampling.LANCZOS)

        png_buffer = io.BytesIO()
        work.save(png_buffer, format="PNG", optimize=True)
        png_bytes = png_buffer.getvalue()
        if len(png_bytes) <= VISION_MAX_INLINE_BYTES:
            return types.Part.from_bytes(data=png_bytes, mime_type="image/png")

        jpg_buffer = io.BytesIO()
        work.convert("RGB").save(jpg_buffer, format="JPEG", quality=88, optimize=True)
        return types.Part.from_bytes(data=jpg_buffer.getvalue(), mime_type="image/jpeg")
    except Exception:
        return types.Part.from_bytes(data=image_path.read_bytes(), mime_type=mime_type)


def _vision_prompt(query: str, owner_name: str, window_title: str) -> str:
    label = window_title or owner_name or "aktif pencere"
    user_query = (query or "Ekranda ne var?").strip()
    return (
        "Sen Windows uzerinde JARVIS icin ekran analizi yapan bir goruntu yorumlayicisisin.\n"
        "Asagidaki ekran goruntusu aktif pencereye ait.\n"
        f"Pencere baglami: {label}\n\n"
        "Gorunen metinleri, hata mesajlarini, butonlari ve arayuz durumunu oku. "
        "Kullanici sorusunu goruntuye gore dogrudan cevapla. Emin olmadigin kisimlarda bunu soyle.\n\n"
        f"Kullanici sorusu: {user_query}\n\n"
        "Yaniti Turkce ver."
    )


def _extract_response_text(response) -> str:
    text = str(getattr(response, "text", "") or "").strip()
    if text:
        return text
    candidates = getattr(response, "candidates", None) or []
    chunks: list[str] = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            part_text = str(getattr(part, "text", "") or "").strip()
            if part_text:
                chunks.append(part_text)
    return "\n".join(chunks).strip()


def _is_transient_vision_error(exc: Exception) -> bool:
    if isinstance(exc, (errors.ServerError, TimeoutError)):
        return True
    message = str(exc or "").lower()
    return any(marker in message for marker in (
        "503", "429", "deadline", "timed out", "timeout", "unavailable",
        "temporarily unavailable", "service unavailable", "internal error",
        "busy", "overloaded", "resource exhausted", "try again later",
    ))


def _friendly_vision_error(exc: Exception) -> str:
    message = str(exc or "").lower()
    if any(marker in message for marker in ("quota", "rate limit", "too many requests", "billing")):
        return "Gemini vision istegi kota veya hiz limitine takildi."
    if _is_transient_vision_error(exc):
        return "Gemini vision servisi su anda yogun veya gecici olarak ulasilamiyor."
    return f"Gemini vision istegi basarisiz oldu: {exc}"


def _analyze_with_gemini(query: str, image_path: Path, owner_name: str, window_title: str) -> str:
    api_key = str(get_app_config_value("gemini_api_key", "") or "").strip()
    if not api_key:
        return "Gemini API anahtari eksik oldugu icin ekran analizi yapilamadi."

    prompt = _vision_prompt(query, owner_name, window_title)
    client = genai.Client(api_key=api_key)
    image_part = _build_image_part(image_path)
    last_error: Exception | None = None

    for model_name in VISION_MODELS:
        for attempt, delay in enumerate((0.9, 1.8, 3.0), start=1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[types.Part.from_text(text=prompt), image_part],
                    config=types.GenerateContentConfig(temperature=0.2),
                )
                merged = _extract_response_text(response)
                if merged:
                    return merged
                raise RuntimeError("Gemini gecerli bir ekran analizi metni dondurmedi.")
            except Exception as exc:
                last_error = exc
                if attempt < 3 and _is_transient_vision_error(exc):
                    time.sleep(delay)
                    continue
                if _is_transient_vision_error(exc):
                    break
                raise RuntimeError(_friendly_vision_error(exc)) from exc

    assert last_error is not None
    raise RuntimeError(_friendly_vision_error(last_error))


def analyze_screen(query: str, target: str = "active_window") -> str:
    target = (target or "active_window").strip().lower()
    if target != "active_window":
        return "Screen Vision v1 yalnizca aktif pencere analizini destekliyor."

    ok, detail, payload = capture_active_window()
    if not ok:
        return f"Ekran goruntusu alinamadi: {detail}. {_screen_permission_message()}"

    image_path = Path(str(payload.get("image_path", "")))
    owner_name = str(payload.get("owner_name", "") or "").strip()
    window_title = str(payload.get("window_title", "") or "").strip()

    try:
        if not image_path.exists() or image_path.stat().st_size <= 0:
            return "Ekran goruntusu dosyasi bos geldi. " + _screen_permission_message()
        if _image_looks_blank(image_path):
            return "Ekran goruntusu siyah veya bos gorunuyor. " + _screen_permission_message()

        try:
            analysis = _analyze_with_gemini(query, image_path, owner_name, window_title)
        except Exception as exc:
            prefix = f"{owner_name} / {window_title}".strip(" /")
            if prefix:
                return f"Ekran goruntusu alindi ({prefix}) ama analiz tamamlanamadi: {exc}"
            return f"Ekran goruntusu alindi ama analiz tamamlanamadi: {exc}"

        title = " / ".join(part for part in (owner_name, window_title) if part).strip()
        if title:
            return f"[Aktif pencere: {title}]\n{analysis}"
        return analysis
    finally:
        try:
            if image_path.exists():
                image_path.unlink()
        except Exception:
            traceback.print_exc()
