"""A disabled account: the shopper is told so when they sign in, and the shop owner gets an email (once in a while)."""

import unittest

from tests.integration_support import API, PASSWORD, reset_limits, skip_unless_db, world

OWNER = "owner-alerts@example.com"


@skip_unless_db
class DisabledAccountTests(unittest.TestCase):
    def setUp(self):
        from app.core.config import get_settings

        reset_limits()
        self.w = world()
        self.cfg = get_settings()
        self._old = self.cfg.contact_to
        self.cfg.contact_to = OWNER

    def tearDown(self):
        self.cfg.contact_to = self._old

    def login(self, email, password):
        return self.w.client.post(f"{API}/auth/login", data={"username": email, "password": password})

    def test_disabled_customer_is_told_and_owner_is_emailed_once(self):
        from app.core.rate_limit import disabled_alert_by_email

        w = self.w
        email, _ = w.register("paused-customer")
        uid = w.value("SELECT id FROM users WHERE email = :e", e=email.lower())
        self.assertEqual(w.client.patch(f"{API}/users/{uid}", json={"is_active": False}, headers=w.admin).status_code, 200)
        disabled_alert_by_email.reset(email.lower())
        before = len(w.mails_to(OWNER, "Disabled account"))

        wrong = self.login(email, "not-the-password")
        self.assertEqual(wrong.status_code, 401)
        self.assertNotIn("disabled", wrong.text.lower())  # a wrong password reveals nothing about the account
        self.assertEqual(len(w.mails_to(OWNER, "Disabled account")), before)

        right = self.login(email, PASSWORD)
        self.assertEqual(right.status_code, 401)
        self.assertIn("Your account is disabled", right.json()["detail"])
        sent = w.mails_to(OWNER, "Disabled account")
        self.assertEqual(len(sent), before + 1)
        self.assertIn(email.lower(), sent[-1].subject.lower())
        self.assertIn("/admin/users", sent[-1].text)

        self.login(email, PASSWORD)  # trying again does not email again
        self.assertEqual(len(w.mails_to(OWNER, "Disabled account")), before + 1)

        # Switched back on, they can sign in.
        w.client.patch(f"{API}/users/{uid}", json={"is_active": True}, headers=w.admin)
        reset_limits()
        self.assertEqual(self.login(email, PASSWORD).status_code, 200)


if __name__ == "__main__":
    unittest.main()
