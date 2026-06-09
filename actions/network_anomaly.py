"""
Network Anomaly Detector — Ağ trafiği anomaly tespiti.
OpenClaw'dan uyarlanmıştır.

Kullanım:
    from actions.network_anomaly import NetworkAnomalyDetector
    detector = NetworkAnomalyDetector(ui_callback)
    alerts = detector.scan()

    # IP reputation kontrolü:
    print(detector.check_ip_reputation("1.2.3.4"))
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable, Optional

import psutil


import traceback
class NetworkAnomalyDetector:
    """
    Ağ trafiği anomaly tespiti.

    Tespit edilen anomaly'ler:
    1. Şüpheli port kullanımı (C2 portları: 4444, 5555, 6666, 31337, vb.)
    2. Bilinmeyen IP'ye aşırı bağlantı sayısı (>50)
    3. Çok fazla farklı port (port scan davranışı, >20 farklı port)
    4. Şüpheli DNS trafiği (DNS port 53, bilinmeyen süreçten)
    5. Yüksek outbound bağlantı sayısı (>100 aynı anda)

    Whitelist: Google, Microsoft, Cloudflare, CDN'ler (false positive azaltmak için)
    """

    # Bilinen C2 / şüpheli portlar
    SUSPICIOUS_PORTS = {
        4444,   # Metasploit default
        5555,   # ADB / malware
        6666,   # IRC / malware
        7777,   # Çeşitli malware
        8888,   # Proxy / C2
        9999,   # Backup / malware
        31337,  # Elite / backdoor
        12345,  # NetBus
        27374,  # SubSeven
        1234,   # Çeşitli
    }

    # Bilinen güvenli domain'ler (IP whitelist)
    TRUSTED_DOMAINS = [
        "google.com", "googleusercontent.com", "googleapis.com",
        "microsoft.com", "windows.net", "office.net",
        "cloudflare.com", "cloudfront.net", "akamai.net",
        "amazonaws.com", "amazon.com",
        "github.com", "githubusercontent.com",
        "discord.com", "discord.gg",
        "spotify.com", "youtube.com", "ytimg.com",
    ]

    # Eşik değerler
    THRESHOLD_CONNECTION_COUNT = 50      # Aynı IP'ye 50+ bağlantı
    THRESHOLD_UNIQUE_PORTS = 20          # Aynı IP'ye 20+ farklı port
    THRESHOLD_TOTAL_OUTBOUND = 100       # Toplam 100+ outbound bağlantı
    THRESHOLD_DNS_PER_PROCESS = 10       # Süreç başına 10+ DNS sorgusu/dakika

    def __init__(self, ui_callback: Optional[Callable] = None):
        self.ui = ui_callback
        self._connection_history: dict[str, dict] = {}  # {remote_ip: {"first_seen": t, "ports": set(), "count": int, "pids": set()}}
        self._alerted: set[str] = set()  # Bir kere uyarılan IP'ler
        self._dns_history: dict[int, list[float]] = {}  # {pid: [timestamp, ...]}
        self._scan_count = 0

    def scan(self) -> list[str]:
        """
        Aktif bağlantıları tarar, anomaly'leri döndürür.
        Her 2 dakikada bir çağrılmalı.
        """
        alerts = []
        self._scan_count += 1

        try:
            conns = psutil.net_connections()
        except psutil.AccessDenied:
            return ["Ağ bağlantı bilgisi alınamadı. Yönetici olarak çalıştır."]

        outbound_count = 0
        current_ips = set()

        for conn in conns:
            if not conn.raddr:
                continue

            remote_ip = conn.raddr.ip
            remote_port = conn.raddr.port
            local_port = conn.laddr.port if conn.laddr else 0
            pid = conn.pid

            outbound_count += 1
            current_ips.add(remote_ip)

            # 1. Şüpheli port kontrolü
            if remote_port in self.SUSPICIOUS_PORTS:
                alert_key = f"suspicious_port:{remote_ip}:{remote_port}"
                if alert_key not in self._alerted:
                    self._alerted.add(alert_key)
                    proc_name = self._get_process_name(pid)
                    alerts.append(
                        f"🚨 ŞÜPHELİ PORT: {remote_ip}:{remote_port} "
                        f"(PID {pid} {proc_name}) — Bilinen C2 portu!"
                    )

            # Bağlantı geçmişi güncelle
            if remote_ip not in self._connection_history:
                self._connection_history[remote_ip] = {
                    "first_seen": time.time(),
                    "ports": set(),
                    "count": 0,
                    "pids": set(),
                }

            self._connection_history[remote_ip]["ports"].add(remote_port)
            self._connection_history[remote_ip]["count"] += 1
            if pid:
                self._connection_history[remote_ip]["pids"].add(pid)

            # 2. Aşırı bağlantı sayısı
            if self._connection_history[remote_ip]["count"] > self.THRESHOLD_CONNECTION_COUNT:
                alert_key = f"excessive:{remote_ip}"
                if alert_key not in self._alerted:
                    self._alerted.add(alert_key)
                    proc_names = [self._get_process_name(p) for p in self._connection_history[remote_ip]["pids"]]
                    alerts.append(
                        f"⚠️ AŞIRI BAĞLANTI: {remote_ip} "
                        f"({self._connection_history[remote_ip]['count']} kez, "
                        f"süreçler: {', '.join(proc_names[:3])})"
                    )

            # 3. Port scan davranışı
            unique_ports = len(self._connection_history[remote_ip]["ports"])
            if unique_ports > self.THRESHOLD_UNIQUE_PORTS:
                alert_key = f"portscan:{remote_ip}"
                if alert_key not in self._alerted:
                    self._alerted.add(alert_key)
                    alerts.append(
                        f"🔍 PORT SCAN BENZERİ: {remote_ip} "
                        f"({unique_ports} farklı port)"
                    )

            # 4. Şüpheli DNS trafiği
            if remote_port == 53 and pid:
                self._check_dns_anomaly(pid, remote_ip, alerts)

        # 5. Toplam outbound kontrolü
        if outbound_count > self.THRESHOLD_TOTAL_OUTBOUND:
            alert_key = f"total_outbound:{self._scan_count}"
            if alert_key not in self._alerted:
                self._alerted.add(alert_key)
                alerts.append(
                    f"⚠️ YÜKSEK OUTBOUND: {outbound_count} aktif bağlantı "
                    f"(normalden fazla ağ aktivitesi)"
                )

        # Eski kayıtları temizle (1 saatten eski)
        self._cleanup_old_history()

        return alerts

    def _check_dns_anomaly(self, pid: int, remote_ip: str, alerts: list):
        """DNS trafiği anomaly kontrolü."""
        now = time.time()

        if pid not in self._dns_history:
            self._dns_history[pid] = []

        self._dns_history[pid].append(now)

        # Son 60 saniyedeki DNS sorgusu sayısı
        recent_dns = [t for t in self._dns_history[pid] if now - t < 60]
        self._dns_history[pid] = recent_dns

        if len(recent_dns) > self.THRESHOLD_DNS_PER_PROCESS:
            proc_name = self._get_process_name(pid)
            # Bilinen güvenli süreçleri atla
            if proc_name.lower() not in ("svchost.exe", "dns.exe", "system", "systemd-resolve", "chrome.exe"):
                alert_key = f"dns_anomaly:{pid}"
                if alert_key not in self._alerted:
                    self._alerted.add(alert_key)
                    alerts.append(
                        f"⚠️ ŞÜPHELİ DNS: {proc_name} (PID {pid}) "
                        f"son 60 saniyede {len(recent_dns)} DNS sorgusu"
                    )

    def _get_process_name(self, pid: Optional[int]) -> str:
        """PID'den süreç adını alır."""
        if not pid:
            return "?"
        try:
            return psutil.Process(pid).name()
        except Exception:
            return "?"

    def _cleanup_old_history(self):
        """1 saatten eski bağlantı geçmişini temizler."""
        cutoff = time.time() - 3600
        to_remove = []

        for ip, data in self._connection_history.items():
            if data["first_seen"] < cutoff and data["count"] < self.THRESHOLD_CONNECTION_COUNT:
                to_remove.append(ip)

        for ip in to_remove:
            del self._connection_history[ip]
            # Alert'leri de temizle
            self._alerted = {a for a in self._alerted if not a.endswith(f":{ip}")}

    def check_ip_reputation(self, ip: str) -> str:
        """
        IP adresi ülke ve ISP bilgisi.
        ipwho.is API'sini kullanır (ücretsiz, rate limit yok).
        """
        try:
            import requests
            r = requests.get(f"https://ipwho.is/{ip}", timeout=5)
            data = r.json()

            if not data.get("success"):
                return f"{ip}: Bilgi alınamadı ({data.get('message', '?')})"

            country = data.get("country", "?")
            region = data.get("region", "?")
            city = data.get("city", "?")
            isp = data.get("connection", {}).get("isp", "?")
            org = data.get("connection", {}).get("org", "?")
            type_ = data.get("connection", {}).get("type", "?")

            lines = [f"── {ip} BİLGİSİ ──"]
            lines.append(f"Ülke: {country} ({region}, {city})")
            lines.append(f"ISP: {isp}")
            if org and org != isp:
                lines.append(f"Organizasyon: {org}")
            lines.append(f"Tip: {type_}")

            # VPN/Proxy/Hosting tespiti
            flags = []
            if data.get("security", {}).get("vpn"): flags.append("VPN")
            if data.get("security", {}).get("proxy"): flags.append("Proxy")
            if data.get("security", {}).get("tor"): flags.append("Tor")
            if data.get("security", {}).get("datacenter"): flags.append("Datacenter")

            if flags:
                lines.append(f"⚠️ Uyarı: {', '.join(flags)}")

            return "\n".join(lines)

        except Exception as e:
            return f"{ip}: Sorgu hatası ({e})"

    def get_connection_summary(self) -> str:
        """Mevcut bağlantıların özet raporu."""
        try:
            conns = psutil.net_connections()
        except psutil.AccessDenied:
            return "Bağlantı bilgisi alınamadı."

        # IP bazında grupla
        ip_stats = defaultdict(lambda: {"count": 0, "ports": set(), "pids": set()})

        for conn in conns:
            if not conn.raddr:
                continue
            ip = conn.raddr.ip
            ip_stats[ip]["count"] += 1
            ip_stats[ip]["ports"].add(conn.raddr.port)
            if conn.pid:
                ip_stats[ip]["pids"].add(conn.pid)

        # En çok bağlantı olan 10 IP
        top_ips = sorted(ip_stats.items(), key=lambda x: x[1]["count"], reverse=True)[:10]

        lines = [f"── AĞ BAĞLANTI ÖZETİ ──"]
        lines.append(f"Toplam aktif bağlantı: {len([c for c in conns if c.raddr])}")
        lines.append(f"Farklı uzak IP: {len(ip_stats)}")
        lines.append("")
        lines.append("En çok bağlantı olan IP'ler:")

        for ip, stats in top_ips:
            proc_names = [self._get_process_name(p) for p in stats["pids"]]
            unique_procs = list(dict.fromkeys(proc_names))[:3]  # Benzersiz, max 3
            lines.append(
                f"  {ip}: {stats['count']} bağlantı, "
                f"{len(stats['ports'])} port — {', '.join(unique_procs)}"
            )

        return "\n".join(lines)

    def reset_alerts(self):
        """Tüm alert'leri sıfırlar (tekrar tespit için)."""
        self._alerted.clear()
        self._connection_history.clear()
        self._dns_history.clear()
        return "Alert'ler sıfırlandı."


def scan_network_anomalies(ui_callback=None) -> list[str]:
    """Hızlı başlatma: anomaly taraması."""
    return NetworkAnomalyDetector(ui_callback).scan()


def check_ip(ip: str) -> str:
    """Hızlı başlatma: IP reputation."""
    return NetworkAnomalyDetector().check_ip_reputation(ip)
