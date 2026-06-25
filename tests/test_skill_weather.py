from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


class TestWeatherSkill(unittest.TestCase):
    """weather_skill pure function tests — mocks get_weather_summary / load_memory."""

    def setUp(self):
        from skills.weather.weather_skill import (
            classify_weather_intent,
            execute_weather_skill,
            route_weather_request,
        )
        self.classify = classify_weather_intent
        self.execute = execute_weather_skill
        self.route = route_weather_request

        self.patchers = [
            patch("skills.weather.weather_skill.get_weather_summary",
                  return_value="Istanbul: 22°C, parçalı bulutlu"),
            patch("skills.weather.weather_skill.load_memory",
                  return_value={"preferences": {"weather_location": {"value": "Istanbul"}}}),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    # ── Classify tests ───────────────────────────────────────────

    def test_classify_hava_durumu(self):
        intent, city = self.classify("hava durumu nasıl")
        self.assertEqual(intent, "get_weather")

    def test_classify_istanbul_hava(self):
        intent, city = self.classify("istanbul hava durumu")
        self.assertEqual(intent, "get_weather")
        self.assertEqual(city, "Istanbul")

    def test_classify_ankara_derece(self):
        intent, city = self.classify("ankara kaç derece")
        self.assertEqual(intent, "get_weather")
        self.assertEqual(city, "Ankara")

    def test_classify_yagmur(self):
        intent, city = self.classify("yağmur var mı")
        self.assertEqual(intent, "get_weather")

    def test_classify_yarin_hava(self):
        intent, city = self.classify("yarın hava nasıl olacak")
        self.assertEqual(intent, "get_weather")

    def test_classify_none(self):
        intent, city = self.classify("merhaba nasılsın")
        self.assertEqual(intent, "none")
        self.assertEqual(city, "")

    def test_classify_empty(self):
        intent, city = self.classify("")
        self.assertEqual(intent, "none")

    # ── Route tests ──────────────────────────────────────────────

    def test_route_weather_match(self):
        result = self.route("istanbul hava durumu")
        self.assertIsNotNone(result)
        self.assertIn("22°C", result)

    def test_route_weather_no_match(self):
        result = self.route("güzel bir gün")
        self.assertIsNone(result)

    def test_route_weather_empty(self):
        result = self.route("")
        self.assertIsNone(result)

    # ── Execute tests ────────────────────────────────────────────

    def test_execute_get_weather(self):
        result = self.execute("get_weather", "Istanbul")
        self.assertIn("22°C", result)

    def test_execute_unknown(self):
        result = self.execute("unknown_action", "")
        self.assertIn("Bilinmeyen", result)
