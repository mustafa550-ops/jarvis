"""
Weather Skill - Hava durumu sorgulama
"""

from __future__ import annotations
import re
from actions.weather import get_weather_summary
from memory.memory_manager import load_memory

SKILL_ID = "weather-v1"
SKILL_NAME = "Hava Durumu"

TRIGGERS = {
    "get_weather": [
        r"(?:hava|havalar|hava durumu|havadurumu).*?(?:nasıl|nasil|durum|kac|kaç|derece|sıcaklık|sicaklik|rapor|tahmin|ozet|özet|bilgi|nedir|nasılsın)",
        r"(?:bugün|bugun|yarın|yarin|bu hafta|gelecek hafta|haftaya|aksam|akşam|sabah|gece|ogle|ögle|oglen|öglen|öğle|ogleyin|öğleyin).*?(?:hava|yağmur|yagmur|kar|güneş|gunes|rüzgar|ruzgar|bulut|fırtına|firtina|sis|nem|derece|sıcaklık|sicaklik)",
        r"(?:derece|sıcaklık|sicaklik|ısı|isi|sıcak|sicak|soğuk|soguk|serin|ılık|ilik).*?(?:kac|kaç|nedir|nasıl|nasil|dusecek|düşecek|yukselecek|yükselecek|olcak|olacak|oldu|oldu)",
        r"(?:yağmur|yagmur|kar|dolu|fırtına|firtina|rüzgar|ruzgar|bulut|sis|nem|kasırga|kasirga|sel|fırtına).*?(?:var mı|var mi|yağacak|yagacak|olacak|bekleniyor|diniyor|dinmis|dinmiş|geliyor|bastıracak|bastiracak)",
        r"(?:hava).*?(?:rapor|tahmin|ozet|özet|durum|bilgi|durus|durumu|raporu|nasilda|nasılda)",
        r"(?:isinicak|ısınacak|isinacak|soguyacak|soğuyacak|serin|sıcak|sicak|soğuk|soguk|ılık|ilik).*?(?:hava|gorunuyor|görünüyor|olcak|olacak|mi|mu|mı)",
        r"(?:en yüksek|en yuksek|en cok|en çok|max|maksimum|en fazla|en sıcak|en sicak|tepe).*?(?:derece|sıcaklık|sicaklik|hava|değer|deger)",
        r"(?:en düşük|en dusuk|en az|en soğuk|en soguk|min|minimum|en serin).*?(?:derece|sıcaklık|sicaklik|hava|değer|deger)",
        r"(?:bugün|yarın|bugun|yarin|bu aksam|bu akşam|bu gece|oglen|öglen|ogle|ögle).*?(?:kac|kaç|nedir).*?(?:derece|sıcaklık|sicaklik|hava|sıcaklık)",
        r"(?:hava).*?(?:soguk|soğuk|sıcak|sicak|güzel|guzel|kötü|kotu|berbat|kirli|temiz|kapalı|kapali|acik|açık|nasıl|nasil)",
        r"(?:kar|yağmur|yagmur|dolu).*?(?:yağacak|yagacak|var mı|var mi|bekleniyor|geliyor|olacak)",
        r"(?:hava).*?(?:kaç|kac).*?(?:derece|sıcaklık|sicaklik)",
    ],
}


def _get_default_city() -> str:
    """Bellekten varsayılan şehri al."""
    try:
        mem = load_memory()
        city = mem.get("preferences", {}).get("weather_location", {}).get("value", "")
        return city or "Istanbul"
    except Exception:
        return "Istanbul"


def classify_weather_intent(text: str) -> tuple[str, str]:
    """Kullanıcı metninden hava durumu intent'ini çıkarır."""
    text_lower = text.lower().strip()

    # Şehir tespiti
    city = _get_default_city()

    # Türkçe şehir isimleri (basit matching)
    turkish_cities = [
        "istanbul", "ankara", "izmir", "bursa", "antalya", "adana", "konya",
        "gaziantep", "mersin", "diyarbakır", "diyarbakir", "kayseri", "eskisehir", "samsun",
        "denizli", "malatya", "kahramanmaraş", "kahramanmaras", "erzurum", "van", "trabzon",
        "sakarya", "balıkesir", "balikesir", "tekirdağ", "tekirdag", "kocaeli", "hatay", "manisa",
        "new york", "london", "paris", "berlin", "tokyo", "dubai",
    ]

    for c in turkish_cities:
        if c in text_lower:
            city = c.title()
            break

    # Intent kontrolü
    for pattern in TRIGGERS["get_weather"]:
        if re.search(pattern, text_lower):
            return "get_weather", city

    # Fallback keyword
    weather_keywords = ["hava", "derece", "sıcaklık", "sicaklik", "yağmur", "yagmur",
                        "kar", "güneş", "gunes", "bulut", "rüzgar", "ruzgar",
                        "nem", "hava durumu", "tahmin"]
    if any(kw in text_lower for kw in weather_keywords):
        return "get_weather", city

    return "none", ""


def execute_weather_skill(action: str, city: str) -> str:
    """Weather skill çalıştırıcı."""
    if action == "get_weather":
        return get_weather_summary(city)
    return f"Bilinmeyen weather action: {action}"


def route_weather_request(user_text: str) -> str | None:
    """Kullanıcı metnini analiz eder, weather skill'i ile eşleşirse çalıştırır."""
    intent, city = classify_weather_intent(user_text)
    if intent == "none":
        return None

    result = execute_weather_skill(intent, city)
    return result
