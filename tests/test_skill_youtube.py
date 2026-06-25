from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


class TestYoutubeSkill(unittest.TestCase):
    """youtube_skill pure function tests — mocks action imports."""

    def setUp(self):
        from skills.youtube.youtube_skill import (
            classify_youtube_intent,
            execute_youtube_skill,
            route_youtube_request,
        )
        self.classify = classify_youtube_intent
        self.execute = execute_youtube_skill
        self.route = route_youtube_request

        self.patchers = [
            patch("skills.youtube.youtube_skill.get_youtube_channel_report",
                  return_value="Kanal raporu: 1500 abone, 50000 izlenme"),
            patch("skills.youtube.youtube_skill.play_media",
                  return_value="YouTube'da çalınıyor..."),
            patch("skills.youtube.youtube_skill.get_app_config_value",
                  return_value="test_handle"),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    # ── Classify tests ───────────────────────────────────────────

    def test_classify_channel_report(self):
        intent, params = self.classify("youtube kanal raporu")
        self.assertEqual(intent, "channel_report")

    def test_classify_channel_abone(self):
        intent, params = self.classify("abone sayısı kaç")
        self.assertEqual(intent, "channel_report")

    def test_classify_channel_izlenme(self):
        intent, params = self.classify("izlenme durumu")
        self.assertEqual(intent, "channel_report")

    def test_classify_play_media(self):
        intent, params = self.classify("youtube'da şarkı aç")
        self.assertEqual(intent, "play_media")

    def test_classify_fallback_keyword(self):
        intent, params = self.classify("kanal istatistik")
        self.assertEqual(intent, "channel_report")

    def test_classify_none(self):
        intent, params = self.classify("merhaba nasılsın")
        self.assertEqual(intent, "none")

    def test_classify_empty(self):
        intent, params = self.classify("")
        self.assertEqual(intent, "none")

    # ── Route tests ──────────────────────────────────────────────

    def test_route_youtube_match(self):
        result = self.route("youtube kanal raporu")
        self.assertIsNotNone(result)
        self.assertIn("raporu", result)

    def test_route_youtube_no_match(self):
        result = self.route("güzel bir gün")
        self.assertIsNone(result)

    def test_route_youtube_empty(self):
        result = self.route("")
        self.assertIsNone(result)

    # ── Execute tests ────────────────────────────────────────────

    def test_execute_channel_report(self):
        result = self.execute("channel_report", {"query": "overview", "handle": "test_handle"})
        self.assertIn("raporu", result)

    def test_execute_channel_report_no_handle(self):
        result = self.execute("channel_report", {"query": "overview", "handle": ""})
        self.assertIn("tanimli degil", result)

    def test_execute_play_media(self):
        result = self.execute("play_media", {"query": "şarkı", "provider": "youtube", "autoplay": True})
        self.assertIn("çalınıyor", result)

    def test_execute_unknown(self):
        result = self.execute("unknown_action", {})
        self.assertIn("Bilinmeyen", result)
