"""
JARVIS Browser Skill — URL açma, arama, YouTube oynatma.
SkillManager tarafından otomatik yüklenir.
"""

from __future__ import annotations

import re
from pathlib import Path

from actions.browser import browser_control


def execute_browser_skill(action: str, url: str | None = None, query: str | None = None) -> str:
    """Browser skill aksiyonlarını çalıştırır."""
    return browser_control(action, url=url, query=query)


# ── Trigger desenleri ───────────────────────────────────────────
_TRIGGER_PATTERNS: list[tuple[re.Pattern[str], str, str]] = []


def _load_triggers():
    """triggers.json'daki desenleri derler."""
    if _TRIGGER_PATTERNS:
        return
    triggers_path = Path(__file__).resolve().parent / "triggers.json"
    if not triggers_path.exists():
        return

    import json
    with open(triggers_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for pattern_str in data.get("triggers", {}).get("patterns", []):
        try:
            compiled = re.compile(pattern_str, re.IGNORECASE)
            # Basit eşleme: action tipini desenden çıkar
            if "google" in pattern_str:
                action = "search"
            elif "youtube" in pattern_str:
                action = "play_youtube"
            else:
                action = "open_url"
            _TRIGGER_PATTERNS.append((compiled, action, pattern_str))
        except re.error:
            continue


def route_browser_request(user_text: str) -> str | None:
    """
    Kullanıcı metnini browser skill desenleriyle eşleştirir.
    Eşleşme varsa skill'i çalıştırır, sonucu döner.
    Eşleşme yoksa None döner.
    """
    _load_triggers()
    text = user_text.strip()

    # 1) Regex desenleriyle eşleştir
    for compiled, action, raw_pattern in _TRIGGER_PATTERNS:
        m = compiled.search(text)
        if m:
            captured = m.group(1).strip()
            if action == "open_url":
                # "youtube aç" → https://youtube.com
                known_sites = {
                    "youtube": "https://youtube.com",
                    "google": "https://google.com",
                    "github": "https://github.com",
                    "gmail": "https://mail.google.com",
                }
                # Çok kelimeli yakalama → muhtemelen skill eşleşmesi değil
                if " " in captured and captured.lower() not in known_sites:
                    return None
                url = known_sites.get(captured.lower(), f"https://{captured}.com")
                return execute_browser_skill("open_url", url=url)
            elif action == "search":
                return execute_browser_skill("search", query=captured)
            elif action == "play_youtube":
                return execute_browser_skill("play_youtube", query=captured)

    # 2) Anahtar kelime bazlı eşleştirme (basit)
    keywords = ["aç", "tarayıcı", "google", "youtube", "ara", "git", "oynat", "video", "şarkı"]
    if any(kw in text.lower() for kw in keywords):
        # "X aç" kalıbı
        ac_match = re.search(r"(.+?)\s+aç$", text, re.IGNORECASE)
        if ac_match:
            site = ac_match.group(1).strip().lower()
            # Çok kelimeli → örn: "youtube sarki ac" browser değil, YouTube skill'ine ait
            if " " in site:
                return None
            known_sites = {
                "youtube": "https://youtube.com",
                "google": "https://google.com",
                "github": "https://github.com",
                "gmail": "https://mail.google.com",
            }
            url = known_sites.get(site, f"https://{site}.com")
            return execute_browser_skill("open_url", url=url)

        # "google'da X ara" kalıbı
        google_ara = re.search(r"google'da\s+(.+?)\s+ara", text, re.IGNORECASE)
        if google_ara:
            return execute_browser_skill("search", query=google_ara.group(1).strip())

        # "youtube'da X oynat" kalıbı
        yt_oynat = re.search(r"youtube'da\s+(.+?)\s+oynat", text, re.IGNORECASE)
        if yt_oynat:
            return execute_browser_skill("play_youtube", query=yt_oynat.group(1).strip())

        # "X ara" kalıbı
        ara_match = re.search(r"(.+?)\s+ara$", text, re.IGNORECASE)
        if ara_match:
            return execute_browser_skill("search", query=ara_match.group(1).strip())

        # "X oynat" kalıbı
        oynat_match = re.search(r"(.+?)\s+oynat$", text, re.IGNORECASE)
        if oynat_match:
            return execute_browser_skill("play_youtube", query=oynat_match.group(1).strip())

    return None
