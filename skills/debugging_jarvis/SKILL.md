---
skill_id: debugging-jarvis-v1
version: "1.0.0"
author: "Adler ASI"
description: "JARVIS sesli asistan projesindeki ses, UI, thread, skill ve entegrasyon hatalarini sistematik debug etme"
dependencies: []
tools:
  - id: debug_audio
    handler: "internal"
  - id: debug_ui
    handler: "internal"
  - id: debug_skill
    handler: "internal"
  - id: debug_system
    handler: "internal"
  - id: debug_network
    handler: "internal"
  - id: debug_logs
    handler: "internal"
triggers:
  keywords:
    - "ses"
    - "mikrofon"
    - "konusma"
    - "UI"
    - "pencere"
    - "thread"
    - "hata"
    - "debug"
    - "skill"
    - "calismiyor"
    - "dondu"
    - "sorun"
    - "bozuk"
    - "baglanti"
    - "api"
    - "ollama"
    - "gemini"
    - "log"
    - "error"
  intents:
    - "debug_audio"
    - "debug_ui"
    - "debug_skill"
    - "debug_system"
    - "debug_network"
  patterns:
    - "(.*) (calismiyor|calismadi|dondu|kitlendi|acilmiyor)"
    - "(ses|mikrofon|konusma) (.*) (gelmiyor|yok|bozuk)"
    - "(.*) (hatasi|sorunu|problemi)"
    - "debug (.*)"
    - "log (goster|oku|bak)"
---

# JARVIS Debugging Skill

Sen bir hata ayıklama uzmanısın. Kullanıcı bir hata veya sorun bildirdiğinde:

## Debug Workflow
Her hata için:
1. `classify_debug_intent()` ile kategorize et (ses/ui/skill/sistem/ag/log)
2. `execute_debug()` ile ilgili teşhis fonksiyonunu çalıştır
3. Sistem komutları ile gerçek teşhis yap (arecord, pactl, amixer, curl, vb.)
4. Sonuçları detaylı rapor olarak döndür

## Kategoriler
| Kategori | Açıklama | Çalıştırdığı Fonksiyon |
|----------|----------|------------------------|
| ses | Ses/SPEECH | `_check_audio_system()` |
| ui | UI/Tkinter | `_check_ui_system()` |
| skill | Skill/Entegrasyon | `_check_skill_system()` |
| sistem | Sistem/Platform | `_check_system_platform()` |
| ag | Ağ/API | `_check_network()` |
| log | Log Analizi | `_check_logs()` |

## Örnekler
- "sesim gelmiyor" → `_check_audio_system()` → arecord, pactl, amixer, RNNoise, TTS teşhisi
- "UI dondu" → `_check_ui_system()` → thread listesi, main thread kontrolü
- "skill calismiyor" → `_check_skill_system()` → dizin yapısı, import kontrolü
- "ollama baglanamiyor" → `_check_network()` → curl, ping, API key kontrolü
- "log goster" → `_check_logs()` → son 50 satır, istatistikler
- "sistemde hata var" → `_general_diagnostics()` → genel durum özeti

## Tkinter Thread Güvenliği
- Background thread → widget'a direkt erişme → `safe_call()` veya `root.after()` kullan
- Uzun işlemler → `threading.Thread(target=..., daemon=True).start()`
- Queue tıkanması → `_gui_queue.qsize()` > 100 ise consumer kontrolü

## Hata Durumları
- Log dosyası yoksa: "Log dosyasi bulunamadi, JARVIS henuz calistirilmamis olabilir"
- Ses cihazı yoksa: "Ses cihazi bulunamadi, `arecord -l` ile kontrol edin"
- Python import hatası: Bagimlilik eksik, `pip install` gerekebilir
- Ollama baglanti hatasi: `ollama serve` calismiyor olabilir
