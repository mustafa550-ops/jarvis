"""
Calendar Skill - Takvim yonetimi (Windows yerel takvimi)
"""

from __future__ import annotations
import re
from datetime import datetime, timedelta
from actions.calendar import get_calendar_events, add_calendar_event, delete_calendar_event

SKILL_ID = "calendar-v1"
SKILL_NAME = "Takvim"

TRIGGERS = {
    "get_events": [
        r"(?:takvim|ajanda|program|plani|planı|plan|programim|programım|ajandam).*?(?:neler|ne var|goster|göster|listele|bak|gor|gör|soyle|söyle|goster|göster)",
        r"(?:bugün|bugun|yarın|yarin|bu hafta|gelecek hafta|önümüzdeki|onumuzdeki|haftaya|bu ay|gelecek ay|sonraki hafta|ertesi hafta).*?(?:takvim|ajanda|program|toplanti|randevu|etkinlik|plan|gorusme|görüşme)",
        r"(?:toplanti|randevu|etkinlik|gorusme|görüşme|meeting|appointment).*?(?:var mı|var mi|ne zaman|saat|kacta|kaçta|listele|goster|göster)",
        r"(?:gunluk|günlük|haftalik|haftalık|aylık|aylik|gunun|günün).*?(?:program|ajanda|takvim|plani|planı|plan)",
        r"(?:siradaki|sonraki|gelecek).*?(?:toplanti|randevu|etkinlik|gorusme|görüşme|ne zaman)",
        r"(?:bugün|yarın|bugun|yarin).*?(?:neler|ne).*?(?:var|yapacak|yapilacak|program|plan)",
        r"(?:takvim|ajanda).*?(?:goster|göster|ac|aç|listele)",
    ],
    "add_event": [
        r"(?:takvime|ajandaya|plana|programa).*?(?:ekle|kaydet|yaz|olustur|oluştur|kur|ayarla|isaretle|işaretle)",
        r"(?:toplanti|randevu|etkinlik|gorusme|görüşme|meeting|appointment|plan).*?(?:ekle|kaydet|olustur|oluştur|ayarla|kur|isaretle|işaretle)",
        r"(?:hatırlat|hatirlat|anımsat|animsat|uyar).*?(?:takvime|ajandaya|plana|programa)",
        r"(?:ekle|kaydet).*?(?:takvime|ajandaya|plana|programa)",
        r"(?:yeni).*?(?:etkinlik|toplanti|randevu|gorusme|görüşme).*?(?:ekle|olustur|oluştur|ayarla|kur)",
    ],
    "delete_event": [
        r"(?:takvimden|ajandadan|plandan|programdan).*?(?:sil|kaldir|kaldır|cikar|çıkar|iptal|kaldır|kaldir)",
        r"(?:toplanti|randevu|etkinlik|gorusme|görüşme).*?(?:sil|kaldir|kaldır|iptal|cikar|çıkar|kaldır)",
        r"(?:sil|iptal|kaldir|kaldır).*?(?:takvimden|ajandadan|etkinligi|etkinliği|toplantiyi|toplantıyı|randevuyu)",
        r"(?:sil).*?(?:toplanti|randevu|etkinlik)",
    ],
}


def _parse_date_from_text(text: str) -> str:
    """Metinden tarih cikarma (basit)."""
    text_lower = text.lower()
    now = datetime.now()

    # Bugun
    if "bugün" in text_lower or "bugun" in text_lower:
        return now.strftime("%Y-%m-%d")

    # Yarin
    if "yarin" in text_lower or "yarın" in text_lower:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")

    # Haftaya
    if "haftaya" in text_lower or "gelecek hafta" in text_lower:
        return (now + timedelta(days=7)).strftime("%Y-%m-%d")

    # Saat tespiti (HH:MM)
    time_match = re.search(r'(\d{1,2}):(\d{2})', text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        date_str = now.strftime("%Y-%m-%d")
        return f"{date_str} {hour:02d}:{minute:02d}"

    return now.strftime("%Y-%m-%d")


def _extract_event_title(text: str) -> str:
    """Etkinlik basligini cikarma."""
    text_lower = text.lower()

    for pattern in [r"(?:takvime|ajandaya)\s+(.+?)\s+(?:ekle|kaydet)",
                    r"(?:toplanti|randevu)\s+(.+?)\s+(?:ekle|ayarla)",
                    r"(.+?)\s+(?:ekle|kaydet)\s+(?:takvime|ajandaya)"]:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip().title()

    # Fallback: son kelimeyi al
    words = text_lower.split()
    if len(words) > 1:
        return " ".join(words[1:-1]).strip().title() if len(words) > 2 else words[0].title()

    return "Yeni Etkinlik"


def classify_calendar_intent(text: str) -> tuple[str, dict]:
    """Kullanici metninden takvim intent'ini cikarir."""
    text_lower = text.lower().strip()

    # 1. Ekleme
    for pattern in TRIGGERS["add_event"]:
        if re.search(pattern, text_lower):
            title = _extract_event_title(text)
            start_iso = _parse_date_from_text(text)
            return "add_event", {"title": title, "start_iso": start_iso}

    # 2. Silme
    for pattern in TRIGGERS["delete_event"]:
        if re.search(pattern, text_lower):
            title = _extract_event_title(text)
            return "delete_event", {"title": title}

    # 3. Listeleme
    for pattern in TRIGGERS["get_events"]:
        if re.search(pattern, text_lower):
            query = "today"
            if "yarin" in text_lower or "yarın" in text_lower:
                query = "tomorrow"
            elif "hafta" in text_lower:
                query = "week"
            elif "sonraki" in text_lower or "siradaki" in text_lower:
                query = "next"
            return "get_events", {"query": query}

    # Fallback keyword
    calendar_keywords = ["takvim", "ajanda", "toplanti", "randevu", "etkinlik", "program"]
    if any(kw in text_lower for kw in calendar_keywords):
        return "get_events", {"query": "today"}

    return "none", {}


def execute_calendar_skill(action: str, params: dict) -> str:
    """Calendar skill calistirici."""
    if action == "get_events":
        return get_calendar_events(params.get("query", "today"), params.get("limit", 6))
    elif action == "add_event":
        return add_calendar_event(
            params.get("title", ""),
            params.get("start_iso", ""),
            params.get("end_iso", ""),
            params.get("notes", ""),
            params.get("location", ""),
            params.get("calendar_name", ""),
            params.get("all_day", False))
    elif action == "delete_event":
        return delete_calendar_event(
            params.get("title", ""),
            params.get("start_iso", ""),
            params.get("calendar_name", ""),
            params.get("delete_all_matches", False))
    return f"Bilinmeyen calendar action: {action}"


def route_calendar_request(user_text: str) -> str | None:
    """Kullanici metnini analiz eder, calendar skill'i ile eslesirse calistirir."""
    intent, params = classify_calendar_intent(user_text)
    if intent == "none":
        return None

    result = execute_calendar_skill(intent, params)
    return result
