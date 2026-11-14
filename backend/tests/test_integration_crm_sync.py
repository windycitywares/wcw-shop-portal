"""CRM sync: changes are recorded in the same transaction, sent once with the current state, signed, and retried."""

import hashlib
import hmac
import json
import unittest

from tests.integration_support import item, reset_limits, skip_unless_db, world

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
        self.assertTrue(by_type["newsletter.subscribed"]["event"]["data"]["at"])  # when they joined, for the CRM

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

    def test_a_contact_form_message_tells_the_crm(self):
        reset_limits()
        email = self.w.email("asker")
        subject = f"Gift wrap {self.w.sfx}"
        message = "Can this ship wrapped with a card?"
        sent = self.w.post("/contact", {"name": "Mia Park", "email": email, "subject": subject,
                                        "order_number": "WCW-3", "message": message})
        self.assertEqual(sent.status_code, 202, sent.text)

        msg_id = self.w.value("SELECT id FROM contact_messages WHERE subject = :s", s=subject)
        self.assertEqual(len(self.outbox("contact", msg_id)), 1)  # the contact page recorded it

        self.deliver()
        events = [s["event"] for s in self.sent if s["event"]["type"] == "contact_message.created"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["data"], {"name": "Mia Park", "email": email, "subject": subject,
                                             "message": message, "order_number": "WCW-3"})
        self.assertEqual(self.outbox("contact", msg_id)[-1]["status"], "sent")

        # The shop's own bookkeeping (open/closed, the emailed flag) is not a second message — the CRM has the
        # ticket already, and a second one would be a duplicate.
        async def handle(session):
            from app.models.account import ContactMessage

            msg = await session.get(ContactMessage, msg_id)
            msg.status, msg.emailed = "open", True
            await session.commit()

        self.w.db(handle)
        self.sent.clear()
        self.assertEqual(self.deliver(), {})
        self.assertEqual(self.sent, [])

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

    def test_nothing_recorded_when_off(self):
        self.cfg.crm_webhook_url = None
        email, _ = self.w.register("off")
        user_id = self.w.value("SELECT id FROM users WHERE email = :e", e=email)
        self.assertEqual(self.outbox("customer", user_id), [])
        self.assertEqual(self.deliver(), {"skipped": "not configured"})

    def test_the_test_copy_sends_test_events(self):
        """Test mode's changes go out under their own id prefix, which the CRM files in its Test copy."""
        import time
        from datetime import datetime, timezone

        from app.core import appmode
        from app.services.crm_sync import CrmSync

        email, _ = self.w.register("testsend")
        user_id = self.w.value("SELECT id FROM users WHERE email = :e", e=email)
        self.assertEqual(len(self.outbox("customer", user_id)), 1)  # recorded: test mode no longer opts out
        counts = {"sent": 0, "skipped": 0, "retry": 0, "failed": 0}
        # Without a copy the search path falls back to the live tables, which is enough to see the id and the send.
        self.w.db(lambda s: CrmSync(s)._deliver(appmode.TEST, self.cfg, time.monotonic(), datetime.now(timezone.utc), counts))
        mine = [e for e in self.sent if e["event"]["data"].get("email") == email]
        self.assertEqual(len(mine), 1)
        self.assertTrue(mine[0]["event"]["id"].startswith("shop-test-"))


