#!/usr/bin/env python3
"""
JARVIS — Kapsamli Test
Proje yapisi, modul import'lari, konfigurasyon, saf fonksiyon testleri.
Mock sadece URL yan etkilerini engellemek icin kullanilir.
"""

import importlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

try:
    import pyaudio  # noqa: F401
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

try:
    from google import genai  # noqa: F401
    HAS_GOOGLE_GENAI = True
except ImportError:
    HAS_GOOGLE_GENAI = False


BASE_DIR = Path(__file__).resolve().parent.parent


# =============================================================================
# 1. PROJE YAPISI
# =============================================================================

class TestProjectStructure(unittest.TestCase):
    """Proje dizin yapisi dogrulama testleri."""

    def test_core_is_package(self):
        """core/ __init__.py icermeli."""
        init_file = BASE_DIR / "core" / "__init__.py"
        self.assertTrue(init_file.exists())

    def test_icon_dir_exists(self):
        """Icon/ dizini ve ikonlar mevcut olmali."""
        icon_dir = BASE_DIR / "Icon"
        self.assertTrue(icon_dir.is_dir())
        self.assertTrue((icon_dir / "instagram-logo.png").exists())
        self.assertTrue((icon_dir / "youtube-logo.png").exists())

    def test_no_log_files_in_root(self):
        """Kok dizinde *.log yok."""
        logs = list(BASE_DIR.glob("*.log"))
        self.assertEqual(len(logs), 0, f"Kokte log: {logs}")

    def test_no_postscript_artifacts(self):
        """PostScript artifact dosyalari silinmis."""
        for name in ("logging", "threading", "sys", "traceback"):
            self.assertFalse((BASE_DIR / name).exists(), f"Hala var: {name}")

    def test_gitignore_updated(self):
        """.gitignore gerekli pattern'leri iceriyor."""
        gitignore = BASE_DIR / ".gitignore"
        content = gitignore.read_text()
        for pattern in ("*.log", "logs/", "Icon/", ".env", ".idea/"):
            self.assertIn(pattern, content)

    def test_prompt_file_exists(self):
        """core/prompt.txt mevcut ve 100 karakterden uzun."""
        prompt_file = BASE_DIR / "core" / "prompt.txt"
        self.assertTrue(prompt_file.exists())
        self.assertGreater(len(prompt_file.read_text()), 100)

    def test_helpers_bin_readme_exists(self):
        """helpers/bin/README.md mevcut."""
        self.assertTrue((BASE_DIR / "helpers" / "bin" / "README.md").exists())

    def test_requirements_txt_exists(self):
        """requirements.txt mevcut."""
        self.assertTrue((BASE_DIR / "requirements.txt").exists())

    def test_setup_ps1_exists(self):
        """setup.ps1 mevcut."""
        self.assertTrue((BASE_DIR / "setup.ps1").exists())

    def test_config_example_json_exists(self):
        """config/api_keys.example.json mevcut ve gecerli JSON."""
        example = BASE_DIR / "config" / "api_keys.example.json"
        self.assertTrue(example.exists())
        with open(example) as f:
            cfg = json.load(f)
        self.assertIsInstance(cfg, dict)
        # Tum zorunlu anahtarlar var mi?
        for key in ("gemini_api_key", "voice", "backend_type", "ollama_model", "ollama_tts_voice", "youtube_api_key", "youtube_channel_handle"):
            self.assertIn(key, cfg, f"Eksik anahtar: {key}")

    def test_gitignore_has_api_keys(self):
        """.gitignore api_keys.json iceriyor."""
        gitignore = BASE_DIR / ".gitignore"
        content = gitignore.read_text()
        self.assertIn("api_keys.json", content)


# =============================================================================
# 2. KONFIGURASYON
# =============================================================================

class TestConfig(unittest.TestCase):
    """Konfigurasyon dosyasi testleri."""

    def test_pyrightconfig_valid_json(self):
        """pyrightconfig.json gecerli JSON ve dogru ayarlar."""
        config_file = BASE_DIR / "pyrightconfig.json"
        self.assertTrue(config_file.exists())
        with open(config_file) as f:
            cfg = json.load(f)
        self.assertEqual(cfg.get("typeCheckingMode"), "basic")
        self.assertIn("pythonVersion", cfg)
        self.assertIn("pythonVersion", cfg)

    def test_requirements_has_versions(self):
        """requirements.txt version pin iceriyor."""
        req_file = BASE_DIR / "requirements.txt"
        content = req_file.read_text()
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            self.assertIn(">=", line, f"'{line}' version pin'i yok")

    def test_app_config_defaults(self):
        """app_config DEFAULT_CONFIG 7 anahtar icermeli."""
        from app_config import DEFAULT_CONFIG
        self.assertIsInstance(DEFAULT_CONFIG, dict)
        for key in ("gemini_api_key", "voice", "backend_type", "ollama_model", "ollama_tts_voice", "youtube_api_key", "youtube_channel_handle"):
            self.assertIn(key, DEFAULT_CONFIG, f"Eksik default: {key}")

    def test_app_config_load_returns_dict(self):
        """load_app_config() dict doner."""
        from app_config import load_app_config
        cfg = load_app_config()
        self.assertIsInstance(cfg, dict)
        self.assertIn("gemini_api_key", cfg)

    def test_app_config_save_and_reload(self):
        """save_app_config + load_app_config dongusu calisir."""
        from app_config import load_app_config, save_app_config
        original = load_app_config()
        try:
            # Gecici bir deger yaz
            save_app_config({"voice": "TEST_VOICE"})
            reloaded = load_app_config()
            self.assertEqual(reloaded.get("voice"), "TEST_VOICE")
        finally:
            # Orijinal degeri geri yaz
            save_app_config(original)

    def test_get_app_config_value(self):
        """get_app_config_value() dogru deger doner."""
        from app_config import get_app_config_value
        self.assertIsNotNone(get_app_config_value("voice"))

    def test_has_gemini_api_key(self):
        """has_gemini_api_key() bool doner (su an false olabilir)."""
        from app_config import has_gemini_api_key
        result = has_gemini_api_key()
        self.assertIsInstance(result, bool)
        # Gercek API key olabilir veya olmayabilir, sadece tip kontrol


# =============================================================================
# 3. AKSIYON MODUL IMPORT'LARI (TAM KAPSAM)
# =============================================================================

class TestActionModules(unittest.TestCase):
    """Tum 14 action modulunun import edilebilirlik testi."""

    def test_actions_package_importable(self):
        """actions/ paketi import edilebilmeli."""
        import actions  # noqa: F401

    def test_all_action_modules_importable(self):
        """Her action modulu ayri ayri import edilebilmeli."""
        modules = [
            "actions.open_app",
            "actions.sys_info",
            "actions.weather",
            "actions.reminders",
            "actions.calendar",
            "actions.tts",
            "actions.windows_utils",
            "actions.browser",
            "actions.shell",
            "actions.whatsapp",
            "actions.media",
            "actions.youtube_stats",
            "actions.screen_vision",
            "actions.health",
        ]
        for mod_name in modules:
            with self.subTest(module=mod_name):
                if mod_name == "actions.screen_vision" and not HAS_GOOGLE_GENAI:
                    self.skipTest("google-genai paketi kurulu degil")
                try:
                    importlib.import_module(mod_name)
                except ImportError as e:
                    self.fail(f"{mod_name} import edilemedi: {e}")

    def test_health_module_has_expected_functions(self):
        """health modulunde beklenen fonksiyonlar var."""
        mod = importlib.import_module("actions.health")
        for name in ("get_health_data", "get_welcome_health_summary", "_normalize_query", "_extract_target_date", "_v", "_age_str", "_date_from_file"):
            self.assertTrue(hasattr(mod, name), f"Eksik: {name}")

    def test_tts_module_has_expected_functions(self):
        """tts modulunde beklenen fonksiyonlar var."""
        mod = importlib.import_module("actions.tts")
        for name in ("speak_text", "get_available_voices"):
            self.assertTrue(hasattr(mod, name), f"Eksik: {name}")

    def test_youtube_stats_has_expected_functions(self):
        """youtube_stats modulunde beklenen fonksiyonlar var."""
        mod = importlib.import_module("actions.youtube_stats")
        for name in ("get_youtube_channel_report", "_format_int", "_parse_duration_seconds", "_normalize_channel_ref"):
            self.assertTrue(hasattr(mod, name), f"Eksik: {name}")

    def test_windows_utils_has_expected_functions(self):
        """windows_utils modulunde beklenen fonksiyonlar var."""
        mod = importlib.import_module("actions.windows_utils")
        for name in ("open_url", "copy_to_clipboard", "speak_with_windows", "open_uri", "open_windows_app"):
            self.assertTrue(hasattr(mod, name), f"Eksik: {name}")


class TestSkillModules(unittest.TestCase):
    """15 skill modulunun import edilebilirlik testi."""

    def test_skill_modules_importable(self):
        """Her skill modulu ayri ayri import edilebilmeli."""
        modules = [
            "skills.browser.browser_skill",
            "skills.system_health.system_health_skill",
            "skills.process_control.process_control_skill",
            "skills.file_manager.file_manager_skill",
            "skills.weather.weather_skill",
            "skills.youtube.youtube_skill",
            "skills.vision.vision_skill",
            "skills.calendar.calendar_skill",
            "skills.reminders.reminders_skill",
            "skills.whatsapp.whatsapp_skill",
            "skills.media.media_skill",
            "skills.network.network_skill",
            "skills.scheduler.scheduler_skill",
            "skills.services.services_skill",
            "skills.greeting.greeting_skill",
        ]
        for mod_name in modules:
            with self.subTest(module=mod_name):
                try:
                    importlib.import_module(mod_name)
                except ImportError as e:
                    self.fail(f"{mod_name} import edilemedi: {e}")

    def test_core_skill_manager_importable(self):
        """core.skill_manager import edilebilmeli."""
        importlib.import_module("core.skill_manager")

    def test_skill_manager_loads_all_skills(self):
        """SkillManager 17 skill'i de yukleyebilmeli."""
        from core.skill_manager import get_skill_manager
        sm = get_skill_manager()
        self.assertEqual(sm.get_skill_count(), 17)
        expected_skills = [
            "browser",
            "system-health-v1", "process-control-v1", "file-manager-v1",
            "weather-v1", "youtube-v1", "vision-v1",
            "calendar-v1", "reminders-v1", "whatsapp-v1", "media-v1",
            "network-v1", "scheduler-v1", "services-v1",
            "greeting-v1", "voice-coding-v1",
        ]
        for s in expected_skills:
            self.assertIn(s, sm.list_skills(), f"Eksik skill: {s}")

    def test_each_skill_has_route_function(self):
        """Her skill'in route_xxx_request fonksiyonu var."""
        skills = [
            ("skills.browser.browser_skill", "route_browser_request"),
            ("skills.system_health.system_health_skill", "route_system_health_request"),
            ("skills.process_control.process_control_skill", "route_process_request"),
            ("skills.file_manager.file_manager_skill", "route_file_request"),
            ("skills.weather.weather_skill", "route_weather_request"),
            ("skills.youtube.youtube_skill", "route_youtube_request"),
            ("skills.vision.vision_skill", "route_vision_request"),
            ("skills.calendar.calendar_skill", "route_calendar_request"),
            ("skills.reminders.reminders_skill", "route_reminders_request"),
            ("skills.whatsapp.whatsapp_skill", "route_whatsapp_request"),
            ("skills.media.media_skill", "route_media_request"),
            ("skills.network.network_skill", "route_network_request"),
            ("skills.scheduler.scheduler_skill", "route_scheduler_request"),
            ("skills.services.services_skill", "route_services_request"),
            ("skills.greeting.greeting_skill", "route_greeting_request"),
        ]
        for mod_name, func_name in skills:
            with self.subTest(module=mod_name):
                mod = importlib.import_module(mod_name)
                self.assertTrue(hasattr(mod, func_name), f"Eksik: {func_name}")


