"""
File Watcher — Gerçek zamanlı dosya sistemi izleyici.
OpenClaw'dan uyarlanmıştır.

Kullanım:
    from actions.watchdog.file_watcher import FileWatcher
    watcher = FileWatcher(["~/Downloads", "~/Desktop"], ui_callback)
    watcher.start()

    # Durdurmak için:
    watcher.stop()
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Deque, Optional

# watchdog opsiyonel — yoksa polling fallback
HAS_WATCHDOG = False
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    pass


class JARVISEventHandler:  # duck-typed: watchdog FileSystemEventHandler metotlarını sağlar
    """watchdog event handler — watchdog yoksa dummy."""

    def __init__(self, callback: Callable[[str, str, Optional[str]], None]):
        self._callback = callback

    def on_created(self, event):
        if not event.is_directory:
            self._callback("created", event.src_path, None)

    def on_deleted(self, event):
        if not event.is_directory:
            self._callback("deleted", event.src_path, None)

    def on_modified(self, event):
        if not event.is_directory:
            self._callback("modified", event.src_path, None)

    def on_moved(self, event):
        if not event.is_directory:
            self._callback("moved", event.src_path, event.dest_path)


class FileWatcher(threading.Thread):
    """
    Gerçek zamanlı dosya sistemi izleyici.

    Özellikler:
    - watchdog kütüphanesi varsa native izleme (düşük CPU)
    - Yoksa 3 saniyelik polling fallback
    - Debounce: 2 saniye içinde aynı dosyaya tekrar event gelirse birleştirir
    - Event geçmişi: son 100 event'i tutar
    - Kritik dosya türleri için TTS bildirim (opsiyonel)
    """

    # Kritik uzantılar — TTS bildirim tetikler
    CRITICAL_EXTENSIONS = {".exe", ".zip", ".rar", ".7z", ".msi", ".bat", ".cmd", ".ps1"}

    # Max geçmiş boyutu
    MAX_HISTORY = 100

    def __init__(
        self,
        paths: list[str],
        ui_callback: Any = None,
        tts_callback: Any = None,
        enable_tts: bool = False,
    ):
        super().__init__(daemon=True, name="FileWatcher")
        self.paths = [Path(p).expanduser().resolve() for p in paths if p]
        self.ui: Any = ui_callback
        self.tts: Any = tts_callback
        self.enable_tts = enable_tts

        # Debounce: {abs_path: last_event_time}
        self._debounce: dict[str, float] = {}
        self._debounce_lock = threading.Lock()
        self._debounce_interval = 2.0  # saniye

        # Event geçmişi
        self._history: Deque[dict[str, Any]] = deque(maxlen=self.MAX_HISTORY)
        self._history_lock = threading.Lock()

        # Polling fallback için
        self._last_snapshot: dict[str, float] = {}  # {path: mtime}
        self._polling_interval = 3.0

        # Durum
        self._running = False
        self._observer: Any = None

    def run(self):
        """Ana izleme döngüsü."""
        self._running = True

        if HAS_WATCHDOG:
            self._run_watchdog()
        else:
            self._run_polling()

    def _run_watchdog(self):
        """watchdog ile native izleme."""
        from watchdog.observers import Observer

        assert HAS_WATCHDOG, "watchdog kurulu değil"
        observer = Observer()
        self._observer = observer

        for path in self.paths:
            if path.exists() and path.is_dir():
                handler = JARVISEventHandler(self._on_event)
                observer.schedule(handler, str(path), recursive=True)
                self._log(f"📁 İzleniyor: {path}")

        observer.start()

        while self._running:
            time.sleep(0.5)

        observer.stop()
        observer.join()

    def _run_polling(self):
        """watchdog yoksa polling fallback."""
        self._log("⚠️ watchdog bulunamadı — polling modu aktif (pip install watchdog)")

        # İlk snapshot
        self._take_snapshot()

        while self._running:
            time.sleep(self._polling_interval)
            self._poll_changes()

    def _take_snapshot(self):
        """Mevcut dosya durumunu kaydet."""
        self._last_snapshot.clear()
        for path in self.paths:
            if not path.exists():
                continue
            try:
                for root, _, files in os.walk(path):
                    for filename in files:
                        filepath = Path(root) / filename
                        try:
                            self._last_snapshot[str(filepath)] = filepath.stat().st_mtime
                        except OSError:
                            continue
            except Exception:
                continue

    def _poll_changes(self):
        """Polling ile değişiklikleri tespit et."""
        current_snapshot: dict[str, float] = {}

        for path in self.paths:
            if not path.exists():
                continue
            try:
                for root, _, files in os.walk(path):
                    for filename in files:
                        filepath = Path(root) / filename
                        try:
                            current_snapshot[str(filepath)] = filepath.stat().st_mtime
                        except OSError:
                            continue
            except Exception:
                continue

        # Yeni dosyalar
        new_files = set(current_snapshot.keys()) - set(self._last_snapshot.keys())
        for f in new_files:
            self._on_event("created", f, None)

        # Silinen dosyalar
        deleted_files = set(self._last_snapshot.keys()) - set(current_snapshot.keys())
        for f in deleted_files:
            self._on_event("deleted", f, None)

        # Değişen dosyalar
        for f in current_snapshot:
            if f in self._last_snapshot and current_snapshot[f] != self._last_snapshot[f]:
                self._on_event("modified", f, None)

        self._last_snapshot = current_snapshot

    def _on_event(self, event_type: str, src_path: str, dest_path: Optional[str] = None):
        """Bir dosya event'i alındığında çağrılır."""
        now = time.time()
        abs_path = str(Path(src_path).resolve())

        # Debounce kontrolü
        with self._debounce_lock:
            last_time = self._debounce.get(abs_path, 0)
            if now - last_time < self._debounce_interval:
                return
            self._debounce[abs_path] = now

        # Event'i kaydet
        event = {
            "type": event_type,
            "src": src_path,
            "dest": dest_path,
            "time": now,
            "filename": Path(src_path).name,
        }

        with self._history_lock:
            self._history.append(event)

        # UI'ye bildir
        msg = self._format_event(event_type, src_path, dest_path)
        self._log(msg)

        # Kritik dosya kontrolü — TTS bildirim
        if self.enable_tts and self.tts:
            ext = Path(src_path).suffix.lower()
            if ext in self.CRITICAL_EXTENSIONS and event_type in ("created", "deleted"):
                action = "indirildi" if event_type == "created" else "silindi"
                self._tts_speak(f"Yeni dosya {action}: {Path(src_path).name}")

    def _format_event(self, event_type: str, src: str, dest: Optional[str]) -> str:
        """Event'i okunabilir formata çevirir."""
        fname = Path(src).name
        icons = {
            "created": "📄",
            "deleted": "🗑️",
            "modified": "✏️",
            "moved": "📦",
        }
        icon = icons.get(event_type, "❓")

        if event_type == "moved" and dest:
            return f"{icon} {fname} → {Path(dest).name}"
        return f"{icon} {fname} — {event_type}"

    def _log(self, message: str):
        """UI log paneline yazar."""
        ui = self.ui
        if ui is not None and hasattr(ui, "write_log"):
            try:
                if threading.current_thread() is not threading.main_thread():
                    ui.after(0, lambda: ui.write_log(message))
                else:
                    ui.write_log(message)
            except Exception:
                traceback.print_exc()

    def _tts_speak(self, message: str):
        """TTS ile konuşur."""
        if self.tts and hasattr(self.tts, "speak"):
            try:
                self.tts.speak(message)
            except Exception:
                traceback.print_exc()

    def stop(self):
        """İzlemeyi durdurur."""
        self._running = False
        if self._observer:
            self._observer.stop()

    def get_recent_events(self, limit: int = 10) -> list[dict[str, Any]]:
        """Son event'leri döndürür."""
        with self._history_lock:
            return list(self._history)[-limit:]

    def get_event_summary(self, seconds: int = 300) -> str:
        """Son N saniyedeki event özetini döndürür."""
        cutoff = time.time() - seconds

        with self._history_lock:
            recent = [e for e in self._history if e["time"] >= cutoff]

        if not recent:
            return f"Son {seconds//60} dakikada değişiklik yok."

        created = len([e for e in recent if e["type"] == "created"])
        deleted = len([e for e in recent if e["type"] == "deleted"])
        modified = len([e for e in recent if e["type"] == "modified"])
        moved = len([e for e in recent if e["type"] == "moved"])

        lines = [f"── SON {seconds//60} DAKİKA ({len(recent)} event) ──"]
        if created: lines.append(f"  📄 Oluşturuldu: {created}")
        if deleted: lines.append(f"  🗑️ Silindi: {deleted}")
        if modified: lines.append(f"  ✏️ Değişti: {modified}")
        if moved: lines.append(f"  📦 Taşındı: {moved}")

        # Son 5 dosya
        lines.append("\nSon dosyalar:")
        for e in recent[-5:]:
            fname = e["filename"][:40]
            lines.append(f"  {fname}")

        return "\n".join(lines)


def watch_paths(paths: list[str], ui_callback=None, tts_callback=None, enable_tts: bool = False) -> FileWatcher:
    """
    Hızlı başlatma fonksiyonu.

    Örnek:
        watcher = watch_paths(["~/Downloads", "~/Desktop"], ui)
        watcher.start()

        # Sonra:
        print(watcher.get_event_summary(600))
        watcher.stop()
    """
    watcher = FileWatcher(paths, ui_callback, tts_callback, enable_tts)
    return watcher
