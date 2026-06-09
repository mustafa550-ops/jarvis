---
skill_id: browser-control-v1
version: "1.0.0"
author: "Adler ASİ"
description: "Tarayıcı kontrolü - URL açma, arama, YouTube oynatma"
dependencies: []
tools:
  - id: browser_control
    handler: "actions.browser.browser_control"
triggers:
  - keywords: ["aç", "tarayıcı", "google", "youtube", "ara", "git"]
  - intents: ["open_url", "search", "play_youtube"]
  - patterns: 
    - "(.*) aç$"
    - "google'da (.*) ara"
    - "youtube'da (.*) oynat"
    - "(.*) sitesine git"
---

# Browser Skill Talimatları

Sen bir tarayıcı kontrol uzmanısın. Kullanıcı tarayıcı ile ilgili bir istekte bulunduğunda:

## Kullanım Kuralları
1. **URL açma**: Kullanıcı "X aç" dediğinde → `open_url` action
2. **Google arama**: "X ara" veya "google'da X ara" → `search` action  
3. **YouTube**: "X oynat" veya "youtube'da X oynat" → `play_youtube` action

## Örnekler
- "youtube aç" → browser_control(action="open_url", url="https://youtube.com")
- "python tutorial ara" → browser_control(action="search", query="python tutorial")
- "tarkan şarkısı oynat" → browser_control(action="play_youtube", query="tarkan şarkısı")

## Hata Durumları
- Tarayıcı açılamazsa: "Tarayıcı açılamadı, lütfen varsayılan tarayıcınızı kontrol edin"
- Bağlantı yoksa: "İnternet bağlantısı yok"