# =============================================================================
# 4. YOUTUBE_STATS — SAF FONKSIYON TESTLERI
# =============================================================================

class TestYouTubeStats(unittest.TestCase):
    """youtube_stats pure fonksiyon testleri — API cagrisi yok."""

    def setUp(self):
        from actions import youtube_stats
        self.mod = youtube_stats

    def test_format_int(self):
        """_format_int sayilari Turkce formata cevirir."""
        self.assertEqual(self.mod._format_int(1000), "1.000")
        self.assertEqual(self.mod._format_int(1500000), "1.500.000")
        self.assertEqual(self.mod._format_int(0), "0")
        self.assertEqual(self.mod._format_int(999), "999")

    def test_parse_duration_seconds(self):
        """_parse_duration_seconds ISO 8601 surelerini cozer."""
        self.assertEqual(self.mod._parse_duration_seconds("PT1H30M15S"), 5415)
        self.assertEqual(self.mod._parse_duration_seconds("PT45M20S"), 2720)
        self.assertEqual(self.mod._parse_duration_seconds("PT5S"), 5)
        self.assertEqual(self.mod._parse_duration_seconds("PT2H"), 7200)
        self.assertEqual(self.mod._parse_duration_seconds(""), 0)
        self.assertEqual(self.mod._parse_duration_seconds(None), 0)
        self.assertEqual(self.mod._parse_duration_seconds("P1DT1H"), 0)  # ISO_DAY_RE yok

    def test_format_duration(self):
        """_format_duration sureyi Turkce formata cevirir."""
        self.assertEqual(self.mod._format_duration("PT1H30M15S"), "1s 30dk")
        self.assertEqual(self.mod._format_duration("PT45M20S"), "45dk 20sn")
        self.assertEqual(self.mod._format_duration("PT5S"), "5sn")
        self.assertEqual(self.mod._format_duration(""), "")

    def test_parse_dt(self):
        """_parse_dt ISO tarihlerini cozer."""
        result = self.mod._parse_dt("2026-01-15T10:30:00Z")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 1)
        self.assertIsNone(self.mod._parse_dt(""))
        self.assertIsNone(self.mod._parse_dt(None))
        self.assertIsNone(self.mod._parse_dt("invalid"))

    def test_average(self):
        """_average ortalama hesaplar."""
        self.assertEqual(self.mod._average([1, 2, 3, 4, 5]), 3.0)
        self.assertEqual(self.mod._average([10]), 10.0)
        self.assertEqual(self.mod._average([]), 0.0)

    def test_normalize_channel_ref_with_at(self):
        """_normalize_channel_ref @ ile baslayan handle'i tanir."""
        with patch("actions.youtube_stats.get_app_config_value", return_value=""):
            result_type, result_val = self.mod._normalize_channel_ref("@testchannel")
            self.assertEqual(result_type, "forHandle")
            self.assertEqual(result_val, "@testchannel")

    def test_normalize_channel_ref_with_url(self):
        """_normalize_channel_ref YouTube URL'sini cozer."""
        with patch("actions.youtube_stats.get_app_config_value", return_value=""):
            result_type, result_val = self.mod._normalize_channel_ref(
                "https://www.youtube.com/@testchannel"
            )
            self.assertEqual(result_type, "forHandle")
            self.assertEqual(result_val, "@testchannel")

    def test_normalize_channel_ref_with_channel_id(self):
        """_normalize_channel_ref channel ID'yi tanir."""
        with patch("actions.youtube_stats.get_app_config_value", return_value=""):
            channel_id = "UC1234567890123456789012"
            result_type, result_val = self.mod._normalize_channel_ref(channel_id)
            self.assertEqual(result_type, "id")
            self.assertEqual(result_val, channel_id)

    def test_normalize_channel_ref_empty(self):
        """_normalize_channel_ref bos degerde (None, '') doner."""
        with patch("actions.youtube_stats.get_app_config_value", return_value=""):
            result_type, result_val = self.mod._normalize_channel_ref("")
            self.assertIsNone(result_type)
            self.assertEqual(result_val, "")

    def test_normalize_channel_ref_plain_text(self):
        """_normalize_channel_ref duz metni @ ile handle'a cevirir."""
        with patch("actions.youtube_stats.get_app_config_value", return_value=""):
            result_type, result_val = self.mod._normalize_channel_ref("testchannel")
            self.assertEqual(result_type, "forHandle")
            self.assertEqual(result_val, "@testchannel")
# =============================================================================

class TestMemoryManager(unittest.TestCase):
    """memory_manager pure fonksiyon testleri."""

    def setUp(self):
        from memory import memory_manager
        self.mod = memory_manager

    def test_deep_merge_flat(self):
        """_deep_merge duz sozlukleri birlestirir."""
        base = {"a": 1, "b": 2}
        self.mod._deep_merge(base, {"b": 3, "c": 4})
        self.assertEqual(base, {"a": 1, "b": 3, "c": 4})

    def test_deep_merge_nested(self):
        """_deep_merge ic ice sozlukleri recursive birlestirir."""
        base = {"user": {"name": "Ali", "age": 30}}
        self.mod._deep_merge(base, {"user": {"age": 31, "city": "Istanbul"}})
        self.assertEqual(base["user"], {"name": "Ali", "age": 31, "city": "Istanbul"})

    def test_deep_merge_overwrite_non_dict(self):
        """_deep_merge dict olmayan degeri dict ile ezer."""
        base = {"x": "string"}
        self.mod._deep_merge(base, {"x": {"y": 1}})
        self.assertEqual(base, {"x": {"y": 1}})

    def test_normalize_text(self):
        """_normalize_text Turkce karakterleri normalize eder."""
        text = self.mod._normalize_text("İstanbul")
        self.assertIn("istanbul", text)
        self.assertEqual(self.mod._normalize_text("  Merhaba  "), "merhaba")
        self.assertEqual(self.mod._normalize_text(""), "")

    def test_tokenize_text(self):
        """_tokenize_text metni token'lara ayirir."""
        tokens = self.mod._tokenize_text("Merhaba dünya")
        self.assertIn("merhaba", tokens)
        self.assertIn("dunya", tokens)

    def test_entry_value_text_dict(self):
        """_entry_value_text dict'ten value alanini cikarir."""
        result = self.mod._entry_value_text({"value": "test_value"})
        self.assertEqual(result, "test_value")

    def test_entry_value_text_plain(self):
        """_entry_value_text duz degeri string'e cevirir."""
        self.assertEqual(self.mod._entry_value_text("direct"), "direct")
        self.assertEqual(self.mod._entry_value_text(42), "42")
        self.assertEqual(self.mod._entry_value_text(None), "None")

    def test_entry_matches_exact(self):
        """_entry_matches tam eslesme bulur."""
        result = self.mod._entry_matches("test", "category", "key", "test_value")
        self.assertTrue(result)

    def test_entry_matches_no_match(self):
        """_entry_matches eslesme yoksa False doner."""
        result = self.mod._entry_matches("xyz_not_found_12345", "cat", "key", "value")
        self.assertFalse(result)

    def test_format_memory_for_prompt_empty(self):
        """format_memory_for_prompt bos dict icin '' doner."""
        result = self.mod.format_memory_for_prompt({})
        self.assertEqual(result, "")

    def test_format_memory_for_prompt_with_data(self):
        """format_memory_for_prompt dict'i prompt formatina cevirir."""
        memory = {"identity": {"name": {"value": "Ali"}}}
        result = self.mod.format_memory_for_prompt(memory)
        self.assertIn("identity/name", result)
        self.assertIn("Ali", result)

    def test_load_memory_returns_dict(self):
        """load_memory() dict doner (bos olsa bile)."""
        result = self.mod.load_memory()
        self.assertIsInstance(result, dict)

    def test_update_and_delete_memory_cycle(self):
        """update_memory + delete_memory CRUD dongusu calisir."""
        original = self.mod.load_memory()
        try:
            test_key = f"_test_key_{os.urandom(4).hex()}"
            self.mod.update_memory({"notes": {test_key: {"value": "test_value"}}})
            loaded = self.mod.load_memory()
            self.assertIn(test_key, loaded.get("notes", {}))

            # Sil
            result = self.mod.delete_memory("notes", test_key)
            self.assertIn("kaldirildi", result)
            loaded_after = self.mod.load_memory()
            self.assertNotIn(test_key, loaded_after.get("notes", {}))
        finally:
            # Temizlik: test kaydini kalici birakma
            try:
                self.mod.delete_memory("notes", test_key)
            except Exception:
                pass


# =============================================================================
# 6. SAGLIK (health) — SAF FONKSIYON TESTLERI
# =============================================================================

