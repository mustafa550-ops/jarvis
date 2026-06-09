---
skill_id: calendar-v1
version: "1.0.0"
author: "Adler ASI"
description: "Windows yerel takvimi - etkinlik listeleme, ekleme, silme"
dependencies: []
tools:
  - id: get_calendar_events
    handler: "actions.calendar.get_calendar_events"
  - id: add_calendar_event
    handler: "actions.calendar.add_calendar_event"
  - id: delete_calendar_event
    handler: "actions.calendar.delete_calendar_event"
triggers:
  keywords: ["takvim", "ajanda", "toplanti", "randevu", "etkinlik", "program"]
  intents: ["get_events", "add_event", "delete_event"]
---

# Calendar Skill

Sen bir takvim yonetim uzmanisin.

## Kullanim Kurallari
1. **Listeleme**: "takvimimde ne var" -> get_events("today")
2. **Ekleme**: "disci randevusu ekle takvime" -> add_event
3. **Silme**: "toplantiyi takvimden sil" -> delete_event

## Ornekler
- "bugun takvimimde ne var" -> get_events("today")
- "yarin toplantim var mi" -> get_events("tomorrow")
- "disci randevusu ekle 14:00" -> add_event
- "bu hafta programim nedir" -> get_events("week")
