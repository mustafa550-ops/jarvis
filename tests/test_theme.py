from __future__ import annotations

import unittest


class TestThemeConstants(unittest.TestCase):
    """ui.theme — renk paleti, font, boyut sabitleri."""

    def test_module_import(self):
        from ui.theme import (
            C_BG, C_PRI, C_ORG, C_MID, C_DIM, C_DIMMER, C_TEXT, C_PANEL,
            C_GREEN, C_RED, C_MUTED, C_BLUE, C_GOLD,
        )
        self.assertEqual(C_BG, "#020c0c")
        self.assertEqual(C_PRI, "#00d4c0")
        self.assertEqual(C_GREEN, "#00ff88")
        self.assertEqual(C_RED, "#ff3344")
        self.assertEqual(C_MUTED, "#cc2255")

    def test_orb_colors_contains_all_states(self):
        from ui.theme import ORB_COLORS
        for state in ("LISTENING", "SPEAKING", "THINKING", "MUTED", "PAUSED", "ERROR", "INITIALISING"):
            self.assertIn(state, ORB_COLORS)
            r, g, b = ORB_COLORS[state]
            self.assertIsInstance(r, int)
            self.assertIsInstance(g, int)
            self.assertIsInstance(b, int)

    def test_state_hex_colors_contains_all_states(self):
        from ui.theme import STATE_HEX_COLORS
        for state in ("LISTENING", "SPEAKING", "THINKING", "INITIALISING", "ERROR"):
            self.assertIn(state, STATE_HEX_COLORS)
            self.assertTrue(STATE_HEX_COLORS[state].startswith("#"))

    def test_orb_color_rgb_ranges(self):
        from ui.theme import ORB_COLORS
        for state, (r, g, b) in ORB_COLORS.items():
            self.assertGreaterEqual(r, 0)
            self.assertLessEqual(r, 255)
            self.assertGreaterEqual(g, 0)
            self.assertLessEqual(g, 255)
            self.assertGreaterEqual(b, 0)
            self.assertLessEqual(b, 255)

    def test_dimensions_positive(self):
        from ui.theme import W_TARGET, H_TARGET, LEFT_W_T, RIGHT_W_T, HDR_H, FOOTER_H, INPUT_H, CONTROL_H
        for val in (W_TARGET, H_TARGET, LEFT_W_T, RIGHT_W_T, HDR_H, FOOTER_H, INPUT_H, CONTROL_H):
            self.assertGreater(val, 0)

    def test_voices_list(self):
        from ui.theme import VOICES
        self.assertIn("Charon", VOICES)
        self.assertIn("Puck", VOICES)
        self.assertGreater(len(VOICES), 5)

    def test_font_families(self):
        from ui.theme import FONT_BODY_FAMILY, FONT_DISPLAY_FAMILY
        self.assertIsInstance(FONT_BODY_FAMILY, str)
        self.assertIsInstance(FONT_DISPLAY_FAMILY, str)
        self.assertGreater(len(FONT_BODY_FAMILY), 0)
        self.assertGreater(len(FONT_DISPLAY_FAMILY), 0)

    def test_font_body_returns_tuple(self):
        from ui.theme import font_body
        result = font_body(14)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 14)

    def test_font_body_bold_returns_tuple(self):
        from ui.theme import font_body_bold
        result = font_body_bold(16)
        self.assertIsInstance(result, tuple)
        self.assertIn("bold", result)

    def test_font_display_returns_tuple(self):
        from ui.theme import font_display
        result = font_display(20)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 20)
