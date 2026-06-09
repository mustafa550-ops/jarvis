"""
Process Timeline — Süreç başlangıç/bitiş zaman çizelgesi ve kategorizasyon.
OpenClaw'dan uyarlanmıştır.

Kullanım:
    from actions.process_timeline import ProcessTimeline
    timeline = ProcessTimeline()
    timeline.poll()  # Her 5 saniyede çağrılır

    print(timeline.get_daily_summary())
    print(timeline.get_current_sessions())
    print(timeline.get_weekly_summary("game"))
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import psutil

import traceback
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "memory" / "process_timeline.db"


class ProcessTimeline:
    """
    Süreç başlangıç/bitiş zaman çizelgesi.

    Özellikler:
    - Her 5 saniyede aktif süreçleri tarar
    - Yeni/silinen süreçleri tespit eder
    - Süreçleri kategorize eder (browser, game, ide, media, system, communication, other)
    - Günlük/haftalık/aylık özet raporlar
    - SQLite kalıcı depolama
    """

    CATEGORIES = {
        "browser": r"chrome|firefox|edge|brave|opera|safari|vivaldi|tor",
        "game": r"steam|epicgames|origin|battlefield|valorant|lol|minecraft|fortnite|pubg|cs2|dota|gta",
        "ide": r"code|pycharm|intellij|visualstudio|eclipse|sublime|atom|vim|neovim|cursor",
        "media": r"spotify|vlc|mediaplayer|netflix|youtube|itunes|groove|winamp",
        "system": r"explorer|svchost|services|lsass|csrss|winlogon|taskhost|dwm",
        "communication": r"discord|teams|zoom|slack|telegram|whatsapp|signal|skype",
        "office": r"word|excel|powerpoint|outlook|onenote|acrobat|pdf",
        "dev": r"docker|kubectl|git|node|python|java|gradle|maven",
    }

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._init_db()
        self._active_processes: dict[int, dict] = {}  # {pid: {"name", "start", "ram_peak", "cpu_samples"}}
        self._last_poll = 0.0

    def _init_db(self):
        """SQLite veritabanını başlatır."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS process_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pid INTEGER NOT NULL,
                name TEXT NOT NULL,
                category TEXT,
                start_time REAL NOT NULL,
                end_time REAL,
                duration REAL,
                cpu_avg REAL,
                ram_peak REAL,
                date TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON process_events(date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_name ON process_events(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON process_events(category)")
        conn.commit()
        conn.close()

    def poll(self) -> str:
        """
        Aktif süreçleri tarar, yeni/silinenleri tespit eder.
        Her 5 saniyede bir çağrılmalı.
        """
        now = time.time()
        current_pids = set()

        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = p.info
                pid = info["pid"]
                name = info["name"]
                current_pids.add(pid)

                if pid not in self._active_processes:
                    # Yeni süreç
                    self._active_processes[pid] = {
                        "name": name,
                        "start": now,
                        "ram_peak": info.get("memory_percent") or 0.0,
                        "cpu_samples": [info.get("cpu_percent") or 0.0],
                    }
                else:
                    # Güncelle
                    ram = info.get("memory_percent") or 0.0
                    if ram > self._active_processes[pid]["ram_peak"]:
                        self._active_processes[pid]["ram_peak"] = ram
                    self._active_processes[pid]["cpu_samples"].append(info.get("cpu_percent") or 0.0)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Biten süreçleri kaydet
        ended = set(self._active_processes.keys()) - current_pids
        for pid in ended:
            proc = self._active_processes.pop(pid)
            self._save_event(pid, proc["name"], proc["start"], now, proc["ram_peak"], proc["cpu_samples"])

        return f"Poll: {len(current_pids)} aktif, {len(ended)} sonlandı"

    def _save_event(self, pid: int, name: str, start: float, end: float, ram_peak: float, cpu_samples: list):
        """Süreç olayını veritabanına kaydeder."""
        duration = end - start
        if duration < 5.0:  # 5 saniyeden kısa süreçleri atla (gürültü)
            return

        category = self._categorize(name)
        date = datetime.fromtimestamp(start).strftime("%Y-%m-%d")
        cpu_avg = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT INTO process_events (pid, name, category, start_time, end_time, duration, cpu_avg, ram_peak, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (pid, name, category, start, end, duration, cpu_avg, ram_peak, date)
            )
            conn.commit()
        except Exception:
            traceback.print_exc()
        finally:
            conn.close()

    def _categorize(self, name: str) -> str:
        """Süreç adını kategorize eder."""
        name_lower = name.lower()
        for cat, pattern in self.CATEGORIES.items():
            if re.search(pattern, name_lower):
                return cat
        return "other"

    def get_daily_summary(self, date: Optional[str] = None) -> str:
        """
        Günlük süreç özet raporu.

        date: YYYY-MM-DD formatında, boşsa bugün.
        """
        date = date or datetime.now().strftime("%Y-%m-%d")

        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                """SELECT name, category, SUM(duration), COUNT(*), AVG(cpu_avg), MAX(ram_peak)
                   FROM process_events WHERE date = ? GROUP BY name ORDER BY SUM(duration) DESC""",
                (date,)
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return f"{date} için kayıt bulunamadı."

        lines = [f"── {date} SÜREÇ ÖZETİ ──"]
        category_totals = {}
        total_duration = 0

        for name, cat, dur, count, cpu_avg, ram_peak in rows[:15]:
            hours = dur / 3600.0
            total_duration += dur
            category_totals[cat] = category_totals.get(cat, 0) + dur

            cpu_str = f"CPU %{cpu_avg:.0f}" if cpu_avg else ""
            ram_str = f"RAM %{ram_peak:.1f}" if ram_peak else ""
            extra = f" ({cpu_str}, {ram_str})" if cpu_str or ram_str else ""

            lines.append(f"  {name}: {hours:.1f} saat ({count} kez){extra}")

        lines.append("")
        lines.append(f"Toplam: {total_duration/3600:.1f} saat, {len(rows)} farklı süreç")
        lines.append("")
        lines.append("Kategori Özeti:")
        for cat, cat_dur in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
            pct = (cat_dur / total_duration * 100) if total_duration else 0
            lines.append(f"  {cat}: {cat_dur/3600:.1f} saat (%{pct:.0f})")

        return "\n".join(lines)

    def get_current_sessions(self) -> str:
        """Şu an çalışan süreçlerin ne kadar süredir açık olduğu."""
        now = time.time()

        if not self._active_processes:
            return "Aktif süreç kaydı yok (henüz poll çalışmadı)."

        lines = ["── AKTİF SÜREÇLER ──"]

        # Süreye göre sırala
        sorted_procs = sorted(
            self._active_processes.items(),
            key=lambda x: x[1]["start"]
        )

        for pid, proc in sorted_procs:
            duration = now - proc["start"]
            hours = int(duration / 3600)
            mins = int((duration % 3600) / 60)

            time_str = f"{hours}s {mins}d" if hours > 0 else f"{mins}d"
            ram = proc["ram_peak"]
            ram_str = f" RAM %{ram:.1f}" if ram else ""

            lines.append(f"  {proc['name']} (PID {pid}): {time_str}{ram_str}")

        return "\n".join(lines)

    def get_weekly_summary(self, category: Optional[str] = None) -> str:
        """
        Son 7 günün özet raporu.

        category: Sadece belirli kategori (browser, game, ide, vb.)
        """
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        conn = sqlite3.connect(str(self.db_path))
        try:
            if category:
                rows = conn.execute(
                    """SELECT name, SUM(duration), COUNT(*) FROM process_events 
                       WHERE date >= ? AND category = ? GROUP BY name ORDER BY SUM(duration) DESC""",
                    (cutoff, category)
                ).fetchall()
                cat_filter = f" ({category})"
            else:
                rows = conn.execute(
                    """SELECT name, SUM(duration), COUNT(*) FROM process_events 
                       WHERE date >= ? GROUP BY name ORDER BY SUM(duration) DESC""",
                    (cutoff,)
                ).fetchall()
                cat_filter = ""
        finally:
            conn.close()

        if not rows:
            return f"Son 7 gün{cat_filter} için kayıt bulunamadı."

        lines = [f"── SON 7 GÜN{cat_filter} ──"]
        total_hours = 0

        for name, dur, count in rows[:20]:
            hours = dur / 3600.0
            total_hours += hours
            lines.append(f"  {name}: {hours:.1f} saat ({count} kez)")

        lines.append(f"\nToplam: {total_hours:.1f} saat, {len(rows)} farklı süreç")
        return "\n".join(lines)

    def get_process_stats(self, name_pattern: str) -> str:
        """
        Belirli bir süreç için istatistikler.

        name_pattern: Süreç adı veya regex (örn. "chrome", "steam")
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                """SELECT date, SUM(duration), COUNT(*), AVG(cpu_avg), MAX(ram_peak)
                   FROM process_events WHERE name LIKE ? GROUP BY date ORDER BY date DESC""",
                (f"%{name_pattern}%",)
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return f"'{name_pattern}' için kayıt bulunamadı."

        lines = [f"── '{name_pattern}' İSTATİSTİKLERİ ──"]
        total_hours = 0
        total_runs = 0

        for date, dur, count, cpu_avg, ram_peak in rows[:14]:
            hours = dur / 3600.0
            total_hours += hours
            total_runs += count
            lines.append(f"  {date}: {hours:.1f} saat ({count} kez)")

        lines.append(f"\nToplam: {total_hours:.1f} saat, {total_runs} çalışma")
        return "\n".join(lines)

    def get_category_breakdown(self, days: int = 7) -> str:
        """
        Kategori bazında zaman dağılımı.
        """
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                """SELECT category, SUM(duration), COUNT(DISTINCT name) FROM process_events 
                   WHERE date >= ? GROUP BY category ORDER BY SUM(duration) DESC""",
                (cutoff,)
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return f"Son {days} gün için kategori verisi bulunamadı."

        total = sum(r[1] for r in rows)
        lines = [f"── SON {days} GÜN KATEGORİ DAĞILIMI ──"]

        for cat, dur, count in rows:
            hours = dur / 3600.0
            pct = (dur / total * 100) if total else 0
            bar = "█" * int(pct / 5)
            lines.append(f"  {cat:<15} {bar:<20} {hours:.1f} saat (%{pct:.0f}) — {count} süreç")

        return "\n".join(lines)

    def cleanup_old_records(self, keep_days: int = 90) -> str:
        """Eski kayıtları temizler."""
        cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d")

        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute("DELETE FROM process_events WHERE date < ?", (cutoff,))
            deleted = cursor.rowcount
            conn.commit()
            return f"Eski kayıtlar temizlendi: {deleted} satır silindi ({keep_days} günden eski)."
        except Exception as e:
            return f"Temizlik hatası: {e}"
        finally:
            conn.close()


def poll_processes() -> str:
    """Hızlı başlatma: süreç poll."""
    return ProcessTimeline().poll()


def get_today_summary() -> str:
    """Hızlı başlatma: bugünün özeti."""
    return ProcessTimeline().get_daily_summary()
