from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


class TestCalendarSkill(unittest.TestCase):
    """calendar_skill pure function tests — mocks action imports."""

    def setUp(self):
        from skills.calendar.calendar_skill import (
            classify_calendar_intent,
            execute_calendar_skill,
            route_calendar_request,
        )
        self.classify = classify_calendar_intent
        self.execute = execute_calendar_skill
        self.route = route_calendar_request

        self.patchers = [
            patch("skills.calendar.calendar_skill.get_calendar_events",
                  return_value="Bugün 3 etkinlik: ..."),
            patch("skills.calendar.calendar_skill.add_calendar_event",
                  return_value="Etkinlik eklendi: Toplantı"),
            patch("skills.calendar.calendar_skill.delete_calendar_event",
                  return_value="Etkinlik silindi: Toplantı"),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    # ── Classify tests ───────────────────────────────────────────

    def test_classify_get_events(self):
        intent, params = self.classify("takvimimi göster")
        self.assertEqual(intent, "get_events")

    def test_classify_get_events_today(self):
        intent, params = self.classify("bugün ne var takvimde")
        self.assertEqual(intent, "get_events")
        self.assertEqual(params.get("query"), "today")

    def test_classify_get_events_tomorrow(self):
        intent, params = self.classify("yarın takvimde ne var")
        self.assertEqual(intent, "get_events")
        self.assertEqual(params.get("query"), "tomorrow")

    def test_classify_get_events_week(self):
        intent, params = self.classify("bu hafta takvim")
        self.assertEqual(intent, "get_events")
        self.assertEqual(params.get("query"), "week")

    def test_classify_add_event(self):
        intent, params = self.classify("takvime etkinlik ekle")
        self.assertEqual(intent, "add_event")

    def test_classify_delete_event(self):
        intent, params = self.classify("takvimden etkinlik sil")
        self.assertEqual(intent, "delete_event")

    def test_classify_fallback_keyword(self):
        intent, params = self.classify("takvim")
        self.assertEqual(intent, "get_events")

    def test_classify_none(self):
        intent, params = self.classify("merhaba nasılsın")
        self.assertEqual(intent, "none")

    def test_classify_empty(self):
        intent, params = self.classify("")
        self.assertEqual(intent, "none")

    # ── Route tests ──────────────────────────────────────────────

    def test_route_calendar_match(self):
        result = self.route("takvimimi göster")
        self.assertIsNotNone(result)
        self.assertIn("etkinlik", result)

    def test_route_calendar_no_match(self):
        result = self.route("güzel bir gün")
        self.assertIsNone(result)

    def test_route_calendar_empty(self):
        result = self.route("")
        self.assertIsNone(result)

    # ── Execute tests ────────────────────────────────────────────

    def test_execute_get_events(self):
        result = self.execute("get_events", {"query": "today", "limit": 6})
        self.assertIn("etkinlik", result)

    def test_execute_add_event(self):
        result = self.execute("add_event", {"title": "Toplantı", "start_iso": "2025-01-01"})
        self.assertIn("eklendi", result)

    def test_execute_delete_event(self):
        result = self.execute("delete_event", {"title": "Toplantı"})
        self.assertIn("silindi", result)

    def test_execute_unknown(self):
        result = self.execute("unknown_action", {})
        self.assertIn("Bilinmeyen", result)