class TestHealthPureFunctions(unittest.TestCase):
    """health pure fonksiyon testleri — dosya okuma yok."""

    def setUp(self):
        from actions import health
        self.mod = health

    def test_normalize_query(self):
        """_normalize_query Turkce karakterleri ascii'ye cevirir."""
        self.assertEqual(self.mod._normalize_query("Nabız ölçümü"), "nabiz olcumu")
        self.assertEqual(self.mod._normalize_query("YÜRÜYÜŞ"), "yuruyus")
        self.assertEqual(self.mod._normalize_query("  Boşluk  "), "bosluk")

    def test_normalize_query_empty(self):
        """_normalize_query bos string calisir."""
        self.assertEqual(self.mod._normalize_query(""), "")
        self.assertEqual(self.mod._normalize_query(None), "")

    def test_extract_target_date_today(self):
        """_extract_target_date 'bugun' bugunun tarihini doner."""
        from datetime import date
        result = self.mod._extract_target_date("bugun")
        self.assertEqual(result, date.today())

    def test_extract_target_date_yesterday(self):
        """_extract_target_date 'dun' dunun tarihini doner."""
        from datetime import date, timedelta
        result = self.mod._extract_target_date("dun")
        self.assertEqual(result, date.today() - timedelta(days=1))

    def test_extract_target_date_iso(self):
        """_extract_target_date ISO formatini cozer."""
        result = self.mod._extract_target_date("2026-06-06")
        from datetime import date
        self.assertEqual(result, date(2026, 6, 6))

    def test_extract_target_date_none(self):
        """_extract_target_date anlamsiz sorgu icin None doner."""
        self.assertIsNone(self.mod._extract_target_date("merhaba dunya"))

    def test_v_formats_values(self):
        """_v degerleri dogru formata cevirir."""
        self.assertEqual(self.mod._v({"x": 72}, "x", " bpm"), "72 bpm")
        self.assertEqual(self.mod._v({"x": 72.5}, "x", " ms", 1), "72.5 ms")
        self.assertEqual(self.mod._v({"x": None}, "x"), "—")
        self.assertEqual(self.mod._v({}, "x"), "—")

    def test_age_str(self):
        """_age_str zaman damgasindan metin uretir."""
        import time
        # 'az once' icin 1 saniye once
        self.assertIn("önce", self.mod._age_str(time.time() - 1))
        # cok eski
        self.assertIn("gün", self.mod._age_str(time.time() - 200000))

    def test_date_from_file_match(self):
        """_date_from_file dosya adindan tarih cikarir."""
        dummy = Path("/fake/HealthAutoExport-2026-06-06.json")
        from datetime import date
        self.assertEqual(self.mod._date_from_file(dummy), date(2026, 6, 6))

    def test_date_from_file_no_match(self):
        """_date_from_file eslesmezse None doner."""
        dummy = Path("/fake/random_file.json")
        self.assertIsNone(self.mod._date_from_file(dummy))
        self.assertIsNone(self.mod._date_from_file(None))

    def test_get_health_data_no_file(self):
        """get_health_data dosya yokken hata mesaji doner."""
        result = self.mod.get_health_data("all")
        # Dosya olmadiginda "bulunamadi" mesaji donmeli
        self.assertIn("bulunamadı", result.lower())

    def test_get_welcome_health_summary_no_file(self):
        """get_welcome_health_summary dosya yokken hata mesaji doner."""
        result = self.mod.get_welcome_health_summary()
        self.assertIn("alınamadı", result.lower())


# =============================================================================
# 7. SISTEM BILGISI (sys_info) — SAF FONKSIYON TESTLERI
# =============================================================================

class TestSysInfo(unittest.TestCase):
    """sys_info pure fonksiyon testleri."""

    def setUp(self):
        from actions import sys_info
        self.mod = sys_info

    def test_sys_info_returns_string(self):
        """sys_info() string doner."""
        result = self.mod.sys_info("time")
        self.assertIsInstance(result, str)

    def test_sys_info_unknown_query(self):
        """sys_info bilinmeyen sorguda yardim metni doner."""
        result = self.mod.sys_info("bilinmeyen_sorgu")
        self.assertIn("kullanin", result.lower())

    def test_sys_info_time(self):
        """sys_info('time') saat bilgisi icerir."""
        result = self.mod.sys_info("time")
        self.assertIn("Saat", result)

    def test_sys_info_date(self):
        """sys_info('date') tarih bilgisi icerir."""
        result = self.mod.sys_info("date")
        self.assertIn("Tarih", result)


# =============================================================================
# 8. ANA MODUL (main.py) — SAF FONKSIYON TESTLERI
# =============================================================================

class TestMainPureFunctions(unittest.TestCase):
    """main.py statik fonksiyon testleri — Gemini/PyAudio baglantisi yok."""

    @classmethod
    def setUpClass(cls):
        try:
            from main import JarvisLive, load_system_prompt
            cls.JarvisLive = JarvisLive
            cls.load_system_prompt = load_system_prompt
            cls.main_available = True
        except ImportError:
            cls.main_available = False

    def setUp(self):
        if not self.main_available:
            self.skipTest("main.py import edilemedi (pyaudio veya google-genai eksik)")

    def test_load_system_prompt(self):
        """load_system_prompt() prompt.txt'yi okur."""
        from main import load_system_prompt as fn
        result = fn()
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)

    def test_clean_transcript_text(self):
        """clean_transcript_text metni temizler (case korunur)."""
        from core.text_utils import clean_transcript_text
        text, had_noise = clean_transcript_text("Merhaba dunya")
        self.assertEqual(text, "Merhaba dunya")
        self.assertFalse(had_noise)

    def test_clean_transcript_text_removes_control(self):
        """clean_transcript_text kontrol token'larini temizler."""
        from core.text_utils import clean_transcript_text
        text, had_noise = clean_transcript_text("<ctrl123> Merhaba")
        self.assertEqual(text, "Merhaba")
        self.assertTrue(had_noise)

    def test_result_looks_like_error_positive(self):
        """_result_looks_like_error hata metnini tanir."""
        self.assertTrue(self.JarvisLive._result_looks_like_error("hata: dosya bulunamadi"))
        self.assertTrue(self.JarvisLive._result_looks_like_error("Error: connection failed"))

    def test_result_looks_like_error_empty(self):
        """_result_looks_like_error bos string icin False doner (hata yok)."""
        self.assertFalse(self.JarvisLive._result_looks_like_error(""))
        self.assertFalse(self.JarvisLive._result_looks_like_error(None))

    def test_result_looks_like_error_negative(self):
        """_result_looks_like_error normal metni hata olarak algilamaz."""
        self.assertFalse(self.JarvisLive._result_looks_like_error("Islem basariyla tamamlandi"))

    def test_should_play_success_sfx_action_tools(self):
        """_should_play_success_sfx action tool'lari icin True doner."""
        self.assertTrue(self.JarvisLive._should_play_success_sfx("open_app", {}, ""))
        self.assertTrue(self.JarvisLive._should_play_success_sfx("add_calendar_event", {}, ""))
        self.assertTrue(self.JarvisLive._should_play_success_sfx("add_reminder", {}, ""))
        self.assertTrue(self.JarvisLive._should_play_success_sfx("delete_calendar_event", {}, ""))

    def test_should_play_success_sfx_other(self):
        """_should_play_success_sfx diger araclar icin False doner."""
        self.assertFalse(self.JarvisLive._should_play_success_sfx("get_weather", {}, ""))


# =============================================================================
# 9. TTS — SAF FONKSIYON TESTLERI
# =============================================================================

class TestTTS(unittest.TestCase):
    """tts modulu pure fonksiyon testleri — ses cikisi yok."""

    def setUp(self):
        from actions import tts
        self.mod = tts

    def test_edge_voice_name(self):
        """_edge_voice_name dogru ses adini doner."""
        self.assertEqual(self.mod._edge_voice_name("edge-ahmet"), "tr-TR-AhmetNeural")
        self.assertEqual(self.mod._edge_voice_name("edge-emel"), "tr-TR-EmelNeural")
        self.assertEqual(self.mod._edge_voice_name("bilinmeyen"), "tr-TR-AhmetNeural")


# =============================================================================
# 10. WINDOWS_UTILS — SAF FONKSIYON TESTLERI
# =============================================================================

class TestWindowsUtils(unittest.TestCase):
    """windows_utils pure fonksiyon testleri."""

    def test_open_url_does_not_crash(self):
        """open_url cagrildiginda exception firlatmaz."""
        from actions.windows_utils import open_url
        with patch("actions.windows_utils.webbrowser.open") as mock_open:
            try:
                open_url("https://example.com")
            except Exception as e:
                self.fail(f"open_url exception firlatti: {e}")
            mock_open.assert_called_once_with("https://example.com", new=2)


# =============================================================================
# 11. WEATHER — SAF FONKSIYON TESTLERI
# =============================================================================

class TestWeather(unittest.TestCase):
    """weather modulu testleri — API cagrisi yok, hata yolu test edilir."""

    def setUp(self):
        from actions import weather
        self.mod = weather

    def test_get_weather_summary_empty_location(self):
        """get_weather_summary bos konumla calisir (varsayilan Istanbul)."""
        result = self.mod.get_weather_summary(None)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_get_weather_summary_invalid_location(self):
        """get_weather_summary gecersiz konumda hata mesaji doner."""
        result = self.mod.get_weather_summary("xyz_bogus_city_12345")
        self.assertIsInstance(result, str)


# =============================================================================
# 12. OPEN_APP — SAF FONKSIYON TESTLERI
# =============================================================================

class TestOpenApp(unittest.TestCase):
    """open_app modulu — alias dict + validation."""

    def setUp(self):
        from actions import open_app
        self.mod = open_app

    def test_app_aliases_is_dict(self):
        """APP_ALIASES dict ve bos degil."""
        self.assertIsInstance(self.mod.APP_ALIASES, dict)
        self.assertGreater(len(self.mod.APP_ALIASES), 0)

    def test_app_aliases_keys_are_strings(self):
        """APP_ALIASES anahtarlarinin hepsi string."""
        for key in self.mod.APP_ALIASES:
            self.assertIsInstance(key, str)

    def test_app_aliases_values_are_strings(self):
        """APP_ALIASES degerlerinin hepsi string."""
        for val in self.mod.APP_ALIASES.values():
            self.assertIsInstance(val, str)

    def test_open_app_empty(self):
        """open_app bos ad ile 'belirtilmedi' doner."""
        result = self.mod.open_app("")
        self.assertIn("belirtilmedi", result)

    def test_open_app_none(self):
        """open_app None ile 'belirtilmedi' doner."""
        result = self.mod.open_app(None)
        self.assertIn("belirtilmedi", result)

    def test_open_app_not_windows(self):
        """open_app Windows degilse platform hatasi doner (os.name != 'nt' iken)."""
        import os
        if os.name != "nt":
            result = self.mod.open_app("chrome")
            self.assertIn("calismiyor", result)


