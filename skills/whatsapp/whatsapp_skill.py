"""
WhatsApp Skill - Mesaj gonderme ve kisi kaydetme
"""

from __future__ import annotations
import re
from actions.whatsapp import send_whatsapp_message, save_whatsapp_contact

SKILL_ID = "whatsapp-v1"
SKILL_NAME = "WhatsApp"

TRIGGERS = {
    "send_message": [
        r"(?:whatsapp|wp|whatsapptan|wpten|whatsapp'a|whatsappa|wa|whatsaptan|wptan).*?(?:gonder|gönder|yolla|at|yaz|mesaj|ilet|ileti|bildirim|bildir|gönder|gonder)",
        r"(?:mesaj|ileti|yazi|yazı|sms|mektup|not).*?(?:gonder|gönder|yolla|at|yaz|ilet|bildir|gönder).*?(?:whatsapp|wp)",
        r"(?:anne|baba|annem|babam|ahmet|mehmet|ece|ali|veli|ayse|fatma|can|emre|selin|hakan|derya|zeki|pelin|berk|mert|elif|zeynep|defne|melis|tuna|arda|cem|ipek|eda|okan|nur|deniz|eda|ali|veli|ayse|fatma).*?(?:'e|'a|'ye|'ya|e |a |ya|ye|yi|yı|e ).*?(?:mesaj|yaz|gonder|gönder|soyle|söyle|ilet|bildir|gönder|gonder|yolla|at)",
        r"(?:gonder|gönder|yolla|at|yaz|ilet|bildir).*?(?:mesaj|whatsapp|wp|ileti|bildirim)",
        r"(?:de ki|deki|deki|soyle|söyle).*?(?:mesaj|whatsapp|wp|ona|buna|annesine|babasina|babasına)",
        r"(?:whatsapp).*?(?:ac|aç|git|goster|göster|yolla|mesaj|bildirim|bildir)",
        r"(?:soyle|söyle|ilet).*?(?:ona|buna|anneme|babama|ahmete|mehmete|annesine|babasina|babasına|kardesime|ablama|abime|arkadasima|arkadaşıma)",
    ],
    "save_contact": [
        r"(?:whatsapp|wp|rehber|kisi|kişi|contact|kayıt|kayit|telefon|telefon defteri|adres defteri|rehberim).*?(?:kaydet|ekle|sakla|kayit|kayıt|yeni|olustur|oluştur|kaydet)",
        r"(?:numara|telefon|tel|gsm|cep|cep telefonu|mobile|mobil).*?(?:kaydet|ekle|sakla|kayit|kayıt|olustur|oluştur)",
        r"(?:kaydet|ekle|sakla|olustur|oluştur).*?(?:kisi|kişi|numara|telefon|rehber|contact|kayıt|kayit)",
        r"(?:yeni).*?(?:kisi|kişi|numara|telefon|contact|kayıt|kayit|rehber).*?(?:kaydet|ekle|olustur|oluştur|kaydet)",
        r"(?:kisi|kişi).*?(?:ekle|kaydet).*?(?:whatsapp|wp|rehber)",
    ],
}


def _extract_contact_name(text: str) -> str:
    """Metinden kisi adi cikarma."""
    text_lower = text.lower()

    known_names = ["anne", "baba", "annem", "babam", "ahmet", "mehmet", "ece",
                   "ali", "veli", "ayse", "fatma", "can", "emre", "selin"]

    for name in known_names:
        if name in text_lower:
            return name.capitalize()

    match = re.search(r'(.+?)(?:\'e|\'a|a |e )\s*(?:mesaj|yaz|gonder|gönder)', text_lower)
    if match:
        return match.group(1).strip().capitalize()

    return ""


def _extract_message_text(text: str) -> str:
    """Metinden mesaj icerigi cikarma."""
    text_lower = text.lower()

    match = re.search(r'(?:mesaj|yaz|gonder|gönder|yolla)\s+(.+?)(?:\s+gonder|\s+gönder|\s+yolla|\s+at|$)', text_lower)
    if match:
        return match.group(1).strip().capitalize()

    match = re.search(r'(?:de ki|diye|ki)\s+(.+?)(?:\s+gonder|\s+gönder|\s+yolla|\s+at|$)', text_lower)
    if match:
        return match.group(1).strip().capitalize()

    return "Merhaba"


def _extract_phone(text: str) -> str:
    """Metinden telefon numarasi cikarma."""
    match = re.search(r'(\+?\d{10,13})', text)
    if match:
        return match.group(1)
    return ""


def classify_whatsapp_intent(text: str) -> tuple[str, dict]:
    """Kullanici metninden WhatsApp intent'ini cikarir."""
    text_lower = text.lower().strip()

    # 1. Kisi kaydetme
    for pattern in TRIGGERS["save_contact"]:
        if re.search(pattern, text_lower):
            name = _extract_contact_name(text)
            phone = _extract_phone(text)
            return "save_contact", {"display_name": name, "phone_number": phone}

    # 2. Mesaj gonderme
    for pattern in TRIGGERS["send_message"]:
        if re.search(pattern, text_lower):
            name = _extract_contact_name(text)
            message = _extract_message_text(text)

            send_now = any(w in text_lower for w in ["gonder", "gönder", "yolla", "at", "hemen"])

            return "send_message", {
                "recipient_name": name,
                "message": message,
                "send_now": send_now,
                "app_target": "auto"
            }

    # Fallback keyword
    whatsapp_keywords = ["whatsapp", "wp", "mesaj at", "mesaj gonder", "mesaj gönder", "yaz"]
    if any(kw in text_lower for kw in whatsapp_keywords):
        return "send_message", {
            "recipient_name": _extract_contact_name(text),
            "message": _extract_message_text(text),
            "send_now": False,
            "app_target": "auto"
        }

    return "none", {}


def execute_whatsapp_skill(action: str, params: dict) -> str:
    """WhatsApp skill calistirici."""
    if action == "send_message":
        if not params.get("recipient_name") and not params.get("phone_number"):
            return "Kisi adi veya telefon numarasi belirtilmedi."
        return send_whatsapp_message(
            params.get("message", ""),
            params.get("phone_number", ""),
            params.get("recipient_name", ""),
            params.get("send_now", False),
            params.get("app_target", "auto"))
    elif action == "save_contact":
        if not params.get("display_name") or not params.get("phone_number"):
            return "Kisi adi ve telefon numarasi zorunlu."
        return save_whatsapp_contact(
            params.get("display_name", ""),
            params.get("phone_number", ""),
            params.get("aliases", ""))
    return f"Bilinmeyen WhatsApp action: {action}"


def route_whatsapp_request(user_text: str) -> str | None:
    """Kullanici metnini analiz eder, WhatsApp skill'i ile eslesirse calistirir."""
    intent, params = classify_whatsapp_intent(user_text)
    if intent == "none":
        return None

    result = execute_whatsapp_skill(intent, params)
    return result
