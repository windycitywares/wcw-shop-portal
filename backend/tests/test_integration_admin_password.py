"""An admin sets a new password for someone who lost theirs (Team page)."""

import time
import unittest

from tests.integration_support import RUN, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class AdminSetsPasswordTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def patch(self, user_id, body, headers):
        return self.w.client.patch(self.w.url(f"/users/{user_id}"), json=body, headers=headers)

    def test_admin_sets_a_password_and_old_sign_ins_stop(self):
        w = self.w
        email, old_headers = w.register("lost-password")
        uid = w.value("SELECT id FROM users WHERE email = :e", e=email)
        self.assertEqual(self.patch(uid, {"password": "short"}, w.admin).status_code, 422)
        self.assertEqual(self.patch(uid, {"password": "new-password-123"}, w.publisher).status_code, 403)

        time.sleep(1.1)  # tokens carry whole seconds; the old one must be older than the change
        self.assertEqual(self.patch(uid, {"password": "new-password-123"}, w.admin).status_code, 200)
        self.assertEqual(w.get("/auth/me", old_headers).status_code, 401)  # signed out everywhere
        self.assertEqual(w.get("/auth/me", w.login(email, "new-password-123")).json()["email"], email)
        self.assertEqual(w.value("SELECT count(*) FROM audit_log WHERE action = 'user.password_set' AND entity_id = :i", i=str(uid)), 1)

    def test_not_for_your_own_account(self):
        w = self.w
        me = w.value("SELECT id FROM users WHERE email = :e", e=w.admin_email)
        res = self.patch(me, {"password": "another-password-1"}, w.admin)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Your account", res.json()["detail"])


if __name__ == "__main__":
    unittest.main()