@skip_unless_db
class CrmReadApiTests(unittest.TestCase):
    TOKEN = "r" * 40

    def setUp(self):
        from app.core.config import get_settings

        self.w = world()
        self.cfg = get_settings()
        self.cfg.crm_api_token = self.TOKEN
        self.auth = {"Authorization": f"Bearer {self.TOKEN}"}

    def tearDown(self):
        self.cfg.crm_api_token = None

    def test_token_and_paging(self):
        self.assertEqual(self.w.get("/integrations/crm/customers").status_code, 401)
        self.assertEqual(self.w.get("/integrations/crm/customers", {"Authorization": "Bearer wrong"}).status_code, 401)
        self.assertEqual(self.w.get("/integrations/crm/customers", self.w.admin).status_code, 401)  # a staff login isn't enough
        self.cfg.crm_api_token = None
        self.assertEqual(self.w.get("/integrations/crm/customers", self.auth).status_code, 404)
        self.cfg.crm_api_token = self.TOKEN

        email, headers = self.w.register("reader", name="Rita Reader")
        user_id = self.w.value("SELECT id FROM users WHERE email = :e", e=email)
        self.w.place(email, [item(self.w.product())], headers)

        page = self.w.get("/integrations/crm/customers", self.auth, after_id=user_id - 1, limit=1).json()
        self.assertEqual(page["items"], [{"id": user_id, "email": email, "full_name": "Rita Reader"}])
        self.assertEqual(page["next_after_id"], user_id)
        staff = {r["email"] for r in self.w.get("/integrations/crm/customers", self.auth, limit=500).json()["items"]}
        self.assertNotIn(self.w.admin_email, staff)

        orders = self.w.get("/integrations/crm/orders", self.auth, email=email.upper()).json()
        self.assertEqual(len(orders["items"]), 1)
        self.assertEqual(orders["items"][0]["user_id"], user_id)
        self.assertIsNone(orders["next_after_id"])

    def test_products_are_paged_and_searchable(self):
        product = self.w.product(price="42.50", title="Walnut bowl")
        sku = self.w.value("SELECT sku FROM products WHERE id = :id", id=product["id"])

        page = self.w.get("/integrations/crm/products", self.auth, after_id=product["id"] - 1, limit=1).json()
        self.assertEqual(page["items"], [{
            "id": product["id"], "parent_id": None, "sku": sku, "name": product["title"], "slug": product["slug"],
            "price": "42.50", "compare_at_price": None, "currency": "USD", "status": "published",
            "stock_status": "in_stock", "image": "https://media.example.com/test.jpg",
        }])
        self.assertEqual(page["next_after_id"], product["id"])

        found = self.w.get("/integrations/crm/products", self.auth, q=sku.lower()).json()["items"]
        self.assertIn(product["id"], [p["id"] for p in found])  # search ignores case
        empty = self.w.get("/integrations/crm/products", self.auth, q="nothing-matches-this").json()
        self.assertEqual(empty["items"], [])

    def test_only_published_products_are_listed(self):
        live = self.w.product(title="Visible item")
        draft = self.w.product(title="Draft item")
        self.w.sql("UPDATE products SET status = 'draft' WHERE id = :id", id=draft["id"])
        ids = [p["id"] for p in self.w.get("/integrations/crm/products", self.auth, after_id=live["id"] - 1,
                                           limit=500).json()["items"]]
        self.assertIn(live["id"], ids)
        self.assertNotIn(draft["id"], ids)

    def test_crm_opt_out_reaches_the_shop(self):
        w = self.w
        email = w.email("crm-optout")
        reset_limits()
        self.assertEqual(w.post("/newsletter", {"email": email}).status_code, 202)
        body = {"email": email.upper()}
        self.assertEqual(w.client.post(w.url("/integrations/crm/newsletter/opt-out"), json=body).status_code, 401)
        r = w.client.post(w.url("/integrations/crm/newsletter/opt-out"), json=body, headers=self.auth)
        self.assertEqual(r.json(), {"result": "unsubscribed"})
        self.assertIsNotNone(w.value("SELECT unsubscribed_at FROM newsletter_subscribers WHERE email = :e", e=email))
        again = w.client.post(w.url("/integrations/crm/newsletter/opt-out"), json=body, headers=self.auth)
        self.assertEqual(again.json(), {"result": "already"})
        unknown = w.client.post(w.url("/integrations/crm/newsletter/opt-out"), json={"email": "nobody-here@example.com"}, headers=self.auth)
        self.assertEqual(unknown.json(), {"result": "unknown"})


if __name__ == "__main__":
    unittest.main()
