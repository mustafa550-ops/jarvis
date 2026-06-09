"""
Network Monitor — Ağ bağlantıları, portlar, bant genişliği.
OpenClaw'dan uyarlanmıştır.
"""

from __future__ import annotations

import socket
from typing import Any

import psutil


import traceback
def get_network_summary() -> str:
    """Ağ özet raporu."""
    lines = ["── AĞ ÖZETİ ──"]

    # Arayüzler
    stats = psutil.net_if_addrs()
    io_stats = psutil.net_io_counters(pernic=True)

    for iface, addrs in stats.items():
        if iface.startswith("Loop") or iface == "lo":
            continue
        ip_addrs = [a.address for a in addrs if a.family == socket.AF_INET]
        if ip_addrs:
            lines.append(f"\n{iface}:")
            lines.append(f"  IP: {', '.join(ip_addrs)}")
            if iface in io_stats:
                io = io_stats[iface]
                lines.append(f"  ▲ {io.bytes_sent / (1024**3):.2f}GB  ▼ {io.bytes_recv / (1024**3):.2f}GB")

    # Genel istatistikler
    total = psutil.net_io_counters()
    lines.append(f"\nToplam trafik:")
    lines.append(f"  Gönderilen: {total.bytes_sent / (1024**3):.2f}GB")
    lines.append(f"  Alınan: {total.bytes_recv / (1024**3):.2f}GB")
    lines.append(f"  Paket gönderim hatası: {total.errout}")
    lines.append(f"  Paket alım hatası: {total.errin}")

    return "\n".join(lines)


def list_connections(state: str = "all", limit: int = 20) -> str:
    """
    Aktif ağ bağlantılarını listeler.
    state: all | established | listen | close_wait | time_wait
    limit: Maksimum sonuç
    """
    state = (state or "all").lower().strip()
    limit = max(1, min(100, int(limit)))

    try:
        conns = psutil.net_connections()
    except psutil.AccessDenied:
        return "Bağlantı bilgisi alınamadı. Yönetici olarak çalıştır."

    if state != "all":
        conns = [c for c in conns if c.status and c.status.lower() == state]

    lines = [f"── AĞ BAĞLANTILARI ({state}, top {limit}) ──"]
    lines.append(f"{'Lokal':<22} {'Uzak':<22} {'Durum':<14} {'PID':<8} {'Süreç':<20}")
    lines.append("─" * 90)

    count = 0
    for conn in conns:
        if count >= limit:
            break
        laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "-"
        raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "-"
        status = conn.status or "?"
        pid = str(conn.pid or "?")

        proc_name = "?"
        if conn.pid:
            try:
                proc_name = psutil.Process(conn.pid).name()
            except Exception:
                traceback.print_exc()

        lines.append(f"{laddr:<22} {raddr:<22} {status:<14} {pid:<8} {proc_name:<20}")
        count += 1

    lines.append(f"\nToplam: {len(conns)} bağlantı")
    return "\n".join(lines)


def find_process_by_port(port: int) -> str:
    """Belirli bir portu kullanan süreçleri bulur."""
    port = int(port)
    found = []

    try:
        for conn in psutil.net_connections():
            if conn.laddr and conn.laddr.port == port:
                try:
                    p = psutil.Process(conn.pid)
                    found.append(f"{p.name()} (PID {conn.pid}) — {conn.status}")
                except Exception:
                    found.append(f"PID {conn.pid} — {conn.status}")
    except psutil.AccessDenied:
        return "Port bilgisi alınamadı. Yönetici olarak çalıştır."

    if found:
        return f"── PORT {port} KULLANANLAR ──\n" + "\n".join(found)
    return f"Port {port} kullanımda değil."


def ping_host(host: str = "google.com", count: int = 4) -> str:
    """Basit ping testi."""
    import subprocess
    import platform

    host = host or "google.com"
    count = max(1, min(10, int(count)))

    param = "-n" if platform.system().lower() == "windows" else "-c"
    try:
        result = subprocess.run(
            ["ping", param, str(count), host],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        if len(output) > 500:
            output = output[:500] + "\n..."
        return output
    except subprocess.TimeoutExpired:
        return f"Ping zaman aşımı: {host}"
    except Exception as e:
        return f"Ping hatası: {e}"


def get_bandwidth_usage(duration: int = 5) -> str:
    """
    Canlı bant genişliği ölçümü.
    duration: Ölçüm süresi saniye
    """
    import time

    duration = max(1, min(30, int(duration)))
    io1 = psutil.net_io_counters()
    time.sleep(duration)
    io2 = psutil.net_io_counters()

    sent = (io2.bytes_sent - io1.bytes_sent) / duration
    recv = (io2.bytes_recv - io1.bytes_recv) / duration

    sent_str = f"{sent / 1024:.1f}KB/s" if sent < 1024**2 else f"{sent / (1024**2):.2f}MB/s"
    recv_str = f"{recv / 1024:.1f}KB/s" if recv < 1024**2 else f"{recv / (1024**2):.2f}MB/s"

    return f"── BANT GENİŞLİĞİ ({duration}s ortalama) ──\n▲ {sent_str}  ▼ {recv_str}"
