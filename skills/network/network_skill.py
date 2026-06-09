"""
Network Skill — Ağ monitoring, ping, bağlantı listesi.
"""

from __future__ import annotations
import re
from actions.network_monitor import get_network_summary, list_connections as list_net_connections, ping_host, get_bandwidth_usage

SKILL_ID = "network-v1"
SKILL_NAME = "Ag Monitoring"

# ── Trigger patterns ──────────────────────────────────────────────────────
# ASCII fallback: tüm Türkçe karakterler için (ş→s, ç→c, ü→u, ö→o, ğ→g, ı→i)
TRIGGERS = {
    "network_summary": [
        r"(?:ag|ağ|internet|baglanti|bağlantı|network|wifi|ethernet).*?(?:durum|durumu|ozet|ozet|rapor|nasil|nasıl|kontrol|calisiyor|çalışıyor|bilgi|nedir)",
        r"(?:ip|ip adresim|lokal ip|public ip|harici ip|dis ip|dış ip|ip'm|ipim).*?(?:ne|kac|kaç|nedir|goster|göster|soyle|söyle|bul)",
        r"(?:wifi|ethernet|modem|router).*?(?:durum|calisiyor|çalışıyor|calısıyor|bagli|bağlı|nasil|nasıl|sorun|kesik)",
        r"(?:internet).*?(?:var mi|var mı|yok mu|calisiyor|çalışıyor|calısıyor|bagli|bağlı|kesik|kesint|sorun|yavaş|yavas)",
        r"(?:localhost|yerel|makina|makinam|bilgisayar|sistem).*?(?:durum|durumu|nasil|nasıl|kontrol)",
        r"(?:ag|ağ).*?(?:turu|türü|tipi|adapter|kart|arayuz|arayüz|arabirim).*?(?:nedir|ne|goster|göster|bilgi)",
        r"(?:network|ağ|ag).*?(?:kart|adapter|arabirim|arayuz|arayüz).*?(?:bilgi|durum|ozellik|özellik|model|marka)",
    ],
    "list_connections": [
        r"(?:kimlere|nelere|hangi|nerelere).*?(?:bagli|bağlı|bagliyim|bağlıyım|baglantim|bağlantım)",
        r"(?:acik|açık|aktif|establish|kurulu).*?(?:baglanti|bağlantı|port|baglantilar|bağlantılar|soket|socket)",
        r"(?:port|baglanti|bağlantı|soket|socket).*?(?:dinleyen|acik|açık|listen|listele|goster|göster|rapor|gor|gör)",
        r"(?:baglanti|bağlantı|connection).*?(?:listele|goster|göster|rapor|yaz|dok|dök)",
        r"(?:hangi).*?(?:port|baglanti|bağlantı).*?(?:acik|açık|dinliyor|kullaniliyor|kullanılıyor|calisiyor|çalışıyor)",
        r"(?:tcp|udp).*?(?:baglanti|bağlantı|port).*?(?:listele|goster|göster|goster|rapor)",
    ],
    "ping_host": [
        r"(?:ping|test).*?(?:at|yap|kontrol|vur|gonder|gönder|yolla)",
        r"(?:google|youtube|facebook|twitter|github|stackoverflow|instagram|reddit|site|server|sitesi|sunucu|web sitesi).*?(?:ping|ulasiyor|ulaşıyor|ulasıyor|erisilebilir|erişilebilir|aciliyor|açılıyor|calisiyor|çalışıyor)",
        r"(?:internet|baglanti|bağlantı|network|web).*?(?:test|kontrol|ping|hiz|hız|kalite)",
        r"(?:localhost|127\.0\.0\.1|loopback|yerel|kendim|kendi|ev|kendi bilgisayarım|makina).*?(?:durum|durumu|kontrol|test|nasil|nasıl|calisiyor|çalışıyor|canli|canlı)",
        r"(?:durum|durumu|kontrol).*?(?:localhost|127\.0\.0\.1|makina|sistem|sunucu|server|baglanti|bağlantı)",
        r"(?:ping).*?(?:localhost|127\.0\.0\.1|kendime|kendine|kendi|server|sunucu|site|makina)",
        r"(?:baglanti|bağlantı).*?(?:hiz|hız|test|kontrol|kalite|guc|güç|seviye)",
    ],
    "bandwidth": [
        r"(?:internet|ag|ağ|network|hat).*?(?:hiz|hız|hizi|hızı|hz|speed|mbps|mb/s|kb/s)",
        r"(?:download|upload|indirme|yukleme|yükleme).*?(?:hiz|hız|hizi|hızı|kac|kaç|ne kadar|test|olc|ölç|hiztesti|hıztesti)",
        r"(?:bandwidth|bant genisligi|bant genişliği|bant).*?(?:kullanim|kullanım|rapor|durum|test|olc|ölç|ne kadar)",
        r"(?:hiz|hız).*?(?:testi|test).*?(?:internet|net|baglanti|bağlantı|ac|aç)",
        r"(?:internet).*?(?:yavaş|yavas|kesik|kopuyor|gidiyor|düşük|dusuk).*?(?:hiz|hız|test|kontrol|sorun)",
        r"(?:speedtest|speed test|internet testi|net testi).*?(?:yap|calistir|çalıştır|kos|koş|baslat|başlat)",
        r"(?:megabit|mbps|mb|mbit).*?(?:hiz|hız|ne|kaç|kac|nedir)",
    ],
}


