"""
Disk Predictor — Disk doluluk trend analizi ve tahmini.
OpenClaw'dan uyarlanmıştır.

Kullanım:
    from actions.disk_predictor import DiskPredictor
    predictor = DiskPredictor()
    predictor.record_sample()  # Her 6 saatte bir çağrılır

    result = predictor.predict_full("C:\\")
    # {"days_until_full": 47.3, "trend": "up", "confidence": 0.92, "daily_growth": 0.3}
"""

from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import psutil

import traceback
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "memory" / "disk_history.db"


class DiskPredictor:
    """
    Disk doluluk trend analizi ve tahmin.

    Her örneklemde:
    - timestamp, mountpoint, percent, used_bytes, free_bytes kaydedilir
    - Lineer regresyon ile günlük büyüme hızı hesaplanır
    - Doluluk %100 olduğu gün tahmin edilir

    Minimum 7 örneklem gerekli (güvenilir tahmin için 14+ önerilir).
    """

    # Minimum örneklem sayısı
    MIN_SAMPLES = 7

    # Güven eşikleri
    CONFIDENCE_HIGH = 0.85
    CONFIDENCE_MEDIUM = 0.60

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _init_db(self):
        """SQLite veritabanını başlatır."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS disk_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                mountpoint TEXT NOT NULL,
                percent REAL NOT NULL,
                used_bytes INTEGER NOT NULL,
                free_bytes INTEGER NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mount_time ON disk_history(mountpoint, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON disk_history(timestamp)")
        conn.commit()
        conn.close()

    def record_sample(self) -> str:
        """
        Mevcut disk durumunu kaydeder.
        system_cron tarafından her 6 saatte bir çağrılır.
        """
        conn = sqlite3.connect(str(self.db_path))
        now = time.time()
        recorded = 0

        try:
            for part in psutil.disk_partitions():
                if os.name == "nt" and ("cdrom" in part.opts or part.fstype == ""):
                    continue
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    conn.execute(
                        "INSERT INTO disk_history (timestamp, mountpoint, percent, used_bytes, free_bytes) VALUES (?, ?, ?, ?, ?)",
                        (now, part.mountpoint, usage.percent, usage.used, usage.free)
                    )
                    recorded += 1
                except Exception:
                    continue
            conn.commit()
            return f"Disk örneği kaydedildi: {recorded} mountpoint"
        except Exception as e:
            return f"Kayıt hatası: {e}"
        finally:
            conn.close()

    def predict_full(self, mountpoint: Optional[str] = None) -> dict:
        """
        Lineer regresyon ile disk doluluk tahmini.

        Döndürür:
        {
            "days_until_full": float | None,  # None = asla dolmaz (azalıyor)
            "trend": "up" | "down" | "stable",
            "confidence": float,  # 0-1 arası R²
            "daily_growth": float,  # Günlük % artış
            "current_percent": float,
            "sample_count": int,
            "prediction_date": str | None,  # ISO format
        }
        """
        mountpoint = mountpoint or ("C:\\" if os.name == "nt" else "/")

        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                "SELECT timestamp, percent, used_bytes FROM disk_history WHERE mountpoint = ? ORDER BY timestamp",
                (mountpoint,)
            ).fetchall()
        finally:
            conn.close()

        if len(rows) < self.MIN_SAMPLES:
            return {
                "error": f"Yetersiz veri ({len(rows)}/{self.MIN_SAMPLES} örneklem). En az {self.MIN_SAMPLES} gün gerekli.",
                "days_until_full": None,
                "trend": "unknown",
                "confidence": 0.0,
                "daily_growth": 0.0,
                "current_percent": 0.0,
                "sample_count": len(rows),
                "prediction_date": None,
            }

        return self._calculate_prediction(rows)

    def _calculate_prediction(self, rows: list[tuple]) -> dict:
        """Lineer regresyon hesaplaması."""
        try:
            import numpy as np
        except ImportError:
            # numpy yoksa basit hesaplama
            return self._simple_prediction(rows)

        timestamps = np.array([r[0] for r in rows], dtype=np.float64)
        percents = np.array([r[1] for r in rows], dtype=np.float64)

        # Gün cinsinden normalize et (ilk örneklem = 0)
        days = (timestamps - timestamps[0]) / 86400.0

        # Lineer regresyon: percent = slope * days + intercept
        coeffs = np.polyfit(days, percents, 1)
        slope = float(coeffs[0])  # Günlük değişim %
        intercept = float(coeffs[1])

        current_percent = float(percents[-1])

        # Trend
        if slope > 0.5:
            trend = "up"
        elif slope < -0.5:
            trend = "down"
        else:
            trend = "stable"

        # Doluluk tahmini
        if slope <= 0:
            days_until_full = float('inf')
            prediction_date = None
        else:
            days_until_full = (100.0 - current_percent) / slope
            prediction_date = (datetime.now() + timedelta(days=days_until_full)).strftime("%Y-%m-%d")

        # R² (güven skoru)
        predicted = np.polyval(coeffs, days)
        ss_res = np.sum((percents - predicted) ** 2)
        ss_tot = np.sum((percents - np.mean(percents)) ** 2)
        r2 = float(1 - (ss_res / ss_tot)) if ss_tot != 0 else 0.0
        r2 = max(0.0, min(1.0, r2))

        return {
            "days_until_full": round(days_until_full, 1) if days_until_full != float('inf') else None,
            "trend": trend,
            "confidence": round(r2, 2),
            "daily_growth": round(slope, 2),
            "current_percent": round(current_percent, 1),
            "sample_count": len(rows),
            "prediction_date": prediction_date,
        }

    def _simple_prediction(self, rows: list[tuple]) -> dict:
        """numpy yoksa basit ortalama büyüme hızı."""
        if len(rows) < 2:
            return {
                "error": "Yetersiz veri",
                "days_until_full": None,
                "trend": "unknown",
                "confidence": 0.0,
                "daily_growth": 0.0,
                "current_percent": rows[-1][1] if rows else 0.0,
                "sample_count": len(rows),
                "prediction_date": None,
            }

        # İlk ve son örneklem arasındaki değişim
        first_time, first_pct, _ = rows[0]
        last_time, last_pct, _ = rows[-1]

        days_diff = (last_time - first_time) / 86400.0
        pct_diff = last_pct - first_pct

        if days_diff <= 0:
            return {
                "error": "Geçersiz zaman aralığı",
                "days_until_full": None,
                "trend": "unknown",
                "confidence": 0.0,
                "daily_growth": 0.0,
                "current_percent": last_pct,
                "sample_count": len(rows),
                "prediction_date": None,
            }

        daily_growth = pct_diff / days_diff

        if daily_growth <= 0:
            days_until_full = float('inf')
            trend = "down" if daily_growth < -0.5 else "stable"
            prediction_date = None
        else:
            days_until_full = (100.0 - last_pct) / daily_growth
            trend = "up"
            prediction_date = (datetime.now() + timedelta(days=days_until_full)).strftime("%Y-%m-%d")

        return {
            "days_until_full": round(days_until_full, 1) if days_until_full != float('inf') else None,
            "trend": trend,
            "confidence": 0.5,  # Basit hesaplama = orta güven
            "daily_growth": round(daily_growth, 2),
            "current_percent": round(last_pct, 1),
            "sample_count": len(rows),
            "prediction_date": prediction_date,
        }

    def get_disk_history(self, mountpoint: Optional[str] = None, days: int = 30) -> str:
        """Son N günün disk geçmişini raporlar."""
        mountpoint = mountpoint or ("C:\\" if os.name == "nt" else "/")
        cutoff = time.time() - (days * 86400)

        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                "SELECT timestamp, percent, used_bytes, free_bytes FROM disk_history WHERE mountpoint = ? AND timestamp >= ? ORDER BY timestamp",
                (mountpoint, cutoff)
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return f"{mountpoint} için son {days} günde kayıt bulunamadı."

        lines = [f"── {mountpoint} DISK GEÇMİŞİ (son {days} gün) ──"]
        lines.append(f"{'Tarih':<20} {'Doluluk%':<10} {'Kullanılan':<15} {'Boş':<15}")
        lines.append("─" * 65)

        for ts, pct, used, free in rows:
            date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
            used_gb = used / (1024**3)
            free_gb = free / (1024**3)
            lines.append(f"{date_str:<20} {pct:<10.1f} {used_gb:<15.1f}GB {free_gb:<15.1f}GB")

        return "\n".join(lines)

    def cleanup_old_records(self, keep_days: int = 90) -> str:
        """Eski kayıtları temizler."""
        cutoff = time.time() - (keep_days * 86400)

        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute("DELETE FROM disk_history WHERE timestamp < ?", (cutoff,))
            deleted = cursor.rowcount
            conn.commit()
            return f"Eski kayıtlar temizlendi: {deleted} satır silindi ({keep_days} günden eski)."
        except Exception as e:
            return f"Temizlik hatası: {e}"
        finally:
            conn.close()

    def get_all_predictions(self) -> str:
        """Tüm mountpoint'ler için tahmin raporu."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            mountpoints = [r[0] for r in conn.execute(
                "SELECT DISTINCT mountpoint FROM disk_history"
            ).fetchall()]
        finally:
            conn.close()

        if not mountpoints:
            return "Henüz disk verisi kaydedilmemiş."

        lines = ["── TÜM DISK TAHMİNLERİ ──"]

        for mp in mountpoints:
            pred = self.predict_full(mp)

            if "error" in pred:
                lines.append(f"\n{mp}: {pred['error']}")
                continue

            status = "✓" if pred["days_until_full"] and pred["days_until_full"] > 30 else "⚠" if pred["days_until_full"] and pred["days_until_full"] > 7 else "✗"
            lines.append(f"\n{status} {mp}")
            lines.append(f"  Mevcut: %{pred['current_percent']:.1f}")
            lines.append(f"  Trend: {pred['trend']} (günlük %{pred['daily_growth']:.2f})")

            if pred["days_until_full"] is None:
                lines.append(f"  Tahmin: Dolmayacak (azalıyor)")
            elif pred["days_until_full"] == float('inf'):
                lines.append(f"  Tahmin: Dolmayacak")
            else:
                lines.append(f"  Tahmin: {pred['days_until_full']:.0f} gün içinde dolacak ({pred['prediction_date']})")

            conf_icon = "✓" if pred["confidence"] >= self.CONFIDENCE_HIGH else "~" if pred["confidence"] >= self.CONFIDENCE_MEDIUM else "?"
            lines.append(f"  Güven: {conf_icon} %{pred['confidence']*100:.0f} ({pred['sample_count']} örneklem)")

        return "\n".join(lines)


def record_disk_sample() -> str:
    """Hızlı başlatma: disk örneği kaydet."""
    return DiskPredictor().record_sample()


def predict_disk_full(mountpoint: Optional[str] = None) -> dict:
    """Hızlı başlatma: disk tahmini."""
    return DiskPredictor().predict_full(mountpoint)
