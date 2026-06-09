"""
YouTube Skill - Kanal istatistikleri ve video arama
"""

from __future__ import annotations
import re
from actions.youtube_stats import get_youtube_channel_report
from actions.media import play_media
from app_config import get_app_config_value

SKILL_ID = "youtube-v1"
SKILL_NAME = "YouTube"

TRIGGERS = {
    "channel_report": [
        r"(?:youtube|kanal|kanalim|kanalım|kanalimiz|kanalımız).*?(?:istatistik|rapor|analiz|durum|buyume|büyüme|ozet|özet|gelisim|gelişim|performans|bilgi|nasıl|nasil)",
        r"(?:abone|abone sayisi|abone sayısı|takipci|takipçi|aboneler|abonem).*?(?:kac|kaç|durum|ne kadar|arttı|artti|azaldı|azaldi|yükseldi|yukseldi|dustu|düştü)",
        r"(?:izlenme|goruntulenme|görüntülenme|views|goruntuleme|görüntüleme).*?(?:sayisi|sayısı|kac|kaç|durum|rapor|toplam|ne kadar)",
        r"(?:son video|videolarim|videolarım|videolar|video).*?(?:performans|analiz|nasil|nasıl|izlenme|begeni|beğeni|yorum|begenilme|beğenilme)",
        r"(?:youtube).*?(?:nasil|nasıl|gidiyor|durum|ilerleme|ozet|özet|durum|performans|büyüme|buyume)",
        r"(?:kanal).*?(?:performans|nasil|nasıl|durum|bilgi|analiz|istatistik|buyume|büyüme)",
        r"(?:abone).*?(?:hedef|sayi|sayı|ne kadar|kac|kaç|oldu)",
    ],
    "play_media": [
        r"(?:youtube'da|youtubeda|youtube da|youtube).*?(?:oynat|ac|aç|cal|çal|izle|dinle|bul|goster|göster|baslat|başlat)",
        r"(?:sarki|şarkı|muzik|müzik|video|klip|film|dizi|oynatma listesi|playlist|sarkiyi|şarkıyı|videoyu|muzigi|müziği).*?(?:oynat|ac|aç|cal|çal|izle|dinle|bul|baslat|başlat)",
        r"(?:cal|çal|oynat|ac|aç|izle|seyret|seyrey|dinle).*?(?:sarki|şarkı|muzik|müzik|video|klip|film|dizi|playlist)",
        r"(?:youtube).*?(?:sarki|şarkı|muzik|müzik|video|klip).*?(?:bul|ara|goster|göster|cal|çal|oynat)",
        r"(?:aç|ac).*?(?:sarki|şarkı|muzik|müzik|video).*?(?:youtube)",
        r"(?:şu).*?(?:sarkiyi|şarkıyı|muzigi|müziği|videoyu).*?(?:youtube).*?(?:cal|çal|oynat|ac|aç)",
    ],
}


def _get_channel_handle() -> str:
    """Ayarlar'dan YouTube handle al."""
    try:
        return str(get_app_config_value("youtube_channel_handle", "") or "").strip()
    except Exception:
        return ""


def classify_youtube_intent(text: str) -> tuple[str, dict]:
    """Kullanici metninden YouTube intent'ini cikarir."""
    text_lower = text.lower().strip()

    # 1. Kanal raporu
    for pattern in TRIGGERS["channel_report"]:
        if re.search(pattern, text_lower):
            return "channel_report", {"query": "overview", "handle": _get_channel_handle()}

    # 2. Video oynatma (media skill ile overlap - ama YouTube-specific)
    for pattern in TRIGGERS["play_media"]:
        match = re.search(pattern, text_lower)
        if match:
            # Query cikarma
            query = text_lower
            for remove in ["youtube'da", "youtubeda", "youtube da", "youtube",
                           "oynat", "ac", "aç", "cal", "çal", "bul",
                           "sarki", "şarkı", "muzik", "müzik", "video"]:
                query = query.replace(remove, "")
            query = query.strip()
            return "play_media", {"query": query, "provider": "youtube", "autoplay": True}

    # Fallback keyword
    channel_keywords = ["abone", "izlenme", "kanal", "kanal istatistik", "youtube rapor", "youtube istatistik"]
    if any(kw in text_lower for kw in channel_keywords):
        return "channel_report", {"query": "overview", "handle": _get_channel_handle()}

    return "none", {}


def execute_youtube_skill(action: str, params: dict) -> str:
    """YouTube skill calistirici."""
    if action == "channel_report":
        handle = params.get("handle", "")
        if not handle:
            return "YouTube kanal handle'i ayarlarda tanimli degil. Ayarlardan ekleyin."
        return get_youtube_channel_report(params.get("query", "overview"), handle, 6)
    elif action == "play_media":
        return play_media(params.get("query", ""), params.get("provider", "youtube"), params.get("autoplay", True))
    return f"Bilinmeyen YouTube action: {action}"


def route_youtube_request(user_text: str) -> str | None:
    """Kullanici metnini analiz eder, YouTube skill'i ile eslesirse calistirir."""
    intent, params = classify_youtube_intent(user_text)
    if intent == "none":
        return None

    result = execute_youtube_skill(intent, params)
    return result
