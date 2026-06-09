# JARVIS Mimarisi

## Genel Bakış

JARVIS, **çift backend** mimarisiyle çalışan, gerçek zamanlı sesli asistandır.  
Birincil backend **Google Gemini AI Audio API**, ikincil backend ise **Ollama** (yerel)dir.

```
┌─────────────────────────────────────────────────────────────┐
│                      JARVIS Çekirdeği                        │
│                        main.py                               │
│                     JarvisLive sınıfı                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  Gemini AI   │    │   Ollama     │    │    Tkinter   │   │
│  │  (bulut)     │    │  (yerel)     │    │    UI (ui.py)│   │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘   │
│         │                   │                   │           │
│         ▼                   ▼                   ▼           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Action Modülleri (actions/)              │   │
│  │  open_app  sys_info  weather  calendar  reminders    │   │
│  │  browser   shell    whatsapp  media   youtube_stats  │   │
│  │  screen_vision  tts  windows_utils  health           │   │
│  │  system_doctor  process_manager  file_guardian      │   │
│  │  network_monitor  system_cron  service_monitor       │   │
│  │  [disk_predictor] [process_timeline] [net_anomaly]  │   │
│  │  [cron_web_ui] [watchdog/file_watcher]              │   │
│  └──────────────────────────────────────────────────────┘   │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            Ses İşleme (audio/)                         │   │
│  │  noise_suppressor.py  RNNoise gürültü bastırma        │   │
│  │  microphone.py         SoundDevice mikrofon akışı     │   │
│  │  lib/librnnoise.so    RNNoise C kütüphanesi           │   │
│  └──────────────────────────────────────────────────────┘   │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            Skill Modülleri (skills/)                   │   │
│  │  browser/         browser_skill.py  (tarayıcı)        │   │
│  │  system_health/   system_health_skill.py  (sistem)     │   │
│  │  process_control/ process_control_skill.py  (süreç)    │   │
│  │  file_manager/    file_manager_skill.py  (dosya)       │   │
│  │  weather/         weather_skill.py  (hava durumu)      │   │
│  │  youtube/         youtube_skill.py  (YouTube)          │   │
│  │  vision/          vision_skill.py  (ekran analizi)     │   │
│  │  calendar/        calendar_skill.py  (takvim)          │   │
│  │  reminders/       reminders_skill.py  (hatırlatıcı)    │   │
│  │  whatsapp/        whatsapp_skill.py  (WhatsApp)        │   │
│  │  media/           media_skill.py  (medya oynatma)      │   │
│  │  network/         network_skill.py  (ağ izleme)        │   │
│  │  scheduler/       scheduler_skill.py  (zamanlanmış)    │   │
│  │  services/        services_skill.py  (servis yönetimi) │   │
│  └──────────────────────────────────────────────────────┘   │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────┐    ┌──────────────┐                       │
│  │    Bellek     │    │  Yapılandırma│                       │
│  │ memory/       │    │  config/     │                       │
│  └──────────────┘    └──────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧠 Çekirdek Mimarisi

### JarvisLive Sınıfı (`main.py`) — Provider Abstraction Pattern

Ana controller sınıfı, **provider abstraction** ile backend'lerden bağımsız çalışır:

```
JarvisLive
├── __init__()          → UI callback'leri bağlar, durum değişkenlerini kurar
│                       → _user_initiated = False
│                       → skill_manager = get_skill_manager()
│
├── run()              → Ana döngü: backend seçimi, provider oluşturma, bağlanma
│   ├── GeminiProvider (Live API — ses akışı + tool calls)
│   └── OllamaProvider (HTTP Chat — VAD/STT + TTS)
│
├── _execute_tool()    → Tool çağrılarını action modüllerine yönlendirir
│                      → TOOL_HANDLER_MAP (tool_registry.py) ile dict dispatch
│
├── set_speaking()     → Konuşma durumunu yönetir (thread-safe)
├── _interrupt_audio() → Ses akışını keser
│
├── _on_text_command() → Metin komutlarını işler, _user_initiated = True yapar
│                      → Önce skill_manager.route() dener, eşleşirse direkt çalıştırır
│                      → Eşleşmezse provider.send_text() ile LLM'e iletir
├── _on_pause_toggle() → Duraklatma durumunu yönetir
├── _on_effects_state_change() → Ses efektleri durumunu yönetir
│
└── _focus_ui_section_for_tool() → UI panel odağını yönetir

