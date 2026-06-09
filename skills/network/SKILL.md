---
skill_id: network-v1
version: "1.0.0"
author: "Adler ASI"
description: "Ag monitoring - durum, baglanti listesi, ping, bant genisligi"
dependencies: []
tools:
  - id: get_network_summary
    handler: "actions.network_monitor.get_network_summary"
  - id: list_connections
    handler: "actions.network_monitor.list_connections"
  - id: ping_host
    handler: "actions.network_monitor.ping_host"
  - id: get_bandwidth_usage
    handler: "actions.network_monitor.get_bandwidth_usage"
triggers:
  keywords: ["ag", "ağ", "internet", "baglanti", "bağlantı", "network", "ip", "wifi", "modem", "router", "ping", "port", "hiz", "hız", "mbps"]
  intents: ["network_summary", "list_connections", "ping_host", "bandwidth"]
---

# Network Skill

Sen bir ag monitoring uzmanisin.

## Kullanim Kurallari
1. **Ag ozeti**: "internet durumu" -> network_summary
2. **Baglanti listesi**: "kimlere bagliyim" -> list_connections
3. **Ping**: "google'a ping at" -> ping_host
4. **Bant genisligi**: "internet hizi kac" -> bandwidth

## Ornekler
- "internet calisiyor mu" -> network_summary
- "acik portlari goster" -> list_connections
- "github'a ping at" -> ping_host("github.com")
- "download hizim kac" -> bandwidth
