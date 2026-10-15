"""Live / Test switch: which schema a connection uses, and emails in test mode."""

import unittest

from app.core import appmode
from app.core.mailer import Mail, _for_test_mode


class ModeStateTests(unittest.TestCase):
    def tearDown(self):
        appmode.remember(appmode.ModeState())

    def test_test_needs_the_copy(self):
        self.assertEqual(appmode.ModeState("test", test_exists=True).search_path, "wcw_test, public")
        self.assertEqual(appmode.ModeState("test", test_exists=False).effective, "live")  # never test without a copy
        self.assertEqual(appmode.ModeState().search_path, "public")

    def test_override_wins_for_a_block_only(self):
        appmode.remember(appmode.ModeState("test", test_exists=True))
        with appmode.use("live"):
            self.assertFalse(appmode.is_test())
        self.assertTrue(appmode.is_test())


class TestModeMailTests(unittest.TestCase):
    mail = Mail(to="customer@example.com", subject="Your order", text="Thanks!", html="<p>Thanks!</p>",
                headers=(("List-Unsubscribe", "<https://x/unsubscribe?token=a>"),))

    def tearDown(self):
        appmode.remember(appmode.ModeState())

    def test_live_mail_is_untouched(self):
        self.assertIs(_for_test_mode(self.mail), self.mail)

    def test_test_mode_redirects_to_the_test_inbox(self):
        appmode.remember(appmode.ModeState("test", test_exists=True, test_mail_to="qa@example.com"))
        out = _for_test_mode(self.mail)
        self.assertEqual((out.to, out.subject), ("qa@example.com", "[TEST] Your order"))
        self.assertIn("customer@example.com", out.text)
        self.assertEqual(out.headers, ())

    def test_test_mode_without_an_inbox_sends_nothing(self):
        appmode.remember(appmode.ModeState("test", test_exists=True))
        self.assertIsNone(_for_test_mode(self.mail))


if __name__ == "__main__":
    unittest.main()