#### Sistem Kontrol Handler'ları (main.py sonu)
```
_handle_get_system_health()    → system_doctor.get_system_health()
_handle_cleanup_temp_files()   → system_doctor.cleanup_temp_files()
_handle_cleanup_recycle_bin()  → system_doctor.cleanup_recycle_bin()
_handle_list_processes()       → process_manager.list_processes()
_handle_kill_process()         → process_manager.kill_process()
_handle_set_process_priority() → process_manager.set_process_priority()
_handle_find_process_by_port() → process_manager.find_process_by_port()
_handle_find_large_files()     → file_guardian.find_large_files()
_handle_find_duplicate_files() → file_guardian.find_duplicate_files()
_handle_cleanup_folder()       → file_guardian.cleanup_folder()
_handle_get_folder_summary()   → file_guardian.get_folder_summary()
_handle_get_network_summary()  → network_monitor.get_network_summary()
_handle_list_net_connections() → network_monitor.list_connections()
_handle_ping_host()            → network_monitor.ping_host()
_handle_add_cron_job()         → system_cron.add_cron_job()
_handle_list_cron_jobs()       → system_cron.list_cron_jobs()
_handle_remove_cron_job()      → system_cron.remove_cron_job()
_handle_list_services()        → service_monitor.list_services()
_handle_control_service()      → service_monitor.control_service()
_handle_set_volume()           → windows_utils.set_volume() (pactl/osascript/nircmd)
_handle_browser_skill()        → skills.browser.browser_skill (AI tool çağrısı için)
```

#### Arka Plan Servisleri (main.py __init__ sonu)
```
start_cron_daemon()            → system_cron cron döngüsü
FileWatcher(paths, ui)         → watchdog/file_watcher.py dosya izleme
ProcessTimeline().poll()       → process_timeline.py süreç zaman çizelgesi
CronWebServer(port=8765)       → cron_web_ui.py web arayüzü
DiskPredictor().record_sample()→ disk_predictor.py (6 saatte bir cron)
NetworkAnomalyDetector().scan()→ network_anomaly.py (2 dakikada bir cron)
```
```

### Thread Modeli

```
Ana Thread (main.py)
└── run() → asyncio event loop (ana döngü)
    ├── Provider seçimi (config → Gemini / Ollama)
    │
    ├── Gemini modu — TaskGroup (4 eşzamanlı coroutine)
    │   ├── _send_realtime()   → ses gönderme (out_queue → Gemini)
    │   ├── _listen_audio()    → ses alma (mikrofon → out_queue + local modüller)
    │   ├── _receive_audio()   → yanıt işleme (tool calls + transcription)
    │   └── _play_audio()      → ses çalma (audio_in_queue → hoparlör)
    │
    ├── Ollama modu — async loop
    │   ├── _stt_listen_loop()     → VAD + faster-whisper (PyAudio task)
    │   ├── _stt_fallback_listen() → speech_recognition yedek STT
    │   └── input_queue → _ollama_chat() → TTS
    │
    ├── UI Thread (Tkinter mainloop)
    │   ├── _sync_sound_state() → ses durumu senkronizasyonu
    │   └── _animate_orb()     → halka animasyonu (after())
    │
    └── Arka Plan Thread'leri
        ├── FileWatcher         → dosya sistemi izleme (watchdog/polling)
        ├── ProcessTimeline     → süreç zaman çizelgesi (5sn polling)
        ├── CronWebServer       → HTTP sunucu (port 8765)
        ├── DiskPredictor       → disk örnekleme (6 saat)
        └── NetworkAnomaly      → ağ taraması (2 dk)
```

**Önemli**: Ses akışı PortAudio üzerinden yapılır. Thread race condition'larını önlemek için giriş/çıkış stream'leri sırayla (sequential) açılır.

---

## 🔄 Ses Akışı

### Gemini Backend

```
Mikrofon → pyaudio (16kHz, paInt16, mono) 
         → out_queue (asyncio.Queue, maxsize=10)
         → Gemini Live API (send_realtime_input)
         │
         ← Gemini Live API (receive)
         → audio_in_queue (asyncio.Queue)
         → pyaudio (24kHz, paInt16, mono)
         → Hoparlör
```

### Ollama Backend

```
Mikrofon → SpeechRecognition (Google STT) 
         → Faster-Whisper (fallback, offline)
         → RNNoise (noise_suppressor.py):
             1. 16kHz → 48kHz upsampling (zero-order hold)
             2. RNNoise C kütüphanesi ile gürültü bastırma
             3. 48kHz → 16kHz downsampling
             4. VAD probability çıktısı
         → clean_transcript_text() (text_utils):
              1. unicodedata.normalize("NFC") — decomposed Türkçe karakter düzeltmesi
              2. fix_turkish_syllable_split() — faster-whisper hece bölmesi birleştirme
         → VAD (Voice Activity Detection)
         → Ollama API (HTTP /api/chat)
         → TTS Zinciri:
             1. Piper (yerel, offline)
             2. Edge-TTS (bulut, Microsoft Neural)
             3. spd-say (son fallback)
         → subprocess (aplay/mpg123)
         → Hoparlör
