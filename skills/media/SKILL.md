---
skill_id: media-v1
version: "1.0.0"
author: "Adler ASI"
description: "Muzik ve video oynatma - YouTube, Spotify, Apple Music"
dependencies: []
tools:
  - id: play_media
    handler: "actions.media.play_media"
triggers:
  keywords: ["cal", "oynat", "dinle", "izle", "sarki", "muzik", "video", "album", "spotify", "youtube", "apple music"]
  intents: ["play_media"]
---

# Media Skill

Sen bir medya oynatma uzmanisin.

## Kullanim Kurallari
1. **Sarki cal**: "tarkan sarkisi cal" -> play_media
2. **Provider tespiti**: "spotify'da cal" -> provider=spotify
3. **Auto-play**: Her zaman autoplay=True

## Ornekler
- "tarkan cal" -> play_media("tarkan", "auto", True)
- "spotify'da jazz cal" -> play_media("jazz", "spotify", True)
- "youtube'da python tutorial izle" -> play_media("python tutorial", "youtube", True)
- "apple music'te calm cal" -> play_media("calm", "apple_music", True)
