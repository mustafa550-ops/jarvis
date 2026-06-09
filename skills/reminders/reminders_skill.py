"""
Reminders Skill - Animsatici (Apple Reminders) yonetimi
"""

from __future__ import annotations
import re
from datetime import datetime, timedelta
from actions.reminders import get_reminders, add_reminder

SKILL_ID = "reminders-v1"
SKILL_NAME = "Animsaticilar"

TRIGGERS = {
    "get_reminders": [
        r"(?:animsatici|anımsatıcı|hatirlatma|hatırlatma|hatirlatici|hatırlatıcı|reminder|reminders).*?(?:neler|ne var|listele|goster|göster|bak|gor|gör|soyle|söyle|yaz)",
        r"(?:bugün|bugun|yarın|yarin|bu hafta|gelecek hafta|haftaya|bu ay).*?(?:animsatici|anımsatıcı|hatirlatma|hatırlatma|yapilacak|yapılacak|gorev|görev|hatirlatma)",
        r"(?:yapacak|yapilacak|yapılacak).*?(?:is|iş|sey|şey|gorev|görev|liste|listem).*?(?:neler|ne var|var mı|var mi|listele|goster|göster)",
        r"(?:hatirlatma|animsatici|anımsatıcı).*?(?:var mı|var mi|listem|listemi|nedir|listele)",
        r"(?:to do|todo|yapilacaklar|yapılacaklar).*?(?:listele|goster|göster|neler|ne var)",
        r"(?:gecmis|geçmiş|gecikmis|gecikmiş|kacirilan|kaçırılan|eskı|eski).*?(?:hatirlatma|animsatici|anımsatıcı|gorev|görev)",
        r"(?:tum|tüm|butun|bütün|hepsi).*?(?:hatirlatma|animsatici|anımsatıcı|gorev|görev)",
    ],
    "add_reminder": [
        r"(?:animsatici|anımsatıcı|hatirlatma|hatırlatma|reminder).*?(?:ekle|kur|olustur|oluştur|ayarla|yap|kaydet)",
        r"(?:beni|bana|bize|ona|bize).*?(?:hatirlat|hatırlat|animsat|anımsat|uyar|hatirla|hatırla)",
        r"(?:unutma).*?(?:diye|ki).*?(?:hatirlat|hatırlat|animsat|anımsat|uyar)",
        r"(?:sabah|aksam|aksam|ogle|ögle|oglen|öglen|gece|oge|öğe|aksamustu|akşamüstü|yarin|yarın|bugün|bugun|haftaya|pazartesi|salı|carsamba|çarşamba|persembe|perşembe|cuma|cumartesi|pazar).*?(?:hatirlat|hatırlat|animsat|anımsat|uyar|hatirla|hatırla)",
        r"(?:hatirlat|hatırlat|animsat|anımsat).*?(?:diye|ki|şunu|sunu|bunu|sunu|bunu)",
        r"(?:ekle|kaydet|kur).*?(?:animsatici|anımsatıcı|hatirlatma|hatırlatma)",
        r"(?:hatirla|hatırla).*?(?:şunu|sunu|bunu|sunu|bunu)",
        r"(?:saat).*?(?:hatirlat|hatırlat|animsat|anımsat|uyar|hatirla|hatırla)",
    ],
}


def _parse_reminder_date(text: str) -> str:
    """Metinden hatirlatma tarihi cikarma."""
    text_lower = text.lower()
    now = datetime.now()

    if "yarın" in text_lower or "yarin" in text_lower:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")

    if "haftaya" in text_lower:
        return (now + timedelta(days=7)).strftime("%Y-%m-%d")

    # Saat tespiti
    time_match = re.search(r'(\d{1,2}):(\d{2})', text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        date_str = now.strftime("%Y-%m-%d")
        return f"{date_str}T{hour:02d}:{minute:02d}"

    return now.strftime("%Y-%m-%d")


def _extract_reminder_title(text: str) -> str:
    """Hatirlatma basligini cikarma."""
    text_lower = text.lower()

    for pattern in [r"(?:animsatici|hatirlatma)\s+(.+?)\s+(?:ekle|kur)",
                    r"(?:beni|bana)\s+(.+?)\s+(?:hatirlat|animsat)",
                    r"(.+?)\s+(?:diye|ki)\s+(?:hatirlat|animsat|unutma)"]:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip().capitalize()

    words = text_lower.split()
    if len(words) > 2:
        return " ".join(words[1:-1]).strip().capitalize()

    return "Yeni Hatirlatma"


def classify_reminders_intent(text: str) -> tuple[str, dict]:
    """Kullanici metninden reminders intent'ini cikarir."""
    text_lower = text.lower().strip()

    # 1. Ekleme
    for pattern in TRIGGERS["add_reminder"]:
        if re.search(pattern, text_lower):
            title = _extract_reminder_title(text)
            due_iso = _parse_reminder_date(text)
            return "add_reminder", {"title": title, "due_iso": due_iso}

    # 2. Listeleme
    for pattern in TRIGGERS["get_reminders"]:
        if re.search(pattern, text_lower):
            query = "today"
            if "yarin" in text_lower or "yarın" in text_lower:
                query = "upcoming"
            elif "gecmis" in text_lower or "gecikmis" in text_lower:
                query = "overdue"
            return "get_reminders", {"query": query}

    # Fallback keyword
    reminder_keywords = ["animsatici", "anımsatıcı", "hatirlatma", "hatırlatma",
                         "reminder", "yapilacak", "yapılacak",
                         "yapacak", "gorev", "görev", "hatirlat", "hatırlat",
                         "animsat", "anımsat", "unutma"]
    if any(kw in text_lower for kw in reminder_keywords):
        return "get_reminders", {"query": "today"}

    return "none", {}


def execute_reminders_skill(action: str, params: dict) -> str:
    """Reminders skill calistirici."""
    if action == "get_reminders":
        return get_reminders(params.get("query", "today"), params.get("limit", 8), params.get("list_name", ""))
    elif action == "add_reminder":
        return add_reminder(
            params.get("title", ""),
            params.get("due_iso", ""),
            params.get("notes", ""),
            params.get("list_name", ""),
            params.get("priority", ""),
            params.get("all_day", False))
    return f"Bilinmeyen reminders action: {action}"


def route_reminders_request(user_text: str) -> str | None:
    """Kullanici metnini analiz eder, reminders skill'i ile eslesirse calistirir."""
    intent, params = classify_reminders_intent(user_text)
    if intent == "none":
        return None

    result = execute_reminders_skill(intent, params)
    return result
