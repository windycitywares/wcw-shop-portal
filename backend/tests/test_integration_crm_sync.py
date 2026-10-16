"""CRM sync: changes are recorded in the same transaction, sent once with the current state, signed, and retried."""

import hashlib
import hmac
import json
import unittest

from tests.integration_support import item, skip_unless_db, world

URL = "https://crm.example.test/api/v1/integrations/shop/webhook"
SECRET = "k" * 48


@skip_unless_db
class CrmSyncTests(unittest.TestCase):
    def setUp(self):
        from app.core.config import get_settings
        from app.services import crm_sync

        self.w = world()
        self.cfg = get_settings()
        self.cfg.crm_webhook_url, self.cfg.crm_webhook_secret = URL, SECRET
        self.sent: list[dict] = []
        self.answer = (200, '{"status":"accepted"}')
        self._real_transport = crm_sync.transport

        def fake(url, body, headers):
            self.sent.append({"url": url, "body": body, "headers": headers, "event": json.loads(body)})
            return self.answer

        crm_sync.transport = fake
        self.w.sql("UPDATE crm_outbox SET status = 'skipped' WHERE status = 'pending'")  # start clean

    def tearDown(self):
        from app.services import crm_sync

        crm_sync.transport = self._real_transport
        self.cfg.crm_webhook_url = self.cfg.crm_webhook_secret = None

    def outbox(self, kind, ref_id):
        return self.w.sql("SELECT * FROM crm_outbox WHERE kind = :k AND ref_id = :r ORDER BY id", k=kind, r=ref_id)

    def deliver(self):
        from app.services.crm_sync import CrmSync

        return self.w.db(lambda s: CrmSync(s).deliver_due())

    def test_account_order_and_consent_are_sent_signed(self):
        email, headers = self.w.register("crm", name="Cora Crm")
        user_id = self.w.value("SELECT id FROM users WHERE email = :e", e=email)
        self.assertEqual(len(self.outbox("customer", user_id)), 1)

        product = self.w.product()
        self.w.place(email, [item(product)], headers, marketing_opt_in=True)
        order_id = self.w.value("SELECT id FROM orders WHERE email = :e ORDER BY id DESC LIMIT 1", e=email)
        self.assertGreaterEqual(len(self.outbox("order", order_id)), 1)
        sub_id = self.w.value("SELECT id FROM newsletter_subscribers WHERE email = :e", e=email)
        self.assertGreaterEqual(len(self.outbox("newsletter", sub_id)), 1)

        result = self.deliver()
        self.assertGreaterEqual(result["sent"], 3)
        by_type = {s["event"]["type"]: s for s in self.sent}
        self.assertEqual(by_type["customer.upserted"]["event"]["data"], {"id": user_id, "email": email, "full_name": "Cora Crm"})
        order = [s["event"]["data"] for s in self.sent if s["event"]["type"] == "order.updated" and s["event"]["data"]["id"] == order_id]
        self.assertEqual(len(order), 1)  # several changes in checkout → one send with the latest state
        self.assertEqual(order[0]["email"], email)
        self.assertTrue(order[0]["marketing_opt_in"])
        self.assertEqual(order[0]["billing_address"]["city"], "Chicago")
        self.assertEqual(by_type["newsletter.subscribed"]["event"]["data"]["email"], email)

        sent = by_type["customer.upserted"]
        ts = sent["headers"]["X-WCW-Timestamp"]
        expected = "sha256=" + hmac.new(SECRET.encode(), f"{ts}.".encode() + sent["body"], hashlib.sha256).hexdigest()
        self.assertEqual(sent["headers"]["X-WCW-Signature"], expected)
        self.assertEqual(sent["url"], URL)
        self.assertTrue(all(r["status"] in ("sent", "merged") for r in self.outbox("order", order_id)))
        self.assertEqual(self.deliver(), {})  # nothing left

    def test_unsubscribe_and_staff_accounts(self):
        email = self.w.email("leaver")

        async def subscribe(session):
            from app.services.auth import NewsletterService

            row = await NewsletterService(session).add(email, "en", source="site", welcome=False)
            return row.id, row.unsubscribe_token

        sub_id, token = self.w.db(subscribe)
        self.deliver()
        self.sent.clear()

        async def leave(session):
            from app.services.auth import NewsletterService

            return await NewsletterService(session).unsubscribe(token)

        self.assertTrue(self.w.db(leave))
        self.deliver()
        self.assertEqual([s["event"]["type"] for s in self.sent], ["newsletter.unsubscribed"])
        self.assertEqual(self.outbox("newsletter", sub_id)[-1]["status"], "sent")

        # staff accounts are not CRM customers
        staff_id = self.w.value("SELECT id FROM users WHERE email = :e", e=self.w.admin_email)
        self.w.sql("UPDATE users SET full_name = 'Raw SQL is not seen' WHERE id = :i", i=staff_id)
        self.assertEqual(self.outbox("customer", staff_id), [])

    def test_retry_then_give_up_on_bad_request(self):
        email, _ = self.w.register("retry")
        user_id = self.w.value("SELECT id FROM users WHERE email = :e", e=email)

        self.answer = (None, "URLError: down")
        self.assertEqual(self.deliver().get("retry"), 1)
        row = self.outbox("customer", user_id)[-1]
        self.assertEqual((row["status"], row["attempts"]), ("pending", 1))
        self.assertGreater(row["next_attempt_at"], row["created_at"])
        self.assertEqual(self.deliver(), {})  # not due yet

        self.w.sql("UPDATE crm_outbox SET next_attempt_at = now() WHERE id = :i", i=row["id"])
        self.answer = (400, '{"detail":"Not a valid event"}')
        self.assertEqual(self.deliver().get("failed"), 1)
        self.assertEqual(self.outbox("customer", user_id)[-1]["status"], "failed")

    def test_nothing_recorded_in_test_mode_or_when_off(self):
        from app.core import appmode

        real = appmode.is_test
        appmode.is_test = lambda: True
        try:
            email, _ = self.w.register("testmode")
        finally:
            appmode.is_test = real
        user_id = self.w.value("SELECT id FROM users WHERE email = :e", e=email)
        self.assertEqual(self.outbox("customer", user_id), [])

        self.cfg.crm_webhook_url = None
        email, _ = self.w.register("off")
        user_id = self.w.value("SELECT id FROM users WHERE email = :e", e=email)
        self.assertEqual(self.outbox("customer", user_id), [])
        self.assertEqual(self.deliver(), {"skipped": "not configured"})


if __name__ == "__main__":
    unittest.main()