def _extract_host(text: str) -> str:
    """Metinden host çıkarma."""
    text_lower = text.lower()

    known_hosts = {
        "google": "google.com",
        "youtube": "youtube.com",
        "facebook": "facebook.com",
        "twitter": "twitter.com",
        "github": "github.com",
        "stackoverflow": "stackoverflow.com",
        "localhost": "127.0.0.1",
        "yerel": "127.0.0.1",
        "kendim": "127.0.0.1",
        "kendi": "127.0.0.1",
        "ev": "127.0.0.1",
        "makina": "127.0.0.1",
    }

    for key, host in known_hosts.items():
        if key in text_lower:
            return host

    # Domain tespiti
    domain_match = re.search(r'([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,})', text)
    if domain_match:
        return domain_match.group(1)

    # IP tespiti
    ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', text)
    if ip_match:
        return ip_match.group(1)

    return "google.com"


def classify_network_intent(text: str) -> tuple[str, dict]:
    """Kullanıcı metninden network intent'ini çıkarır."""
    text_lower = text.lower().strip()

    # 1. Ping (spesifik sorgular önce)
    for pattern in TRIGGERS["ping_host"]:
        if re.search(pattern, text_lower):
            host = _extract_host(text)
            return "ping_host", {"host": host, "count": 4}

    # 2. Bandwidth
        if re.search(pattern, text_lower):
            return "bandwidth", {}

    # 2. Ping
    for pattern in TRIGGERS["ping_host"]:
        if re.search(pattern, text_lower):
            host = _extract_host(text)
            return "ping_host", {"host": host, "count": 4}

    # 3. Bağlantı listesi
    for pattern in TRIGGERS["list_connections"]:
        if re.search(pattern, text_lower):
            state = "all"
            if "established" in text_lower or "aktif" in text_lower:
                state = "established"
            elif "listen" in text_lower or "dinleyen" in text_lower:
                state = "listen"
            return "list_connections", {"state": state, "limit": 20}

    # 4. Network özeti
    for pattern in TRIGGERS["network_summary"]:
        if re.search(pattern, text_lower):
            return "network_summary", {}

    # Fallback keyword
    network_keywords = ["ag", "ağ", "internet", "baglanti", "bağlantı", "network",
                        "ip", "wifi", "modem", "router", "ping", "port", "hiz", "hız", "mbps",
                        "localhost", "127.0.0.1", "127", "loopback", "yerel", "makina",
                        "bilgisayar", "sistem"]
    if any(kw in text_lower for kw in network_keywords):
        return "network_summary", {}

    return "none", {}


def execute_network_skill(action: str, params: dict) -> str:
    """Network skill çalıştırıcı."""
    if action == "network_summary":
        return get_network_summary()
    elif action == "list_connections":
        return list_net_connections(params.get("state", "all"), params.get("limit", 20))
    elif action == "ping_host":
        return ping_host(params.get("host", "google.com"), params.get("count", 4))
    elif action == "bandwidth":
        return get_bandwidth_usage()
    return f"Bilinmeyen network action: {action}"


def route_network_request(user_text: str) -> str | None:
    """Kullanıcı metnini analiz eder, network skill'i ile eşleşirse çalıştırır."""
    intent, params = classify_network_intent(user_text)
    if intent == "none":
        return None

    result = execute_network_skill(intent, params)
    return result