```

---

## 🎨 UI Mimarisi

### Tkinter UI (`ui.py`)

```
JarvisUI (Tkinter.Toplevel)
├── Ana Pencere (2200×1320)
│   ├── Header (HDR_H=72px)
│   │   ├── Logo / Sistem adı
│   │   ├── Durum göstergesi (orb)
│   │   └── Panel yönlendirme
│   │
│   ├── Sol Panel (LEFT_W_T=360px)
│   │   ├── Hava durumu
│   │   ├── Sistem bilgisi
│   │   └── Zaman
│   │
│   ├── Orta Panel (konsantrik halka)
│   │   ├── _OrbCanvas — özel animasyonlu canvas
│   │   │   ├── İç halka (canlı)
│   │   │   ├── Orta halka (dönen segmentler)
│   │   │   └── Dış halka (durum renkli)
│   │   ├── Durum metni
│   │   └── Mikrofon butonu
│   │
│   ├── Sağ Panel (RIGHT_W_T=410px)
│   │   ├── Log paneli
│   │   ├── Debug paneli
│   │   └── Ayarlar sekmesi
│   │
│   ├── Input Çubuğu (INPUT_H=34px)
│   │   └── Metin girişi
│   │
│   ├── Kontrol Paneli (CONTROL_H=146px)
│   │   ├── Mute/Unmute
│   │   ├── Duraklat/Devam
│   │   └── Ses efekti geçişi
│   │
│   └── Footer (FOOTER_H=26px)
│       ├── Platform bilgisi
│       └── Sosyal medya ikonları
│
├── SoundManager
│   ├── playsound ile SFX çalma
│   └── _sync_sound_state ile thread-safe durum yönetimi
│
└── Yardımcı Metotlar
    ├── set_state() — durum geçişleri + renk güncelleme
    ├── write_log() — log yazma
    ├── write_debug() — debug yazma
    ├── mark_user_activity() — kullanıcı etkinliği işareti
    └── focus_panel() — panel odağı yönetimi
```

### Durum Makinesi

```
INITIALISING → LISTENING ↔ SPEAKING
                    ↕        ↕
                THINKING → ERROR
                    ↕
               MUTED / PAUSED
```

Her durum, orb (konsantrik halka) rengini değiştirir:
- **LISTENING**: Yeşil `#00ff88`
- **SPEAKING**: Mavi `#4488ff`
- **THINKING**: Altın `#ffcc00`
- **ERROR**: Kırmızı `#ff3344`
- **MUTED**: Koyu pembe `#cc2255`
- **PAUSED**: Koyu teal `#1e3c37`

---

## 🧩 Action Modülleri

### İletişim Modeli

```
Gemini/Ollama → function_call → _execute_tool()
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
            loop.run_in_executor()        Direkt fonksiyon çağrısı
            (thread pool)                 (basit işlemler)
                    │                               │
                    ▼                               ▼
            Action Modülü → str result    → JarvisLive._execute_tool()
                                            → result looks like error?
                                              → EVET: ERROR state
                                              → HAYIR: success SFX + LISTENING
```

### Modül Listesi