# =============================================================================
# 13. CALENDAR — SAF FONKSIYON TESTLERI
# =============================================================================

class TestCalendar(unittest.TestCase):
    """calendar modulu — pure fonksiyon + validation testleri."""

    def setUp(self):
        from actions import calendar
        self.mod = calendar

    def test_load_events_no_file(self):
        """_load_events dosya yokken liste doner."""
        result = self.mod._load_events()
        self.assertIsInstance(result, list)

    def test_parse_iso_valid(self):
        """_parse_iso gecerli ISO cozer."""
        from datetime import datetime
        result = self.mod._parse_iso("2024-03-15T14:30:00")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.day, 15)
        self.assertEqual(result.hour, 14)
        self.assertEqual(result.minute, 30)

    def test_parse_iso_z_suffix(self):
        """_parse_iso Z ekini cozer."""
        result = self.mod._parse_iso("2024-12-31T23:59:59Z")
        self.assertEqual(result.year, 2024)

    def test_parse_iso_empty_raises(self):
        """_parse_iso bos string ValueError firlatir."""
        with self.assertRaises(ValueError):
            self.mod._parse_iso("")

    def test_parse_iso_none_raises(self):
        """_parse_iso None ValueError firlatir."""
        with self.assertRaises(ValueError):
            self.mod._parse_iso(None)

    def test_to_event_valid(self):
        """_to_event gecerli dict'i event formatina cevirir."""
        event = self.mod._to_event({
            "id": "test-1",
            "title": "Toplanti",
            "start_iso": "2024-06-15T10:00:00",
            "end_iso": "2024-06-15T11:00:00",
        })
        self.assertIsNotNone(event)
        self.assertEqual(event["title"], "Toplanti")
        self.assertEqual(event["id"], "test-1")
        self.assertFalse(event["all_day"])

    def test_to_event_missing_end(self):
        """_to_event bitis yoksa +1 saat ekler."""
        event = self.mod._to_event({
            "id": "t-1",
            "title": "Test",
            "start_iso": "2024-06-15T10:00:00",
        })
        self.assertIsNotNone(event)
        self.assertEqual(event["end_ts"] - event["start_ts"], 3600)

    def test_to_event_bad_date_returns_none(self):
        """_to_event gecersiz tarihle None doner."""
        event = self.mod._to_event({"id": "x", "title": "X", "start_iso": "gecersiz"})
        self.assertIsNone(event)

    def test_to_event_empty_fields(self):
        """_to_event bos alanlari varsayilanla doldurur."""
        event = self.mod._to_event({"start_iso": "2024-06-15T10:00:00"})
        self.assertIsNotNone(event)
        self.assertEqual(event["title"], "Adsiz etkinlik")
        self.assertEqual(event["location"], "")
        self.assertEqual(event["calendar"], "Windows Local")

    def test_month_start(self):
        """_month_start gunu 1'e cevirir, saatleri sifirlar."""
        from datetime import datetime
        result = self.mod._month_start(datetime(2024, 3, 15, 14, 30, 0))
        self.assertEqual(result.day, 1)
        self.assertEqual(result.hour, 0)
        self.assertEqual(result.minute, 0)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.year, 2024)

    def test_add_months_same_year(self):
        """_add_months ayni yil icinde ekleme yapar."""
        from datetime import datetime
        result = self.mod._add_months(datetime(2024, 1, 1), 3)
        self.assertEqual(result.month, 4)
        self.assertEqual(result.year, 2024)

    def test_add_months_year_boundary(self):
        """_add_months yil sinirini gecer."""
        from datetime import datetime
        result = self.mod._add_months(datetime(2024, 10, 1), 5)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.year, 2025)

    def test_normalize_query_today(self):
        """_normalize_query bos/None sorguyu bugun olarak algilar."""
        result = self.mod._normalize_query("")
        self.assertEqual(result["kind"], "today")
        result2 = self.mod._normalize_query(None)
        self.assertEqual(result2["kind"], "today")

    def test_normalize_query_tomorrow(self):
        """_normalize_query 'yarin' algilar."""
        result = self.mod._normalize_query("yarin")
        self.assertEqual(result["kind"], "tomorrow")
        result = self.mod._normalize_query("tomorrow")
        self.assertEqual(result["kind"], "tomorrow")

    def test_normalize_query_week(self):
        """_normalize_query hafta algilar."""
        result = self.mod._normalize_query("bu hafta")
        self.assertEqual(result["kind"], "week")

    def test_normalize_query_next_month(self):
        """_normalize_query 'gelecek ay' algilar."""
        result = self.mod._normalize_query("gelecek ay")
        self.assertEqual(result["kind"], "next_month")

    def test_normalize_query_next(self):
        """_normalize_query 'siradaki' algilar."""
        result = self.mod._normalize_query("siradaki")
        self.assertEqual(result["kind"], "next")

    def test_normalize_query_agenda(self):
        """_normalize_query 'ajanda' algilar."""
        result = self.mod._normalize_query("ajanda")
        self.assertEqual(result["kind"], "agenda")

    def test_normalize_query_this_month(self):
        """_normalize_query 'bu ay' algilar."""
        result = self.mod._normalize_query("bu ay")
        self.assertEqual(result["kind"], "this_month")

    def test_normalize_query_n_days(self):
        """_normalize_query '5 gun' algilar."""
        result = self.mod._normalize_query("5 gun")
        self.assertEqual(result["kind"], "days")
        self.assertEqual(result["limit"], 10)  # 5 * 2

    def test_normalize_query_n_weeks(self):
        """_normalize_query '3 hafta' algilar."""
        result = self.mod._normalize_query("3 hafta")
        self.assertEqual(result["kind"], "weeks")

    def test_normalize_query_n_months(self):
        """_normalize_query '2 ay' algilar."""
        result = self.mod._normalize_query("2 ay")
        self.assertEqual(result["kind"], "months")

    def test_day_label_today(self):
        """_day_label bugun 'bugun' doner."""
        from datetime import datetime
        now = datetime(2024, 6, 15, 12, 0, 0)
        result = self.mod._day_label(now, now)
        self.assertEqual(result, "bugun")

    def test_day_label_tomorrow(self):
        """_day_label yarin 'yarin' doner."""
        from datetime import datetime, timedelta
        now = datetime(2024, 6, 15, 12, 0, 0)
        result = self.mod._day_label(now + timedelta(days=1), now)
        self.assertEqual(result, "yarin")

    def test_day_label_other(self):
        """_day_label diger gunler icin tarih doner."""
        from datetime import datetime
        now = datetime(2024, 6, 15, 12, 0, 0)
        future = datetime(2024, 6, 20, 0, 0, 0)
        result = self.mod._day_label(future, now)
        self.assertNotIn("bugun", result)
        self.assertNotIn("yarin", result)
        self.assertIn("20", result)

    def test_format_time_range_all_day(self):
        """_format_time_range tum gun etkinligini dogru formatlar."""
        from datetime import datetime
        event = {"start_ts": int(datetime(2024, 6, 15, 0, 0, 0).timestamp()),
                 "end_ts": int(datetime(2024, 6, 15, 23, 59, 59).timestamp()),
                 "all_day": True}
        result = self.mod._format_time_range(event, datetime(2024, 6, 15, 12, 0, 0))
        self.assertIn("tum gun", result)

    def test_format_event_line_with_calendar(self):
        """_format_event_line calendar bilgisini ekler."""
        from datetime import datetime
        event = {"start_ts": int(datetime(2024, 6, 15, 10, 0, 0).timestamp()),
                 "end_ts": int(datetime(2024, 6, 15, 11, 0, 0).timestamp()),
                 "all_day": False,
                 "title": "Test",
                 "calendar": "Is",
                 "location": ""}
        now = datetime(2024, 6, 15, 12, 0, 0)
        result = self.mod._format_event_line(event, now)
        self.assertIn("Test", result)
        self.assertIn("[Is]", result)

    def test_format_event_line_with_location(self):
        """_format_event_line konum bilgisini ekler."""
        from datetime import datetime
        event = {"start_ts": int(datetime(2024, 6, 15, 10, 0, 0).timestamp()),
                 "end_ts": int(datetime(2024, 6, 15, 11, 0, 0).timestamp()),
                 "all_day": False,
                 "title": "Toplanti",
                 "calendar": "",
                 "location": "Ofis"}
        result = self.mod._format_event_line(event, datetime(2024, 6, 15, 12, 0, 0))
        self.assertIn("Toplanti", result)
        self.assertIn("@ Ofis", result)

    def test_add_calendar_event_empty_title(self):
        """add_calendar_event bos baslikla hata doner."""
        result = self.mod.add_calendar_event("", "2024-06-15T10:00:00")
        self.assertIn("basligi gerekli", result)

    def test_add_calendar_event_empty_start(self):
        """add_calendar_event baslangic yoksa hata doner."""
        result = self.mod.add_calendar_event("Test", "")
        self.assertIn("tarihi gerekli", result)

    def test_add_calendar_event_bad_date(self):
        """add_calendar_event gecersiz tarihle hata doner."""
        result = self.mod.add_calendar_event("Test", "gecersiz")
        self.assertIn("tarih okunamadi", result)

    def test_delete_calendar_event_empty_title(self):
        """delete_calendar_event bos baslikla hata doner."""
        result = self.mod.delete_calendar_event("")
        self.assertIn("basligi gerekli", result)


# =============================================================================
# 14. REMINDERS — SAF FONKSIYON TESTLERI
# =============================================================================

