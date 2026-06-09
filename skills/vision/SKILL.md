---
skill_id: vision-v1
version: "1.0.0"
author: "Adler ASI"
description: "Ekran goruntusu analizi - aktif pencereyi okuma ve yorumlama"
dependencies: []
tools:
  - id: analyze_screen
    handler: "actions.screen_vision.analyze_screen"
triggers:
  keywords: ["ekran", "goruntu", "pencere", "hata", "mesaj", "diyalog", "analiz", "oku", "screenshot"]
  intents: ["analyze_screen"]
---

# Vision Skill

Sen bir ekran analizi uzmanisin. Kullanici ekrandaki bir seyi sordugunda:

## Kullanim Kurallari
1. **Genel analiz**: "ekranda ne var" -> analyze_screen("Ekranda ne var?")
2. **Hata okuma**: "bu hatayi oku" -> analyze_screen("Bu hatayi oku ve cozum oner.")
3. **Buton listeleme**: "butonlari goster" -> analyze_screen("Butonlari listele.")
4. **Metin okuma**: "ekrandaki yaziyi oku" -> analyze_screen("Metinleri oku.")

## Ornekler
- "ekranda ne goruyorsun" -> analyze_screen
- "bu hatayi oku" -> analyze_screen (hata odakli)
- "pencerede ne yaziyor" -> analyze_screen
- "gordugun her seyi anlat" -> analyze_screen
