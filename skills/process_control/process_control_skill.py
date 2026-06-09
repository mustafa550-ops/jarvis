"""
Process Control Skill - Süreç yönetimi
"""

from __future__ import annotations
import re
from actions.process_manager import list_processes, kill_process, set_process_priority, find_process_by_port

SKILL_ID = "process-control-v1"
SKILL_NAME = "Süreç Kontrol"

TRIGGERS = {
    "list_processes": [
        r"(?:hangi|calisan|çalışan|aktif|acik|açık|calısan).*?(?:program|uygulama|süreç|surec|islem|işlem|uygulamalar|yazılım|yazilim|proses)",
        r"(?:cpu|ram|bellek|islemci|işlemci|bellek|gpu|ekran karti|ekran kartı).*?(?:kullanan|tuketen|tüketen|yiyen|harcayan|en cok|en çok|en fazla).*?(?:program|uygulama|süreç|surec|islem|işlem|proses)",
        r"(?:süreç|surec|islem|işlem|process|proses).*?(?:listele|goster|göster|bak|gor|gör|yaz|dok|dök)",
        r"(?:arka plan|arkaplanda|background).*?(?:ne|neler|hangi|ne kadar).*?(?:calisiyor|çalışıyor|calisan|çalışan|donuyor|donuyor)",
        r"(?:gorev yoneticisi|görev yöneticisi|task manager|görev yönetimi|gorev yonetimi).*?(?:goster|göster|listele|bak|ac|aç)",
        r"(?:ne calisiyor|neler calisiyor|ne açık|neler acik|ne calisiyo|neler calisiyo).*?(?:su anda|şu anda|simdi|şimdi)",
        r"(?:kac|kaç).*?(?:program|uygulama|süreç|surec|islem|işlem|uygulama).*?(?:acik|açık|calisiyor|çalışıyor|aktif)",
        r"(?:goster|göster|listele|bak).*?(?:program|uygulama|süreç|surec|islem|işlem)",
    ],
    "kill_process": [
        r"(?:chrome|spotify|firefox|edge|discord|steam|notepad|explorer|telegram|slack|vs.?code|vscode|pycharm|intellij|idea|whatsapp|skype|zoom|teams|outlook|word|excel|powerpoint|photoshop|premiere|after.?effects|illustrator|figma).*?(?:kapat|durdur|sonlandır|sonlandir|bitir|oldur|öldür|kapa)",
        r"(?:kapat|durdur|sonlandır|sonlandir|oldur|öldür|bitir|kapa).*?(?:chrome|spotify|firefox|program|uygulama|süreç|surec|islem|işlem|uygulamayı|programı)",
        r"(?:pid|process id).*?(?:sonlandır|sonlandir|oldur|öldür|kapat|durdur)",
        r"(?:uygulama|program|sekmeler|tablar|sayfalar).*?(?:kapat|durdur|sonlandır|sonlandir|bitir|kapa)",
        r"(?:öldür|oldur|bitir).*?(?:şu|su|bu|programı|uygulamayı|işlemi|islemi)",
        r"(?:zorla|force|hard).*?(?:kapat|durdur|sonlandır|sonlandir|oldur|öldür)",
        r"(?:yanıt vermiyor|yanit vermiyor|dondu|takıldı|dondu|kilitlendi).*?(?:kapat|durdur|sonlandır|sonlandir)",
    ],
    "set_priority": [
        r"(?:öncelik|oncelik|priority|hizlandir|hızlandır|hizlandirma|hızlandırma).*?(?:oyun|program|uygulama|süreç|surec|islem|işlem|proses)",
        r"(?:program|uygulama|oyun).*?(?:düşük|dusuk|yüksek|yuksek|normal|gerçek zamanlı|gercek zamanlı|yuksek|yüksek).*?(?:öncelik|oncelik|priority)",
        r"(?:hizlandir|hızlandır|hizlandir|hizlandirma).*?(?:oyun|program|uygulama|bilgisayar)",
        r"(?:öncelik|oncelik).*?(?:ver|ata|ayarla|degistir|değiştir|yap)",
        r"(?:daha hizli|daha hızlı|hızlı|hizli|kasma|kasmasın).*?(?:calissin|çalışsın|oyun|program)",
    ],
    "find_by_port": [
        r"(?:(\d{2,5})).*?(?:port|portunu|portta|nolu port).*?(?:kim|hangi|ne|hangi program|hangi uygulama).*?(?:kullanıyor|kullaniyor|dinliyor|calisiyor|çalışıyor|acik|açık)",
        r"(?:port).*?(?:kim|hangi|ne|hangi program).*?(?:kullanıyor|kullaniyor|dinliyor|calisiyor|çalışıyor|acik|açık)",
        r"(?:port).*?(?:(\d{2,5})).*?(?:ara|bul|gor|gör|goster|göster|listele)",
        r"(?:hangi).*?(?:port|portta).*?(?:calisiyor|çalışıyor|dinliyor|acik|açık)",
    ],
}


def classify_process_intent(text: str) -> tuple[str, dict]:
    """Kullanıcı metninden süreç kontrol intent'ini çıkarır."""
    text_lower = text.lower().strip()

    # 1. Port sorgusu (özel: sayı + port)
    port_match = re.search(r'(\d{2,5}).*?(?:port|portunu)', text_lower)
    if port_match:
        return "find_by_port", {"port": int(port_match.group(1))}

    # 2. Kill process (program adı)
    kill_match = re.search(r'(chrome|spotify|firefox|edge|discord|steam|notepad|explorer).*?(?:kapat|durdur|öldür)', text_lower)
    if kill_match:
        return "kill_process", {"identifier": kill_match.group(1)}

    # 3. Priority
    if any(w in text_lower for w in ["öncelik", "priority", "hızlandır"]):
        prog_match = re.search(r'(\w+).*?(?:öncelik|priority)', text_lower)
        if prog_match:
            priority = "high" if any(w in text_lower for w in ["yüksek", "high", "artır"]) else "normal"
            return "set_priority", {"identifier": prog_match.group(1), "priority": priority}

    # 4. List processes
    for pattern in TRIGGERS["list_processes"]:
        if re.search(pattern, text_lower):
            sort_by = "cpu"
            if "ram" in text_lower or "bellek" in text_lower:
                sort_by = "memory"
            return "list_processes", {"sort_by": sort_by, "limit": 10}

    return "none", {}


def execute_process_skill(action: str, params: dict) -> str:
    """Process skill çalıştırıcı."""
    if action == "list_processes":
        return list_processes(params.get("sort_by", "cpu"), params.get("limit", 10))
    elif action == "kill_process":
        return kill_process(params.get("identifier", ""), params.get("force", False))
    elif action == "set_priority":
        return set_process_priority(params.get("identifier", ""), params.get("priority", "normal"))
    elif action == "find_by_port":
        return find_process_by_port(params.get("port", 0))
    return f"Bilinmeyen process action: {action}"


def route_process_request(user_text: str) -> str | None:
    """Kullanıcı metnini analiz eder, süreç kontrol skill'i ile eşleşirse çalıştırır."""
    intent, params = classify_process_intent(user_text)
    if intent == "none":
        return None

    result = execute_process_skill(intent, params)
    return result
