from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


class TestRemindersSkill(unittest.TestCase):
    """reminders_skill pure function tests — mocks action imports."""

    def setUp(self):
        from skills.reminders.reminders_skill import (
            classify_reminders_intent,
            execute_reminders_skill,
            route_reminders_request,
        )
        self.classify = classify_reminders_intent
        self.execute = execute_reminders_skill
        self.route = route_reminders_request

        self.patchers = [
            patch("skills.reminders.reminders_skill.get_reminders",
                  return_value="Bugün 2 hatırlatıcı: ..."),
            patch("skills.reminders.reminders_skill.add_reminder",
                  return_value="Hatırlatıcı eklendi: Test başlığı"),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    # ── Classify tests ───────────────────────────────────────────

    def test_classify_get_reminders(self):
        intent, params = self.classify("hatırlatıcıları göster")
        self.assertEqual(intent, "get_reminders")

    def test_classify_get_reminders_today(self):
        intent, params = self.classify("hatırlatıcıları göster")
        self.assertEqual(intent, "get_reminders")

    def test_classify_add_reminder(self):
        intent, params = self.classify("hatırlatma ekle")
        self.assertEqual(intent, "add_reminder")

    def test_classify_add_reminder_with_title(self):
        intent, params = self.classify("toplantı için reminder ekle")
        self.assertEqual(intent, "add_reminder")

    def test_classify_fallback_keyword(self):
        intent, params = self.classify("reminder")
        self.assertEqual(intent, "get_reminders")

    def test_classify_none(self):
        intent, params = self.classify("merhaba nasılsın")
        self.assertEqual(intent, "none")

    def test_classify_empty(self):
        intent, params = self.classify("")
        self.assertEqual(intent, "none")

    # ── Route tests ──────────────────────────────────────────────

    def test_route_reminders_match(self):
        result = self.route("hatırlatıcıları göster")
        self.assertIsNotNone(result)
        self.assertIn("hatırlatıcı", result)

    def test_route_reminders_no_match(self):
        result = self.route("güzel bir gün")
        self.assertIsNone(result)

    def test_route_reminders_empty(self):
        result = self.route("")
        self.assertIsNone(result)

    # ── Execute tests ────────────────────────────────────────────

    def test_execute_get_reminders(self):
        result = self.execute("get_reminders", {"query": "today", "limit": 8, "list_name": ""})
        self.assertIn("hatırlatıcı", result)

    def test_execute_add_reminder(self):
        result = self.execute("add_reminder", {"title": "Test", "due_iso": "2025-01-01"})
        self.assertIn("eklendi", result)

    def test_execute_unknown(self):
        result = self.execute("unknown_action", {})
        self.assertIn("Bilinmeyen", result)
