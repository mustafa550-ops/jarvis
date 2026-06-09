"""
System Doctor — Sistem sağlık teşhisi ve otomatik raporlama.
OpenClaw'dan uyarlanmıştır.
"""

from __future__ import annotations

import os
import shutil
import socket
from datetime import datetime, timedelta
from pathlib import Path

import psutil


def get_system_health(query: str = "all") -> str:
    """
    Sistem sağlık raporu üretir.
    query: all | disk | memory | cpu | network | startup | processes | temperature
    """
    query = (query or "").lower().strip()
    results = []

    if query in ("all", "disk", "depolama"):
        results.append(_check_disk_health())
    if query in ("all", "memory", "ram", "bellek"):
        results.append(_check_memory_health())
    if query in ("all", "cpu", "işlemci", "islemci"):
        results.append(_check_cpu_health())
    if query in ("all", "network", "ağ", "ag"):
        results.append(_check_network_health())
    if query in ("all", "startup", "başlangıç", "baslangic"):
        results.append(_check_startup_health())
    if query in ("all", "processes", "süreçler", "surecler"):
        results.append(_check_processes_health())
    if query in ("all", "temperature", "sıcaklık", "sicaklik"):
        results.append(_check_temperature())

    if not results:
        return "Bilinmeyen sorgu: all/disk/memory/cpu/network/startup/processes/temperature"
    return "\n\n".join(r for r in results if r)


def _check_disk_health() -> str:
    """Disk sağlığı ve doluluk analizi."""
    partitions = psutil.disk_partitions()
    lines = ["── DISK SAĞLIĞI ──"]
    warnings = []

    for part in partitions:
        if os.name == "nt" and ("cdrom" in part.opts or part.fstype == ""):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            total_gb = usage.total / (1024**3)
            used_gb = usage.used / (1024**3)
            free_gb = usage.free / (1024**3)
            pct = usage.percent

            status = "✓" if pct < 80 else "⚠" if pct < 90 else "✗"
            lines.append(f"{status} {part.device} ({part.mountpoint}): {used_gb:.1f}GB / {total_gb:.1f}GB (%{pct:.0f})")

            if pct >= 90:
                warnings.append(f"KRİTİK: {part.device} %{pct:.0f} dolu!")
            elif pct >= 80:
                warnings.append(f"UYARI: {part.device} %{pct:.0f} dolu.")
        except Exception:
            continue

    # Temp klasörü kontrolü
    temp_size = _get_folder_size(Path(os.environ.get("TEMP", "/tmp")))
    if temp_size > 1024**3:  # 1GB
        warnings.append(f"UYARI: Temp klasörü {temp_size / (1024**3):.1f}GB.")

    if warnings:
        lines.append("")
        lines.extend(warnings)

    return "\n".join(lines)


def _check_memory_health() -> str:
    """RAM ve swap kullanımı."""
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    lines = ["── BELLEK SAĞLIĞI ──"]

    total_gb = vm.total / (1024**3)
    used_gb = vm.used / (1024**3)
    lines.append(f"RAM: {used_gb:.1f}GB / {total_gb:.1f}GB (%{vm.percent:.0f})")

    if swap.total > 0:
        swap_used = swap.used / (1024**3)
        swap_total = swap.total / (1024**3)
        lines.append(f"Swap: {swap_used:.1f}GB / {swap_total:.1f}GB (%{swap.percent:.0f})")

    # Bellek yiyen en büyük 3 süreç
    procs = sorted(
        ((p.info["pid"], p.info["name"], p.info["memory_percent"])
         for p in psutil.process_iter(["pid", "name", "memory_percent"])
         if p.info["memory_percent"] is not None),
        key=lambda x: x[2],
        reverse=True,
    )[:3]

    if procs:
        lines.append("")
        lines.append("En çok RAM kullanan:")
        for pid, name, pct in procs:
            lines.append(f"  • {name} (PID {pid}): %{pct:.1f}")

    if vm.percent > 90:
        lines.append("")
        lines.append("KRİTİK: RAM kullanımı çok yüksek!")
    elif vm.percent > 75:
        lines.append("")
        lines.append("UYARI: RAM kullanımı yüksek.")

    return "\n".join(lines)


def _check_cpu_health() -> str:
    """CPU kullanımı ve yük analizi."""
    cpu_pct = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count(logical=True)
    freq = psutil.cpu_freq()
    lines = ["── CPU SAĞLIĞI ──"]
    lines.append(f"Kullanım: %{cpu_pct:.1f} ({cpu_count} çekirdek)")
    if freq:
        lines.append(f"Frekans: {freq.current:.0f} MHz (max {freq.max:.0f} MHz)")

    # CPU yiyen en büyük 3 süreç
    procs = sorted(
        ((p.info["pid"], p.info["name"], p.info["cpu_percent"])
         for p in psutil.process_iter(["pid", "name", "cpu_percent"])
         if p.info["cpu_percent"] is not None),
        key=lambda x: x[2],
        reverse=True,
    )[:3]

    if procs:
        lines.append("")
        lines.append("En çok CPU kullanan:")
        for pid, name, pct in procs:
            lines.append(f"  • {name} (PID {pid}): %{pct:.1f}")

    if cpu_pct > 90:
        lines.append("")
        lines.append("KRİTİK: CPU kullanımı çok yüksek!")
    elif cpu_pct > 70:
        lines.append("")
        lines.append("UYARI: CPU kullanımı yüksek.")

    return "\n".join(lines)


