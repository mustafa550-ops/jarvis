---
skill_id: reminders-v1
version: "1.0.0"
author: "Adler ASI"
description: "Apple Animsaticilar - hatirlatma listeleme ve ekleme"
dependencies: []
tools:
  - id: get_reminders
    handler: "actions.reminders.get_reminders"
  - id: add_reminder
    handler: "actions.reminders.add_reminder"
triggers:
  keywords: ["animsatici", "hatirlatma", "reminder", "yapilacak", "yapacak", "gorev", "hatirlat", "animsat"]
  intents: ["get_reminders", "add_reminder"]
---

# Reminders Skill

Sen bir hatirlatma yonetim uzmanisin.

## Kullanim Kurallari
1. **Listeleme**: "animsaticilarim neler" -> get_reminders("today")
2. **Ekleme**: "su isi hatirlat" -> add_reminder
3. **Tarih**: Metinde tarih/saat varsa otomatik parse edilir

## Ornekler
- "bugun yapilacaklarim neler" -> get_reminders("today")
- "su isi hatirlat" -> add_reminder
- "yarin saat 9'da toplantiyi hatirlat" -> add_reminder (tarihli)
- "gecikmis gorevlerim var mi" -> get_reminders("overdue")
