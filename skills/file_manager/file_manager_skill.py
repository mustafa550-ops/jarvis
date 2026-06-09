"""
File Manager Skill - Dosya yönetimi
"""

from __future__ import annotations
import re
import os
from actions.file_guardian import find_large_files, find_duplicate_files, cleanup_folder, get_folder_summary

SKILL_ID = "file-manager-v1"
SKILL_NAME = "Dosya Yöneticisi"

TRIGGERS = {
    "find_large": [
        r"(?:büyük|buyuk|dev|kocaman|iri|şişman|sis|şiş|şişkin|siskin).*?(?:dosya|dosyalar|file|files)",
        r"(?:(\d+).*?(?:mb|gb|tb)).*?(?:üzeri|uzeri|buyuk|büyük|ustu|üstü|kadar|dan|fazla|daha)",
        r"(?:disk|yer|alan|depolama|hafıza|hafiza).*?(?:dolu|şişmiş|sis|sis|tıka basa|tika basa|dolmuş|dolmus|azalmış|azalmis)",
        r"(?:alan kapla|yer kapla|alan kaplayan|yer kaplayan).*?(?:en çok|en cok|ne kadar|en fazla|en buyuk|en büyük)",
        r"(?:hangi).*?(?:dosya|klasor|klasör).*?(?:büyük|buyuk|şiş|sis|en çok|en cok|en fazla)",
        r"(?:bos yer|boş yer|yer ac|yer aç|alan ac|alan aç).*?(?:nerede|nasıl|nasil|bul)",
    ],
    "find_duplicate": [
        r"(?:ayni|aynı|tekrar|duplicate|kopya|yinele|yinelenen|mükerrer|mukerrer|cift|çift|ikiz).*?(?:dosya|dosyalar|file|files|kayıt|kayit)",
        r"(?:kopya).*?(?:bul|tara|ara|gor|gör|listele|goster|göster|sil)",
        r"(?:mükerrer|mukerrer|çift|cift|ikiz).*?(?:dosya|foto|resim|fotograf|fotoğraf|belge)",
        r"(?:aynı|ayni).*?(?:isimli|adlı|adli).*?(?:dosya|klasor|klasör)",
    ],
    "cleanup_folder": [
        r"(?:downloads|indirilenler|desktop|masaüstü|masaustu|documents|dokumanlar|dokümanlar|belgeler|temp|gecici|geçici).*?(?:temizle|sil|temizlik|yap|duzenle|düzenle|toparla|duzelt|düzelt)",
        r"(?:masaustu|masaüstü|downloads|indirilenler|belgeler).*?(?:dagınık|dagınık|dağınık|karışık|karisik|karmaşa).*?(?:temizle|duzenle|düzenle|toparla)",
        r"(?:klasor|klasör|dizin|folder|kutu).*?(?:temizle|bosalt|boşalt|sil|yap)",
        r"(?:dağınık|dagınık|karışık|karisik|karmaşa).*?(?:masaustu|masaüstü|desktop|klasor|klasör)",
        r"(?:gereksiz).*?(?:dosya|dosyalar).*?(?:sil|temizle|kaldir|kaldır)",
    ],
    "folder_summary": [
        r"(?:downloads|desktop|masaüstü|masaustu|documents|dokumanlar|dokümanlar|belgeler|indirilenler).*?(?:kac|kaç|boyut|buyukluk|büyüklük|ozet|özet|summary|durum|bilgi|ne var|neler var)",
        r"(?:klasor|klasör|dizin|folder).*?(?:ozet|özet|durum|bilgi|boyut|buyukluk|büyüklük|istatistik)",
        r"(?:hangi).*?(?:klasor|klasör).*?(?:kac|kaç|ne kadar|boyut|buyukluk|büyüklük)",
        r"(?:ozet|özet).*?(?:dosya|klasor|klasör|depolama)",
    ],
}

# Klasör haritalama
FOLDER_MAP = {
    "downloads": os.path.expanduser("~/Downloads"),
    "indirilenler": os.path.expanduser("~/Downloads"),
    "desktop": os.path.expanduser("~/Desktop"),
    "masaüstü": os.path.expanduser("~/Desktop"),
    "documents": os.path.expanduser("~/Documents"),
    "dokümanlar": os.path.expanduser("~/Documents"),
}


def classify_file_intent(text: str) -> tuple[str, dict]:
    """Kullanıcı metninden dosya yönetimi intent'ini çıkarır."""
    text_lower = text.lower().strip()

    # Klasör tespiti
    path = ""
    for key, folder_path in FOLDER_MAP.items():
        if key in text_lower:
            path = folder_path
            break

    if not path:
        path = os.path.expanduser("~")

    # 1. Büyük dosyalar
    size_match = re.search(r'(\d+)\s*(?:mb|gb)', text_lower)
    if size_match:
        size_mb = int(size_match.group(1))
        if "gb" in text_lower:
            size_mb *= 1024
        return "find_large", {"path": path, "min_size_mb": size_mb}

    for pattern in TRIGGERS["find_large"]:
        if re.search(pattern, text_lower):
            return "find_large", {"path": path, "min_size_mb": 100}

    # 2. Duplicate
    for pattern in TRIGGERS["find_duplicate"]:
        if re.search(pattern, text_lower):
            return "find_duplicate", {"path": path}

    # 3. Cleanup
    for pattern in TRIGGERS["cleanup_folder"]:
        if re.search(pattern, text_lower):
            return "cleanup_folder", {"path": path, "dry_run": "dry" not in text_lower}

    # 4. Summary
    for pattern in TRIGGERS["folder_summary"]:
        if re.search(pattern, text_lower):
            return "folder_summary", {"path": path}

    return "none", {}


def execute_file_skill(action: str, params: dict) -> str:
    """File manager skill çalıştırıcı."""
    if action == "find_large":
        return find_large_files(params.get("path", ""), params.get("min_size_mb", 100), 20)
    elif action == "find_duplicate":
        return find_duplicate_files(params.get("path", ""), 10)
    elif action == "cleanup_folder":
        return cleanup_folder(params.get("path", ""), "*", params.get("dry_run", True))
    elif action == "folder_summary":
        return get_folder_summary(params.get("path", ""))
    return f"Bilinmeyen file action: {action}"


def route_file_request(user_text: str) -> str | None:
    """Kullanıcı metnini analiz eder, dosya yönetimi skill'i ile eşleşirse çalıştırır."""
    intent, params = classify_file_intent(user_text)
    if intent == "none":
        return None

    result = execute_file_skill(intent, params)
    return result
