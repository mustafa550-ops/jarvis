from __future__ import annotations

import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class TestDrawUtils(unittest.TestCase):
    """ui.draw_utils pure fonksiyon testleri — Tkinter canvas gerektirmeyenler."""

    def test_module_import(self):
        """ui.draw_utils import edilebilmeli."""
        from ui import draw_utils
        self.assertIsNotNone(draw_utils)

    def test_ac_alpha_composite(self):
        """_ac alpha composite hex renk dondurur."""
        from ui.draw_utils import _ac
        result = _ac(0, 255, 136, 255)
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith("#"))
        self.assertEqual(len(result), 7)

    def test_ac_zero_alpha(self):
        """_ac alpha=0 siyah doner."""
        from ui.draw_utils import _ac
        result = _ac(255, 255, 255, 0)
        self.assertEqual(result, "#000000")

    def test_ac_full_alpha(self):
        """_ac alpha=255 tam renk doner."""
        from ui.draw_utils import _ac
        result = _ac(255, 0, 0, 255)
        self.assertEqual(result, "#ff0000")

    def test_ac_half_alpha(self):
        """_ac alpha=127 yari saydam renk doner."""
        from ui.draw_utils import _ac
        result = _ac(255, 255, 255, 127)
        self.assertEqual(len(result), 7)
        self.assertTrue(result.startswith("#"))

    def test_ac_clamps_alpha_low(self):
        """_ac alpha < 0 degerini 0'a kilitler."""
        from ui.draw_utils import _ac
        result = _ac(255, 0, 0, -50)
        self.assertEqual(result, "#000000")

    def test_ac_clamps_alpha_high(self):
        """_ac alpha > 255 degerini 255'e kilitler."""
        from ui.draw_utils import _ac
        result = _ac(0, 255, 0, 300)
        self.assertEqual(result, "#00ff00")

    def test_orb_rgb_listening(self):
        """_orb_rgb LISTENING state icin ORB_COLORS degerini dondurur."""
        from ui.draw_utils import _orb_rgb
        from ui.theme import ORB_COLORS
        result = _orb_rgb("LISTENING", False)
        self.assertEqual(result, ORB_COLORS["LISTENING"])

    def test_orb_rgb_paused(self):
        """_orb_rgb paused=True iken PAUSED rengini dondurur."""
        from ui.draw_utils import _orb_rgb
        from ui.theme import ORB_COLORS
        result = _orb_rgb("LISTENING", True)
        self.assertEqual(result, ORB_COLORS["PAUSED"])

    def test_orb_rgb_speaking(self):
        """_orb_rgb SPEAKING state icin dogru rengi dondurur."""
        from ui.draw_utils import _orb_rgb
        from ui.theme import ORB_COLORS
        result = _orb_rgb("SPEAKING", False)
        self.assertEqual(result, ORB_COLORS["SPEAKING"])

    def test_orb_rgb_error(self):
        """_orb_rgb ERROR state icin dogru rengi dondurur."""
        from ui.draw_utils import _orb_rgb
        from ui.theme import ORB_COLORS
        result = _orb_rgb("ERROR", False)
        self.assertEqual(result, ORB_COLORS["ERROR"])

    def test_orb_rgb_unknown_fallback(self):
        """_orb_rgb bilinmeyen state LISTENING'e fallback yapar."""
        from ui.draw_utils import _orb_rgb
        from ui.theme import ORB_COLORS
        result = _orb_rgb("UNKNOWN_STATE_XYZ", False)
        self.assertEqual(result, ORB_COLORS["LISTENING"])

    def test_orb_rgb_thinking(self):
        """_orb_rgb THINKING state icin dogru rengi dondurur."""
        from ui.draw_utils import _orb_rgb
        from ui.theme import ORB_COLORS
        result = _orb_rgb("THINKING", False)
        self.assertEqual(result, ORB_COLORS["THINKING"])

    def test_sparkline_empty(self):
        """_sparkline bos data ile hata firlatmamali."""
        from ui.draw_utils import _sparkline
        # _sparkline n<2 ise early return
        # Canvas gerektirir, sadece import testi
        self.assertTrue(callable(_sparkline))

    def test_bar_import(self):
        """_bar fonksiyonu mevcut ve cagirilabilir."""
        from ui.draw_utils import _bar
        self.assertTrue(callable(_bar))

    def test_bracket_import(self):
        """_bracket fonksiyonu mevcut ve cagirilabilir."""
        from ui.draw_utils import _bracket
        self.assertTrue(callable(_bracket))

    def test_draw_info_card_import(self):
        """_draw_info_card fonksiyonu mevcut ve cagirilabilir."""
        from ui.draw_utils import _draw_info_card
        self.assertTrue(callable(_draw_info_card))


class TestDoubleBuffer(unittest.TestCase):
    """DoubleBuffer testleri — Tkinter gerektirir."""

    def setUp(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.withdraw()
        self.canvas = tk.Canvas(self.root, width=100, height=100)

    def tearDown(self):
        self.root.destroy()

    def test_init_defaults(self):
        from ui.draw_utils import DoubleBuffer
        buf = DoubleBuffer(self.canvas, 200, 150)
        self.assertEqual(buf.width, 200)
        self.assertEqual(buf.height, 150)
        self.assertTrue(buf.dirty)

    def test_clear_sets_dirty(self):
        from ui.draw_utils import DoubleBuffer
        buf = DoubleBuffer(self.canvas, 100, 100)
        buf.clear()
        self.assertTrue(buf.dirty)

    def test_resize_updates_dimensions(self):
        from ui.draw_utils import DoubleBuffer
        buf = DoubleBuffer(self.canvas, 100, 100)
        buf.resize(300, 200)
        self.assertEqual(buf.width, 300)
        self.assertEqual(buf.height, 200)

    def test_render_context(self):
        from ui.draw_utils import DoubleBuffer
        buf = DoubleBuffer(self.canvas, 100, 100)
        with buf.render() as off:
            off.create_text(50, 50, text="test")
        # Render context exits without error (PostScript blit may fail headless)
        self.assertFalse(buf.dirty)

    def test_render_context_clear(self):
        from ui.draw_utils import DoubleBuffer
        buf = DoubleBuffer(self.canvas, 100, 100)
        with buf.render() as off:
            off.create_text(10, 10, text="hello")
        self.assertFalse(buf.dirty)
        # Second render should clear previous content
        with buf.render() as off:
            off.create_text(20, 20, text="world")
        self.assertFalse(buf.dirty)


if __name__ == "__main__":
    unittest.main(verbosity=2)
