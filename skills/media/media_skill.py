"""
Media Skill - Muzik ve video oynatma (YouTube, Spotify, Apple Music)
"""

from __future__ import annotations
import re
from actions.media import play_media

SKILL_ID = "media-v1"
SKILL_NAME = "Medya"

TRIGGERS = {
    "play_media": [
        r"(?:cal|çal|oynat|baslat|başlat|ac|aç|dinle|izle|seyret|koy|koy|goster|göster).*?(?:sarki|şarkı|muzik|müzik|video|album|albüm|playlist|sarkı|sarkilar|şarkılar|parca|parça|radyoda|radyo|roportaj|röportaj|konser|canli|canlı|ses|kayit|kayıt)",
        r"(?:sarki|şarkı|muzik|müzik|video|album|albüm|playlist|sarkilar|şarkılar|parca|parça|radyoda|radyo|ses|kayit|kayıt|film|dizi|belgesel|roportaj|röportaj|podcast|sesli kitap|sesli).*?(?:cal|çal|oynat|baslat|başlat|ac|aç|dinle|izle|seyret|goster|göster|bul|ara)",
        r"(?:spotify|youtube|apple music|itunes|deezer|soundcloud|tidal|amazon music|music|media player|winamp|vlc|mp3|mp4).*?(?:cal|çal|oynat|baslat|başlat|ac|aç|dinle|izle|goster|göster)",
        r"(?:dinle|izle|seyret|bak|goster|göster|kulak ver).*?(?:sarki|şarkı|muzik|müzik|video|film|dizi|klip|belgesel|roportaj|röportaj|podcast|ses)", 
        r"(?:muzik|müzik|sarki|şarkı|ses).*?(?:ac|aç|baslat|başlat|koy|cal|çal|dinle|goster|göster)",
        r"(?:hızlı|hizli|yavas|yavaş|huzlu|hüzlü|yavaştan|yavastan|normal).*?(?:sarki|şarkı|muzik|müzik|cal|çal|oynat|gec|geç)",
        r"(?:bir|bir tane|güzel|guzel|bir şey|bir sey|rastgele|herhangi).*?(?:sarki|şarkı|muzik|müzik|parca|parça|sarki|şarkı|ses).*?(?:cal|çal|oynat|ac|aç|dinle|bul|ara|goster|göster)",
        r"(?:şu|su|bu|bunu|bunları|sunları|şunları).*?(?:sarkiyi|şarkıyı|muzigi|müziği|videoyu|parcayi|parçayı|albümü|albumu).*?(?:cal|çal|oynat|ac|aç|dinle|izle|goster|göster)",
        r"(?:calma listem|calma listesi|calma listemi|oynatma listem|oynatma listemi|listem|kütüphane|kutuphane).*?(?:cal|çal|oynat|baslat|başlat|ac|aç|goster|göster|listele)",
        r"(?:radyo|radyoda|fm|internet radyosu).*?(?:cal|çal|ac|aç|dinle|baslat|başlat|goster|göster)",
        r"(?:arka planda|background).*?(?:cal|çal|oynat|dinle|devam)",
        r"(?:sıradaki|siradaki|sonraki|atla|gec|geç|ileri|geri).*?(?:sarki|şarkı|parca|parça|video).*?(?:cal|çal|oynat|gec|geç|atla)",
        r"(?:durdur|kapat|stop|pause|bekle).*?(?:sarki|şarkı|muzik|müzik|video|album|albüm)",
    ],
}

# Provider tespiti
PROVIDER_MAP = {
    "spotify": "spotify",
    "youtube": "youtube",
    "apple music": "apple_music",
    "itunes": "apple_music",
}


def _extract_media_query(text: str) -> tuple[str, str]:
    """Metinden medya sorgusu ve provider cikarma."""
    text_lower = text.lower()

    # Provider tespiti
    provider = "auto"
    for key, val in PROVIDER_MAP.items():
        if key in text_lower:
            provider = val
            break

    # Sorgu cikarma
    query = text_lower

    # Kaldirilacak kelimeler
    remove_words = [
        "cal", "çal", "oynat", "baslat", "başlat", "ac", "aç", "dinle", "izle",
        "sarki", "şarkı", "muzik", "müzik", "video", "album", "albüm", "playlist",
        "spotify", "youtube", "apple music", "itunes",
        "bir", "lutfen", "lütfen", "bana", "su", "şu",
    ]

    for word in remove_words:
        query = query.replace(word, "")

    query = query.strip()

    # "X'in Y'si" formati
    if not query:
        match = re.search(r'(.+?)\s+(?:cal|çal|oynat|baslat|başlat|ac|aç|dinle|izle)', text_lower)
        if match:
            query = match.group(1).strip()

    return query, provider


def classify_media_intent(text: str) -> tuple[str, dict]:
    """Kullanici metninden media intent'ini cikarir."""
    text_lower = text.lower().strip()

    # 1. Medya oynatma
    for pattern in TRIGGERS["play_media"]:
        if re.search(pattern, text_lower):
            query, provider = _extract_media_query(text)
            if query:
                return "play_media", {
                    "query": query,
                    "provider": provider,
                    "autoplay": True
                }

    # Fallback keyword
    media_keywords = ["cal", "çal", "oynat", "dinle", "izle",
                      "sarki", "şarkı", "muzik", "müzik", "video",
                      "spotify", "youtube", "apple music"]
    if any(kw in text_lower for kw in media_keywords):
        query, provider = _extract_media_query(text)
        if query:
            return "play_media", {
                "query": query,
                "provider": provider,
                "autoplay": True
            }

    return "none", {}


def execute_media_skill(action: str, params: dict) -> str:
    """Media skill calistirici."""
    if action == "play_media":
        return play_media(
            params.get("query", ""),
            params.get("provider", "auto"),
            params.get("autoplay", True))
    return f"Bilinmeyen media action: {action}"


def route_media_request(user_text: str) -> str | None:
    """Kullanici metnini analiz eder, media skill'i ile eslesirse calistirir."""
    intent, params = classify_media_intent(user_text)
    if intent == "none":
        return None

    result = execute_media_skill(intent, params)
    return result
