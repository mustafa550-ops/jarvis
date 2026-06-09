---
skill_id: scheduler-v1
version: "1.0.0"
author: "Adler ASI"
description: "Zamanlanmis gorev yonetimi - listeleme, ekleme, silme"
dependencies: []
tools:
  - id: list_cron_jobs
    handler: "actions.system_cron.list_cron_jobs"
  - id: add_cron_job
    handler: "actions.system_cron.add_cron_job"
  - id: remove_cron_job
    handler: "actions.system_cron.remove_cron_job"
triggers:
  keywords: ["gorev", "görev", "task", "zamanlanmis", "zamanlanmış", "cron", "zamanlayici", "zamanlayıcı", "hatirlat", "hatırlat", "rapor", "schedule"]
  intents: ["list_jobs", "add_job", "remove_job"]
---

# Scheduler Skill

Sen bir zamanlanmis gorev yonetim uzmanisin.

## Kullanim Kurallari
1. **Listeleme**: "gorevlerim neler" -> list_jobs
2. **Ekleme**: "her gun temp temizle gorevi ekle" -> add_job
3. **Silme**: "gorev 5'i sil" -> remove_job

## Ornekler
- "zamanlanmis gorevlerim neler" -> list_jobs
- "her gun saat 8'de saglik kontrolu yap" -> add_job("Saglik Kontrol", "health_check", "daily", "08:00")
- "haftalik disk temizligi ekle" -> add_job("Disk Temizlik", "temp_cleanup", "weekly", "0-08:00")
- "gorev 3'u sil" -> remove_job(3)
