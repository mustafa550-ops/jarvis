from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


class TestMediaSkill(unittest.TestCase):
    """media_skill pure function tests — mocks play_media."""

    def setUp(self):
        from skills.media.media_skill import (
            classify_media_intent,
            execute_media_skill,
            route_media_request,
        )
        self.classify = classify_media_intent
        self.execute = execute_media_skill
        self.route = route_media_request

        self.patchers = [
            patch("skills.media.media_skill.play_media",
                  return_value="YouTube'da çalınıyor: sevdiğim şarkı"),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    # ── Classify tests ───────────────────────────────────────────

    def test_classify_sarki_cal(self):
        intent, params = self.classify("şarkı çal")
        self.assertEqual(intent, "play_media")
        self.assertIn("query", params)

    def test_classify_muzik_ac(self):
        intent, params = self.classify("müzik aç")
        self.assertEqual(intent, "play_media")

    def test_classify_youtube_video(self):
        intent, params = self.classify("youtube video aç")
        self.assertEqual(intent, "play_media")

    def test_classify_spotify_bul(self):
        intent, params = self.classify("spotify'dan şarkı bul")
        self.assertEqual(intent, "play_media")

    def test_classify_none(self):
        intent, params = self.classify("merhaba nasılsın")
        self.assertEqual(intent, "none")

    def test_classify_empty(self):
        intent, params = self.classify("")
        self.assertEqual(intent, "none")

    # ── Route tests ──────────────────────────────────────────────

    def test_route_media_match(self):
        result = self.route("şarkı çal")
        self.assertIsNotNone(result)
        self.assertIn("çalınıyor", result)

    def test_route_media_no_match(self):
        result = self.route("güzel bir gün")
        self.assertIsNone(result)

    def test_route_media_empty(self):
        result = self.route("")
        self.assertIsNone(result)

    # ── Execute tests ────────────────────────────────────────────

    def test_execute_play_media(self):
        result = self.execute("play_media", {"query": "şarkı", "provider": "auto", "autoplay": True})
        self.assertIn("çalınıyor", result)

    def test_execute_unknown(self):
        result = self.execute("unknown_action", {})
        self.assertIn("Bilinmeyen", result)
