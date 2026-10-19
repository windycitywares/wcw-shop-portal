"""Live / Test switch: which schema a connection uses, and emails in test mode."""

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.core import appmode
from app.core.enums import UserRole
from app.core.mailer import Mail, _for_test_mode
from app.services.auth import may_sign_in


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


class TestSignInTests(unittest.TestCase):
    """Who may sign in: on live data everyone active may; on the copy only staff, listed addresses,
    and accounts made inside the copy."""

    def tearDown(self):
        appmode.remember(appmode.ModeState())

    @staticmethod
    def user(email="shopper@example.com", role=UserRole.CUSTOMER, created_at=None):
        return SimpleNamespace(email=email, role=role, created_at=created_at)

    def test_the_stored_list_is_parsed_and_tidied(self):
        self.assertEqual(appmode.login_emails(" A@x.com,\n b@Y.com ; a@x.com "), ("a@x.com", "b@y.com"))
        self.assertEqual(appmode.login_emails(None), ())

    def test_live_data_lets_every_active_account_sign_in(self):
        self.assertTrue(may_sign_in(self.user()))

    def test_the_copy_refuses_a_copied_shopper_unless_listed(self):
        appmode.remember(appmode.ModeState("test", test_exists=True, login_emails=("shopper@example.com",)))
        self.assertTrue(may_sign_in(self.user()))
        self.assertFalse(may_sign_in(self.user(email="copied@example.com")))
        self.assertTrue(may_sign_in(self.user(role=UserRole.ADMIN)))  # staff always

    def test_an_account_made_inside_the_copy_may_sign_in(self):
        synced = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        appmode.remember(appmode.ModeState("test", test_exists=True, test_synced_at=synced))
        self.assertTrue(may_sign_in(self.user(created_at=synced + timedelta(minutes=5))))
        self.assertFalse(may_sign_in(self.user(created_at=synced - timedelta(days=3))))


if __name__ == "__main__":
    unittest.main()
