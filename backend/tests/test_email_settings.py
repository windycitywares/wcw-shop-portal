"""Email sending settings: the sealed password, the validation, and how admin settings sit on top of the server's."""

import unittest

from pydantic import ValidationError

from app.core import mailer, secretbox
from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError
from app.schemas.settings import EmailSettings
from app.services.settings import _email_patch
from tests.integration_support import reset_limits, skip_unless_db, world


class SecretBoxTests(unittest.TestCase):
    def test_round_trip_and_not_readable(self):
        sealed = secretbox.seal("hunter2-Pa$$")
        self.assertNotIn("hunter2", sealed)
        self.assertEqual(secretbox.unseal(sealed), "hunter2-Pa$$")
        self.assertNotEqual(secretbox.seal("x"), secretbox.seal("x"))  # a fresh nonce each time

    def test_garbage_and_tampering_open_to_nothing(self):
        self.assertIsNone(secretbox.unseal(None))
        self.assertIsNone(secretbox.unseal("plain text"))
        self.assertIsNone(secretbox.unseal("v1:!!!"))
        sealed = secretbox.seal("secret")
        self.assertIsNone(secretbox.unseal(sealed[:-3] + ("AAA" if not sealed.endswith("AAA") else "BBB")))

    def test_a_different_server_secret_cannot_open_it(self):
        settings = get_settings()
        saved = settings.jwt_secret
        sealed = secretbox.seal("secret")
        try:
            settings.jwt_secret = saved + "-rotated"
            self.assertIsNone(secretbox.unseal(sealed))
        finally:
            settings.jwt_secret = saved


