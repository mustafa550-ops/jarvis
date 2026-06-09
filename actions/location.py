"""
Mevcut konum bilgisi — çoklu kaynak.

Strateji sırası:
  1. GeoClue2 (Linux D-Bus konum servisi — WiFi/GPS ile en hassas)
  2. IP geolocation (ip-api.com — internet varsa çalışır)
  3. Hafızada kayıtlı weather_location
"""

from __future__ import annotations

import json
import os
import time
import traceback
from urllib.request import Request, urlopen
from urllib.error import URLError


# ── GeoClue2 (Linux D-Bus konum servisi) ──────────────────────────────


def _geoclue_location() -> str | None:
    """
    GeoClue2 D-Bus servisi üzerinden konum al.
    dbus-python venv'de olmadığı için subprocess ile sistem python'u çağırır.

    Gereklilikler: geoclue-2.0 paketi, D-Bus system bus, python3-dbus.
    GeoClue izin yapılandırması:
      /etc/geoclue/geoclue.conf içine:
      [jarvis]
      allowed=true
      system=true
      users=
    """
    import subprocess
    import sys

    # dbus-python venv'de yoksa sistem python'unu dene
    python_bin = "/usr/bin/python3"
    if not os.path.exists(python_bin):
        python_bin = sys.executable  # fallback to venv python (başarısız olabilir)

    code = r"""
import json, time, dbus, traceback

try:
    bus = dbus.SystemBus()

    # GeoClue2 Manager
    manager_obj = bus.get_object(
        "org.freedesktop.GeoClue2",
        "/org/freedesktop/GeoClue2/Manager",
    )
    manager = dbus.Interface(manager_obj, "org.freedesktop.GeoClue2.Manager")

    # Client oluştur
    client_path = manager.GetClient()
    client_obj = bus.get_object("org.freedesktop.GeoClue2", client_path)
    client = dbus.Interface(client_obj, "org.freedesktop.GeoClue2.Client")
    client_props = dbus.Interface(client_obj, "org.freedesktop.DBus.Properties")

    # Client yapılandır (D-Bus tip uyumu: unsigned int için dbus.UInt32)
    client_props.Set("org.freedesktop.GeoClue2.Client", "DesktopId", "jarvis")
    client_props.Set("org.freedesktop.GeoClue2.Client", "DistanceThreshold", dbus.UInt32(0))
    client_props.Set("org.freedesktop.GeoClue2.Client", "TimeThreshold", dbus.UInt32(0))
    client_props.Set("org.freedesktop.GeoClue2.Client", "RequestedAccuracyLevel", dbus.UInt32(8))

    # Start konum taraması
    client.Start()
    deadline = time.monotonic() + 8
    location_path = None
    while time.monotonic() < deadline:
        try:
            path = client_props.Get("org.freedesktop.GeoClue2.Client", "Location")
            if path and str(path) != "/" and str(path) != "":
                location_path = path
                break
        except Exception:
            pass
        time.sleep(0.3)

    try:
        client.Stop()
    except Exception:
        pass

    if location_path is None:
        print("[Location|GeoClue] Zaman asimi (8s)")
        print("RESULT: null")
    else:
        loc_obj = bus.get_object("org.freedesktop.GeoClue2", location_path)
        loc_props = dbus.Interface(loc_obj, "org.freedesktop.DBus.Properties")
        lat = float(loc_props.Get("org.freedesktop.GeoClue2.Location", "Latitude"))
        lon = float(loc_props.Get("org.freedesktop.GeoClue2.Location", "Longitude"))
        print(f"[Location|GeoClue] {lat:.4f},{lon:.4f}")
        print(f"RESULT: {lat},{lon}")
except Exception as e:
    print(f"[Location|GeoClue] Hata: {e}")
    traceback.print_exc()
    print("RESULT: null")
"""

    try:
        result = subprocess.run(
            [python_bin, "-c", code],
            capture_output=True, text=True, timeout=15,
        )
        for line in result.stdout.splitlines():
            if line.startswith("RESULT: "):
                val = line.removeprefix("RESULT: ").strip()
                if val and val != "null" and "," in val:
                    lat_str, lon_str = val.split(",", 1)
                    try:
                        lat, lon = float(lat_str), float(lon_str)
                        print(f"[Location] GeoClue kooridanatlari: {lat:.4f}, {lon:.4f}")
                        return _reverse_geocode(lat, lon)
                    except ValueError:
                        pass
                return None
        # Log output for debugging
        stderr = result.stderr.strip()
        if stderr:
            print(f"[Location] GeoClue stderr: {stderr[:300]}")
        return None
    except subprocess.TimeoutExpired:
        print("[Location] GeoClue zaman asimi (subprocess)")
        return None
    except FileNotFoundError:
        print(f"[Location] Sistem python bulunamadi: {python_bin}")
        return None
    except Exception:
        print("[Location] GeoClue subprocess hatasi:")
        traceback.print_exc()
        return None


