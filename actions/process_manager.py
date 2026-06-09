"""
Process Manager — Süreç listeleme, öldürme, öncelik ayarı.
OpenClaw'dan uyarlanmıştır.
"""

from __future__ import annotations

import os
import signal
from typing import Any

import psutil


import traceback
def list_processes(sort_by: str = "cpu", limit: int = 10) -> str:
    """
    Çalışan süreçleri listeler.
    sort_by: cpu | memory | name | pid
    limit: kaç süreç gösterilecek (1-50)
    """
    sort_by = (sort_by or "cpu").lower().strip()
    limit = max(1, min(50, int(limit or 10)))

    sort_map = {
        "cpu": "cpu_percent",
        "memory": "memory_percent",
        "mem": "memory_percent",
        "name": "name",
        "pid": "pid",
    }
    sort_key = sort_map.get(sort_by, "cpu_percent")

    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = p.info
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sırala
    reverse = sort_key != "name"
    procs.sort(key=lambda x: x.get(sort_key) or 0, reverse=reverse)

    lines = [f"── ÇALIŞAN SÜREÇLER (top {limit}, sıralama: {sort_by}) ──"]
    lines.append(f"{'PID':<8} {'İsim':<28} {'CPU%':<8} {'RAM%':<8} {'Durum':<12}")
    lines.append("─" * 70)

    for info in procs[:limit]:
        pid = info.get("pid", "?")
        name = str(info.get("name", "?"))[:26]
        cpu = info.get("cpu_percent", 0.0) or 0.0
        mem = info.get("memory_percent", 0.0) or 0.0
        status = str(info.get("status", "?"))[:10]
        lines.append(f"{pid:<8} {name:<28} {cpu:<8.1f} {mem:<8.1f} {status:<12}")

    return "\n".join(lines)


def kill_process(identifier: str, force: bool = False) -> str:
    """
    Süreç sonlandırır.
    identifier: PID (sayı) veya süreç adı
    force: True ise zorla öldürür (SIGKILL / taskkill /F)
    """
    identifier = str(identifier or "").strip()
    if not identifier:
        return "Süreç adı veya PID belirtilmedi."

    # PID mi yoksa isim mi?
    try:
        pid = int(identifier)
        return _kill_by_pid(pid, force)
    except ValueError:
        return _kill_by_name(identifier, force)


def _kill_by_pid(pid: int, force: bool) -> str:
    try:
        p = psutil.Process(pid)
        name = p.name()

        if force:
            p.kill()
            return f"{name} (PID {pid}) zorla sonlandırıldı."
        else:
            p.terminate()
            try:
                p.wait(timeout=3)
                return f"{name} (PID {pid}) düzgün şekilde sonlandırıldı."
            except psutil.TimeoutExpired:
                p.kill()
                return f"{name} (PID {pid}) sonlandırılamadı, zorla öldürüldü."
    except psutil.NoSuchProcess:
        return f"PID {pid} bulunamadı."
    except psutil.AccessDenied:
        return f"PID {pid} sonlandırma yetkisi reddedildi. Yönetici olarak çalıştır."
    except Exception as e:
        return f"PID {pid} sonlandırma hatası: {e}"


def _kill_by_name(name: str, force: bool) -> str:
    killed = []
    errors = []

    for p in psutil.process_iter(["pid", "name"]):
        try:
            if p.info["name"] and name.lower() in p.info["name"].lower():
                pid = p.info["pid"]
                proc_name = p.info["name"]
                if force:
                    p.kill()
                    killed.append(f"{proc_name} (PID {pid})")
                else:
                    p.terminate()
                    try:
                        p.wait(timeout=3)
                        killed.append(f"{proc_name} (PID {pid})")
                    except psutil.TimeoutExpired:
                        p.kill()
                        killed.append(f"{proc_name} (PID {pid}) [zorla]")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except Exception as e:
            errors.append(str(e))

    if killed:
        return f"Sonlandırıldı: {', '.join(killed)}"
    if errors:
        return f"Hata: {errors[0]}"
    return f"'{name}' adında süreç bulunamadı."


def set_process_priority(identifier: str, priority: str) -> str:
    """
    Süreç önceliğini ayarlar.
    identifier: PID veya süreç adı
    priority: high | normal | low | realtime | idle
    """
    priority = (priority or "").lower().strip()
    priority_map = {
        "high": psutil.HIGH_PRIORITY_CLASS if os.name == "nt" else -10,
        "normal": psutil.NORMAL_PRIORITY_CLASS if os.name == "nt" else 0,
        "low": psutil.IDLE_PRIORITY_CLASS if os.name == "nt" else 10,
        "realtime": psutil.REALTIME_PRIORITY_CLASS if os.name == "nt" else -20,
        "idle": psutil.IDLE_PRIORITY_CLASS if os.name == "nt" else 19,
    }

    if priority not in priority_map:
        return f"Geçersiz öncelik: {priority}. high/normal/low/realtime/idle kullan."

    try:
        pid = int(identifier)
        p = psutil.Process(pid)
        p.nice(priority_map[priority])
        return f"{p.name()} (PID {pid}) önceliği '{priority}' olarak ayarlandı."
    except ValueError:
        # İsimle bul
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if p.info["name"] and identifier.lower() in p.info["name"].lower():
                    proc = psutil.Process(p.info["pid"])
                    proc.nice(priority_map[priority])
                    return f"{proc.name()} (PID {p.info['pid']}) önceliği '{priority}' olarak ayarlandı."
            except Exception:
                continue
        return f"'{identifier}' adında süreç bulunamadı."
    except psutil.NoSuchProcess:
        return f"Süreç bulunamadı."
    except psutil.AccessDenied:
        return "Yetki reddedildi. Yönetici olarak çalıştır."
    except Exception as e:
        return f"Öncelik ayarı hatası: {e}"


def find_process_by_port(port: int) -> str:
    """Belirli bir portu kullanan süreçleri bulur."""
    port = int(port)
    found = []

    for conn in psutil.net_connections():
        if conn.laddr and conn.laddr.port == port:
            try:
                p = psutil.Process(conn.pid)
                found.append(f"{p.name()} (PID {conn.pid}) — {conn.status}")
            except Exception:
                found.append(f"PID {conn.pid} — {conn.status}")

    if found:
        return f"── PORT {port} KULLANANLAR ──\n" + "\n".join(found)
    return f"Port {port} kullanımda değil."


def get_process_tree(pid: int) -> str:
    """Süreç ağacını gösterir."""
    try:
        p = psutil.Process(int(pid))
        lines = [f"── SÜREÇ AĞACI: {p.name()} (PID {pid}) ──"]
        lines.append(f"Durum: {p.status()}")
        lines.append(f"CPU: %{p.cpu_percent(interval=0.1):.1f}")
        lines.append(f"RAM: %{p.memory_percent():.1f}")
        lines.append(f"Çalışma süresi: {p.create_time()}")

        children = p.children(recursive=True)
        if children:
            lines.append("")
            lines.append("Alt süreçler:")
            for child in children:
                lines.append(f"  • {child.name()} (PID {child.pid})")
        else:
            lines.append("Alt süreç yok.")

        return "\n".join(lines)
    except psutil.NoSuchProcess:
        return f"PID {pid} bulunamadı."
    except Exception as e:
        return f"Hata: {e}"
