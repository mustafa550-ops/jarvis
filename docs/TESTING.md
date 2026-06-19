# J.A.R.V.I.S — Test ve Diagnostic Rehberi

> İki test katmanı: `tests/` klasöründe **pytest/unittest** (geliştirici) + UI üzerinden **built-in diagnostic skill** (kullanıcı).

---

## Genel Bakış

JARVIS'te iki test altyapısı bulunur:

### 1. Birim Testleri (`tests/` klasörü) — Geliştirici

**86 test dosyası**, pytest + unittest ile. Gerçek production kodunu gerçek veriyle test eder. Mock sadece donanım bağımlılıklarında (mikrofon, ses kartı) kullanılır.

```bash
# Tüm testleri koş
python -m pytest tests/ -q

# Belirli modül testi
python -m pytest tests/test_barge_in.py -v

# Smoke test
python -m pytest tests/test_smoke.py -v
```

### 2. Diagnostic Skill (UI üzerinden) — Kullanıcı

Tkinter UI içinden `debugging_jarvis` skill'i ile 7 kategoride teşhis:

```
UI input (text/voice)
    │
    ├── "test" veya "tüm testler"
    │       → debugging_jarvis skill'i
    │       → _run_full_diagnostics()
    │       → Tüm kategorileri art arda çalıştırır
    │       → Sonuç UI'da gösterilir
    │
    ├── "ses testi" / "UI dondu" / "sistem kontrol"
    │       → debugging_jarvis skill'i
    │       → İlgili kategori teşhisi
    │       → Sonuç UI'da gösterilir
    │
    └── "sistem durum" / "cpu kaç"
            → system_health skill'i
            → CPU/RAM/disk bilgisi
            → Sonuç UI'da gösterilir
```

---

## Diagnostic Kategorileri

| Kategori | Keyword Örnekleri | Çalıştırdığı Fonksiyon | Ne Kontrol Eder? |
|----------|-------------------|------------------------|------------------|
| 🔴 Ses | "ses gelmiyor", "mikrofon bozuk", "konusma yok" | `_check_audio_system()` | ALSA, PulseAudio, PipeWire, Python kütüphaneleri, RNNoise, ses seviyeleri |
| 🟡 UI | "UI dondu", "pencere acilmiyor", "thread hatasi" | `_check_ui_system()` | Thread listesi, main thread, Tkinter durumu |
| 🟢 Skill | "skill calismiyor", "import hatasi", "hotreload" | `_check_skill_system()` | Skill dizinleri, import kontrolü, route fonksiyonları |
| 🔵 Sistem | "sistem hatasi", "port cakismasi", "json parse" | `_check_system_platform()` | Platform, portlar, ses izinleri, grup üyelikleri, bellek |
| 🌐 Ağ | "baglanti yok", "gemini hatasi", "ollama baglanamiyor" | `_check_network()` | İnternet, Ollama, Gemini API key, model durumu |
| 📋 Log | "log goster", "son satirlari oku", "kayit gor" | `_check_logs()` | `logs/jarvis.log` analizi, hata istatistikleri |
| ⚪ Genel | "hata var", "sorun", "debug", "calismiyor" | `_general_diagnostics()` | Platform, kritik dosyalar, bellek, CPU, öneriler |
| 🔍 Full Test | "test", "test yap", "tüm testler", "full kontrol", "diagnostik" | `_run_full_diagnostics()` | **Tüm kategorileri art arda çalıştırır** |

---

## Diagnostic Çalıştırma

### UI Üzerinden (Önerilen)

JARVIS çalışırken input kutusuna aşağıdaki komutları yazın:

| Komut | Ne Yapar? |
|-------|-----------|
| `test` | Tüm sistem diagnostic'lerini çalıştırır |
| `tüm testler` | Aynı — full diagnostic suite |
| `full kontrol` | Aynı |
| `diagnostik` | Aynı |
| `ses testi` | Ses sistemi teşhisi (mikrofon, hoparlör, RNNoise) |
| `ses gelmiyor` | Ses sorunlarına odaklı teşhis |
| `UI dondu` | UI/Tkinter thread durumu |
| `sistem` | Platform, port, bellek teşhisi |
| `ollama baglanamiyor` | Ollama/Gemini bağlantı testi |
| `log goster` | Log dosyası hata analizi |
| `hata var` | Genel sistem durumu özeti |
| `sistem durum` | CPU/RAM/disk sağlık bilgisi |

### Terminalden (Geliştirici)