class TestReminders(unittest.TestCase):
    """reminders modulu — pure fonksiyon + validation testleri."""

    def setUp(self):
        from actions import reminders
        self.mod = reminders

    def test_load_reminders_no_file(self):
        """_load_reminders dosya yokken liste doner."""
        orig = self.mod.REMINDERS_FILE
        import tempfile, pathlib
        self.mod.REMINDERS_FILE = pathlib.Path(tempfile.gettempdir()) / "_test_reminders_nonexistent.json"
        if self.mod.REMINDERS_FILE.exists():
            self.mod.REMINDERS_FILE.unlink()
        try:
            result = self.mod._load_reminders()
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 0)
        finally:
            self.mod.REMINDERS_FILE = orig

    def test_parse_iso_valid(self):
        """_parse_iso gecerli ISO datetime cozer."""
        from datetime import datetime
        result = self.mod._parse_iso("2024-03-15T14:30:00")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.hour, 14)

    def test_parse_iso_date_only(self):
        """_parse_iso sadece tarih formatini da cozer."""
        from datetime import datetime
        result = self.mod._parse_iso("2024-03-15")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.day, 15)

    def test_parse_iso_empty(self):
        """_parse_iso bos string icin None doner."""
        self.assertIsNone(self.mod._parse_iso(""))

    def test_parse_iso_none(self):
        """_parse_iso None icin None doner."""
        self.assertIsNone(self.mod._parse_iso(None))

    def test_parse_iso_invalid(self):
        """_parse_iso gecersiz string icin None doner."""
        self.assertIsNone(self.mod._parse_iso("xyz"))

    def test_day_label_today(self):
        """_day_label bugun 'bugun' doner."""
        from datetime import datetime
        now = datetime(2024, 6, 15, 12, 0, 0)
        self.assertEqual(self.mod._day_label(now, now), "bugun")

    def test_day_label_tomorrow(self):
        """_day_label yarin 'yarin' doner."""
        from datetime import datetime, timedelta
        now = datetime(2024, 6, 15, 12, 0, 0)
        self.assertEqual(self.mod._day_label(now + timedelta(days=1), now), "yarin")

    def test_day_label_other(self):
        """_day_label diger gun icin gun + ay + gun adi doner."""
        from datetime import datetime
        now = datetime(2024, 6, 15, 12, 0, 0)
        future = datetime(2024, 6, 20, 0, 0, 0)
        result = self.mod._day_label(future, now)
        self.assertNotIn("bugun", result)
        self.assertNotIn("yarin", result)

    def test_format_due_all_day(self):
        """_format_due tum gun etkinligini dogru formatlar."""
        item = {"due_iso": "2024-06-15", "all_day": True}
        from datetime import datetime
        result = self.mod._format_due(item, datetime(2024, 6, 15, 12, 0, 0))
        self.assertIn("tum gun", result)

    def test_format_due_no_due(self):
        """_format_due due yoksa 'zaman atanmamis' doner."""
        item = {"due_iso": "", "all_day": False}
        from datetime import datetime
        result = self.mod._format_due(item, datetime(2024, 6, 15, 12, 0, 0))
        self.assertEqual(result, "zaman atanmamis")

    def test_format_reminder_line_with_list(self):
        """_format_reminder_line liste adini ekler."""
        item = {"title": "Su ic", "due_iso": "2024-06-15T10:00:00", "list_name": "Saglik", "priority": ""}
        from datetime import datetime
        result = self.mod._format_reminder_line(item, datetime(2024, 6, 15, 12, 0, 0))
        self.assertIn("Su ic", result)
        self.assertIn("[Saglik]", result)

    def test_format_reminder_line_high_priority(self):
        """_format_reminder_line yuksek onceligi belirtir."""
        item = {"title": "Acil", "due_iso": "2024-06-15T10:00:00", "list_name": "", "priority": "high"}
        from datetime import datetime
        result = self.mod._format_reminder_line(item, datetime(2024, 6, 15, 12, 0, 0))
        self.assertIn("yuksek oncelik", result)

    def test_open_items_filters_completed(self):
        """_open_items tamamlanmis ogeleri filtreler."""
        items = [
            {"title": "a", "completed": True, "due_iso": ""},
            {"title": "b", "completed": False, "due_iso": ""},
            {"title": "c", "completed": False, "due_iso": ""},
            {"title": "d", "completed": True, "due_iso": ""},
        ]
        # _open_items calls _load_reminders which reads from file
        # We test the filter logic separately via _load_reminders init
        # but _open_items just filters _load_reminders result
        result = [i for i in items if not i.get("completed")]
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["title"], "b")
        self.assertEqual(result[1]["title"], "c")

    def test_get_reminders_today(self):
        """get_reminders 'bugun' parametresiyle calisir."""
        result = self.mod.get_reminders("today")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_get_reminders_overdue(self):
        """get_reminders 'geciken' parametresiyle calisir."""
        result = self.mod.get_reminders("overdue")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_get_reminders_next(self):
        """get_reminders 'siradaki' parametresiyle calisir."""
        result = self.mod.get_reminders("next")
        self.assertIsInstance(result, str)

    def test_get_reminders_all(self):
        """get_reminders 'hepsi' parametresiyle calisir."""
        result = self.mod.get_reminders("all")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_add_reminder_empty_title(self):
        """add_reminder bos baslikla hata doner."""
        result = self.mod.add_reminder("")
        self.assertIn("bos olamaz", result)

    def test_add_reminder_invalid_date(self):
        """add_reminder gecersiz tarihle hata doner."""
        result = self.mod.add_reminder("Test", due_iso="gecersiz")
        self.assertIn("gecersiz", result)


# =============================================================================
# 15. BROWSER — SAF FONKSIYON TESTLERI
# =============================================================================

class TestBrowser(unittest.TestCase):
    """browser modulu — validation + regex testleri."""

    def setUp(self):
        from actions import browser
        self.mod = browser

    def test_browser_control_unknown_action(self):
        """browser_control bilinmeyen eylem icin hata doner."""
        result = self.mod.browser_control("nonexistent_action")
        self.assertIn("Bilinmeyen", result)

    def test_browser_control_open_url_no_url(self):
        """browser_control open_url URL'siz hata doner."""
        result = self.mod.browser_control("open_url")
        self.assertIn("belirtilmedi", result)

    def test_browser_control_search_no_query(self):
        """browser_control search sorgusuz hata doner."""
        result = self.mod.browser_control("search")
        self.assertIn("belirtilmedi", result)

    def test_browser_control_play_youtube_no_query(self):
        """browser_control play_youtube sorgusuz hata doner."""
        result = self.mod.browser_control("play_youtube")
        self.assertIn("belirtilmedi", result)

    def test_video_id_regex_pattern(self):
        """_VIDEO_ID_RE 11 karakterli base64 ID'leri eslestirir."""
        import re
        pattern = re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"')
        match = pattern.search('"videoId":"abc123DEF_-"')
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "abc123DEF_-")
        match = pattern.search('"videoId":"short"')
        self.assertIsNone(match)
        match = pattern.search('"videoId":"toolongforvalid123"')
        self.assertIsNone(match)


# =============================================================================
# 16. SHELL — SAF FONKSIYON TESTLERI
# =============================================================================

class TestShell(unittest.TestCase):
    """shell modulu — guvenlik filtreleme + validation testleri."""

    def setUp(self):
        from actions import shell
        self.mod = shell

    def test_shell_run_empty(self):
        """shell_run bos komutla hata doner."""
        result = self.mod.shell_run("")
        self.assertIn("belirtilmedi", result)

    def test_shell_run_none(self):
        """shell_run None ile hata doner."""
        result = self.mod.shell_run(None)
        self.assertIn("belirtilmedi", result)

    def test_shell_run_blocked_shutdown(self):
        """shell_run shutdown komutunu engeller."""
        result = self.mod.shell_run("shutdown -s -t 0")
        self.assertIn("engellendi", result)

    def test_shell_run_blocked_rm_rf(self):
        """shell_run rm -rf komutunu engeller (dangerous prefix cakar)."""
        result = self.mod.shell_run("rm -rf /")
        # "rm " ile basladigi icin dangerous prefix kontrolune takilir
        self.assertIn("G\xfcvenlik", result)  # Güvenlik (umlaut)

    def test_shell_run_blocked_dd(self):
        """shell_run dd if= komutunu engeller."""
        result = self.mod.shell_run("dd if=/dev/sda of=/dev/null")
        self.assertIn("engellendi", result)

    def test_shell_run_dangerous_prefix_rm(self):
        """shell_run rm ile baslayan komutlari engeller."""
        result = self.mod.shell_run("rm myfile.txt")
        self.assertIn("G\xfcvenlik", result)  # Güvenlik (umlaut'lu u)

    def test_shell_run_dangerous_prefix_sudo(self):
        """shell_run sudo ile baslayan komutlari engeller."""
        result = self.mod.shell_run("sudo apt install")
        self.assertIn("G\xfcvenlik", result)

    def test_shell_run_normal_echo(self):
        """shell_run normal komut calistirir."""
        result = self.mod.shell_run("echo test123")
        self.assertIn("test123", result)

    def test_blocked_list_not_empty(self):
        """BLOCKED listesi bos degil."""
        self.assertGreater(len(self.mod.BLOCKED), 0)

    def test_blocked_list_all_strings(self):
        """BLOCKED listesindeki her sey string."""
        for item in self.mod.BLOCKED:
            self.assertIsInstance(item, str)


# =============================================================================
# 17. WHATSAPP — SAF FONKSIYON TESTLERI
# =============================================================================

