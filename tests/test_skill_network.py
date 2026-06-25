from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


class TestNetworkSkill(unittest.TestCase):
    """network_skill pure function tests — mocks all action imports."""

    def setUp(self):
        from skills.network.network_skill import (
            classify_network_intent,
            execute_network_skill,
            route_network_request,
        )
        self.classify = classify_network_intent
        self.execute = execute_network_skill
        self.route = route_network_request

        self.patchers = [
            patch("skills.network.network_skill.get_network_summary",
                  return_value="Ağ özeti: 2 bağlantı, IP 192.168.1.100"),
            patch("skills.network.network_skill.list_net_connections",
                  return_value="TCP 192.168.1.1:443 ESTABLISHED"),
            patch("skills.network.network_skill.ping_host",
                  return_value="google.com: 4/4 başarılı, ortalama 25ms"),
            patch("skills.network.network_skill.get_bandwidth_usage",
                  return_value="İndirme: 50 Mbps, Yükleme: 10 Mbps"),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    # ── Classify tests ───────────────────────────────────────────

    def test_classify_network_summary(self):
        intent, params = self.classify("ağ durumu nasıl")
        self.assertEqual(intent, "network_summary")

    def test_classify_ping_google(self):
        intent, params = self.classify("google ping at")
        self.assertEqual(intent, "ping_host")
        self.assertEqual(params.get("host"), "google.com")

    def test_classify_list_connections(self):
        intent, params = self.classify("bağlantıları listele")
        self.assertEqual(intent, "list_connections")

    def test_classify_list_connections_established(self):
        intent, params = self.classify("aktif bağlantıları listele")
        self.assertEqual(intent, "list_connections")
        self.assertEqual(params.get("state"), "established")

    def test_classify_none(self):
        intent, params = self.classify("merhaba nasılsın")
        self.assertEqual(intent, "none")

    def test_classify_empty(self):
        intent, params = self.classify("")
        self.assertEqual(intent, "none")

    def test_classify_ip_sorgu(self):
        intent, params = self.classify("ip adresim nedir")
        self.assertEqual(intent, "network_summary")

    # ── Route tests ──────────────────────────────────────────────

    def test_route_network_match(self):
        result = self.route("ağ durumu")
        self.assertIsNotNone(result)
        self.assertIn("Ağ özeti", result)

    def test_route_network_no_match(self):
        result = self.route("güzel bir gün")
        self.assertIsNone(result)

    def test_route_network_empty(self):
        result = self.route("")
        self.assertIsNone(result)

    def test_route_ping_match(self):
        result = self.route("google ping at")
        self.assertIsNotNone(result)
        self.assertIn("başarılı", result)

    # ── Execute tests ────────────────────────────────────────────

    def test_execute_network_summary(self):
        result = self.execute("network_summary", {})
        self.assertIn("Ağ özeti", result)

    def test_execute_list_connections(self):
        result = self.execute("list_connections", {"state": "all", "limit": 20})
        self.assertIn("ESTABLISHED", result)

    def test_execute_ping_host(self):
        result = self.execute("ping_host", {"host": "google.com", "count": 4})
        self.assertIn("başarılı", result)

    def test_execute_unknown(self):
        result = self.execute("unknown_action", {})
        self.assertIn("Bilinmeyen", result)
