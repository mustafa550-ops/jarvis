"""
System Cron — Zamanlanmış görev yönetimi.
OpenClaw'dan uyarlanmıştır.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import traceback
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "memory" / "cron.db"

# Aktif timer'ları tut
_active_timers: dict[int, threading.Timer] = {}
_timer_lock = threading.Lock()


def _init_db() -> sqlite3.Connection:
    """SQLite veritabanını başlatır."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cron_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            command TEXT NOT NULL,
            schedule_type TEXT NOT NULL,  -- once | daily | weekly | interval
            schedule_value TEXT NOT NULL,
            next_run TEXT,
            last_run TEXT,
            run_count INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def add_cron_job(name: str, command: str, schedule_type: str, schedule_value: str) -> str:
    """
    Yeni zamanlanmış görev ekler.
    schedule_type: once | daily | weekly | interval
    schedule_value:
      - once: ISO datetime (2026-06-07T08:00)
      - daily: HH:MM (08:00)
      - weekly: D-HH:MM (1-08:00 = Pazartesi 08:00)
      - interval: saniye (3600 = 1 saat)
    """
    name = (name or "").strip()
    command = (command or "").strip()
    if not name or not command:
        return "İsim ve komut zorunlu."

    schedule_type = (schedule_type or "").lower().strip()
    if schedule_type not in ("once", "daily", "weekly", "interval"):
        return "Geçersiz schedule_type: once/daily/weekly/interval"

    # next_run hesapla
    next_run = _calculate_next_run(schedule_type, schedule_value)
    if not next_run:
        return f"Geçersiz schedule_value: {schedule_value}"

    conn = _init_db()
    try:
        conn.execute(
            "INSERT INTO cron_jobs (name, command, schedule_type, schedule_value, next_run) VALUES (?, ?, ?, ?, ?)",
            (name, command, schedule_type, schedule_value, next_run.isoformat())
        )
        conn.commit()
        job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return f"Görev eklendi (ID {job_id}): '{name}' — {schedule_type} ({schedule_value})"
    except Exception as e:
        return f"Ekleme hatası: {e}"
    finally:
        conn.close()


def list_cron_jobs(enabled_only: bool = False) -> str:
    """Zamanlanmış görevleri listeler."""
    conn = _init_db()
    try:
        query = "SELECT id, name, command, schedule_type, schedule_value, next_run, last_run, run_count, enabled FROM cron_jobs"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY next_run"

        rows = conn.execute(query).fetchall()
        if not rows:
            return "Zamanlanmış görev bulunmuyor."

        lines = ["── ZAMANLANMIŞ GÖREVLER ──"]
        lines.append(f"{'ID':<5} {'İsim':<20} {'Tip':<10} {'Sonraki Çalışma':<20} {'Durum':<8}")
        lines.append("─" * 70)

        for row in rows:
            job_id, name, cmd, stype, sval, next_run, last_run, run_count, enabled = row
            status = "✓" if enabled else "✗"
            next_str = next_run[:16] if next_run else "?"
            lines.append(f"{job_id:<5} {name[:18]:<20} {stype:<10} {next_str:<20} {status:<8}")

        return "\n".join(lines)
    except Exception as e:
        return f"Listeleme hatası: {e}"
    finally:
        conn.close()


def remove_cron_job(job_id: int) -> str:
    """Görevi siler."""
    job_id = int(job_id)

    # Aktif timer'ı durdur
    with _timer_lock:
        if job_id in _active_timers:
            _active_timers[job_id].cancel()
            del _active_timers[job_id]

    conn = _init_db()
    try:
        conn.execute("DELETE FROM cron_jobs WHERE id = ?", (job_id,))
        conn.commit()
        return f"Görev {job_id} silindi."
    except Exception as e:
        return f"Silme hatası: {e}"
    finally:
        conn.close()


def toggle_cron_job(job_id: int, enabled: bool) -> str:
    """Görevi etkinleştirir/devre dışı bırakır."""
    job_id = int(job_id)
    conn = _init_db()
    try:
        conn.execute("UPDATE cron_jobs SET enabled = ? WHERE id = ?", (1 if enabled else 0, job_id))
        conn.commit()
        status = "etkinleştirildi" if enabled else "devre dışı bırakıldı"
        return f"Görev {job_id} {status}."
    except Exception as e:
        return f"Güncelleme hatası: {e}"
    finally:
        conn.close()


