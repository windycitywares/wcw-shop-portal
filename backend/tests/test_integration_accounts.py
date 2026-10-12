"""End-to-end API tests against a real PostgreSQL database.

Runs only when TEST_DATABASE_URL is set (GitHub Actions starts PostgreSQL 13 for this); skipped on the
server, where the deploy script runs the unit tests.
"""

import os
import time
import unittest
import uuid

RUN = bool(os.environ.get("TEST_DATABASE_URL"))
if RUN:
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ.setdefault("DB_USE_NULL_POOL", "true")


@unittest.skipUnless(RUN, "TEST_DATABASE_URL not set")
class AccountFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        from app.core import mailer
        from app.main import create_app

        cls.sent = []

        async def fake_send(mail):
            cls.sent.append(mail)

        cls._real_send = mailer.send
        mailer.send = fake_send
        cls.client = TestClient(create_app())
        cls.api = "/api/v1"

    @classmethod
    def tearDownClass(cls):
        from app.core import mailer

        mailer.send = cls._real_send

    def signup(self, password="first-password-1"):
        email = f"t-{uuid.uuid4().hex[:10]}@example.com"
        r = self.client.post(f"{self.api}/auth/register",
                             json={"email": email, "password": password, "full_name": "Test Person"})
        self.assertEqual(r.status_code, 201, r.text)
        return email, {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_addresses(self):
        _, auth = self.signup()
        url = f"{self.api}/account/addresses"
        base = {"full_name": "Ana Ruiz", "line1": "1 Main St", "city": "Chicago", "region": "IL",
                "postal_code": "60601", "country": "us"}
        a = self.client.post(url, json={**base, "label": "Home"}, headers=auth).json()
        self.assertTrue(a["is_default"])  # first address becomes the default
        self.assertEqual(a["country"], "US")
        b = self.client.post(url, json={**base, "label": "Work", "is_default": True}, headers=auth).json()
        listed = self.client.get(url, headers=auth).json()
        self.assertEqual([x["id"] for x in listed if x["is_default"]], [b["id"]])
        r = self.client.post(f"{url}/{a['id']}/default", headers=auth)
        self.assertTrue(r.json()["is_default"])
        r = self.client.put(f"{url}/{b['id']}", json={**base, "label": "Office"}, headers=auth)
        self.assertEqual(r.json()["label"], "Office")
        self.assertEqual(self.client.delete(f"{url}/{a['id']}", headers=auth).status_code, 204)
        listed = self.client.get(url, headers=auth).json()
        self.assertEqual(len(listed), 1)
        self.assertTrue(listed[0]["is_default"])  # remaining address promoted
        # Someone else can't see or touch these addresses.
        _, other = self.signup()
        self.assertEqual(self.client.get(url, headers=other).json(), [])
        self.assertEqual(self.client.delete(f"{url}/{b['id']}", headers=other).status_code, 404)
        self.assertEqual(self.client.get(url).status_code, 401)

    def test_forgot_and_reset_password(self):
        email, old_auth = self.signup()
        self.sent.clear()
        r = self.client.post(f"{self.api}/auth/forgot-password", json={"email": email, "locale": "es"})
        self.assertEqual(r.status_code, 202)
        self.assertEqual(len(self.sent), 1)
        mail = self.sent[0]
        self.assertEqual(mail.to, email)
        self.assertIn("/es/reset-password?token=", mail.text)
        token = mail.text.split("token=")[1].split()[0]

        # Unknown email: same answer, no email.
        r = self.client.post(f"{self.api}/auth/forgot-password", json={"email": "nobody@example.com"})
        self.assertEqual(r.status_code, 202)
        self.assertEqual(len(self.sent), 1)

        time.sleep(1.1)  # token "issued at" has 1-second resolution; real resets come much later
        r = self.client.post(f"{self.api}/auth/reset-password", json={"token": token, "new_password": "second-password-2"})
        self.assertEqual(r.status_code, 200, r.text)
        # Link works once.
        r = self.client.post(f"{self.api}/auth/reset-password", json={"token": token, "new_password": "third-password-3"})
        self.assertEqual(r.status_code, 422)
        # New password works, old one doesn't, old session is signed out.
        ok = self.client.post(f"{self.api}/auth/login", data={"username": email, "password": "second-password-2"})
        self.assertEqual(ok.status_code, 200)
        bad = self.client.post(f"{self.api}/auth/login", data={"username": email, "password": "first-password-1"})
        self.assertEqual(bad.status_code, 401)
        self.assertEqual(self.client.get(f"{self.api}/auth/me", headers=old_auth).status_code, 401)

    def test_contact(self):
        self.sent.clear()
        body = {"name": "Ana", "email": "ana@example.com", "subject": "Question about sizes",
                "message": "Do you ship the keepsake set to Canada?", "order_number": "WCW-1001"}
        r = self.client.post(f"{self.api}/contact", json=body)
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0].reply_to, "ana@example.com")
        self.assertIn("WCW-1001", self.sent[0].text)
        # Honeypot: accepted silently, nothing sent.
        r = self.client.post(f"{self.api}/contact", json={**body, "website": "http://spam.test"})
        self.assertEqual(r.status_code, 202)
        self.assertEqual(len(self.sent), 1)

    def test_site_config(self):
        r = self.client.get(f"{self.api}/site-config")
        self.assertEqual(r.status_code, 200)
        self.assertIn("turnstile_site_key", r.json())


if __name__ == "__main__":
    unittest.main()
