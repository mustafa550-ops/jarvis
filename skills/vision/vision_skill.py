"""
Vision Skill - Ekran goruntusu analizi
"""

from __future__ import annotations
import re
from actions.screen_vision import analyze_screen

SKILL_ID = "vision-v1"
SKILL_NAME = "Ekran Analizi"

TRIGGERS = {
    "analyze_screen": [
        r"(?:ekran|ekranda|ekranı|ekrani|goruntu|görüntü|pencere|window|windows).*?(?:ne var|oku|gor|gör|analiz|yorumla|incele|anlat|soyle|söyle|goster|göster)",
        r"(?:bu|şu|su|o|bunu|şunu|sunu|buna|suna|şuna).*?(?:hata|mesaj|uyarı|uyari|pencere|diyalog|ekran|popup|bildirim|uygulama|program).*?(?:oku|ne|analiz|yorumla|incele|cevir|çevir|okur musun|okurmusun|icinde|içinde)",
        r"(?:gordugun|gördüğün|gordugum|gördüğüm|görüyorsun|goruyorsun|görüyor musun|goruyor musun|görüyor|goruyor).*?(?:ne|oku|analiz|yorumla|anlat|soyle|söyle|görüyor musun|goruyor musun)",
        r"(?:aktif|acik|açık|su anki|şu anki|mevcut|açık olan|acik olan|öndeki|ondeki).*?(?:pencere|ekran|uygulama|program|sayfa|tab|sekme).*?(?:ne|oku|analiz|incele|yorumla|goster|göster)",
        r"(?:ekran).*?(?:goruntusu|görüntüsü|görüntü|goruntu|shot|screenshot|foto|capture|görüntüsünü|goruntusunu|resim|resmini).*?(?:al|cek|çek|oku|analiz|incele|yorumla|at|yolla|gonder|gönder|cek|çek)",
        r"(?:ne).*?(?:goruyorsun|görüyorsun|gosteriyor|gösteriyor|var|oluyor|olmus|olmuş).*?(?:ekran|pencere|sayfa|uygulama|program|goruntu|görüntü)",
        r"(?:ekran).*?(?:analiz|incele|oku|yorumla|anlat|betimle|tarif).*?(?:et|yap|iver|iverir|lütfen|lutfen)",
        r"(?:hata|error|bug|sorun|problem|arıza|ariza).*?(?:mesajı|mesaji|kodu|penceresi|ekranı|ekrani|bildirimi).*?(?:oku|ne|analiz|yorumla|incele|goster|göster)",
        r"(?:görsel|gorsel|resim|fotograf|fotoğraf).*?(?:analiz|incele|oku|yorumla|anlat)",
        r"(?:ekranda).*?(?:ne|ne var|ne goruyorsun|ne görüyorsun|neler oluyor)",
        r"(?:bunu).*?(?:analiz|incele|oku|yorumla|anlat|goster|göster)",
    ],
}


def classify_vision_intent(text: str) -> tuple[str, str]:
    """Kullanici metninden vision intent'ini cikarir."""
    text_lower = text.lower().strip()

    # Query cikarma (kullanici ne sordu)
    query = "Ekranda ne var?"

    for pattern in TRIGGERS["analyze_screen"]:
        match = re.search(pattern, text_lower)
        if match:
            # Ozel query var mi?
            if "hata" in text_lower:
                query = "Bu hatayi oku ve cozum oner."
            elif "buton" in text_lower or "tus" in text_lower:
                query = "Ekrandaki butonlari ve secenekleri listele."
            elif "metin" in text_lower or "yazi" in text_lower:
                query = "Ekrandaki metinleri oku."
            elif "renk" in text_lower or "tasarim" in text_lower:
                query = "Ekran tasarimini ve renkleri analiz et."
            return "analyze_screen", query

    # Fallback keyword
    vision_keywords = ["ekran", "görüntü", "goruntu", "pencere", "hata", "mesaj", "diyalog",
                       "gördüğün", "gordugun", "screenshot", "analiz et", "oku"]
    if any(kw in text_lower for kw in vision_keywords):
        return "analyze_screen", query

    return "none", ""


def execute_vision_skill(action: str, query: str) -> str:
    """Vision skill calistirici."""
    if action == "analyze_screen":
        return analyze_screen(query, "active_window")
    return f"Bilinmeyen vision action: {action}"


def route_vision_request(user_text: str) -> str | None:
    """Kullanici metnini analiz eder, vision skill'i ile eslesirse calistirir."""
    intent, query = classify_vision_intent(user_text)
    if intent == "none":
        return None

    result = execute_vision_skill(intent, query)
    return result
