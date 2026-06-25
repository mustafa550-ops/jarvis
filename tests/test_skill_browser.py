from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


class TestBrowserSkill(unittest.TestCase):
    """browser_skill pure function tests — mocks browser_control."""

    def setUp(self):
        from skills.browser.browser_skill import route_browser_request, execute_browser_skill
        self.route = route_browser_request
        self.execute = execute_browser_skill

        self.patchers = [
            patch("skills.browser.browser_skill.browser_control",
                  return_value="Chrome'da açıldı."),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    # ── Route tests ──────────────────────────────────────────────

    def test_route_open_url_google(self):
        result = self.route("google aç")
        self.assertIsNotNone(result)

    def test_route_open_url_youtube(self):
        result = self.route("youtube aç")
        self.assertIsNotNone(result)

    def test_route_open_url_github(self):
        result = self.route("github aç")
        self.assertIsNotNone(result)

    def test_route_open_url_gmail(self):
        result = self.route("gmail aç")
        self.assertIsNotNone(result)

    def test_route_search_google_ara(self):
        result = self.route("google'da python ara")
        self.assertIsNotNone(result)

    def test_route_search_simple(self):
        result = self.route("python ara")
        self.assertIsNotNone(result)

    def test_route_play_youtube_oynat(self):
        result = self.route("şarkı oynat")
        self.assertIsNotNone(result)

    def test_route_keyword_fallback_browser(self):
        result = self.route("google ara")
        self.assertIsNotNone(result)

    def test_route_no_match_random(self):
        result = self.route("bugün hava çok güzel")
        self.assertIsNone(result)

    def test_route_no_match_empty(self):
        result = self.route("")
        self.assertIsNone(result)

    def test_route_no_match_multiword_open(self):
        # "youtube sarki ac" — multi-word after aç triggers None
        result = self.route("youtube sarki aç")
        self.assertIsNone(result)

    # ── Execute tests ────────────────────────────────────────────

    def test_execute_open_url(self):
        result = self.execute("open_url", url="https://google.com")
        self.assertIn("açıldı", result)

    def test_execute_search(self):
        result = self.execute("search", query="python")
        self.assertIn("açıldı", result)

    def test_execute_play_youtube(self):
        result = self.execute("play_youtube", query="şarkı")
        self.assertIn("açıldı", result)

    def test_execute_unknown_action(self):
        result = self.execute("unknown", {})
        self.assertIn("açıldı", result)
