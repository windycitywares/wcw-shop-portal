import asyncio
import unittest

from pydantic import ValidationError

from app.core import captcha
from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError
from app.core.mailer import Mail, build_message
from app.schemas.account import AddressIn, ContactIn
from app.services.account import hash_token, localized_path


class CaptchaTests(unittest.TestCase):
    def setUp(self):
        self.settings = get_settings()
        self.saved = (self.settings.turnstile_secret, self.settings.turnstile_hostnames)

    def tearDown(self):
        self.settings.turnstile_secret, self.settings.turnstile_hostnames = self.saved

    def run_verify(self, token, result, action="signup"):
        calls = []

        def post(secret, tok, ip):
            calls.append((secret, tok, ip))
            if isinstance(result, Exception):
                raise result
            return result

        asyncio.run(captcha.verify(token, "1.2.3.4", action=action, post=post))
        return calls

    def test_skipped_without_secret(self):
        self.settings.turnstile_secret = None
        self.assertEqual(self.run_verify(None, {"success": False}), [])

    def test_missing_token_rejected(self):
        self.settings.turnstile_secret = "secret"
        with self.assertRaises(ValidationFailedError):
            self.run_verify(None, {"success": True})

    def test_success_and_failure(self):
        self.settings.turnstile_secret = "secret"
        ok = {"success": True, "action": "signup", "hostname": "shop.windycitywares.com"}
        self.assertEqual(self.run_verify("tok", ok), [("secret", "tok", "1.2.3.4")])
        with self.assertRaises(ValidationFailedError):
            self.run_verify("tok", {"success": False, "error-codes": ["invalid-input-response"]})

    def test_action_and_hostname_must_match(self):
        self.settings.turnstile_secret = "secret"
        self.settings.turnstile_hostnames = ["shop.windycitywares.com"]
        ok = {"success": True, "action": "signup", "hostname": "shop.windycitywares.com"}
        self.run_verify("tok", ok)
        with self.assertRaises(ValidationFailedError):  # token solved on the contact form
            self.run_verify("tok", {**ok, "action": "contact"})
        with self.assertRaises(ValidationFailedError):  # token solved on another site
            self.run_verify("tok", {**ok, "hostname": "evil.example"})
        with self.assertRaises(ValidationFailedError):  # oversized token
            self.run_verify("x" * 3000, ok)

    def test_network_error_is_a_validation_error(self):
        self.settings.turnstile_secret = "secret"
        with self.assertRaises(ValidationFailedError):
            self.run_verify("tok", OSError("down"))


class MailTests(unittest.TestCase):
    def test_message_headers(self):
        msg = build_message(Mail(to="a@example.com", subject="Hi", text="Body", reply_to="b@example.com"),
                            get_settings())
        self.assertEqual(msg["To"], "a@example.com")
        self.assertEqual(msg["Reply-To"], "b@example.com")
        self.assertIn("WindyCityWares", msg["From"])
        self.assertIn("Body", msg.get_content())

    def test_header_injection_blocked(self):
        with self.assertRaises(ValueError):
            build_message(Mail(to="a@example.com", subject="Hi\r\nBcc: x@evil.test", text="x"), get_settings())


class HelperTests(unittest.TestCase):
    def test_hash_token_is_stable_and_not_the_token(self):
        self.assertEqual(hash_token("abc"), hash_token("abc"))
        self.assertNotEqual(hash_token("abc"), "abc")
        self.assertEqual(len(hash_token("abc")), 64)

    def test_localized_path(self):
        self.assertEqual(localized_path("en", "/reset-password"), "/reset-password")
        self.assertEqual(localized_path("es", "/reset-password"), "/es/reset-password")


class SchemaTests(unittest.TestCase):
    def test_address_is_cleaned(self):
        a = AddressIn(full_name="  Ana   Ruiz ", line1="1 Main St", city="Chicago", postal_code="60601",
                      country="us", line2="  ")
        self.assertEqual(a.full_name, "Ana Ruiz")
        self.assertEqual(a.country, "US")
        self.assertIsNone(a.line2)

    def test_address_rejects_bad_phone_and_country(self):
        base = dict(full_name="A", line1="1", city="C", postal_code="1")
        with self.assertRaises(ValidationError):
            AddressIn(**base, phone="call me<script>")
        with self.assertRaises(ValidationError):
            AddressIn(**base, country="USA")

    def test_contact_subject_is_one_line(self):
        c = ContactIn(name="Ana", email="ana@example.com", subject="Hello\r\nBcc: x@evil.test",
                      message="A message long enough.")
        self.assertNotIn("\n", c.subject)
        with self.assertRaises(ValidationError):
            ContactIn(name="Ana", email="ana@example.com", subject="Hi", message="short")
        with self.assertRaises(ValidationError):
            ContactIn(name="Ana", email="ana@example.com", subject="Hi", message="A message long enough.",
                      locale="fr")


if __name__ == "__main__":
    unittest.main()
