from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


class TestWhatsappSkill(unittest.TestCase):
    """whatsapp_skill pure function tests — mocks action imports."""

    def setUp(self):
        from skills.whatsapp.whatsapp_skill import (
            classify_whatsapp_intent,
            execute_whatsapp_skill,
            route_whatsapp_request,
        )
        self.classify = classify_whatsapp_intent
        self.execute = execute_whatsapp_skill
        self.route = route_whatsapp_request

        self.patchers = [
            patch("skills.whatsapp.whatsapp_skill.send_whatsapp_message",
                  return_value="WhatsApp mesajı gönderildi."),
            patch("skills.whatsapp.whatsapp_skill.save_whatsapp_contact",
                  return_value="Kişi kaydedildi: Ahmet"),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    # ── Classify tests ───────────────────────────────────────────

    def test_classify_send_message(self):
        intent, params = self.classify("whatsapp mesaj gönder")
        self.assertEqual(intent, "send_message")

    def test_classify_send_message_to_contact(self):
        intent, params = self.classify("ahmet'e whatsapp mesaj at")
        self.assertEqual(intent, "send_message")
        self.assertEqual(params.get("recipient_name"), "Ahmet")

    def test_classify_save_contact(self):
        intent, params = self.classify("whatsapp kişi kaydet")
        self.assertEqual(intent, "save_contact")

    def test_classify_fallback_keyword(self):
        intent, params = self.classify("wp")
        self.assertIn(intent, ("send_message",))

    def test_classify_none(self):
        intent, params = self.classify("merhaba nasılsın")
        self.assertEqual(intent, "none")

    def test_classify_empty(self):
        intent, params = self.classify("")
        self.assertEqual(intent, "none")

    # ── Route tests ──────────────────────────────────────────────

    def test_route_whatsapp_match(self):
        result = self.route("ahmet'e whatsapp mesaj gönder")
        self.assertIsNotNone(result)
        self.assertIn("gönderildi", result)

    def test_route_whatsapp_no_match(self):
        result = self.route("güzel bir gün")
        self.assertIsNone(result)

    def test_route_whatsapp_empty(self):
        result = self.route("")
        self.assertIsNone(result)

    # ── Execute tests ────────────────────────────────────────────

    def test_execute_send_message(self):
        result = self.execute("send_message", {
            "recipient_name": "Ahmet", "message": "Merhaba",
            "phone_number": "", "send_now": False, "app_target": "auto"
        })
        self.assertIn("gönderildi", result)

    def test_execute_send_message_no_recipient(self):
        result = self.execute("send_message", {
            "recipient_name": "", "message": "",
            "phone_number": "", "send_now": False, "app_target": "auto"
        })
        self.assertIn("belirtilmedi", result)

    def test_execute_save_contact(self):
        result = self.execute("save_contact", {
            "display_name": "Ahmet", "phone_number": "+905551234567"
        })
        self.assertIn("kaydedildi", result)

    def test_execute_save_contact_no_name(self):
        result = self.execute("save_contact", {
            "display_name": "", "phone_number": ""
        })
        self.assertIn("zorunlu", result)

    def test_execute_unknown(self):
        result = self.execute("unknown_action", {})
        self.assertIn("Bilinmeyen", result)