class ValidationTests(unittest.TestCase):
    def test_blank_means_unset_and_values_are_checked(self):
        e = EmailSettings(from_name=" ", from_address="", smtp_host="")
        self.assertEqual((e.from_name, e.from_address, e.smtp_host), (None, None, None))
        for bad in ({"from_address": "nope"}, {"reply_to": "a b@c.com"}, {"smtp_host": "mail.example.com/evil"},
                    {"smtp_host": "a b"}, {"from_name": "Shop\nBcc: x@y.z"}, {"from_name": "<Shop>"}, {"smtp_port": 0},
                    {"smtp_port": 70000}, {"smtp_security": "tls13"}, {"smtp_user": "a\nb"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                EmailSettings(**bad)

    def test_the_password_cannot_be_sent_pre_sealed_and_is_sealed_on_the_way_in(self):
        with self.assertRaises(ValidationFailedError):
            _email_patch({"smtp_password_enc": "v1:whatever"})
        patch = _email_patch({"smtp_host": "mail.example.com", "smtp_password": "pw-123456"})
        self.assertNotIn("smtp_password", patch)
        self.assertEqual(secretbox.unseal(patch["smtp_password_enc"]), "pw-123456")
        self.assertIsNone(_email_patch({"clear_smtp_password": True})["smtp_password_enc"])
        self.assertNotIn("smtp_password_enc", _email_patch({"smtp_password": ""}))  # blank keeps what is saved
        with self.assertRaises(ValidationFailedError):
            _email_patch({"smtp_password": "x" * 500})


class OverlayTests(unittest.TestCase):
    base = get_settings().model_copy(update={"smtp_host": "env.example.com", "smtp_port": 465, "smtp_security": "ssl",
                                             "smtp_user": "env-user", "smtp_password": "env-pass",
                                             "mail_from": "env@example.com", "mail_from_name": "Env", "mail_reply_to": None})

    def test_nothing_saved_means_the_servers_own_settings(self):
        s = mailer.apply_overrides(self.base, {})
        self.assertEqual((s.smtp_host, s.smtp_user, s.smtp_password, s.mail_from), ("env.example.com", "env-user", "env-pass", "env@example.com"))

    def test_sender_fields_override_one_by_one(self):
        s = mailer.apply_overrides(self.base, {"from_name": "Windy City Wares", "reply_to": "help@example.com"})
        self.assertEqual((s.mail_from_name, s.mail_from, s.mail_reply_to, s.smtp_host), ("Windy City Wares", "env@example.com", "help@example.com", "env.example.com"))

    def test_a_saved_mail_server_replaces_every_smtp_field(self):
        sealed = secretbox.seal("new-pass")
        s = mailer.apply_overrides(self.base, {"smtp_host": "smtp.new.example", "smtp_security": "starttls", "smtp_password_enc": sealed})
        self.assertEqual((s.smtp_host, s.smtp_port, s.smtp_security, s.smtp_user, s.smtp_password),
                         ("smtp.new.example", 587, "starttls", None, "new-pass"))  # no leftover env user next to the new host

    def test_reply_to_is_added_to_the_message(self):
        msg = mailer.build_message(mailer.Mail(to="a@example.com", subject="Hi", text="x"), self.base.model_copy(update={"mail_reply_to": "help@example.com"}))
        self.assertEqual(msg["Reply-To"], "help@example.com")
        own = mailer.build_message(mailer.Mail(to="a@example.com", subject="Hi", text="x", reply_to="cust@example.com"), self.base.model_copy(update={"mail_reply_to": "help@example.com"}))
        self.assertEqual(own["Reply-To"], "cust@example.com")


@skip_unless_db
class AdminEmailSettingsTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def tearDown(self):
        self.w.put("/admin/settings/email", {"smtp_host": "", "smtp_port": None, "smtp_security": None, "smtp_user": "", "clear_smtp_password": True,
                                             "from_name": "", "from_address": "", "reply_to": ""}, self.w.admin)

    def test_save_never_reveals_the_password_and_the_flags_follow(self):
        w = self.w
        r = w.put("/admin/settings/email", {"smtp_host": "smtp.example.test", "smtp_security": "starttls", "smtp_user": "shop",
                                            "smtp_password": "very-secret-pw", "from_name": "Windy City Wares", "from_address": "hello@example.test"}, w.admin)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("very-secret-pw", r.text)
        email = r.json()["settings"]["email"]
        self.assertEqual((email["smtp_host"], email["smtp_user"], email["smtp_password_enc"]), ("smtp.example.test", "shop", None))
        self.assertTrue(r.json()["status"]["email_password_set"])
        self.assertTrue(r.json()["status"]["email_from_settings"])
        again = w.get("/admin/settings", w.admin)
        self.assertNotIn("very-secret-pw", again.text)
        self.assertNotIn("v1:", again.text)
        # Leaving the password box empty keeps it; the audit log never holds it.
        kept = w.put("/admin/settings/email", {"from_name": "WCW"}, w.admin).json()
        self.assertTrue(kept["status"]["email_password_set"])
        audit = w.get("/admin/audit", w.admin, q="settings").text
        self.assertNotIn("very-secret-pw", audit)
        self.assertNotIn("v1:", audit)
        cleared = w.put("/admin/settings/email", {"clear_smtp_password": True}, w.admin).json()
        self.assertFalse(cleared["status"]["email_password_set"])

    def test_bad_values_and_a_sealed_password_sent_directly_are_refused(self):
        w = self.w
        for body in ({"from_address": "not-an-address"}, {"smtp_host": "bad host/x"}, {"smtp_port": 99999}, {"smtp_password_enc": "v1:abc"}):
            with self.subTest(body=body):
                self.assertIn(w.put("/admin/settings/email", body, w.admin).status_code, (422, 400))
        self.assertEqual(w.put("/admin/settings/email", {"from_name": "x"}, w.publisher).status_code, 403)

    def test_test_email_goes_to_the_signed_in_admin(self):
        w = self.w
        before = len(w.sent)
        r = w.post("/admin/settings/test-email", None, w.admin)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(any(m.subject.startswith("Test email") for m in w.sent[before:]))


if __name__ == "__main__":
    unittest.main()
