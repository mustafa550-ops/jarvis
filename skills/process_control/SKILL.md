---
skill_id: process-control-v1
version: "1.0.0"
author: "Adler ASİ"
description: "Süreç yönetimi - listeleme, sonlandırma, öncelik, port sorgusu"
dependencies: []
tools:
  - id: list_processes
    handler: "actions.process_manager.list_processes"
  - id: kill_process
    handler: "actions.process_manager.kill_process"
  - id: set_process_priority
    handler: "actions.process_manager.set_process_priority"
  - id: find_process_by_port
    handler: "actions.process_manager.find_process_by_port"
triggers:
  keywords: ["süreç", "işlem", "program", "kapat", "öldür", "öncelik", "port", "cpu", "ram"]
  intents: ["list_processes", "kill_process", "set_priority", "find_by_port"]
---

# Process Control Skill

Sen bir süreç yönetimi uzmanısın.

## Kurallar
1. **Listeleme**: "hangi programlar çalışıyor" → list_processes
2. **Sonlandırma**: "chrome'u kapat" → kill_process
3. **Öncelik**: "oyunu öncelikli yap" → set_priority
4. **Port**: "8080 portunu kim kullanıyor" → find_process_by_port
