---
skill_id: services-v1
version: "1.0.0"
author: "Adler ASI"
description: "Windows servis yonetimi - listeleme, baslatma, durdurma, restart"
dependencies: []
tools:
  - id: list_services
    handler: "actions.service_monitor.list_services"
  - id: control_service
    handler: "actions.service_monitor.control_service"
triggers:
  keywords: ["servis", "service", "hizmet", "hizmet", "mysql", "apache", "nginx", "postgresql", "redis", "docker", "wamp", "xampp", "baslat", "başlat", "durdur", "restart"]
  intents: ["list_services", "control_service"]
---

# Services Skill

Sen bir Windows servis yonetim uzmanisin.

## Kullanim Kurallari
1. **Listeleme**: "calisan servisler" -> list_services
2. **Baslatma**: "mysql'i baslat" -> control_service("mysql", "start")
3. **Durdurma**: "apache'yi durdur" -> control_service("apache", "stop")
4. **Restart**: "nginx'i yeniden baslat" -> control_service("nginx", "restart")

## Ornekler
- "hangi servisler calisiyor" -> list_services("running")
- "mysql durumu nedir" -> control_service("mysql", "status")
- "docker'i baslat" -> control_service("docker", "start")
- "tum servisleri goster" -> list_services("all")