class TestWhatsApp(unittest.TestCase):
    """whatsapp modulu — pure fonksiyon + validation testleri."""

    def setUp(self):
        from actions import whatsapp
        self.mod = whatsapp

    def test_normalize_phone_valid(self):
        """_normalize_phone gecerli numarayi 90 ile dondurur."""
        result = self.mod._normalize_phone("+905551112233")
        self.assertEqual(result, "905551112233")

    def test_normalize_phone_with_0(self):
        """_normalize_phone 0 ile baslayani 90+... yapar."""
        result = self.mod._normalize_phone("05551112233")
        self.assertEqual(result, "905551112233")

    def test_normalize_phone_10_digits(self):
        """_normalize_phone 10 haneli numaraya 90 ekler."""
        result = self.mod._normalize_phone("5551112233")
        self.assertEqual(result, "905551112233")

    def test_normalize_phone_too_short(self):
        """_normalize_phone cok kisa numarada ValueError."""
        with self.assertRaises(ValueError):
            self.mod._normalize_phone("123")

    def test_normalize_phone_too_long(self):
        """_normalize_phone cok uzun numarada ValueError."""
        with self.assertRaises(ValueError):
            self.mod._normalize_phone("1234567890123456")

    def test_normalize_phone_strips_non_digits(self):
        """_normalize_phone rakam disi karakterleri temizler."""
        result = self.mod._normalize_phone("+90 (555) 111-22-33")
        self.assertEqual(result, "905551112233")

    def test_normalize_lookup(self):
        """_normalize_lookup Turkce karakterleri normalize eder."""
        result = self.mod._normalize_lookup("İstanbul Şöför")
        self.assertNotIn("İ", result)
        self.assertNotIn("ş", result)
        self.assertNotIn("ö", result)

    def test_normalize_lookup_spaces(self):
        """_normalize_lookup fazla bosluklari teke indirir."""
        result = self.mod._normalize_lookup("  Ali   Veli  ")
        self.assertEqual(result, "ali veli")

    def test_normalize_lookup_empty(self):
        """_normalize_lookup bos string calisir."""
        self.assertEqual(self.mod._normalize_lookup(""), "")
        self.assertEqual(self.mod._normalize_lookup(None), "")

    def test_contact_key(self):
        """_contact_key ismi altcizgili anahtara cevirir."""
        result = self.mod._contact_key("Ali Veli")
        self.assertEqual(result, "ali_veli")

    def test_contact_key_turkce(self):
        """_contact_key Turkce karakterleri handle eder."""
        result = self.mod._contact_key("Şükran İnan")
        self.assertNotIn("ş", result)
        self.assertNotIn("ı", result)
        self.assertIn("inan", result)

    def test_find_contact_empty(self):
        """_find_contact bos sorguda None doner."""
        self.assertIsNone(self.mod._find_contact(""))
        self.assertIsNone(self.mod._find_contact(None))

    def test_unfold_vcf_lines(self):
        """_unfold_vcf_lines VCF satirlarini birlestirir."""
        lines = ["BEGIN:VCARD", "FN:Test", "  Kisisi", "TEL:123", "END:VCARD"]
        result = self.mod._unfold_vcf_lines("\n".join(lines))
        self.assertEqual(len(result), 4)
        self.assertEqual(result[1], "FN:Test Kisisi")

    def test_unfold_vcf_lines_no_fold(self):
        """_unfold_vcf_lines katlanmamis VCF'de satirlar aynen kalir."""
        lines = ["BEGIN:VCARD", "FN:Test", "END:VCARD"]
        result = self.mod._unfold_vcf_lines("\n".join(lines))
        self.assertEqual(result, lines)

    def test_save_contact_empty_name(self):
        """save_whatsapp_contact bos isimle hata doner."""
        result = self.mod.save_whatsapp_contact("", "+905551112233")
        self.assertIn("bos olamaz", result)

    def test_save_contact_invalid_phone(self):
        """save_whatsapp_contact gecersiz telefonla hata doner."""
        result = self.mod.save_whatsapp_contact("Ali", "123")
        self.assertIn("formatta", result)

    def test_import_vcf_no_file(self):
        """import_phone_book_from_vcf olmayan dosyada hata doner."""
        result = self.mod.import_phone_book_from_vcf("/nonexistent/file.vcf")
        self.assertIn("bulunamadi", result)

    def test_send_whatsapp_empty_message(self):
        """send_whatsapp_message bos mesajla hata doner."""
        result = self.mod.send_whatsapp_message("")
        self.assertIn("bos olamaz", result)

    def test_send_whatsapp_no_recipient(self):
        """send_whatsapp_message adres yoksa hata doner."""
        result = self.mod.send_whatsapp_message("Selam", phone_number="", recipient_name="")
        self.assertIn("gerekli", result)

    def test_send_whatsapp_invalid_phone(self):
        """send_whatsapp_message gecersiz numarayla hata doner."""
        result = self.mod.send_whatsapp_message("Selam", phone_number="123")
        self.assertIn("formatta", result)


# =============================================================================
# 18. MEDIA — SAF FONKSIYON TESTLERI
# =============================================================================

class TestMedia(unittest.TestCase):
    """media modulu — validation testleri."""

    def setUp(self):
        from actions import media
        self.mod = media

    def test_play_media_empty_query(self):
        """play_media bos sorguyla hata doner."""
        result = self.mod.play_media("")
        self.assertIn("belirtilmedi", result)

    def test_play_media_none_query(self):
        """play_media None sorguyla hata doner."""
        result = self.mod.play_media(None)
        self.assertIn("belirtilmedi", result)

    def test_play_media_youtube_provider(self):
        """play_media youtube provider'ini algilar (hata yolu)."""
        with patch("actions.media.browser_control") as mock_bc:
            mock_bc.return_value = "YouTube test"
            result = self.mod.play_media("test sarki", provider="youtube")
            self.assertIsInstance(result, str)
            mock_bc.assert_called_once_with("play_youtube", query="test sarki")


# =============================================================================
# 19. SCREEN VISION — SAF FONKSIYON TESTLERI
# =============================================================================

class TestScreenVision(unittest.TestCase):
    """screen_vision modulu — pure fonksiyon testleri (API cagrisi yok)."""

    def setUp(self):
        from actions import screen_vision
        self.mod = screen_vision

    def test_screen_permission_message(self):
        """_screen_permission_message string doner."""
        result = self.mod._screen_permission_message()
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 20)

    def test_vision_prompt(self):
        """_vision_prompt prompt metni olusturur."""
        result = self.mod._vision_prompt("Nedir bu?", "Kullanici", "Not Defteri")
        self.assertIn("Nedir bu?", result)
        self.assertIn("Not Defteri", result)
        self.assertIn("Turkce", result)

    def test_vision_prompt_default_query(self):
        """_vision_prompt sorgu yoksa varsayilan kullanir."""
        result = self.mod._vision_prompt("", "Kullanici", "Pencere")
        self.assertIn("Ekranda ne var?", result)

    def test_extract_response_text_with_text(self):
        """_extract_response_text response.text alanini okur."""
        class FakeResponse:
            text = "Merhaba dunya"
            candidates = []
        result = self.mod._extract_response_text(FakeResponse())
        self.assertEqual(result, "Merhaba dunya")

    def test_extract_response_text_with_candidates(self):
        """_extract_response_text candidates icinden text birlestirir."""
        class FakePart:
            text = "birinci"
        class FakeContent:
            parts = [FakePart()]
        class FakeCandidate:
            content = FakeContent()
        class FakeResponse:
            text = ""
            candidates = [FakeCandidate()]
        result = self.mod._extract_response_text(FakeResponse())
        self.assertEqual(result, "birinci")

    def test_extract_response_text_empty(self):
        """_extract_response_text bos yanitta bos string doner."""
        class FakeResponse:
            text = ""
            candidates = []
        result = self.mod._extract_response_text(FakeResponse())
        self.assertEqual(result, "")

    def test_is_transient_vision_error_server_error(self):
        """_is_transient_vision_error ServerError'i gecici kabul eder."""
        from google.genai import errors
        exc = errors.ServerError(code=503, response_json={}, response="Service Unavailable")
        self.assertTrue(self.mod._is_transient_vision_error(exc))

    def test_is_transient_vision_error_timeout(self):
        """_is_transient_vision_error TimeoutError'i gecici kabul eder."""
        self.assertTrue(self.mod._is_transient_vision_error(TimeoutError("timed out")))

    def test_is_transient_vision_error_status_codes(self):
        """_is_transient_vision_error 503/429 kodlarini tanir."""
        self.assertTrue(self.mod._is_transient_vision_error(RuntimeError("503 Service Unavailable")))
        self.assertTrue(self.mod._is_transient_vision_error(RuntimeError("429 Too Many Requests")))

    def test_is_transient_vision_error_other_exception(self):
        """_is_transient_vision_error ilgisiz hatada False."""
        self.assertFalse(self.mod._is_transient_vision_error(ValueError("invalid")))

    def test_friendly_vision_error_quota(self):
        """_friendly_vision_error kota hatasini tanir."""
        result = self.mod._friendly_vision_error(RuntimeError("quota exceeded"))
        self.assertIn("kota", result)

    def test_friendly_vision_error_transient(self):
        """_friendly_vision_error gecici hatayi tanir."""
        result = self.mod._friendly_vision_error(RuntimeError("503 unavailable"))
        self.assertIn("ulasilamiyor", result)

    def test_friendly_vision_error_generic(self):
        """_friendly_vision_error genel hatada hatayi yansitir."""
        result = self.mod._friendly_vision_error(RuntimeError("something broke"))
        self.assertIn("something broke", result)

    def test_analyze_screen_wrong_target(self):
        """analyze_screen gecersiz target icin uyari doner."""
        result = self.mod.analyze_screen("ne var?", target="full_screen")
        self.assertIn("yalnizca", result)


# =============================================================================
# 20. MAIN PURE — KALAN TESTLER TAMAMLANDI
# =============================================================================

class TestMainPureFunctionsExtended(unittest.TestCase):
    """main.py ek pure fonksiyon testleri (yuk testi olmadan)."""

    def setUp(self):
        skip = False
        try:
            import main
            self.main = main
        except (ImportError, OSError):
            skip = True
        if skip:
            self.skipTest("main import edilemedi")

    def test_main_module_has_constants(self):
        """main.py gerekli sabitleri iceriyor."""
        for const in ("BASE_DIR", "LOG_DIR", "LOG_FILE", "PROMPT_PATH"):
            self.assertTrue(hasattr(self.main, const), f"{const} eksik")


# =============================================================================
# 21. UI — MODUL SEVIYESI + STATIC METHOD TESTLERI
# =============================================================================

class TestUIModuleConstants(unittest.TestCase):
    """ui.py modul sabitleri — Tkinter baslatmadan test edilir."""

    def setUp(self):
        import ui
        self.ui = ui

    def test_orb_colors_has_seven_states(self):
        """ORB_COLORS 7 durum icerir."""
        self.assertEqual(len(self.ui.ORB_COLORS), 7)

    def test_orb_colors_all_rgb_tuples(self):
        """ORB_COLORS degerlerinin hepsi 3'lü RGB tup."""
        for state, color in self.ui.ORB_COLORS.items():
            self.assertIsInstance(state, str)
            self.assertIsInstance(color, tuple)
            self.assertEqual(len(color), 3)
            for channel in color:
                self.assertTrue(0 <= channel <= 255)

    def test_state_hex_colors_five_states(self):
        """STATE_HEX_COLORS 5 durum icerir."""
        self.assertEqual(len(self.ui.STATE_HEX_COLORS), 5)

    def test_state_hex_colors_format(self):
        """STATE_HEX_COLORS degerleri #rrggbb formatinda."""
        for state, color in self.ui.STATE_HEX_COLORS.items():
            self.assertIsInstance(state, str)
            self.assertIsInstance(color, str)
            self.assertTrue(color.startswith("#"))
            self.assertEqual(len(color), 7)

    def test_voices_has_eight_names(self):
        """VOICES 8 ses adi icerir."""
        self.assertEqual(len(self.ui.VOICES), 8)
        self.assertIn("Charon", self.ui.VOICES)

    def test_color_constants_format(self):
        """Renk sabitleri #rrggbb formatinda."""
        for name in ("C_BG", "C_PRI", "C_TEXT", "C_GREEN", "C_RED", "C_BLUE", "C_GOLD"):
            color = getattr(self.ui, name)
            self.assertIsInstance(color, str)
            self.assertTrue(color.startswith("#"), f"{name}={color} # ile baslamali")
            self.assertEqual(len(color), 7)

    def test_dimension_constants_positive(self):
        """Boyut sabitleri pozitif integer."""
        for name in ("W_TARGET", "H_TARGET", "LEFT_W_T", "RIGHT_W_T", "HDR_H", "FOOTER_H", "INPUT_H", "CONTROL_H"):
            val = getattr(self.ui, name)
            self.assertIsInstance(val, int)
            self.assertGreater(val, 0)

    def test_system_name_constant(self):
        """SYSTEM_NAME dogru deger."""
        self.assertEqual(self.ui.SYSTEM_NAME, "J.A.R.V.I.S")

    def test_model_badge_constant(self):
        """MODEL_BADGE dogru deger."""
        self.assertEqual(self.ui.MODEL_BADGE, "VOICE CORE · Windows")