def _check_network_health() -> str:
    """Ağ bağlantısı ve istatistikler."""
    lines = ["── AĞ SAĞLIĞI ──"]

    # Aktif bağlantılar
    try:
        conns = psutil.net_connections()
        established = [c for c in conns if c.status == "ESTABLISHED"]
        listening = [c for c in conns if c.status == "LISTEN"]
        lines.append(f"Bağlantılar: {len(established)} aktif, {len(listening)} dinleyen")
    except Exception:
        lines.append("Bağlantı bilgisi alınamadı (yetki gerekli).")

    # Arayüz istatistikleri
    stats = psutil.net_io_counters()
    lines.append(f"Toplam: ▲ {stats.bytes_sent / (1024**3):.2f}GB  ▼ {stats.bytes_recv / (1024**3):.2f}GB")

    # DNS çözümleme testi
    try:
        socket.getaddrinfo("google.com", None)
        lines.append("DNS: ✓ Çalışıyor")
    except Exception:
        lines.append("DNS: ✗ Sorunlu")

    return "\n".join(lines)


def _check_startup_health() -> str:
    """Başlangıç programları ve boot süresi."""
    lines = ["── BAŞLANGIÇ SAĞLIĞI ──"]

    # Boot süresi
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    lines.append(f"Çalışma süresi: {uptime.days} gün, {uptime.seconds // 3600} saat, {(uptime.seconds % 3600) // 60} dakika")

    # Windows başlangıç programları
    if os.name == "nt":
        try:
            import winreg
            startup_paths = [
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            ]
            startup_items = []
            for hkey, path in startup_paths:
                try:
                    with winreg.OpenKey(hkey, path) as key:
                        i = 0
                        while True:
                            try:
                                name, _, _ = winreg.EnumValue(key, i)
                                startup_items.append(name)
                                i += 1
                            except OSError:
                                break
                except Exception:
                    continue
            lines.append(f"Başlangıç programları: {len(startup_items)}")
            if startup_items:
                for item in startup_items[:5]:
                    lines.append(f"  • {item}")
                if len(startup_items) > 5:
                    lines.append(f"  ... ve {len(startup_items) - 5} tane daha")
        except Exception:
            lines.append("Başlangıç programları alınamadı.")
    else:
        lines.append("Başlangıç programları: Linux desteği yakında.")

    return "\n".join(lines)


def _check_processes_health() -> str:
    """Süreç sayısı ve zombi süreç kontrolü."""
    lines = ["── SÜREÇ SAĞLIĞI ──"]

    process_count = len(psutil.pids())
    lines.append(f"Toplam süreç: {process_count}")

    # Zombi süreçler (Linux)
    if os.name != "nt":
        zombies = [p for p in psutil.process_iter(["status"]) if p.info["status"] == psutil.STATUS_ZOMBIE]
        lines.append(f"Zombi süreç: {len(zombies)}")
        if zombies:
            lines.append("UYARI: Zombi süreçler tespit edildi.")

    # Thread sayısı
    thread_count = sum(p.num_threads() for p in psutil.process_iter())
    lines.append(f"Toplam thread: {thread_count}")

    return "\n".join(lines)


def _check_temperature() -> str:
    """Sıcaklık sensörleri."""
    lines = ["── SICAKLIK ──"]

    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            lines.append("Sıcaklık sensörü bulunamadı.")
            return "\n".join(lines)

        for name, entries in temps.items():
            for entry in entries:
                if entry.current:
                    status = "✓" if entry.current < 70 else "⚠" if entry.current < 85 else "✗"
                    lines.append(f"{status} {name}: {entry.current:.1f}°C")
    except Exception:
        lines.append("Sıcaklık bilgisi alınamadı.")

    return "\n".join(lines)


def _get_folder_size(path: Path) -> int:
    """Klasör boyutunu bayt olarak döndürür."""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += _get_folder_size(Path(entry.path))
    except Exception:
        pass
    return total


def cleanup_temp_files() -> str:
    """Temp klasörünü temizler."""
    temp_path = Path(os.environ.get("TEMP", "/tmp"))
    deleted = 0
    freed = 0

    try:
        for entry in os.scandir(temp_path):
            try:
                if entry.is_file():
                    size = entry.stat().st_size
                    os.unlink(entry.path)
                    deleted += 1
                    freed += size
                elif entry.is_dir() and entry.name not in (".", ".."):
                    size = _get_folder_size(Path(entry.path))
                    shutil.rmtree(entry.path)
                    deleted += 1
                    freed += size
            except Exception:
                continue
    except Exception as e:
        return f"Temp temizliği hatası: {e}"

    freed_mb = freed / (1024**2)
    return f"Temp temizlendi: {deleted} öğe silindi, {freed_mb:.1f}MB boşaltıldı."


def cleanup_recycle_bin() -> str:
    """Geri dönüşüm kutusunu boşaltır (Windows)."""
    if os.name != "nt":
        return "Geri dönüşüm kutusu temizliği sadece Windows'ta destekleniyor."

    try:
        import winshell
        recycle_bin = winshell.recycle_bin()
        count = len(list(recycle_bin))
        recycle_bin.empty(confirm=False, show_progress=False, sound=False)
        return f"Geri dönüşüm kutusu boşaltıldı: {count} öğe silindi."
    except Exception as e:
        return f"Geri dönüşüm kutusu temizliği hatası: {e}"
