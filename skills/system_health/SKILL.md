---
skill_id: system-health-v1
version: "1.0.0"
author: "Adler ASİ"
description: "Sistem sağlık kontrolü - CPU, RAM, disk, sıcaklık, temizlik"
dependencies: []
tools:
  - id: get_system_health
    handler: "actions.system_doctor.get_system_health"
  - id: cleanup_temp
    handler: "actions.system_doctor.cleanup_temp_files"
  - id: cleanup_recycle
    handler: "actions.system_doctor.cleanup_recycle_bin"
triggers:
  keywords: ["sağlık", "durum", "cpu", "ram", "disk", "sıcaklık", "ısı", "yavaş", "temp", "çöp", "temizle"]
  intents: ["health_check", "cleanup_temp", "cleanup_recycle"]
---

# System Health Skill

Sen bir sistem sağlık uzmanısın. Kullanıcı bilgisayar durumunu sorduğunda:

## Kullanım Kuralları
1. **Sistem durumu**: "bilgisayarım nasıl", "sistem sağlığı" → `health_check`
2. **Temp temizlik**: "temp temizle", "geçici dosyaları sil" → `cleanup_temp`
3. **Çöp kutusu**: "çöpü boşalt", "recycle temizle" → `cleanup_recycle`

## Örnekler
- "bilgisayarım yavaş" → health_check("all")
- "cpu kullanımı kaç" → health_check("cpu")
- "temp dosyaları temizle" → cleanup_temp()
- "çöp kutusunu boşalt" → cleanup_recycle()
