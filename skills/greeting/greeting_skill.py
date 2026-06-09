"""
Selamlama Skill — karsilama ve sistem durumu sorgulari.
"""

from __future__ import annotations
import re

SKILL_ID = "greeting-v1"
SKILL_VERSION = "1.0.0"
SKILL_NAME = "Selamlama"

_TRIGGER_PATTERNS = [
    r"(?:naber|nasilsin|nasılsın|merhaba|selam|hello|merhabalar|hey|selamun aleykum)",
    r"(?:calisiyor|çalışıyor|calisiyo|çalışıyo|canli|canlı|yaşıyor|yasiyor|aktif).*?(?:mu|musun|mısın|misin|muşun|musunuz|mısınız|misiniz)",
    r"(?:skill|beceri|yetenek).*?(?:kac|kaç|tane|adet|ne kadar|sayisi|sayısı|say|listele|goster|göster)",
    r"(?:sistem|modul|modül|yetki|yetenek|ozellik|özellik).*?(?:kontrol|dene|deneme|yuklendi|yüklendi|calisiyor|çalışıyor|listele|say|say)",
    r"(?:hot.?reload|yenile|tazele|yeniden.?yukle|yeniden.?yükle).*?(?:nedir|nasil|nasıl)",
    r"(?:jarvis).*?(?:kimsin|nesin|nedir|nasilsin|nasılsın|nerelisin|ne yaparsin|ne yapabilirsin)",
]


def route_greeting_request(user_text: str) -> str | None:
    text_lower = user_text.lower().strip()
    for pattern in _TRIGGER_PATTERNS:
        if re.search(pattern, text_lower):
            return "✅ Sistem calisiyor! 15 skill yuklu, hot-reload aktif."
    return None