def _reverse_geocode(lat: float, lon: float) -> str | None:
    """
    Koordinatları şehir adına çevir.
    Önce ip-api.com (hızlı), başarısızsa Nominatim (OSM).
    """
    # 1) ip-api.com reverse geocode
    try:
        url = f"http://ip-api.com/json/{lat},{lon}"
        req = Request(url, headers={"User-Agent": "JARVIS-Windows/1.0"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == "success":
            city = data.get("city", "")
            region = data.get("regionName", "")
            country = data.get("country", "")
            parts = [p for p in [city, region, country] if p]
            if parts:
                result = ", ".join(parts)
                print(f"[Location] Reverse geocode (ip-api): {result}")
                return result
    except Exception:
        pass

    # 2) Nominatim (OSM) — yedek
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=tr"
        req = Request(url, headers={"User-Agent": "JARVIS-Windows/1.0"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        addr = data.get("address", {})
        city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county", "")
        country = addr.get("country", "")
        parts = [p for p in [city, country] if p]
        if parts:
            result = ", ".join(parts)
            print(f"[Location] Reverse geocode (Nominatim): {result}")
            return result
    except Exception:
        pass

    print(f"[Location] Reverse geocode basarisiz: {lat},{lon}")
    return None


# ── IP geolocation ────────────────────────────────────────────────────


def _ip_location() -> str | None:
    """
    IP adresine göre yaklaşık konum.
    ip-api.com — 45 istek/dakika limiti, API anahtarı gerekmez.
    """
    try:
        req = Request(
            "http://ip-api.com/json/",
            headers={"User-Agent": "JARVIS-Windows/1.0"},
        )
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("status") != "success":
            return None

        city = data.get("city", "")
        region = data.get("regionName", "")
        country = data.get("country", "")

        parts = [p for p in [city, region, country] if p]
        if parts:
            result = ", ".join(parts)
            print(f"[Location] IP konumu: {result} ({data.get('query', '?')})")
            return result

    except (URLError, json.JSONDecodeError, OSError):
        print("[Location] IP konumu alinamadi:")
        traceback.print_exc()

    return None


# ── Hafıza ────────────────────────────────────────────────────────────


def check_saved_location() -> str | None:
    """
    Hafızada kayıtlı weather_location varsa döndür.
    """
    try:
        from memory.memory_manager import load_memory
        mem = load_memory()
        val = mem.get("preferences", {}).get("weather_location", {}).get("value")
        if val:
            return str(val)
    except Exception:
        traceback.print_exc()
    return None


# ── Ana API ────────────────────────────────────────────────────────────


def get_current_location() -> str | None:
    """
    En doğru konumu bulmak için sırasıyla dene:

      1. GeoClue2 (Linux D-Bus) — en hassas, WiFi/GPS
      2. IP geolocation — internet varsa çalışır
      3. Hafızada kayıtlı konum — son çare

    Dönen: \"Şehir, Ülke\" veya None
    """
    # 1) GeoClue2 (yalnızca Linux)
    loc = _geoclue_location()
    if loc:
        return loc

    # 2) IP geolocation
    loc = _ip_location()
    if loc:
        return loc

    # 3) Hafıza
    loc = check_saved_location()
    if loc:
        print(f"[Location] Hafızadan konum: {loc}")
        return loc

    return None