def _calculate_next_run(schedule_type: str, schedule_value: str) -> datetime | None:
    """Bir sonraki çalışma zamanını hesaplar."""
    now = datetime.now()

    try:
        if schedule_type == "once":
            return datetime.fromisoformat(schedule_value.replace("Z", "+00:00")).replace(tzinfo=None)

        elif schedule_type == "daily":
            hour, minute = map(int, schedule_value.split(":"))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run

        elif schedule_type == "weekly":
            day_str, time_str = schedule_value.split("-", 1)
            weekday = int(day_str)  # 0=Pazartesi
            hour, minute = map(int, time_str.split(":"))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            days_ahead = weekday - now.weekday()
            if days_ahead < 0 or (days_ahead == 0 and next_run <= now):
                days_ahead += 7
            next_run += timedelta(days=days_ahead)
            return next_run

        elif schedule_type == "interval":
            seconds = int(schedule_value)
            return now + timedelta(seconds=seconds)

    except Exception:
        traceback.print_exc()
    return None


def run_due_jobs() -> list[str]:
    """
    Vadesi gelen görevleri çalıştırır.
    Döndürülen liste: çalıştırılan görevlerin sonuçları.
    """
    now = datetime.now()
    conn = _init_db()
    results = []

    try:
        rows = conn.execute(
            "SELECT id, name, command, schedule_type, schedule_value FROM cron_jobs WHERE enabled = 1 AND next_run <= ?",
            (now.isoformat(),)
        ).fetchall()

        for row in rows:
            job_id, name, command, stype, sval = row
            # Çalıştır
            result = _execute_cron_command(command)
            results.append(f"[{name}] {result}")

            # next_run güncelle
            next_run = _calculate_next_run(stype, sval)
            if stype == "once":
                conn.execute("UPDATE cron_jobs SET last_run = ?, run_count = run_count + 1, enabled = 0 WHERE id = ?",
                           (now.isoformat(), job_id))
            else:
                conn.execute("UPDATE cron_jobs SET last_run = ?, run_count = run_count + 1, next_run = ? WHERE id = ?",
                           (now.isoformat(), next_run.isoformat() if next_run else None, job_id))
            conn.commit()

    except Exception as e:
        results.append(f"Cron hatası: {e}")
    finally:
        conn.close()

    return results


def _execute_cron_command(command: str) -> str:
    """Cron komutunu çalıştırır."""
    command = command.lower().strip()

    # Dahili komutlar
    if command.startswith("temp_cleanup"):
        from actions.system_doctor import cleanup_temp_files
        return cleanup_temp_files()
    elif command.startswith("recycle_cleanup"):
        from actions.system_doctor import cleanup_recycle_bin
        return cleanup_recycle_bin()
    elif command.startswith("health_check"):
        from actions.system_doctor import get_system_health
        return get_system_health("all")
    elif command.startswith("sys_info"):
        from actions.sys_info import sys_info
        return sys_info("all")

    # Shell komutu
    from actions.shell import shell_run
    return shell_run(command, timeout=60)


def start_cron_daemon() -> None:
    """Cron daemon'ını başlatır (her 60 saniyede kontrol)."""
    def _check():
        try:
            results = run_due_jobs()
            for r in results:
                print(f"[CRON] {r}")
        except Exception as e:
            print(f"[CRON] Hata: {e}")
        finally:
            timer = threading.Timer(60.0, _check)
            timer.daemon = True
            with _timer_lock:
                _active_timers[-1] = timer  # -1 = daemon
            timer.start()

    _check()


def stop_cron_daemon() -> None:
    """Cron daemon'ını durdurur."""
    with _timer_lock:
        for timer in _active_timers.values():
            timer.cancel()
        _active_timers.clear()


# === DISK PREDICTOR CRON (6 saatte bir) ===
def _init_disk_predictor_cron() -> None:
    """DiskPredictor otomatik kayıt cron görevi."""
    try:
        from actions.disk_predictor import DiskPredictor
        dp = DiskPredictor()

        def _run_dp():
            try:
                dp.record_sample()
            except Exception:
                traceback.print_exc()
            timer = threading.Timer(6 * 3600, _run_dp)
            timer.daemon = True
            timer.start()

        _run_dp()
    except Exception:
        traceback.print_exc()


# === NETWORK ANOMALY CRON (2 dakikada bir) ===
_nad_lock = threading.Lock()
def _init_network_anomaly_cron() -> None:
    """NetworkAnomalyDetector otomatik tarama cron görevi."""
    try:
        from actions.network_anomaly import NetworkAnomalyDetector
        nad = NetworkAnomalyDetector()

        def _run_nad():
            if not _nad_lock.acquire(blocking=False):
                timer = threading.Timer(120, _run_nad)
                timer.daemon = True
                timer.start()
                return
            try:
                nad.scan()
            except Exception:
                traceback.print_exc()
            finally:
                _nad_lock.release()
            timer = threading.Timer(120, _run_nad)
            timer.daemon = True
            timer.start()

        _run_nad()
    except Exception:
        traceback.print_exc()


# Otomatik başlat
_init_disk_predictor_cron()
_init_network_anomaly_cron()
