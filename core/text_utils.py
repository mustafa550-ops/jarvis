# ── Text Utilities ───────────────────────────────────────────
# Shared text processing functions used by main.py, gemini_provider, etc.
# Extracted to avoid circular imports between modules.
# ──────────────────────────────────────────────────────────────

from __future__ import annotations

import re
import unicodedata


def fix_turkish_syllable_split(text: str) -> str:
    """faster-whisper'in Türkçe eklemeli kelimeleri yanlış bölmesini düzeltir.

    - Tek harfli parçaları sonraki kelimeye yapıştır: 'İ stanbul' → 'İstanbul'
    - Ardışık kısa parçaları max 8 karaktere kadar birleştir, sonra ayrı kelime yap
    - Buffer'daki parçaları asla normal kelimeye yapıştırma (kelime sınırı koruma)
    """
    words = text.split()
    if len(words) <= 1:
        return text
    TURKISH_STOP = {
        "ve", "bir", "ile", "için", "gibi", "ama", "veya",
        "ki", "de", "da", "mi", "mı", "mu", "mü", "ise", "çünkü",
        "üzere", "kadar", "diye", "karşı", "sonra", "önce",
        "bu", "şu", "o", "ben", "sen", "biz", "siz", "onlar",
    }
    result: list[str] = []
    buf: list[str] = []
    for w in words:
        is_short = len(w) <= 3 and w.isalpha() and w.lower() not in TURKISH_STOP
        if is_short:
            if buf and len("".join(buf)) + len(w) > 8:
                result.append("".join(buf))
                buf = []
            buf.append(w)
        else:
            if buf:
                if len(buf) == 1 and len(buf[0]) == 1:
                    result.append(buf[0] + w)
                else:
                    result.append("".join(buf))
                    result.append(w)
                buf = []
            else:
                result.append(w)
    if buf:
        result.append("".join(buf))
    return " ".join(result)


def clean_transcript_text(text: str) -> tuple[str, bool]:
    """Normalize and clean transcription text.

    Returns (cleaned_text, had_noise).
    """
    raw = unicodedata.normalize("NFC", str(text or ""))
    had_noise = False
    import re as _re
    control_re = _re.compile(
        r"\[[\w\s,.-]+\]|"
        r"\([\w\s,.-]+\)|"
        r"<[\w\s=.,/\"'-]+>|"
        r"\{[\w\s,.-]+\}", _re.IGNORECASE
    )
    if control_re.search(raw):
        had_noise = True
        raw = control_re.sub(" ", raw)
    cleaned: list[str] = []
    for ch in raw:
        if ch in "\n\r\t" or ord(ch) >= 32:
            cleaned.append(ch)
        else:
            had_noise = True
    normalized = " ".join("".join(cleaned).split())
    normalized = fix_turkish_syllable_split(normalized)
    return normalized.strip(), had_noise