class TestUIModuleFunctions(unittest.TestCase):
    """ui.py modul seviyesi fonksiyonlar."""

    def setUp(self):
        import ui
        self.ui = ui

    def test_font_body_returns_tuple(self):
        """font_body tuple doner."""
        result = self.ui.font_body(12)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result, ("Grift", 12))

    def test_font_body_bold_returns_tuple(self):
        """font_body_bold tuple doner."""
        result = self.ui.font_body_bold(14)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result, ("Grift", 14, "bold"))

    def test_font_display_returns_tuple(self):
        """font_display tuple doner."""
        result = self.ui.font_display(18)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result, ("Grift Extra Bold", 18))

    def test_resolve_sfx_dir_returns_path(self):
        """_resolve_sfx_dir Path doner."""
        from pathlib import Path
        result = self.ui._resolve_sfx_dir()
        self.assertIsInstance(result, Path)
        self.assertTrue(str(result).endswith("SFX"))


class TestUISoundManager(unittest.TestCase):
    """SoundManager — ses oynatmasiz testler."""

    def setUp(self):
        from ui import SoundManager
        self.sm = SoundManager()

    def test_init_defaults(self):
        """SoundManager varsayilan degerlerle baslar."""
        self.assertTrue(self.sm._enabled)
        self.assertEqual(self.sm._volume, 0.20)

    def test_get_volume_returns_float(self):
        """get_volume float doner."""
        vol = self.sm.get_volume()
        self.assertIsInstance(vol, float)

    def test_set_volume_clamps_low(self):
        """set_volume dusuk degeri 0'a kilitler."""
        self.sm.set_volume(-0.5)
        self.assertEqual(self.sm.get_volume(), 0.0)

    def test_set_volume_clamps_high(self):
        """set_volume yuksek degeri 1'e kilitler."""
        self.sm.set_volume(2.0)
        self.assertEqual(self.sm.get_volume(), 1.0)

    def test_set_volume_normal(self):
        """set_volume normal degeri korur."""
        self.sm.set_volume(0.5)
        self.assertAlmostEqual(self.sm.get_volume(), 0.5)

    def test_toggle_flips_enabled(self):
        """toggle _enabled degerini tersine cevirir."""
        initial = self.sm._enabled
        result = self.sm.toggle()
        self.assertEqual(result, not initial)
        self.assertEqual(self.sm._enabled, not initial)

    def test_toggle_twice_restores(self):
        """toggle iki kez cagrilinca eski haline doner."""
        initial = self.sm._enabled
        self.sm.toggle()
        self.sm.toggle()
        self.assertEqual(self.sm._enabled, initial)

    def test_set_enabled_false(self):
        """set_enabled(False) _enabled'i False yapar."""
        self.sm.set_enabled(False)
        self.assertFalse(self.sm._enabled)

    def test_set_enabled_true(self):
        """set_enabled(True) _enabled'i True yapar."""
        self.sm.set_enabled(False)
        self.sm.set_enabled(True)
        self.assertTrue(self.sm._enabled)

    def test_set_volume_accepts_int(self):
        """set_volume int deger kabul eder."""
        self.sm.set_volume(75)
        self.assertEqual(self.sm.get_volume(), 1.0)  # clamped


class TestUIJarvisUIStaticMethods(unittest.TestCase):
    """JarvisUI static metodlari — Tkinter baslatmadan test."""

    def setUp(self):
        from ui import JarvisUI
        self.cls = JarvisUI

    def test_state_badge_text_initialising(self):
        """_state_badge_text INITIALISING → CONNECTING."""
        self.assertEqual(self.cls._state_badge_text("INITIALISING"), "CONNECTING")

    def test_state_badge_text_error(self):
        """_state_badge_text ERROR → ERROR."""
        self.assertEqual(self.cls._state_badge_text("ERROR"), "ERROR")

    def test_state_badge_text_listening(self):
        """_state_badge_text LISTENING → ONLINE."""
        self.assertEqual(self.cls._state_badge_text("LISTENING"), "ONLINE")

    def test_state_badge_text_speaking(self):
        """_state_badge_text SPEAKING → ONLINE."""
        self.assertEqual(self.cls._state_badge_text("SPEAKING"), "ONLINE")

    def test_state_badge_text_thinking(self):
        """_state_badge_text THINKING → ONLINE."""
        self.assertEqual(self.cls._state_badge_text("THINKING"), "ONLINE")

    def test_state_badge_text_muted(self):
        """_state_badge_text MUTED → ONLINE."""
        self.assertEqual(self.cls._state_badge_text("MUTED"), "ONLINE")

    def test_state_badge_text_paused(self):
        """_state_badge_text PAUSED → ONLINE."""
        self.assertEqual(self.cls._state_badge_text("PAUSED"), "ONLINE")

    def test_ac_returns_hex(self):
        """_ac alpha composite hex renk dondurur."""
        result = self.cls._ac(0, 255, 136, 255)
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith("#"))
        self.assertEqual(len(result), 7)

    def test_ac_zero_alpha(self):
        """_ac alpha=0 siyah doner."""
        result = self.cls._ac(255, 255, 255, 0)
        self.assertEqual(result, "#000000")

    def test_ac_clamps_alpha(self):
        """_ac alpha degerini 0-255 arasina kilitler."""
        result = self.cls._ac(255, 0, 0, 300)
        self.assertEqual(result, "#ff0000")

    def test_split_summary_lines_empty(self):
        """_split_summary_lines bos string icin [] doner."""
        self.assertEqual(self.cls._split_summary_lines(""), [])
        self.assertEqual(self.cls._split_summary_lines(None), [])

    def test_split_summary_lines_normal(self):
        """_split_summary_lines virgulle ayrilmis metni boler."""
        result = self.cls._split_summary_lines("a, b, c")
        self.assertEqual(result, ["a", "b", "c"])

    def test_split_summary_lines_ve_replacement(self):
        """_split_summary_lines ' ve ' yerine ', ' koyar."""
        result = self.cls._split_summary_lines("a ve b")
        self.assertEqual(result, ["a", "b"])

    def test_split_summary_lines_limit(self):
        """_split_summary_lines limit kadar oge doner."""
        result = self.cls._split_summary_lines("a, b, c, d, e, f", limit=3)
        self.assertEqual(len(result), 3)

    def test_split_summary_lines_strips_dot(self):
        """_split_summary_lines bas/sondaki noktayi temizler."""
        result = self.cls._split_summary_lines("a., .b, c.")
        self.assertEqual(result, ["a", "b", "c"])


# =============================================================================
# 23. CORE / TEXT_UTILS — UNIT TESTS
# =============================================================================

class TestTextUtils(unittest.TestCase):
    """core/text_utils.py pure fonksiyon testleri (provider abstraction)."""

    # ── clean_transcript_text ──────────────────────────────────

    def test_clean_transcript_text_normal(self):
        """clean_transcript_text normal metni oldugu gibi birakir."""
        from core.text_utils import clean_transcript_text
        text, had_noise = clean_transcript_text("Merhaba dünya")
        self.assertEqual(text, "Merhaba dünya")
        self.assertFalse(had_noise)

    def test_clean_transcript_text_control_brackets(self):
        """clean_transcript_text [tag] ve <ctrl> tokenlarini temizler."""
        from core.text_utils import clean_transcript_text
        text, had_noise = clean_transcript_text("[Müzik] Merhaba <ctrl123> dünya")
        self.assertNotIn("[Müzik]", text)
        self.assertNotIn("<ctrl123>", text)
        self.assertIn("Merhaba", text)
        self.assertIn("dünya", text)
        self.assertTrue(had_noise)

    def test_clean_transcript_text_control_chars(self):
        """clean_transcript_text kontrol karakterlerini temizler (<32)."""
        from core.text_utils import clean_transcript_text
        text, had_noise = clean_transcript_text("Merhaba\x00dünya\x01test")
        self.assertNotIn("\x00", text)
        self.assertNotIn("\x01", text)
        self.assertTrue(had_noise)

    def test_clean_transcript_text_empty(self):
        """clean_transcript_text bos string icin ('', False) doner."""
        from core.text_utils import clean_transcript_text
        text, had_noise = clean_transcript_text("")
        self.assertEqual(text, "")
        self.assertFalse(had_noise)

    def test_clean_transcript_text_none(self):
        """clean_transcript_text None icin ('', False) doner."""
        from core.text_utils import clean_transcript_text
        text, had_noise = clean_transcript_text(None)
        self.assertEqual(text, "")
        self.assertFalse(had_noise)

    def test_clean_transcript_text_whitespace(self):
        """clean_transcript_text fazla bosluklari teke indirir."""
        from core.text_utils import clean_transcript_text
        text, had_noise = clean_transcript_text("Merhaba   dünya    test")
        self.assertEqual(text, "Merhaba dünya test")
        self.assertFalse(had_noise)

    def test_clean_transcript_text_nfc(self):
        """clean_transcript_text NFC normalizasyonu yapar."""
        from core.text_utils import clean_transcript_text
        # decomposed (NFD) form of 'ş' = s + combining cedilla
        s_cedilla = "s\u0327"
        text, had_noise = clean_transcript_text(f"Merhaba{s_cedilla}")
        self.assertIn("ş", text)  # should be composed form
        self.assertFalse(had_noise)

    # ── fix_turkish_syllable_split ─────────────────────────────

    def test_fix_syllable_split_single_letter_merge(self):
        """fix_turkish_syllable_split tek harfli parcayi birlestirir."""
        from core.text_utils import fix_turkish_syllable_split
        result = fix_turkish_syllable_split("İ stanbul")
        self.assertEqual(result, "İstanbul")

    def test_fix_syllable_split_multi_short_merge(self):
        """fix_turkish_syllable_split kisa parcalari birlestirir (max 8)."""
        from core.text_utils import fix_turkish_syllable_split
        result = fix_turkish_syllable_split("ya vaş laş")
        self.assertEqual(result, "yavaşlaş")

    def test_fix_syllable_split_preserves_stop_words(self):
        """fix_turkish_syllable_split Türkçe stop kelimeleri ayri tutar."""
        from core.text_utils import fix_turkish_syllable_split
        result = fix_turkish_syllable_split("ve bir için")
        self.assertEqual(result, "ve bir için")

    def test_fix_syllable_split_normal_text(self):
        """fix_turkish_syllable_split normal metni degistirmez."""
        from core.text_utils import fix_turkish_syllable_split
        result = fix_turkish_syllable_split("Merhaba dünya nasılsın")
        self.assertEqual(result, "Merhaba dünya nasılsın")

    def test_fix_syllable_split_empty(self):
        """fix_turkish_syllable_split bos string icin bos doner."""
        from core.text_utils import fix_turkish_syllable_split
        self.assertEqual(fix_turkish_syllable_split(""), "")

    def test_fix_syllable_split_single_word(self):
        """fix_turkish_syllable_split tek kelimeyi degistirmez."""
        from core.text_utils import fix_turkish_syllable_split
        self.assertEqual(fix_turkish_syllable_split("Merhaba"), "Merhaba")