| Modül | İşlev | Backend |
|-------|-------|---------|
| `open_app.py` | 50+ Windows uygulamasını açma | `os.startfile` / `subprocess` |
| `sys_info.py` | CPU, RAM, Disk, Batarya, Ağ, Saat/Tarih | `psutil` + `socket` |
| `weather.py` | wttr.in API ile anlık hava durumu | `requests` |
| `calendar.py` | Windows takvim CRUD | PowerShell COM |
| `reminders.py` | Hatırlatıcı yönetimi | PowerShell COM |
| `browser.py` | URL açma, Google arama, YouTube oynatma | `webbrowser` + URI |
| `shell.py` | Güvenlik filtreli komut çalıştırma | `subprocess` |
| `whatsapp.py` | WhatsApp mesaj gönderme | Selenium WebDriver |
| `media.py` | YouTube/Spotify medya oynatma | URI + webbrowser |
| `youtube_stats.py` | Kanal istatistikleri ve video analizi | YouTube Data API |
| `screen_vision.py` | Ekran görüntüsü + Gemini Vision analizi | `pyautogui` + Gemini |
| `tts.py` | 3 backend TTS (Piper → Edge → spd-say) | subprocess |
| `windows_utils.py` | Windows API (URI, PowerShell, clipboard, ses) | `ctypes` + `powershell` |
| `health.py` | Platform sağlık verisi (iCloud/Windows) | platform-conditional |
| `system_doctor.py` | Sistem sağlık raporu (disk, RAM, CPU, ağ) | `psutil` |
| `process_manager.py` | Süreç listeleme/öldürme/öncelik | `psutil` |
| `file_guardian.py` | Büyük dosya, yinelenen dosya, klasör temizlik | `os` + `pathlib` |
| `network_monitor.py` | Ağ özeti, bağlantı listesi, ping | `psutil` + `socket` |
| `system_cron.py` | Zamanlanmış görev ekleme/listeleme/silme | `sqlite3` + `threading` |
| `service_monitor.py` | Windows servis listeleme/kontrol | `psutil` |
| `disk_predictor.py` | Disk doluluk tahmini (opsiyonel) | `psutil` + `sqlite3` |
| `process_timeline.py` | Süreç zaman çizelgesi (opsiyonel) | `psutil` + `sqlite3` |
| `network_anomaly.py` | Ağ anomali tespiti (opsiyonel) | `psutil` |
| `cron_web_ui.py` | Cron web yönetim arayüzü (opsiyonel) | `http.server` |
| `watchdog/file_watcher.py` | Gerçek zamanlı dosya izleme (opsiyonel) | `watchdog` / polling |
---

## 🧩 Skill Sistemi

### Skill Manager (`core/skill_manager.py`)

```
SkillManager (singleton)
├── __init__()
│   └── _load_all_skills()
│       ├── skills/ klasöründeki her alt klasörü tara
│       ├── SKILL.md varsa metadata parse et
│       ├── triggers.json varsa trigger tanımlarını oku
│       └── route_xxx_request() fonksiyonunu bul ve kaydet
├── route(user_text) → str | None
│   └── Tüm router fonksiyonlarını sırayla dene
│       → İlk eşleşen skill'in sonucunu döndür
│       → Hiçbiri eşleşmezse None döndür (LLM'e git)
└── list_skills() → list[str]
    → Yüklü skill ID'lerini döndür
```

### İletişim Modeli

Skill sistemi, kullanıcı metnini **AI'a göndermeden önce** işler:

```
Kullanıcı: "youtube aç"
         │
         ▼
  _on_text_command()
         │
         ├── skill_manager.route(text)
         │       │
         │       ├── EŞLEŞTİ → skill doğrudan çalışır
         │       │              Sonuç UI'da gösterilir
         │       │              LLM'e GİDİLMEZ
         │       │
         │       └── EŞLEŞMEDİ → Normal LLM akışına devam
         │
         └── Gemini/Ollama → actions/...
```

### Action vs Skill Farkı

| | Action Modülü | Skill Modülü |
|---|---|---|
| **Kim çağırır?** | AI (function_call) | SkillManager, AI'dan önce |
| **AI dahil mi?** | Evet, AI düşünür sonra çağırır | Hayır, anında çalışır |
| **Hız** | ~1-3sn (AI düşünme süresi) | ~1ms |
| **Kayıt** | tool_registry.py (tek kaynak) + _TOOL_HANDLERS | skills/ klasörü + route fonksiyonu |
| **Kullanım** | Karmaşık, bağlam gerektiren işler | Basit, öngörülebilir komutlar |

### Yeni Skill Ekleme

```python
# skills/yeni_skill/yeni_skill.py
TRIGGERS = {
    "action_name": [
        r"(?:tetikleyici|keyword).*?(?:örnek|pattern)",
    ],
}

def route_yeni_skill_request(user_text: str) -> str | None:
    """user_text'te trigger ara, eşleşirse skill çalıştır."""
    text = user_text.lower()
    for action, patterns in TRIGGERS.items():
        for pattern in patterns:
            if re.search(pattern, text):
                return f"Skill sonucu: {action}"
    return None
```

**Kurallar:**
- `route_<name>_request(user_text) → str | None` fonksiyonu zorunlu
- TRIGGERS dict inline (triggers.json opsiyonel)
- Türkçe karakterler için ASCII fallback eklenmeli: `(?:yavaş|yavas)`, `(?:göster|goster)`, `(?:işlem|islem)`
- SkillManager otomatik keşfeder, kayıt gerekmez

---

## 💾 Veri Akışı

### Yapılandırma

