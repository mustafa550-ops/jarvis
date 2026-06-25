from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


class TestVisionSkill(unittest.TestCase):
    """vision_skill pure function tests — mocks analyze_screen."""

    def setUp(self):
        from skills.vision.vision_skill import (
            classify_vision_intent,
            execute_vision_skill,
            route_vision_request,
        )
        self.classify = classify_vision_intent
        self.execute = execute_vision_skill
        self.route = route_vision_request

        self.patchers = [
            patch("skills.vision.vision_skill.analyze_screen",
                  return_value="Ekranda: Chrome tarayıcı açık, ..."),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    # ── Classify tests ───────────────────────────────────────────

    def test_classify_analyze_screen(self):
        intent, query = self.classify("ekranda ne var")
        self.assertEqual(intent, "analyze_screen")

    def test_classify_analyze_error(self):
        intent, query = self.classify("ekrandaki hatayı oku")
        self.assertEqual(intent, "analyze_screen")
        self.assertIn("hatayi", query.lower())

    def test_classify_analyze_buttons(self):
        intent, query = self.classify("ekrandaki butonları analiz et")
        self.assertEqual(intent, "analyze_screen")
        self.assertIn("butonlari", query.lower())

    def test_classify_analyze_text(self):
        intent, query = self.classify("ekrandaki metinleri oku")
        self.assertEqual(intent, "analyze_screen")
        self.assertIn("metinleri", query.lower())

    def test_classify_screenshot(self):
        intent, query = self.classify("screenshot al")
        self.assertEqual(intent, "analyze_screen")

    def test_classify_fallback_keyword(self):
        intent, query = self.classify("pencereyi analiz et")
        self.assertEqual(intent, "analyze_screen")

    def test_classify_none(self):
        intent, query = self.classify("merhaba nasılsın")
        self.assertEqual(intent, "none")

    def test_classify_empty(self):
        intent, query = self.classify("")
        self.assertEqual(intent, "none")

    # ── Route tests ──────────────────────────────────────────────

    def test_route_vision_match(self):
        result = self.route("ekranda ne var")
        self.assertIsNotNone(result)
        self.assertIn("Ekranda:", result)

    def test_route_vision_no_match(self):
        result = self.route("güzel bir gün")
        self.assertIsNone(result)

    def test_route_vision_empty(self):
        result = self.route("")
        self.assertIsNone(result)

    # ── Execute tests ────────────────────────────────────────────

    def test_execute_analyze_screen(self):
        result = self.execute("analyze_screen", "Ekranda ne var?")
        self.assertIn("Ekranda:", result)

    def test_execute_unknown(self):
        result = self.execute("unknown_action", "")
        self.assertIn("Bilinmeyen", result)