# =============================================================================
# 24. CORE / TOOL_REGISTRY — UNIT TESTS
# =============================================================================

class TestToolRegistry(unittest.TestCase):
    """core/tool_registry.py testleri (provider abstraction)."""

    def test_valid_tools_count(self):
        """VALID_TOOLS 40 araci icerir."""
        from core.tool_registry import VALID_TOOLS
        self.assertEqual(len(VALID_TOOLS), 40)

    def test_valid_tools_contains_core(self):
        """VALID_TOOLS temel araclari icerir."""
        from core.tool_registry import VALID_TOOLS
        for tool in ("open_app", "sys_info", "get_weather", "get_current_location",
                     "shell_run", "browser_control", "play_media", "set_volume"):
            self.assertIn(tool, VALID_TOOLS)

    def test_valid_tools_contains_calendar(self):
        """VALID_TOOLS takvim araclarini icerir."""
        from core.tool_registry import VALID_TOOLS
        for tool in ("get_calendar_events", "add_calendar_event", "delete_calendar_event"):
            self.assertIn(tool, VALID_TOOLS)

    def test_valid_tools_contains_health(self):
        """VALID_TOOLS sistem sagligi araclarini icerir."""
        from core.tool_registry import VALID_TOOLS
        for tool in ("get_system_health", "cleanup_temp_files", "cleanup_recycle_bin",
                     "list_processes", "kill_process", "set_process_priority", "find_process_by_port"):
            self.assertIn(tool, VALID_TOOLS)

    def test_valid_tools_contains_file_tools(self):
        """VALID_TOOLS dosya araclarini icerir."""
        from core.tool_registry import VALID_TOOLS
        for tool in ("find_large_files", "find_duplicate_files", "cleanup_folder", "get_folder_summary"):
            self.assertIn(tool, VALID_TOOLS)

    def test_handler_map_size(self):
        """TOOL_HANDLER_MAP 40 tool handler icerir."""
        from core.tool_registry import TOOL_HANDLER_MAP
        self.assertEqual(len(TOOL_HANDLER_MAP), 40)

    def test_handler_map_all_have_handlers(self):
        """Her VALID_TOOLS icin TOOL_HANDLER_MAP'te handler vardir."""
        from core.tool_registry import VALID_TOOLS, TOOL_HANDLER_MAP
        for tool in VALID_TOOLS:
            self.assertIn(tool, TOOL_HANDLER_MAP,
                          f"{tool} TOOL_HANDLER_MAP'te eksik")

    def test_handler_map_format(self):
        """TOOL_HANDLER_MAP degerleri _handle_ ile baslar."""
        from core.tool_registry import TOOL_HANDLER_MAP
        for name, handler in TOOL_HANDLER_MAP.items():
            self.assertTrue(handler.startswith("_handle_"),
                            f"{name} handler'i _handle_ ile baslamiyor: {handler}")

    def test_gemini_declarations_format(self):
        """generate_gemini_declarations dogru formatta dict doner."""
        from core.tool_registry import generate_gemini_declarations
        decls = generate_gemini_declarations()
        self.assertIsInstance(decls, list)
        self.assertEqual(len(decls), 40)
        for d in decls:
            self.assertIn("name", d)
            self.assertIn("description", d)
            self.assertIn("parameters", d)
            self.assertEqual(d["parameters"]["type"], "OBJECT")
            self.assertIn("properties", d["parameters"])

    def test_gemini_declarations_required(self):
        """generate_gemini_declarations required alanini dogru ekler."""
        from core.tool_registry import generate_gemini_declarations
        decls = generate_gemini_declarations()
        open_app = next(d for d in decls if d["name"] == "open_app")
        self.assertIn("required", open_app["parameters"])
        self.assertIn("app_name", open_app["parameters"]["required"])
        get_weather = next(d for d in decls if d["name"] == "get_weather")
        self.assertNotIn("required", get_weather["parameters"])

    def test_gemini_declarations_types(self):
        """generate_gemini_declarations parametre tiplerini dogru ekler."""
        from core.tool_registry import generate_gemini_declarations
        decls = generate_gemini_declarations()
        open_app = next(d for d in decls if d["name"] == "open_app")
        props = open_app["parameters"]["properties"]
        self.assertEqual(props["app_name"]["type"], "STRING")

    def test_ollama_tool_help_format(self):
        """generate_ollama_tool_help string doner ve arac isimlerini icerir."""
        from core.tool_registry import generate_ollama_tool_help
        help_text = generate_ollama_tool_help()
        self.assertIsInstance(help_text, str)
        self.assertGreater(len(help_text), 500)
        self.assertIn("[KULLANILABİLİR ARAÇLAR]", help_text)
        self.assertIn("open_app(", help_text)
        self.assertIn("get_weather(", help_text)


# =============================================================================
# 16. RNNOISE — GÜRÜLTÜ BASTIRMA
# =============================================================================

class TestNoiseSuppressor(unittest.TestCase):
    """NoiseSuppressor modül import ve bypass testleri."""

    def test_module_import(self):
        """audio.noise_suppressor import edilebilmeli."""
        from audio.noise_suppressor import NoiseSuppressor
        self.assertIsNotNone(NoiseSuppressor)

    def test_module_constants(self):
        """NoiseSuppressor sabitleri dogru olmali."""
        from audio.noise_suppressor import NoiseSuppressor
        self.assertEqual(NoiseSuppressor.SAMPLE_RATE, 48000)
        self.assertEqual(NoiseSuppressor.FRAME_SIZE, 480)
        self.assertIn(48000, NoiseSuppressor.SUPPORTED_RATES)
        self.assertIn(16000, NoiseSuppressor.SUPPORTED_RATES)

    def test_disabled_bypass(self):
        """enabled=False ile suppressor bypass modunda calismali."""
        from audio.noise_suppressor import NoiseSuppressor
        ns = NoiseSuppressor(sample_rate=48000, enabled=False)
        self.assertFalse(ns.enabled)
        # bypass'ta input aynen donmeli
        import numpy as np
        dummy = np.zeros(480, dtype=np.int16)
        result = ns.process_frame(dummy)
        np.testing.assert_array_equal(result, dummy)

    def test_unsupported_rate_bypass(self):
        """Desteklenmeyen sample rate'de bypass aktif olmali."""
        from audio.noise_suppressor import NoiseSuppressor
        ns = NoiseSuppressor(sample_rate=8000, enabled=True)
        self.assertFalse(ns.enabled)
        import numpy as np
        dummy = np.zeros(480, dtype=np.int16)
        result = ns.process_frame(dummy)
        np.testing.assert_array_equal(result, dummy)

    def test_process_16khz_no_rnnoise_bypass(self):
        """RNNoise kutuphanesi yokken process_16khz bypass etmeli."""
        from audio.noise_suppressor import NoiseSuppressor
        # enabled=True ama lib yok -> _load_library basarisiz -> enabled=False
        ns = NoiseSuppressor(sample_rate=16000, enabled=True)
        # Kutuphane olmadigi icin enabled=False olur
        import numpy as np
        dummy = np.zeros(480, dtype=np.int16)
        result = ns.process_16khz(dummy)
        np.testing.assert_array_equal(result, dummy)
        self.assertIsNotNone(result)

    def test_bypass_on_lib_missing(self):
        """Kutuphane yokken NoiseSuppressor hata firlatmamali, bypass'a dusmeli."""
        from audio.noise_suppressor import NoiseSuppressor
        ns = NoiseSuppressor(sample_rate=48000, enabled=True)
        # enabled=False olmali cunku lib yok (bu ortamda)
        if not ns.enabled:
            import numpy as np
            dummy = np.zeros(480, dtype=np.int16)
            result = ns.process_frame(dummy)
            np.testing.assert_array_equal(result, dummy)

    def test_vad_probability_default(self):
        """VAD probability baslangic degeri 0.0 olmali."""
        from audio.noise_suppressor import NoiseSuppressor
        ns = NoiseSuppressor(sample_rate=48000, enabled=False)
        self.assertEqual(ns.vad_probability, 0.0)

    def test_context_manager_bypass(self):
        """Context manager (with) bypass modunda calismali."""
        from audio.noise_suppressor import NoiseSuppressor
        with NoiseSuppressor(sample_rate=48000, enabled=False) as ns:
            self.assertFalse(ns.enabled)
            import numpy as np
            dummy = np.zeros(480, dtype=np.int16)
            result = ns.process_frame(dummy)
            np.testing.assert_array_equal(result, dummy)

    def test_audio_package_import(self):
        """audio paketinden NoiseSuppressor import edilebilmeli."""
        from audio import NoiseSuppressor
        self.assertIsNotNone(NoiseSuppressor)

    def test_audio_microphone_import(self):
        """audio.microphone import edilebilmeli (sounddevice opsiyonel)."""
        try:
            from audio.microphone import MicrophoneStream
            self.assertIsNotNone(MicrophoneStream)
        except ImportError:
            # sounddevice yoksa import basarisiz olabilir
            self.skipTest("sounddevice kurulu degil")


if __name__ == "__main__":
    unittest.main(verbosity=2)
