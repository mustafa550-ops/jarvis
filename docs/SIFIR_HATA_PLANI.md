# Sıfır Hata Stratejisi — JARVIS

## Mevcut Durum Analizi

### Teknoloji Yığını
| Katman | Teknoloji | Test Durumu |
|--------|-----------|-------------|
| Backend | Python 3.13, asyncio | ✅ 87 test dosyası |
| AI Provider | Gemini API, Ollama HTTP | ❌ 0 test (gemini_provider, ollama_provider) |
| Orkestrasyon | PyAudio, RNNoise, scipy | ❌ 0 test (orchestrator.py) |
| UI | Tkinter, CustomTkinter | ⚠️ test_ui.py var |
| Bellek | JSON dosya, RLock | ✅ test_memory.py var |
| Skill | 18 Python modülü | ✅ test_skill_*.py var |
| Ses İşleme | PyAudio, sounddevice | ⚠️ test_microphone.py var |
| Tool Dispatch | Dict dispatch (main.py) | ⚠️ 45 handler, 0 doğrudan test |

### Test Boşlukları (Kritik)
| Dosya | Satır | Test | Risk |
|-------|-------|------|------|
| `core/orchestrator.py` | 739 | ❌ Yok | **KRİTİK** — tüm ses pipeline + provider yönetimi |
| `core/gemini_provider.py` | 565 | ❌ Yok | **KRİTİK** — ana AI provider |
| `core/ollama_provider.py` | 493 | ❌ Yok | **KRİTİK** — ikincil AI provider |
| `main.py` (handlers) | 1329 | ⚠️ 9 test, 0 handler test | **KRİTİK** — 45 tool handler çalışma garantisi yok |
| `core/_skill_engine.py` | ~200 | ❌ Yok | Orta |
| `core/audio_system/*.py` | ~500 | ❌ Yok | Orta |

### LSP Durumu
- `orchestrator.py`: 2 hint (unused import)
- `main.py`: 11 hint (unused param, unused import)
- Diğer: temiz

---

## Strateji: Bottom-Up Test Katmanları

```
Katman 4: Pre-commit hook / CI
Katman 3: main.py handler testleri
Katman 2: Provider testleri (gemini, ollama)
Katman 1: orchestrator.py testleri ← BURADAN BAŞLA
```

Her katman bir öncekine güvenir. Alttan başlamak = her adımda doğrulanabilir testler.

---

## Adım Adım Plan

### Adım 1: Dev Tools Kurulumu
- `pytest-cov` (coverage raporu)
- `pytest-mock` (mock kolaylıkları)
- `pre-commit` (git hook)
- `.coveragerc` yapılandırması

### Adım 2: orchestrator.py Testleri
- `tests/test_orchestrator.py` — 4 ana class:
  - `resample_audio()` — pure function test
  - `UnifiedAudioPipeline` — state machine, always_listen, queue ops, trigger_wake_word
  - `ProviderRouter` — provider selection, state transitions, retry logic
  - `JarvisOrchestrator` — send_text, switch_provider, lifecycle
- Mock: PyAudio, scipy.signal.resample
- Gerçek: state logic, queue ops, string manipulation

### Adım 3: Provider Testleri
- `tests/test_gemini_provider.py` — Gemini API wrapper
- `tests/test_ollama_provider.py` — Ollama HTTP client
- Mock: HTTP çağrıları, stream response
- Gerçek: param handling, error parsing, state logic

### Adım 4: main.py Handler Testleri
- `tests/test_main_handlers.py` — 45 handler, herbiri için:
  - Doğru parametreyle çağrı → başarılı yanıt
  - Eksik parametre → hata mesajı
  - Exception → graceful handling
- Mock: action modülleri (gerçek browser/shell/WhatsApp çalışmaz)
- Gerçek: handler mapping, error string matching

### Adım 5: Pre-commit Hook
- `pre-commit` kurulumu
- Hook: `python -m pytest tests/ -q` (30sn)
- Hook: `basedpyright` LSP check
- Hook: `black` format check (opsiyonel)

### Adım 6: Coverage Baseline
- `coverage run -m pytest tests/`
- `coverage report --fail-under=60`
- Hedef: Mevcut %? → %60 → %80

---

## Sıfır Hata İçin Ek Önlemler

| Önlem | Açıklama | Çaba |
|-------|----------|------|
| **Pre-commit hook** | Commit öncesi test + LSP | 15dk |
| **Coverage gate** | %80 altı PR reddedilir | 10dk |
| **Runtime assertion** | Kritik fonksiyonlarda `assert` ile invariant koruma | 30dk |
| **Type guard** | `isinstance`, `hasattr` ile None/type kontrolü (çoğu zaten var) | 0 |
| **try/except daraltma** | `except:` yerine `except SpecificError:` | 1 saat |
| **Düzenli test koşumu** | Her değişiklikten sonra `pytest tests/ -q` | 30sn |
| **LSP diagnostics** | Her dosya değişiminden sonra kontrol | 5sn |

---

## Timeline

| Adım | Süre | Bağımlılık |
|------|------|-----------|
| 1. Dev tools | 5dk | — |
| 2. orchestrator testleri | 45dk | Adım 1 |
| 3. Provider testleri | 30dk | Adım 1 |
| 4. main.py handler testleri | 1 saat | Adım 1 |
| 5. Pre-commit hook | 15dk | Adım 1 |
| 6. Coverage baseline | 10dk | Adım 2-4 |
| **Toplam** | **~2.5 saat** | |

---

*Oluşturulma: 2026-06-19*
