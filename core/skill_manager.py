"""
JARVIS Skill Manager v3 — Hot-Reload Destekli
Çalışırken yeni skill ekleme, skill güncelleme, skill kaldırma.
"""

from __future__ import annotations
import importlib.util
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Optional
from dataclasses import dataclass, field
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = BASE_DIR / "skills"


@dataclass
class SkillInfo:
    """Skill metadata ve durum bilgisi"""
    skill_id: str
    name: str
    version: str
    folder: str
    module_path: Path
    md_path: Optional[Path] = None
    triggers_path: Optional[Path] = None
    route_func: Optional[Callable[..., Any]] = None
    loaded_at: datetime = field(default_factory=datetime.now)
    last_modified: float = 0.0
    load_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "version": self.version,
            "folder": self.folder,
            "loaded_at": self.loaded_at.isoformat(),
            "last_modified": self.last_modified,
            "load_count": self.load_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "is_active": self.is_active,
        }


class SkillManager:
    """Hot-reload destekli skill yöneticisi"""

    def __init__(self, auto_reload: bool = True, reload_interval: float = 3.0):
        self._skills: dict[str, SkillInfo] = {}
        self._routers: dict[str, Callable[..., Any]] = {}
        self._folder_map: dict[str, str] = {}
        self._lock = threading.RLock()
        self._auto_reload = auto_reload
        self._reload_interval = reload_interval
        self._watcher_thread: Optional[threading.Thread] = None
        self._running = False
        self._callbacks: list[Callable[..., Any]] = []

        # İlk yükleme
        self._load_all_skills()

        # Watcher başlat
        if self._auto_reload:
            self._start_watcher()

    # ── Watcher (Hot-Reload) ─────────────────────────────────────

    def _start_watcher(self):
        """Dosya değişikliklerini izleyen thread başlat"""
        self._running = True
        self._watcher_thread = threading.Thread(
            target=self._watcher_loop,
            daemon=True,
            name="SkillWatcher"
        )
        self._watcher_thread.start()
        print(f"[SkillManager] Hot-reload watcher başlatıldı ({self._reload_interval}s)")

    def _watcher_loop(self):
        """Sürekli dosya değişikliklerini kontrol eder"""
        while self._running:
            try:
                self._check_for_changes()
            except Exception as e:
                print(f"[SkillManager] Watcher hata: {e}")
            time.sleep(self._reload_interval)

    def _check_for_changes(self):
        """Skill dosyalarında değişiklik var mı kontrol et"""
        if not SKILLS_DIR.exists():
            return

        # 1. Yeni skill'leri tespit et
        current_folders = {f.name for f in SKILLS_DIR.iterdir() if f.is_dir()}
        known_folders = set(self._folder_map.keys())

        new_folders = current_folders - known_folders
        removed_folders = known_folders - current_folders

        # Yeni skill ekle
        for folder in new_folders:
            folder_path = SKILLS_DIR / folder
            skill_file = folder_path / f"{folder}_skill.py"
            if skill_file.exists():
                print(f"[SkillManager] Yeni skill tespit edildi: {folder}")
                self._load_skill_folder(folder_path)

        # Kaldırılmış skill'leri devre dışı bırak
        for folder in removed_folders:
            skill_id = self._folder_map.get(folder)
            if skill_id and skill_id in self._skills:
                self._disable_skill(skill_id)
                print(f"[SkillManager] Skill klasörü kaldırıldı: {folder}")

        # 2. Mevcut skill'lerde değişiklik kontrolü
        for skill_id, info in list(self._skills.items()):
            if not info.is_active:
                continue

            module_path = info.module_path
            if not module_path.exists():
                self._disable_skill(skill_id)
                continue

            current_mtime = module_path.stat().st_mtime

            # SKILL.md ve triggers.json da kontrol et
            for extra_file in [info.md_path, info.triggers_path]:
                if extra_file and extra_file.exists():
                    current_mtime = max(current_mtime, extra_file.stat().st_mtime)

            if current_mtime > info.last_modified:
                print(f"[SkillManager] Skill değişikliği tespit edildi: {skill_id}")
                self._reload_skill(skill_id)

    # ── Skill Yükleme ────────────────────────────────────────────

    def _load_all_skills(self):
        """Tüm skill'leri ilk kez yükle"""
        if not SKILLS_DIR.exists():
            print("[SkillManager] skills/ klasörü bulunamadı")
            return

        for skill_folder in sorted(SKILLS_DIR.iterdir()):
            if not skill_folder.is_dir():
                continue
            self._load_skill_folder(skill_folder)

    def _load_skill_folder(self, folder_path: Path) -> bool:
        """Tek bir skill klasörünü yükle"""
        folder_name = folder_path.name
        skill_file = folder_path / f"{folder_name}_skill.py"

        if not skill_file.exists():
            return False

        try:
            # Önceden yüklü mü kontrol et
            if folder_name in self._folder_map:
                old_skill_id = self._folder_map[folder_name]
                self._disable_skill(old_skill_id)

            # Dinamik import
            module_name = f"skills.{folder_name}.{folder_name}_skill"
            spec = importlib.util.spec_from_file_location(module_name, str(skill_file))
            if spec is None:
                print(f"[SkillManager] ⚠ {skill_file} için spec alınamadı")
                return False
            module = importlib.util.module_from_spec(spec)

            # Module cache temizle (hot-reload için)
            if module_name in sys.modules:
                del sys.modules[module_name]

            # Module'i yükle
            if spec.loader is None:
                print(f"[SkillManager] ⚠ {skill_file} için loader bulunamadı")
                return False
            spec.loader.exec_module(module)

            # Skill metadata oku (None/"" → folder_name fallback)
            skill_id = getattr(module, "SKILL_ID", None) or folder_name
            skill_name = getattr(module, "SKILL_NAME", None) or folder_name
            skill_version = getattr(module, "SKILL_VERSION", "0.0.0")

            # Route fonksiyonunu bul
            route_func = None
            for attr_name in dir(module):
                if attr_name.startswith("route_") and attr_name.endswith("_request"):
                    route_func = getattr(module, attr_name)
                    break

            if not route_func:
                print(f"[SkillManager] ⚠ {folder_name}: route fonksiyonu bulunamadı")
                return False

            # SkillInfo oluştur
            md_path = folder_path / "SKILL.md"
            triggers_path = folder_path / "triggers.json"

            info = SkillInfo(
                skill_id=skill_id,
                name=skill_name,
                version=skill_version,
                folder=folder_name,
                module_path=skill_file,
                md_path=md_path if md_path.exists() else None,
                triggers_path=triggers_path if triggers_path.exists() else None,
                route_func=route_func,
                last_modified=skill_file.stat().st_mtime,
                load_count=1,
            )

            # Kaydet
            with self._lock:
                self._skills[skill_id] = info
                self._routers[skill_id] = route_func
                self._folder_map[folder_name] = skill_id

            print(f"[SkillManager] ✓ {folder_name} skill yüklendi (v{skill_version})")
            self._notify_callbacks("loaded", skill_id)
            return True

        except SyntaxError as e:
            print(f"[SkillManager] ✗ {folder_name} syntax hatası: {e}")
            self._register_failed_skill(folder_name, skill_file, f"SyntaxError: {e}")
            return False
        except Exception as e:
            print(f"[SkillManager] ✗ {folder_name} yüklenemedi: {e}")
            traceback.print_exc()
            self._register_failed_skill(folder_name, skill_file, str(e))
            return False

    def _reload_skill(self, skill_id: str):
        """Mevcut skill'i yeniden yükle (hot-reload)"""
        if skill_id not in self._skills:
            return

        info = self._skills[skill_id]
        folder_path = SKILLS_DIR / info.folder

        print(f"[SkillManager] 🔄 {skill_id} yeniden yükleniyor...")

        # Module cache temizle
        module_name = f"skills.{info.folder}.{info.folder}_skill"
        if module_name in sys.modules:
            del sys.modules[module_name]

        # Tekrar yükle
        success = self._load_skill_folder(folder_path)

        if success:
            new_info = self._skills.get(skill_id)
            if new_info:
                new_info.load_count = info.load_count + 1
                new_info.last_modified = max(
                    new_info.module_path.stat().st_mtime,
                    *[f.stat().st_mtime for f in [new_info.md_path, new_info.triggers_path] if f and f.exists()]
                )
            print(f"[SkillManager] ✓ {skill_id} yeniden yüklendi")
            self._notify_callbacks("reloaded", skill_id)
        else:
            print(f"[SkillManager] ✗ {skill_id} yeniden yüklenemedi")
            self._notify_callbacks("reload_failed", skill_id)

    def _disable_skill(self, skill_id: str):
        """Skill'i devre dışı bırak"""
        with self._lock:
            if skill_id in self._skills:
                self._skills[skill_id].is_active = False
                self._skills[skill_id].route_func = None
            if skill_id in self._routers:
                del self._routers[skill_id]

        print(f"[SkillManager] ⏸ {skill_id} devre dışı bırakıldı")
        self._notify_callbacks("disabled", skill_id)

    def _register_failed_skill(self, folder_name: str, module_path: Path, error: str):
        """Başarısız skill kaydı"""
        skill_id = f"failed-{folder_name}"
        info = SkillInfo(
            skill_id=skill_id,
            name=folder_name,
            version="0.0.0",
            folder=folder_name,
            module_path=module_path,
            last_error=error,
            is_active=False,
        )
        with self._lock:
            self._skills[skill_id] = info
            self._folder_map[folder_name] = skill_id

    # ── Callback Sistemi ─────────────────────────────────────────

    def on_reload(self, callback: Callable[..., Any]):
        """Reload event'lerini dinleyen callback ekle"""
        self._callbacks.append(callback)

    def _notify_callbacks(self, event: str, skill_id: str):
        """Tüm callback'leri bilgilendir"""
        for cb in self._callbacks:
            try:
                cb(event, skill_id)
            except Exception:
                traceback.print_exc()

    # ── Public API ───────────────────────────────────────────────

    def route(self, user_text: str) -> str | None:
        """Kullanıcı metnini tüm aktif skill'lere yönlendir"""
        with self._lock:
            routers = list(self._routers.items())

        for skill_id, router in routers:
            try:
                result = router(user_text)
                if result is not None:
                    return result
            except Exception as e:
                print(f"[SkillManager] Router hata ({skill_id}): {e}")
                if skill_id in self._skills:
                    self._skills[skill_id].error_count += 1
                    self._skills[skill_id].last_error = str(e)
                continue
        return None

    def reload_skill(self, skill_id: str) -> bool:
        """Manuel skill yeniden yükleme"""
        if skill_id not in self._skills:
            print(f"[SkillManager] Skill bulunamadı: {skill_id}")
            return False

        self._reload_skill(skill_id)
        return True

    def reload_all(self):
        """Tüm skill'leri yeniden yükle"""
        print("[SkillManager] Tüm skill'ler yeniden yükleniyor...")
        for skill_id in list(self._skills.keys()):
            if self._skills[skill_id].is_active:
                self._reload_skill(skill_id)

    def disable_skill(self, skill_id: str) -> bool:
        """Skill'i devre dışı bırak"""
        if skill_id not in self._skills:
            return False
        self._disable_skill(skill_id)
        return True

    def enable_skill(self, skill_id: str) -> bool:
        """Devre dışı skill'i tekrar aktif et"""
        if skill_id not in self._skills:
            return False

        info = self._skills[skill_id]
        folder_path = SKILLS_DIR / info.folder
        return self._load_skill_folder(folder_path)

    def get_skill_info(self, skill_id: str) -> Optional[SkillInfo]:
        """Skill bilgisi al"""
        return self._skills.get(skill_id)

    def list_skills(self) -> list[str]:
        """Aktif skill ID'lerini listele"""
        with self._lock:
            return [sid for sid, info in self._skills.items() if info.is_active]

    def get_skill_count(self) -> int:
        """Aktif skill sayısını döndür"""
        with self._lock:
            return sum(1 for info in self._skills.values() if info.is_active)

    def list_all_skills(self) -> list[dict[str, Any]]:
        """Tüm skill'lerin detaylı bilgisini listele"""
        with self._lock:
            return [info.to_dict() for info in self._skills.values()]

    def get_stats(self) -> dict[str, Any]:
        """Skill manager istatistikleri"""
        with self._lock:
            active = sum(1 for info in self._skills.values() if info.is_active)
            failed = sum(1 for info in self._skills.values() if not info.is_active)
            total_errors = sum(info.error_count for info in self._skills.values())

        return {
            "total_skills": len(self._skills),
            "active": active,
            "failed": failed,
            "total_errors": total_errors,
            "auto_reload": self._auto_reload,
            "reload_interval": self._reload_interval,
        }

    def stop_watcher(self):
        """Watcher thread'ini durdur"""
        self._running = False
        if self._watcher_thread:
            self._watcher_thread.join(timeout=5.0)
        print("[SkillManager] Watcher durduruldu")


# ── Singleton ──────────────────────────────────────────────────
_skill_manager = None


def get_skill_manager(auto_reload: bool = True, reload_interval: float = 3.0) -> SkillManager:
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager(auto_reload=auto_reload, reload_interval=reload_interval)
    return _skill_manager


def reload_skill_manager():
    """Skill manager'i sıfırla ve yeniden başlat"""
    global _skill_manager
    if _skill_manager:
        _skill_manager.stop_watcher()
        _skill_manager = None
    return get_skill_manager()