```bash
# Diagnostic skill'ini doğrudan test et
python3 -c "
from skills.debugging_jarvis.debugging_jarvis_skill import classify_debug_intent, execute_debug
cat = classify_debug_intent('test')
print(f'Kategori: {cat}')
print(execute_debug(cat))
"
```

### Skill Manager Durumu

```bash
python3 -c "
from core.skill_manager import get_skill_manager
sm = get_skill_manager()
print('Skill list:', sm.list_skills())
print('Stats:', sm.get_stats())
"
```

---

## Skill Doğrulama Testleri

Her skill aşağıdaki kriterlere göre test edilebilir:

### 1. Import Testi
```python
from skills.<name>.<name>_skill import route_<name>_request
assert route_<name>_request is not None
```

### 2. Route Testi
```python
result = route_<name>_request("tetikleyici kelime")
assert result is not None, "Skill tetiklenmedi"
assert isinstance(result, str), "String dönmeli"
```

### 3. No-Match Testi
```python
result = route_<name>_request("ilgisiz kelime")
assert result is None, "Eşleşmeyen metin None dönmeli"
```

### 4. Hata Yönetimi
```python
try:
    result = route_<name>_request(None)
    assert result is None, "None input None dönmeli"
except Exception:
    pass  # Bazı skill'ler None'da exception fırlatabilir
```

---

## Sık Kullanılan Debug Komutları

### UI Debug Paneli

JARVIS çalışırken **Settings → DEBUG** sekmesinde runtime hata kayıtları görüntülenir. `write_debug()` ile eklenen tüm error/warn/info mesajları burada listelenir.

### Thread Durumu

```bash
# Tüm thread'leri listele
python3 -c "
import threading
for t in threading.enumerate():
    print(f'{t.name} ({t.ident}) - {\"daemon\" if t.daemon else \"normal\"} - {\"canlı\" if t.is_alive() else \"ölü\"}')"
```

### Log Analizi

```bash
# Son 50 satır
tail -50 logs/jarvis.log

# Sadece ERROR/CRITICAL satırları
grep -E "ERROR|CRITICAL|Traceback" logs/jarvis.log | tail -20

# Thread bazlı sorgulama
grep "ThreadName" logs/jarvis.log | sort -u
```

### Port Kontrolü

```bash
# Ollama portu
curl -s --max-time 3 http://localhost:11434/api/tags | python3 -m json.tool

# Cron Web UI portu
ss -tlnp | grep 8765
```

---

## Test Prensipleri

| Kural | Açıklama |
|-------|----------|
| **Birim test** | `tests/` klasöründe pytest + unittest, mock sadece donanım bağımlılıklarında |
| **Skill doğrulama** | Her yeni skill için route/import/no-match testleri `tests/test_skill_*.py` |
| **Diagnostic kapsamı** | Ses → UI → Skill → Sistem → Ağ → Log → Genel (7 kategori) |
| **Full suite** | "test" komutu ile tüm kategoriler sırayla çalışır |
| **Hata durumu** | Her diagnostic try/except ile sarılıdır, tek hata tüm suite'i durdurmaz |
| **Çalıştırma** | `python -m pytest tests/ -q` — tüm birim testleri |
| **Ekleme** | Yeni test dosyası: `tests/test_<modul>.py`, unittest.TestCase ile |

---

## Diagnostic Genişletme

Yeni bir diagnostic kategorisi eklemek için:

1. `skills/debugging_jarvis/debugging_jarvis_skill.py` dosyasında:
   - Yeni kategori sabiti ekleyin (örn: `CAT_NEW = "yeni"`)
   - `CATEGORY_LABELS` sözlüğüne ekleyin
   - Teşhis fonksiyonunu yazın (`def _check_new_system()`)
   - `CATEGORY_HANDLERS` sözlüğüne ekleyin
   - `classify_debug_intent()`'e yeni regex pattern'i ekleyin
   - `_run_full_diagnostics()`'a yeni kategoriyi ekleyin

2. Gerekirse `_general_diagnostics()`'a yeni kontroller ekleyin.

---

## Bilinen Diagnostic Sınırlamaları

| Durum | Açıklama |
|-------|----------|
| Bazı teşhisler Linux komutları gerektirir | `arecord`, `pactl`, `amixer` — Windows/macOS'ta çalışmaz |
| Ollama/Gemini teşhisi | İlgili servis çalışıyor olmalı |
| Ses donanımı teşhisi | Gerçek ses donanımı gerektirir (sanal ortamda sınırlı) |
| Log dosyası | `logs/jarvis.log` yoksa log analizi yapılamaz |