```
app_config.py
├── DEFAULT_CONFIG (dict) — 7 varsayılan anahtar
├── load_app_config() → JSON'dan oku + DEFAULT ile merge
├── save_app_config(updates) → JSON'a yaz
├── get_app_config_value(key, default) → tek değer oku
├── has_gemini_api_key() → API anahtarı var mı?
├── get_ollama_models() → localhost:11434/api/tags
└── get_ollama_tts_voices() → Piper + Edge + spd-say
```

### Bellek Sistemi

```
memory/memory_manager.py
├── load_memory() → JSON'dan oku
├── update_memory(updates) → _deep_merge ile birleştir + yaz
├── delete_memory(category, key, match_text) → sil
└── format_memory_for_prompt() → system prompt'a ekle

Kategoriler: identity, preferences, projects, notes
```

### Log Sistemi

```
main.py
├── logging.basicConfig → logs/jarvis.log (DEBUG seviyesi)
├── handle_exception() → yakalanmayan exception'ları logla
├── handle_thread_exception() → thread exception'larını logla
└── httpcore → WARNING seviyesinde (gereksiz DEBUG'leri kapat)
```

---

## 🛡 Güvenlik Mimarisi

### Shell Komut Filtreleme (`actions/shell.py`)

```
BLOCKED_PREFIXES = [
    "rm", "sudo", "mkfs", "dd", "shutdown", "reboot",
    "init", "poweroff", "halt", ":(){", "diskutil",
    "mv /", "chmod 777 /"
]

Her komut:
1. normalize edilir (lowercase + trim)
2. BLOCKED_PREFIXES ile karşılaştırılır
3. Bloklanırsa → güvenlik uyarısı
4. Geçerse → subprocess.run(timeout=30)
```

### Platform Güvenliği

- macOS özel kodları `if IS_MACOS:` bloğu içinde
- Windows'ta `rm -rf /` gibi UNIX komutları çalışmaz
- API anahtarları `.gitignore` ile korunuyor
- Tüm action modülleri try/except ile sarılı
- **`_user_initiated` güvenlik gate**: `_handle_browser_control()` kullanıcı ilk mesajını gönderene kadar `_user_initiated = False` kontrolü yapar. AI'nın izinsiz tarayıcı açmasını engeller.
- **OS detection**: `GeminiProvider.build_config()` sistem prompt'una `[SISTEM BILGISI]` enjekte eder (OS, shell, path separator). AI'nın yanlış platform komutu üretmesini önler.
- **Input validation**: Tool call girişi 2000 char, arg değerleri 500 char ile sınırlı; tool adı whitelist ile doğrulanır
- **Exception logging**: Tüm `except Exception: pass`'ler `traceback.print_exc()` ile loglanır (NDJSON streaming hariç)

### Thread Safety

Thread kullanan modüller ve koruma stratejileri:

| Modül | Korumalı Alan | Kullanılan Kilit | Durum |
|-------|--------------|-----------------|-------|
| `main.py` | `_is_speaking` | `_speaking_lock` (Lock) | ✅ |
| `core/skill_manager.py` | Skills listesi, watcher state | `_lock` (RLock) — 10+ yerde | ✅ |
| `ui/sound_manager.py` | `_all_sound_procs`, `_ambient_proc`, `_foreground_proc` | `_lock` (RLock) — 18 yerde | ✅ |
| `actions/watchdog/file_watcher.py` | Debounce timer, history, event queue | `_debounce_lock`, `_history_lock` | ✅ |
| `actions/system_cron.py:298` | NetworkAnomalyDetector.scan() | `_nad_lock` (Lock) — non-blocking acquire | ✅ |
| `actions/cron_web_ui.py` | `_running` flag | Yok (tek boolean, minör race) | ⚠️ Benign |

---

## 🔌 Backend Karşılaştırması

| Özellik | Gemini AI | Ollama |
|---------|-----------|--------|
| **Bağlantı** | İnternet gerekli | Tamamen yerel |
| **Gecikme** | Düşük (bulut) | Orta (CPU) |
| **Ses Kalitesi** | Yüksek (doğal) | Orta (TTS zinciri) |
| **STT** | Gemini Audio API | Google STT → Faster-Whisper |
| **TTS** | Gemini doğal ses | Piper → Edge-TTS → spd-say |
| **Tool Calling** | Yerleşik (function_declarations) | System prompt + JSON parsing |
| **Maliyet** | API kullanımı ücretli | Ücretsiz |
| **Gizlilik** | Bulut | Tamamen yerel |
| **Model** | Gemini 2.5 Flash | qwen2.5:1.5b (değiştirilebilir) |
