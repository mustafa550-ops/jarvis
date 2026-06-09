"""
Service Monitor — Windows servisleri izleme ve kontrol.
OpenClaw'dan uyarlanmıştır.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

import psutil


import traceback
def list_services(status_filter: str = "all", limit: int = 20) -> str:
    """
    Windows servislerini listeler.
    status_filter: all | running | stopped | auto | manual
    limit: Maksimum sonuç
    """
    if os.name != "nt":
        return "Servis yönetimi sadece Windows'ta destekleniyor."

    status_filter = (status_filter or "all").lower().strip()
    limit = max(1, min(100, int(limit)))

    try:
        import win32service
        import win32serviceutil
    except ImportError:
        return "pywin32 gerekli: pip install pywin32"

    services = []
    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ENUMERATE_SERVICE)
    try:
        enum = win32service.EnumServicesStatus(scm, win32service.SERVICE_WIN32, win32service.SERVICE_STATE_ALL)
        for svc in enum:
            name, display_name, status = svc
            state = "running" if status == win32service.SERVICE_RUNNING else "stopped"
            start_type = "unknown"
            try:
                hsvc = win32service.OpenService(scm, name, win32service.SERVICE_QUERY_CONFIG)
                cfg = win32service.QueryServiceConfig(hsvc)
                start_type_map = {2: "auto", 3: "manual", 4: "disabled"}
                start_type = start_type_map.get(cfg[1], "unknown")
                win32service.CloseServiceHandle(hsvc)
            except Exception:
                traceback.print_exc()

            if status_filter == "all" or status_filter == state or status_filter == start_type:
                services.append((name, display_name, state, start_type))
    finally:
        win32service.CloseServiceHandle(scm)

    lines = [f"── SERVİSLER ({status_filter}, top {limit}) ──"]
    lines.append(f"{'İsim':<30} {'Durum':<10} {'Başlangıç':<10}")
    lines.append("─" * 55)

    for name, display, state, start_type in services[:limit]:
        icon = "●" if state == "running" else "○"
        lines.append(f"{display[:28]:<30} {icon} {state:<8} {start_type:<10}")

    lines.append(f"\nToplam: {len(services)} servis")
    return "\n".join(lines)


def control_service(service_name: str, action: str) -> str:
    """
    Servis kontrolü.
    action: start | stop | restart | status
    """
    if os.name != "nt":
        return "Servis yönetimi sadece Windows'ta destekleniyor."

    action = (action or "").lower().strip()
    service_name = (service_name or "").strip()

    if not service_name:
        return "Servis adı belirtilmedi."

    try:
        import win32service
        import win32serviceutil
    except ImportError:
        return "pywin32 gerekli: pip install pywin32"

    try:
        if action == "start":
            win32serviceutil.StartService(service_name)
            return f"{service_name} başlatıldı."
        elif action == "stop":
            win32serviceutil.StopService(service_name)
            return f"{service_name} durduruldu."
        elif action == "restart":
            win32serviceutil.RestartService(service_name)
            return f"{service_name} yeniden başlatıldı."
        elif action == "status":
            status = win32serviceutil.QueryServiceStatus(service_name)
            state_map = {
                1: "stopped",
                2: "start pending",
                3: "stop pending",
                4: "running",
                5: "continue pending",
                6: "pause pending",
                7: "paused",
            }
            return f"{service_name} durumu: {state_map.get(status[1], 'unknown')}"
        else:
            return f"Geçersiz işlem: {action}. start/stop/restart/status kullan."
    except Exception as e:
        return f"Servis işlemi hatası: {e}"


def get_service_dependencies(service_name: str) -> str:
    """Servis bağımlılıklarını gösterir."""
    if os.name != "nt":
        return "Servis yönetimi sadece Windows'ta destekleniyor."

    try:
        import win32service
        scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ENUMERATE_SERVICE)
        hsvc = win32service.OpenService(scm, service_name, win32service.SERVICE_QUERY_CONFIG)
        cfg = win32service.QueryServiceConfig(hsvc)
        deps = cfg[6]  # dependencies
        win32service.CloseServiceHandle(hsvc)
        win32service.CloseServiceHandle(scm)

        if deps:
            return f"{service_name} bağımlılıkları:\n" + "\n".join(f"  • {d}" for d in deps)
        return f"{service_name} bağımlılığı yok."
    except Exception as e:
        return f"Bağımlılık hatası: {e}"
