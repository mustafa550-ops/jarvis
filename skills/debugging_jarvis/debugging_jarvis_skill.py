"""
JARVIS Debugging Skill — Hata Ayıklama ve Düzeltme Ajanı
Ses, UI, skill, sistem ve ağ hatalarını teşhis edip çözüm önerir.
Sistem komutlarını çalıştırarak gerçek teşhis raporu üretir.
"""

from __future__ import annotations
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import traceback
from pathlib import Path

SKILL_ID = "debugging-jarvis-v1"
SKILL_NAME = "Hata Ayıklama"
SKILL_VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = BASE_DIR / "logs"
SKILLS_DIR = BASE_DIR / "skills"


# ── Yardımcılar ─────────────────────────────────────────────────

def _run_cmd(cmd: str, timeout: float = 5.0) -> str:
    """Güvenli shell komut çalıştırma — hata durumunda hata mesajı döndür."""
    try:
        result = subprocess.run(
            shlex.split(cmd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        if result.stderr:
            stderr_clean = result.stderr.strip()
            # ALSA lib uyarılarını gizle (normaldir)
            non_alsa = [l for l in stderr_clean.split("\n") if "pcm_dmix" not in l and "pcm_dsnoop" not in l]
            if non_alsa:
                output += f"\n⚠️ {chr(10).join(non_alsa[:3])}"
        return output or f"(çıktı yok, exit code: {result.returncode})"
    except FileNotFoundError:
        return f"❌ Komut bulunamadı: `{cmd.split()[0]}` — paket kurulu değil."
    except subprocess.TimeoutExpired:
        return f"⚠️ Zaman aşımı ({timeout}s): `{cmd}`"
    except Exception as e:
        return f"⚠️ Hata: {e}"


# Allowlist of safe modules for exec-based import check
_SAFE_MODULES = {
    "sounddevice", "pyaudio", "pyttsx3", "tkinter", "faster_whisper",
    "speech_recognition", "numpy", "scipy", "httpx", "psutil",
    "audio.noise_suppressor",
}


def _check_python_import(module_name: str, import_expr: str = "") -> str:
    """Bir Python modülünün import edilip edilemediğini kontrol et."""
    if not module_name or not isinstance(module_name, str):
        return "❌ Geçersiz modül adı."

    if import_expr and module_name not in _SAFE_MODULES:
        return f"❌ Güvenlik: '{module_name}' için exec() kullanımına izin verilmiyor."

    try:
        if import_expr:
            exec(f"import {module_name}; {import_expr}", {"__builtins__": __builtins__})
        else:
            __import__(module_name)
        return "✅ Başarılı"
    except ImportError as e:
        return f"❌ Import hatası: {e}"
    except Exception as e:
        return f"⚠️ {e}"


def _try_read_log(path: Path, lines: int = 30) -> str:
    """Log dosyasının son N satırını oku."""
    if not path.exists():
        return "❌ Log dosyası bulunamadı."
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        all_lines = content.strip().split("\n")
        tail = all_lines[-lines:]
        # Sadece ERROR/CRITICAL/EXCEPTION içeren satırları filtrele
        error_lines = [l for l in tail if re.search(r"(ERROR|CRITICAL|EXCEPTION|Traceback)", l)]
        if error_lines:
            return "\n".join(error_lines[-15:])
        return f"(son {lines} satırda hata bulunamadı)"
    except Exception as e:
        return f"⚠️ Log okuma hatası: {e}"


# ── Kategori Tanımları ──────────────────────────────────────────

CAT_AUDIO = "ses"
CAT_UI = "ui"
CAT_SKILL = "skill"
CAT_SYSTEM = "sistem"
CAT_NETWORK = "ag"
CAT_GENERAL = "genel"
CAT_LOG = "log"

CATEGORY_LABELS = {
    CAT_AUDIO: "🔴 Ses/SPEECH",
    CAT_UI: "🟡 UI/Tkinter",
    CAT_SKILL: "🟢 Skill/Entegrasyon",
    CAT_SYSTEM: "🔵 Sistem/Platform",
    CAT_NETWORK: "🌐 Ağ/API",
    CAT_GENERAL: "⚪ Genel",
    CAT_LOG: "📋 Log",
}


# ── Intent Sınıflandırma ──────────────────────────────────────

def classify_debug_intent(text: str) -> str:
    """Kullanıcı metninden debug kategorisini belirle."""
    t = text.lower().strip()

    # Log talebi
    if re.search(r"(?:log|kayıt|kayit|gor|gör|oku|bak|goster|göster|son satır|son satir)", t) and \
       re.search(r"(?:log|kayıt|kayit|hata|error|son|output)", t):
        return CAT_LOG

    # Ses
    ses_patterns = [
        r"(?:ses|səs|sos|sosum).*?(?:gelmiyor|yok|gitmiyor|bozuk|kesik|donuk|az|kısık|kisik)",
        r"(?:mikrofon|mikro|mic|mıkrofon).*?(?:calismiyor|çalışmıyor|yok|bozuk|duymuyor|algilamiyor|algılamıyor)",
        r"(?:konusmuyor|konuşmuyor|konusamiyor|konuşamıyor|sessiz|dilsiz)",
        r"(?:dinlemiyor|dinleme|duymuyor|isitmiyor|işitmiyor)",
        r"(?:tts|seslendirme|konusma|konuşma).*?(?:calismiyor|çalışmıyor|hata|bozuk)",
        r"(?:gurultu|gürültü|tıslama|tislama|parazit|ugultu|uğultu|ses bozuk|ses kirli)",
        r"(?:rnnoise|gurultu bastirma|gürültü bastirma).*?(?:yuklenemedi|yüklenemedi|hata)",
        r"(?:hoparlor|hoparlör|speaker|bazı).*?(?:calismiyor|çalışmıyor|ses gelmiyor)",
        r"(?:ses|səs).*?(?:kontrol|ayar|sorun|hata|problem|test)",
    ]
    for p in ses_patterns:
        if re.search(p, t):
            return CAT_AUDIO

    # UI
    ui_patterns = [
        r"(?:ui|arayuz|arayüz|pencere|ekran|goruntu|goruntü).*?(?:dondu|donuyor|kitlendi|kilitlendi|acilmiyor|açılmıyor|yanit vermiyor|yanıt vermiyor)",
        r"(?:main thread|thread).*?(?:hatası|hatasi|sorunu|dondurdu|dondu)",
        r"(?:buton|dugme|düğme|button|tus|tuş).*?(?:calismiyor|çalışmıyor|yanit vermiyor)",
        r"(?:animasyon|orb|halka|cember|çember).*?(?:dondu|takildi|takıldı|calismiyor)",
        r"(?:tkinter|root\.after|safe_call|gui_queue).*?(?:hatası|hatasi)",
        r"(?:ui).*?(?:hatası|hatasi|sorun|problem|bug)",
        r"(?:pencere).*?(?:acilmiyor|açılmıyor|dondu|kayboldu)",
    ]
    for p in ui_patterns:
        if re.search(p, t):
            return CAT_UI

    # Skill
    skill_patterns = [
        r"(?:skill|beceri).*?(?:calismiyor|çalışmıyor|yuklenmedi|yüklenmedi|bulunamadi|bulunamadı|hata|sorun|eklendi)",
        r"(?:bilinmeyen arac|bilinmeyen araç|unknown tool|taninmayan|tanınmayan).*?(?:arac|araç|tool)",
        r"(?:import|module|modul|modül).*?(?:bulunamadi|bulunamadı|hata|error)",
        r"(?:hot.?reload).*?(?:calismiyor|çalışmıyor|sorun|hata)",
        r"(?:route).*?_request.*?(?:bulunamadi|bulunamadı|yok|eksik)",
        r"(?:skill).*?(?:ekle|ekledim|yukle|yükle|kur|calismadi|çalışmadı|olmadi|olmadı)",
    ]
    for p in skill_patterns:
        if re.search(p, t):
            return CAT_SKILL

    # Sistem
    sys_patterns = [
        r"(?:sistem|platform|isletim|işletim|windows|linux|mac).*?(?:uyumsuz|hatası|hatasi|sorunu|calismadi|çalışmadı|desteklenmiyor|patladi|patladı|calismiyor|çalışmıyor)",
        r"(?:winshell|ctypes\.windll).*?(?:hatası|hatasi|import error)",
        r"(?:port|baglanti|bağlantı).*?(?:cakismasi|çakışması|kullaniliyor|kullanılıyor|dolu|mesgul|meşgul)",
        r"(?:sqlite|lock|kilit|veritabani|veritabanı|database).*?(?:hatası|hatasi|kilitlenme)",
        r"(?:json).*?(?:parse|coz|çöz|hatası|hatasi|bozuk|corrupt)",
        r"(?:permission|izin|yetki|erişim|erisim).*?(?:hatası|hatasi|red|yok|engellendi)",
    ]
    for p in sys_patterns:
        if re.search(p, t):
            return CAT_SYSTEM

    # Ağ/API
    net_patterns = [
        r"(?:baglanti|bağlantı|internet|network|ag|ağ).*?(?:yok|kurulamadi|kurulamadı|kesik|kopuk|koptu|zayıf)",
        r"(?:gemini|api).*?(?:hatası|hatasi|quota|limit|429|403|503|timeout|zaman asimi|zaman aşımı)",
        r"(?:ollama|localhost|11434).*?(?:baglanti|bağlantı|baglanamiyor|bağlanamıyor|connection|calismiyor|çalışmıyor|refused|bulunamadi|bulunamadı)",
    ]
    for p in net_patterns:
        if re.search(p, t):
            return CAT_NETWORK

    # Genel debug keyword'leri (sadece İngilizce/teknikal terimler,
    # çok genel Türkçe kelimeler günlük konuşmada false positive üretir)
    general_kw = [
        "hata", "sorun", "problem", "bug", "debug",
        "calismiyor", "çalışmıyor", "calismadi", "çalışmadı",
        "error", "exception", "traceback", "failed", "crash",
    ]
    if any(kw in t for kw in general_kw):
        return CAT_GENERAL

    return "none"


# ── Teşhis Fonksiyonları ────────────────────────────────────────

def _report_header(title: str, emoji: str) -> str:
    sep = "─" * 40
    return f"{emoji} **{title}**\n{sep}"


def _check_audio_system() -> str:
    """Ses sistemi teşhisi — gerçek sistem komutlarını çalıştır."""
    lines = [_report_header("Ses Sistemi Teşhisi", "🔴")]

    # 1. ALSA cihazları
    lines.append("\n**🎤 ALSA Kayıt Cihazları:**")
    lines.append(f"```\n{_run_cmd('arecord -l 2>&1')}\n```")

    # 2. PulseAudio kaynakları
    lines.append("\n**🔊 PulseAudio Kaynakları:**")
    lines.append(f"```\n{_run_cmd('pactl list sources short 2>&1')}\n```")

    # 3. PipeWire (varsa)
    pw = _run_cmd("pw-cli list-objects Node 2>&1 | head -30", timeout=3.0)
    if "Komut bulunamadı" not in pw:
        lines.append("\n**🔊 PipeWire Düğümleri:**")
        lines.append(f"```\n{pw}\n```")

    # 4. ALSA oynatma
    lines.append("\n**🔈 ALSA Oynatma Cihazları:**")
    lines.append(f"```\n{_run_cmd('aplay -l 2>&1')}\n```")

    # 5. Ses seviyeleri
    lines.append("\n**🔉 Ses Seviyeleri:**")
    amixer_out = _run_cmd("amixer 2>&1", timeout=3.0)
    lines.append(f"```\n{amixer_out[:600]}\n```")

    # 6. Python kütüphaneleri
    lines.append("\n**🐍 Python Ses Kütüphaneleri:**")
    for mod, expr in [
        ("sounddevice", "print(sounddevice.query_devices())"),
        ("pyaudio", None),
        ("pyttsx3", None),
    ]:
        if expr:
            result = _check_python_import(mod, expr)
        else:
            result = _check_python_import(mod)
        icon = "✅" if result.startswith("✅") else "❌"
        lines.append(f"   {icon} `{mod}` — {result.split('—')[-1].strip() if '—' in result else result}")

    # 7. RNNoise
    lines.append("\n**🔇 RNNoise:**")
    rnnoise_out = _run_cmd("python3 -c 'from audio.noise_suppressor import NoiseSuppressor; ns = NoiseSuppressor(); print(\"RNNoise OK\")' 2>&1", timeout=5.0)
    lines.append(f"```\n{rnnoise_out[:300]}\n```")

    # 8. Varsayılan ses cihazı
    lines.append("\n**🎚 Varsayılan Ses Kaynağı:**")
    lines.append(f"```\n{_run_cmd('pactl get-default-source 2>&1')}\n```")

    # 9. Audio grup izinleri
    lines.append("\n**👤 Kullanıcı Grupları (audio):**")
    groups_out = _run_cmd("groups", timeout=2.0)
    has_audio = "audio" in groups_out
    lines.append(f"   {'✅' if has_audio else '❌'} audio grubu: {'var' if has_audio else 'YOK — `sudo usermod -aG audio $USER` gerekli'}")

    return "\n".join(lines)


def _check_ui_system() -> str:
    """UI/Tkinter teşhisi."""
    lines = [_report_header("UI/Tkinter Teşhisi", "🟡")]

    # 1. Thread kontrolü
    lines.append("\n**🧵 Mevcut Thread'ler:**")
    try:
        threads = threading.enumerate()
        lines.append(f"   Toplam thread: {len(threads)}")
        for t in threads:
            daemon = "daemon" if t.daemon else "      "
            alive = "✓" if t.is_alive() else "✗"
            lines.append(f"   {alive} {t.name} ({t.ident}) [{daemon}]")
    except Exception as e:
        lines.append(f"   ❌ Thread kontrolü başarısız: {e}")

    # 2. Main thread kontrolü
    try:
        is_main = threading.current_thread() is threading.main_thread()
        lines.append(f"\n   {'✅' if is_main else '⚠️'} Main thread: {'evet' if is_main else 'hayır — UI güncellemeleri riskli!'}")
        lines.append(f"   Current thread: {threading.current_thread().name}")
    except Exception as e:
        lines.append(f"   ❌ {e}")

    # 3. Tkinter varlığı
    tk_result = _check_python_import("tkinter")
    lines.append(f"\n   {tk_result} `tkinter`")

    # 4. GUI Queue (çalışma zamanı)
    lines.append("\n**📤 GUI Queue:**")
    lines.append("   (Bu teşhis JARVIS çalışırken `main.py` içinden GUI'ye erişimle yapılır)")
    lines.append("   ```python")
    lines.append("   # Çalışma zamanında:")
    lines.append("   jarvis.ui._gui_queue.qsize()  # >100 ise tıkanma var")
    lines.append("   threading.enumerate()         # Thread sayısı artıyorsa leak")
    lines.append("   ```")

    # 5. Tkinter güvenli çağrı pattern'i
    lines.append("\n**🛡 Tkinter Thread Güvenliği:**")
    lines.append("   ```python")
    lines.append("   # DOĞRU — safe_call() kullan")
    lines.append("   self.safe_call(self.set_state, \"ERROR\")")
    lines.append("   # veya")
    lines.append("   self._gui_queue.put((func, args, kwargs))")
    lines.append("   ```")
    lines.append("   ❌ Asla: `self.label.config(text=\"hata\")` → RuntimeError!")

    return "\n".join(lines)


def _check_skill_system() -> str:
    """Skill sistemi teşhisi."""
    lines = [_report_header("Skill Sistemi Teşhisi", "🟢")]

    # 1. Skill dizin yapısı
    lines.append("\n**📁 Skill Dizinleri:**")
    if SKILLS_DIR.exists():
        for folder in sorted(SKILLS_DIR.iterdir()):
            if not folder.is_dir():
                continue
            skill_file = folder / f"{folder.name}_skill.py"
            init_file = folder / "__init__.py"
            md_file = folder / "SKILL.md"
            parts = []
            parts.append("✅" if skill_file.exists() else "❌")
            parts.append("✅" if md_file.exists() or folder.name == "greeting" else "⬜")
            parts.append("✅" if init_file.exists() else "⬜")
            lines.append(f"   [{'/'.join(parts)}] {folder.name}/")
    else:
        lines.append("   ❌ skills/ dizini bulunamadı!")

    # 2. Skill Manager (çalışma zamanı)
    lines.append("\n**⚙️ Skill Manager:**")
    lines.append("   (Bu teşhis JARVIS çalışırken daha detaylı olur)")
    lines.append("   ```python")
    lines.append("   from core.skill_manager import get_skill_manager")
    lines.append("   sm = get_skill_manager()")
    lines.append("   print(sm.list_skills())          # Aktif skill'ler")
    lines.append("   print(sm.list_all_skills())      # Detaylı bilgi")
    lines.append("   print(sm.get_stats())            # İstatistikler")
    lines.append("   ```")

    # 3. Import kontrolü — tüm _skill.py dosyaları
    lines.append("\n**🔍 Skill Import Kontrolü:**")
    import_count = 0
    import_fail = 0
    for folder in sorted(SKILLS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        skill_file = folder / f"{folder.name}_skill.py"
        if not skill_file.exists():
            continue
        try:
            mod_name = f"skills.{folder.name}.{folder.name}_skill"
            import importlib.util
            spec = importlib.util.spec_from_file_location(mod_name, str(skill_file))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                route_fn = getattr(mod, f"route_{folder.name}_request", None)
                if route_fn:
                    import_count += 1
                else:
                    import_fail += 1
                    lines.append(f"   ⚠️ {folder.name}_skill.py → route_{folder.name}_request() bulunamadı")
            else:
                import_fail += 1
                lines.append(f"   ❌ {folder.name}: spec alınamadı")
        except Exception as e:
            import_fail += 1
            lines.append(f"   ❌ {folder.name}: {e}")

    lines.append(f"\n   ✅ {import_count} skill başarıyla yüklendi" + (f", ⚠️ {import_fail} hatalı" if import_fail else ""))

    return "\n".join(lines)


def _check_system_platform() -> str:
    """Sistem/platform teşhisi."""
    lines = [_report_header("Sistem/Platform Teşhisi", "🔵")]

    # 1. Platform bilgisi
    lines.append(f"\n**💻 Platform:**")
    lines.append(f"   İşletim: {os.name} ({sys.platform})")
    lines.append(f"   Python:  {sys.version.split()[0]}")
    lines.append(f"   Makine:  {os.uname().nodename}")

    # 2. Port kontrolü
    lines.append("\n**🔌 Port Kontrolü:**")
    for port, name in [("11434", "Ollama"), ("8765", "Cron Web UI")]:
        port_result = _run_cmd(f"ss -tlnp | grep {port} || lsof -i :{port} 2>/dev/null || echo 'Port {port} boş'", timeout=3.0)
        if "boş" in port_result:
            lines.append(f"   ⬜ Port {port} ({name}): boş")
        else:
            lines.append(f"   ✅ Port {port} ({name}): kullanımda")

    # 3. Ses cihazı izinleri
    lines.append("\n**🔊 Ses Cihazı İzinleri:**")
    snd_devices = list(Path("/dev/snd").glob("*")) if Path("/dev/snd").exists() else []
    if snd_devices:
        lines.append(f"   {len(snd_devices)} cihaz bulundu")
        for d in snd_devices[:5]:
            try:
                st = d.stat()
                lines.append(f"   {'✅' if st.st_mode & 0o004 else '❌'} {d.name} (okunabilir: {bool(st.st_mode & 0o004)})")
            except OSError:
                lines.append(f"   ❌ {d.name} (erişilemiyor)")
    else:
        lines.append("   ❌ /dev/snd/ bulunamadı — ses donanımı yok veya izin yetersiz")

    # 4. Grup üyelikleri
    lines.append("\n**👤 Grup Üyelikleri:**")
    groups_out = _run_cmd("groups", timeout=2.0)
    for g in ["audio", "video", "plugdev", "wheel", "sudo"]:
        if g in groups_out:
            lines.append(f"   ✅ {g} grubunda")
    lines.append(f"\n   Tüm gruplar: {groups_out}")

    # 5. Bellek kullanımı
    lines.append("\n**💾 Bellek Durumu:**")
    mem_out = _run_cmd("free -h", timeout=3.0)
    lines.append(f"```\n{mem_out[:300]}\n```")

    return "\n".join(lines)


def _check_network() -> str:
    """Ağ/API teşhisi."""
    lines = [_report_header("Ağ/API Teşhisi", "🌐")]

    # 1. Temel bağlantı
    lines.append("\n**🌍 Temel Bağlantı:**")
    ping_out = _run_cmd("ping -c 1 -W 2 google.com 2>&1", timeout=5.0)
    if "1 received" in ping_out or "1 packets transmitted, 1 received" in ping_out:
        lines.append("   ✅ İnternet bağlantısı var")
    elif "unknown host" in ping_out.lower() or "Name or service not known" in ping_out:
        lines.append("   ❌ DNS çözümleme hatası — internet yok")
    else:
        lines.append(f"   ⚠️ {ping_out[:200]}")

    # 2. Ollama
    lines.append("\n**🤖 Ollama Durumu:**")
    ollama_out = _run_cmd("curl -s --max-time 3 http://localhost:11434/api/tags 2>&1", timeout=5.0)
    if "models" in ollama_out or "{" in ollama_out:
        lines.append("   ✅ Ollama çalışıyor")
        try:
            data = json.loads(ollama_out)
            models = data.get("models", [])
            if models:
                lines.append(f"   📦 Yüklü modeller ({len(models)}):")
                for m in models[:5]:
                    name = m.get("name", "?")
                    size = m.get("size", 0)
                    size_str = f"{size / 1e9:.1f}GB" if size else "?"
                    lines.append(f"      - {name} ({size_str})")
            else:
                lines.append("   ⚠️ Hiç model yüklü değil — `ollama pull qwen2.5:1.5b`")
        except json.JSONDecodeError:
            lines.append(f"   ⚠️ Yanıt: {ollama_out[:200]}")
    elif "Connection refused" in ollama_out:
        lines.append("   ❌ Ollama çalışmıyor — `ollama serve` başlatın")
    elif "Could not resolve host" in ollama_out:
        lines.append("   ❌ localhost çözülemedi — hosts dosyasını kontrol et")
    else:
        lines.append(f"   ⚠️ {ollama_out[:200]}")

    # 3. Gemini API
    lines.append("\n**☁️ Gemini API:**")
    api_keys_path = BASE_DIR / "config" / "api_keys.json"
    if api_keys_path.exists():
        try:
            keys = json.loads(api_keys_path.read_text(encoding="utf-8"))
            key = keys.get("gemini_api_key", "")
            if key and key != "AIzaSy...":
                masked = key[:8] + "..." + key[-4:]
                lines.append(f"   ✅ API key mevcut: {masked}")
                lines.append(f"   🔍 Doğrulama: `curl -s \"https://generativelanguage.googleapis.com/v1beta/models?key={key[:8]}...\"`")
            else:
                lines.append("   ❌ API key boş veya varsayılan")
        except (json.JSONDecodeError, Exception) as e:
            lines.append(f"   ❌ api_keys.json okunamadı: {e}")
    else:
        lines.append("   ❌ config/api_keys.json bulunamadı")

    # 4. Ollama model kontrolü
    lines.append("\n**📦 Ollama Model (yapılandırma):**")
    if api_keys_path.exists():
        try:
            keys = json.loads(api_keys_path.read_text(encoding="utf-8"))
            model = keys.get("ollama_model", "qwen2.5:1.5b")
            backend = keys.get("backend_type", "gemini")
            lines.append(f"   Backend: {backend}")
            lines.append(f"   Model: {model}")
            lines.append(f"   TTS Voice: {keys.get('ollama_tts_voice', 'piper-fahrettin')}")
        except Exception:
            pass

    return "\n".join(lines)


def _check_logs() -> str:
    """Log dosyası teşhisi."""
    lines = [_report_header("Log Analizi", "📋")]

    log_file = LOGS_DIR / "jarvis.log"
    if not log_file.exists():
        # Alt dizinlerde ara
        for p in [BASE_DIR / "logs", Path("logs")]:
            p2 = p / "jarvis.log"
            if p2.exists():
                log_file = p2
                break
        else:
            # Hiçbir yerde yok
            lines.append("\n❌ `logs/jarvis.log` bulunamadı.")
            # Logs klasörü var mı?
            if LOGS_DIR.exists():
                files = list(LOGS_DIR.iterdir())
                if files:
                    lines.append(f"\n📁 logs/ içeriği: {', '.join(f.name for f in files[:10])}")
                else:
                    lines.append("\n📁 logs/ klasörü boş.")
            else:
                lines.append("\n📁 logs/ klasörü yok. JARVIS henüz çalıştırılmamış olabilir.")
            return "\n".join(lines)

    # Dosya bilgisi
    try:
        stat = log_file.stat()
        size_kb = stat.st_size / 1024
        from datetime import datetime
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"\n📄 `{log_file}` ({size_kb:.0f} KB, son güncelleme: {mtime})")
    except Exception as e:
        lines.append(f"\n⚠️ Dosya bilgisi alınamadı: {e}")

    # Son 50 satırdaki hatalar
    lines.append(f"\n**🔴 Son 50 satırda hata/uyarı:**")
    lines.append(f"```\n{_try_read_log(log_file, 50)[:800]}\n```")

    # İstatistik
    try:
        content = log_file.read_text(encoding="utf-8", errors="replace")
        all_lines = content.split("\n")
        error_count = sum(1 for l in all_lines if "ERROR" in l)
        crit_count = sum(1 for l in all_lines if "CRITICAL" in l)
        warn_count = sum(1 for l in all_lines if "WARNING" in l)
        lines.append(f"\n**📊 Log İstatistikleri:**")
        lines.append(f"   🔴 ERROR: {error_count}")
        lines.append(f"   🟠 CRITICAL: {crit_count}")
        lines.append(f"   🟡 WARNING: {warn_count}")
        lines.append(f"   📝 Toplam satır: {len(all_lines)}")
    except Exception as e:
        lines.append(f"\n⚠️ İstatistik alınamadı: {e}")

    return "\n".join(lines)


def _general_diagnostics() -> str:
    """Genel sistem durumu özeti."""
    lines = [_report_header("Genel Sistem Durumu", "⚪")]

    # Platform
    lines.append(f"\n**💻 Platform:** {os.name} / {sys.platform}")
    lines.append(f"**🐍 Python:** {sys.version.split()[0]}")

    # Çalışma dizini
    lines.append(f"\n**📂 Çalışma Dizini:** {BASE_DIR}")

    # Kritik dosyaların varlığı
    lines.append("\n**📄 Kritik Dosyalar:**")
    for name, path in [
        ("main.py", BASE_DIR / "main.py"),
        ("ui.py", BASE_DIR / "ui.py"),
        ("app_config.py", BASE_DIR / "app_config.py"),
        ("config/api_keys.json", BASE_DIR / "config" / "api_keys.json"),
        ("core/skill_manager.py", BASE_DIR / "core" / "skill_manager.py"),
        ("audio/noise_suppressor.py", BASE_DIR / "audio" / "noise_suppressor.py"),
    ]:
        exists = path.exists()
        lines.append(f"   {'✅' if exists else '❌'} {name}")

    # Bellek
    try:
        import psutil
        mem = psutil.virtual_memory()
        lines.append(f"\n**💾 Bellek:** {mem.percent}% kullanımda ({mem.used / 1e9:.1f}GB / {mem.total / 1e9:.1f}GB)")
        cpu = psutil.cpu_percent(interval=0.1)
        lines.append(f"**⚙️ CPU:** {cpu}%")
    except ImportError:
        lines.append("\n**💾 Bellek:** `psutil` kurulu değil — `pip install psutil`")
    except Exception as e:
        lines.append(f"\n⚠️ {e}")

    # Öneriler
    lines.append(f"\n**💡 Öneriler:**")
    lines.append("   Daha spesifik bir hata için şunlardan birini deneyin:")
    lines.append('   • "sesim gelmiyor" — Ses sistemi teşhisi')
    lines.append('   • "UI dondu" — UI/Tkinter teşhisi')
    lines.append('   • "skill calismiyor" — Skill sistemi teşhisi')
    lines.append('   • "log göster" — Log analizi')
    lines.append('   • "ollama baglanamiyor" — Ağ/API teşhisi')

    return "\n".join(lines)


# ── Debug Çalıştırıcı ──────────────────────────────────────────

CATEGORY_HANDLERS = {
    CAT_AUDIO: _check_audio_system,
    CAT_UI: _check_ui_system,
    CAT_SKILL: _check_skill_system,
    CAT_SYSTEM: _check_system_platform,
    CAT_NETWORK: _check_network,
    CAT_LOG: _check_logs,
    CAT_GENERAL: _general_diagnostics,
}


def execute_debug(category: str) -> str:
    """Debug kategorisini çalıştır ve sonucu döndür."""
    handler = CATEGORY_HANDLERS.get(category, _general_diagnostics)
    try:
        body = handler()
        label = CATEGORY_LABELS.get(category, "⚪ Genel")
        return (
            f"🛠 **JARVIS Debug Asistanı — {label}**\n\n"
            f"{body}\n\n"
            f"─" * 40 + "\n"
            f"💡 Bu teşhis yardımcı oldu mu? Daha spesifik bir hata detayı verebilirsiniz."
        )
    except Exception as e:
        traceback.print_exc()
        return (
            f"❌ Debug sırasında hata oluştu: {e}\n\n"
            f"Logları kontrol edin: `tail -50 logs/jarvis.log`"
        )


# ── Route Fonksiyonu (Skill Manager API) ───────────────────────

def route_debugging_jarvis_request(user_text: str) -> str | None:
    """Kullanıcı metnini analiz eder, debug skill'i ile eşleşirse çalıştırır."""
    if not user_text or not user_text.strip():
        return None

    try:
        category = classify_debug_intent(user_text)
        if category == "none":
            return None

        return execute_debug(category)

    except Exception:
        traceback.print_exc()
        return "❌ Debug skill'inde hata: logları kontrol edin — `tail -50 logs/jarvis.log`"
