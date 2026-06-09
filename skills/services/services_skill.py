"""
Services Skill — Servis yönetimi (listeleme, başlatma, durdurma, restart).
"""

from __future__ import annotations
import re
from actions.service_monitor import list_services, control_service

SKILL_ID = "services-v1"
SKILL_NAME = "Servis Yonetimi"

# ── Trigger patterns ──────────────────────────────────────────────────────
# ASCII fallback: tüm Türkçe karakterler için (ş→s, ç→c, ü→u, ö→o, ğ→g, ı→i)
TRIGGERS = {
    "list_services": [
        r"(?:servis|service|hizmet|hizmet|arka plan|arkaplan|arka plan).*?(?:neler|ne var|listele|goster|göster|bak|gor|gör|durum|liste|yaz|dok|dök|bilgi|nedir)",
        r"(?:calisan|çalışan|calışan|aktif|durmus|durmuş|stopped|running|çalışmayan|calismayan|pasif|kapalı|kapali).*?(?:servis|service|hizmet|hizmet|arka plan|arkaplan)",
        r"(?:windows).*?(?:servis|service|hizmet|hizmet).*?(?:listele|goster|göster|durum|neler|ne var|bilgi|rapor)",
        r"(?:hangi).*?(?:servis|service|hizmet|hizmet).*?(?:calisiyor|çalışıyor|aktif|acik|açık|durmus|durmuş|kapalı|kapali|devre dışı|devre disi)",
        r"(?:servisler).*?(?:listele|goster|göster|durum|rapor|kontrol|bilgi|neler)",
        r"(?:tum|tüm|butun|bütün|hepsi).*?(?:servis|service|hizmet|hizmet).*?(?:listele|goster|göster|durum|kontrol|rapor)",
        r"(?:servis).*?(?:durum|kontrol|listele|goster|göster|rapor|bilgi|yaz|dok|dök)",
        r"(?:servis|service).*?(?:kac|kaç|tane|adet|ne kadar).*?(?:var|calisiyor|çalışıyor|aktif)",
    ],
    "control_service": [
        r"(?:mysql|apache|nginx|postgresql|redis|docker|mongodb|elasticsearch|rabbitmq|kafka|wamp|xampp|iis|ftp|ssh|rdp|vnc|samba|tomcat|jenkins|gitlab|prometheus|grafana|kubernetes|k8s|sql).*?(?:baslat|başlat|durdur|yeniden baslat|yeniden başlat|restart|durum|kontrol|ac|aç|kapat|durumunu|kontrol|calistir|çalıştır)",
        r"(?:servis|service|hizmet|hizmet).*?(?:baslat|başlat|durdur|yeniden baslat|yeniden başlat|restart|durum|kontrol|ac|aç|kapat|durumunu|calistir|çalıştır)",
        r"(?:baslat|başlat|calistir|çalıştır|ac|aç).*?(?:servis|service|mysql|apache|nginx|redis|docker|postgresql)",
        r"(?:durdur|kapat|stop|kapa).*?(?:servis|service|mysql|apache|nginx|redis|docker|postgresql)",
        r"(?:restart|yeniden baslat|yeniden başlat|tekrar baslat|tekrar başlat).*?(?:servis|service|mysql|apache|nginx|redis|docker|postgresql)",
        r"(?:servis|service).*?(?:durum|kontrol).*?(?:mysql|apache|nginx|redis|docker|postgresql)",
        r"(?:mysql|apache|nginx|redis|docker).*?(?:calisiyor|çalışıyor|durmus|durmuş|acik|açık|kapalı|kapali|calismiyor|çalışmıyor)",
        r"(?:control).*?(?:servis|service).*?(?:et|yap)",
    ],
}

# Bilinen servisler
KNOWN_SERVICES = [
    "mysql", "mysqld", "apache", "apache2", "nginx", "postgresql", "redis",
    "docker", "mongodb", "elasticsearch", "rabbitmq", "kafka", "wamp",
    "xampp", "iis", "ftp", "ssh", "rdp", "remote desktop",
]


def _extract_service_name(text: str) -> tuple[str, str]:
    """Metinden servis adı ve action çıkarma."""
    text_lower = text.lower()

    # Servis adı tespiti
    service_name = ""
    for svc in KNOWN_SERVICES:
        if svc in text_lower:
            service_name = svc
            break

    # Action tespiti
    action = "status"
    if any(w in text_lower for w in ["baslat", "başlat", "start", "calistir", "çalıştır", "ac", "aç"]):
        action = "start"
    elif any(w in text_lower for w in ["durdur", "stop", "kapat", "dur"]):
        action = "stop"
    elif any(w in text_lower for w in ["yeniden baslat", "yeniden başlat", "restart", "tekrar baslat", "tekrar başlat"]):
        action = "restart"

    return service_name, action


def classify_services_intent(text: str) -> tuple[str, dict]:
    """Kullanıcı metninden services intent'ini çıkarır."""
    text_lower = text.lower().strip()

    # 1. Servis kontrolü
    for pattern in TRIGGERS["control_service"]:
        if re.search(pattern, text_lower):
            service_name, action = _extract_service_name(text)
            if service_name:
                return "control_service", {"service_name": service_name, "action": action}

    # 2. Listeleme
    for pattern in TRIGGERS["list_services"]:
        if re.search(pattern, text_lower):
            status_filter = "all"
            if "calisan" in text_lower or "calışan" in text_lower or "çalışan" in text_lower or "aktif" in text_lower or "running" in text_lower:
                status_filter = "running"
            elif "durmus" in text_lower or "durmuş" in text_lower or "stopped" in text_lower:
                status_filter = "stopped"
            return "list_services", {"status_filter": status_filter, "limit": 20}

    # Fallback keyword
    services_keywords = ["servis", "service", "hizmet", "hizmet", "mysql", "apache", "nginx",
                         "postgresql", "redis", "docker", "wamp", "xampp"]
    if any(kw in text_lower for kw in services_keywords):
        service_name, action = _extract_service_name(text)
        if service_name:
            return "control_service", {"service_name": service_name, "action": action}
        return "list_services", {"status_filter": "all", "limit": 20}

    return "none", {}


def execute_services_skill(action: str, params: dict) -> str:
    """Services skill çalıştırıcı."""
    if action == "list_services":
        return list_services(params.get("status_filter", "all"), params.get("limit", 20))
    elif action == "control_service":
        return control_service(params.get("service_name", ""), params.get("action", "status"))
    return f"Bilinmeyen services action: {action}"


def route_services_request(user_text: str) -> str | None:
    """Kullanıcı metnini analiz eder, services skill'i ile eşleşirse çalıştırır."""
    intent, params = classify_services_intent(user_text)
    if intent == "none":
        return None

    result = execute_services_skill(intent, params)
    return result
