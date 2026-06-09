---
skill_id: youtube-v1
version: "1.0.0"
author: "Adler ASI"
description: "YouTube kanal istatistikleri ve video oynatma"
dependencies: []
tools:
  - id: get_youtube_channel_report
    handler: "actions.youtube_stats.get_youtube_channel_report"
  - id: play_media
    handler: "actions.media.play_media"
triggers:
  keywords: ["youtube", "kanal", "abone", "izlenme", "istatistik", "rapor", "sarki", "muzik", "video", "oynat"]
  intents: ["channel_report", "play_media"]
---

# YouTube Skill

Sen bir YouTube uzmanisin.

## Kullanim Kurallari
1. **Kanal raporu**: "kanalim nasil", "abone sayim kac" -> channel_report
2. **Video oynatma**: "youtube'da X oynat" -> play_media (youtube provider)
3. **Handle**: Ayarlardaki youtube_channel_handle kullanilir

## Ornekler
- "kanalim nasil gidiyor" -> channel_report
- "son videolarim nasil" -> channel_report
- "youtube'da tarkan oynat" -> play_media (overlap with browser/media skill)
- "abone sayim kac" -> channel_report
