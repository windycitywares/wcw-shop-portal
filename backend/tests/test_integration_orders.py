"""Batch 3 API tests against PostgreSQL: checkout, payments, order emails, stock, orders admin, newsletter, carts."""

import csv
import hashlib
import hmac
import io
import json
import re
import time
import unittest
import uuid

from tests.integration_support import RUN, item, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


def order_count(email: str) -> int:
    return world().value("SELECT count(*) FROM orders WHERE email = :e", e=email)


@skip_unless_db
class CheckoutTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def test_guest_checkout_pays_reserves_stock_and_emails(self):
        w = self.w
        p = w.product("40.00", stock=10, cost="15.00")
        email = w.email("guest")
        before = len(w.sent)
        data = w.place(email, [item(p, 2)])
        order = data["order"]
        self.assertEqual(data["payment"]["status"], "paid")
        self.assertEqual((order["status"], order["payment_status"]), ("paid", "paid"))
        self.assertTrue(order["number"].startswith("WCW-"))
        self.assertEqual((order["subtotal"], order["shipping_total"], order["grand_total"]), (80.0, 8.95, 88.95))
        self.assertEqual(w.stock(p), {"stock_quantity": 8, "status": "in_stock", "units_sold": 2})
        mails = w.mails_to(email, "confirmed")
        self.assertEqual(len(mails), 1)
        self.assertIn(order["number"], mails[0].subject)
        self.assertIn(f"/order/{order['access_token']}", mails[0].text)
        if any(m.subject.startswith("New order") for m in w.sent[before:]):
            self.assertTrue(any(order["number"] in m.subject for m in w.sent[before:] if m.subject.startswith("New order")))

        # The private link shows the order and is never cached or indexed; a wrong token shows nothing.
        r = w.get(f"/orders/by-token/{order['access_token']}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["cache-control"], "no-store")
        self.assertIn("noindex", r.headers["x-robots-tag"])
        self.assertEqual([e["type"] for e in r.json()["timeline"]], ["placed", "paid"])
        self.assertEqual(w.get("/orders/by-token/not-a-real-token").status_code, 404)

        # Number + email finds it (with or without the prefix); a wrong email doesn't.
        found = w.post("/orders/lookup", {"number": order["number"].lower(), "email": email.upper()})
        self.assertEqual(found.json()["detail"], order["access_token"])
        self.assertEqual(w.post("/orders/lookup", {"number": order["number"][4:], "email": email}).status_code, 200)
        self.assertEqual(w.post("/orders/lookup", {"number": order["number"], "email": w.email()}).status_code, 404)

    def test_same_request_twice_makes_one_order(self):
        w = self.w
        p = w.product(stock=10)
        email = w.email("double")
        key = f"idem-{uuid.uuid4().hex}"
        first = w.place(email, [item(p)], idempotency_key=key)
        second = w.place(email, [item(p)], idempotency_key=key)
        self.assertEqual(first["order"]["number"], second["order"]["number"])
        self.assertEqual(w.stock(p)["stock_quantity"], 9)
        self.assertEqual(order_count(email), 1)
        w.place(w.email("thief"), [item(p)], idempotency_key=key, expect=409)

    def test_refusals_leave_nothing_behind(self):
        w = self.w
        ok, gone = w.product(stock=5), w.product(out_of_stock=True)
        email = w.email("refused")
        w.place(email, [item(ok), item(gone)], expect=409)  # something in the cart can't be bought
        w.place(email, [item(gone)], expect=422)  # nothing left to buy
        w.place(email, [item(ok)], shipping_address=w.address(country="CA"), expect=422)  # we don't ship there
        w.place(email, [item(ok)], coupon="NOT-A-CODE", expect=422)
        w.place(email, [item(ok)], payment_method="paypal", expect=422)
        w.place(email, [], expect=422)
        w.place(email, [item(ok, 6)], expect=409)  # more than in stock
        self.assertEqual(order_count(email), 0)
        self.assertEqual(w.stock(ok)["stock_quantity"], 5)

    def test_checkout_is_rate_limited_per_network(self):
        from app.core import rate_limit

        w = self.w
        p = w.product()
        for _ in range(rate_limit.checkout_by_ip.max_hits):
            rate_limit.checkout_by_ip.hit("203.0.113.9")
        r = w.client.post("/api/v1/checkout", json=w.checkout_body(w.email(), [item(p)]), headers={"X-Forwarded-For": "203.0.113.9"})
        self.assertEqual(r.status_code, 429)

    def test_signed_in_shopper_sees_own_orders(self):
        w = self.w
        email, me = w.register("buyer")
        p = w.product()
        order = w.place(email, [item(p)], me, save_address=True)["order"]
        mine = w.get("/account/orders", me).json()
        self.assertEqual(mine["total"], 1)
        self.assertEqual(mine["items"][0]["number"], order["number"])
        self.assertEqual(w.get(f"/account/orders/{order['id']}", me).json()["number"], order["number"])
        self.assertEqual(len(w.get("/account/addresses", me).json()), 1)
        _, other = w.register("nosy")
        self.assertEqual(w.get(f"/account/orders/{order['id']}", other).status_code, 404)
        self.assertEqual(w.get("/account/orders").status_code, 401)

    def test_personal_code_works_once(self):
        w = self.w
        p = w.product()
        email = w.email("once")
        code = w.post("/admin/promotions/coupons/bulk", {"emails": [email], "campaign": f"once-{w.sfx}", "value": 10}, w.admin).json()["sample"][0]
        order = w.place(email, [item(p)], coupon=code)["order"]
        self.assertEqual(order["coupon_code"], code)
        self.assertEqual(order["discount_total"], 4.0)
        w.place(email, [item(p)], coupon=code, expect=422)


@skip_unless_db
class OrderAdminTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def test_staff_only(self):
        w = self.w
        for path in ("/admin/orders", "/admin/carts"):
            self.assertEqual(w.get(path).status_code, 401)
            self.assertEqual(w.get(path, w.customer).status_code, 403)
            self.assertEqual(w.get(path, w.publisher).status_code, 403)

    def test_lifecycle_ship_deliver_refund(self):
        w = self.w
        p = w.product("40.00", cost="15.00")
        email = w.email("life")
        order = w.place(email, [item(p, 2)], shipping_address=w.address(full_name="=SUM(1+1)"))["order"]
        oid = order["id"]
        listed = w.get("/admin/orders", w.admin, q=order["number"]).json()
        self.assertEqual([o["number"] for o in listed["items"]], [order["number"]])
        self.assertEqual(listed["stats"]["revenue"], 88.95)
        detail = w.get(f"/admin/orders/{oid}", w.admin).json()
        self.assertEqual((detail["cost_total"], detail["profit"]), (30.0, 50.0))
        self.assertEqual({e["type"] for e in detail["events"]}, {"placed", "paid"})

        self.assertEqual(w.post(f"/admin/orders/{oid}/note", {"message": "Call before delivery"}, w.admin).status_code, 201)
        self.assertEqual(w.post(f"/admin/orders/{oid}/status", {"status": "processing"}, w.admin).json()["status"], "processing")
        shipped = w.post(f"/admin/orders/{oid}/ship", {"carrier": "usps", "tracking_number": "9400  1000 0000"}, w.admin).json()
        self.assertEqual((shipped["status"], shipped["tracking_number"]), ("shipped", "9400 1000 0000"))
        self.assertTrue(shipped["tracking_url"].startswith("https://"))
        self.assertEqual(len(w.mails_to(email, "on its way")), 1)
        self.assertEqual(w.post(f"/admin/orders/{oid}/cancel", {}, w.admin).status_code, 409)
        self.assertEqual(w.post(f"/admin/orders/{oid}/status", {"status": "delivered"}, w.admin).json()["status"], "delivered")

        self.assertEqual(w.post(f"/admin/orders/{oid}/refund", {"amount": 1000}, w.admin).status_code, 422)
        part = w.post(f"/admin/orders/{oid}/refund", {"amount": 10, "reason": "Scratched lid"}, w.admin).json()
        self.assertEqual((part["payment_status"], part["refunded_total"]), ("partially_refunded", 10.0))
        self.assertEqual(len(w.mails_to(email, "refund")), 1)
        full = w.post(f"/admin/orders/{oid}/refund", {"amount": 78.95, "notify_customer": False}, w.admin).json()
        self.assertEqual((full["status"], full["payment_status"]), ("refunded", "refunded"))
        self.assertEqual(w.post(f"/admin/orders/{oid}/refund", {"amount": 1}, w.admin).status_code, 409)

        public = w.get(f"/orders/by-token/{order['access_token']}").text
        self.assertIn("delivered", public)
        self.assertNotIn("Call before delivery", public)  # staff notes stay internal

        exported = w.get("/admin/orders/export.csv", w.admin, q=order["number"]).text
        rows = list(csv.reader(io.StringIO(exported)))
        row = dict(zip(rows[0], rows[1]))
        self.assertEqual(row["Ship to"], "Chicago, IL, US")
        self.assertEqual(row["Customer"], "'=SUM(1+1)")  # formula neutralised

    def test_cancel_gives_everything_back(self):
        w = self.w
        p = w.product(stock=5)
        coupon = w.post("/admin/promotions/coupons", {"code": f"BACK{w.sfx}", "value": 10, "usage_limit": 3}, w.admin).json()
        order = w.place(w.email("cancel"), [item(p, 2)], coupon=coupon["code"])["order"]
        self.assertEqual(w.get(f"/admin/promotions/coupons/{coupon['id']}", w.admin).json()["used_count"], 1)
        self.assertEqual(w.post(f"/admin/orders/{order['id']}/cancel", {"refund": False}, w.admin).status_code, 409)
        done = w.post(f"/admin/orders/{order['id']}/cancel", {"reason": "Customer asked"}, w.admin).json()
        self.assertEqual((done["status"], done["payment_status"]), ("cancelled", "refunded"))
        self.assertEqual(w.stock(p), {"stock_quantity": 5, "status": "in_stock", "units_sold": 0})
        self.assertEqual(w.get(f"/admin/promotions/coupons/{coupon['id']}", w.admin).json()["used_count"], 0)
        self.assertEqual(w.post(f"/admin/orders/{order['id']}/ship", {}, w.admin).status_code, 409)
        self.assertEqual(w.post(f"/admin/orders/{order['id']}/cancel", {}, w.admin).status_code, 409)

    def test_pay_later_is_no_longer_offered(self):
        w = self.w
        p = w.product(stock=2)
        r = w.post("/checkout", w.checkout_body(w.email("nolater"), [item(p)], payment_method="manual"))
        self.assertEqual(r.status_code, 422, r.text)
        self.assertIn("available", r.text)
        self.assertEqual(w.stock(p)["stock_quantity"], 2)  # nothing was held for an order that can't be paid

    def test_an_order_waiting_for_money_can_be_marked_paid_by_staff(self):
        w = self.w
        p = w.product(stock=4)
        email = w.email("later")
        data = w.place_unpaid(email, [item(p)])
        order = data["order"]
        self.assertEqual((data["payment"]["status"], order["status"]), ("pending", "pending"))
        self.assertEqual(w.stock(p)["stock_quantity"], 3)  # held for the customer
        self.assertEqual(len(w.mails_to(email, "received")), 1)
        paid = w.post(f"/admin/orders/{order['id']}/mark-paid", {"reference": "CHECK-1042"}, w.admin).json()
        self.assertEqual((paid["status"], paid["payment_status"]), ("paid", "paid"))
        self.assertEqual(paid["payments"][-1]["provider_ref"], "CHECK-1042")
        self.assertEqual(w.post(f"/admin/orders/{order['id']}/mark-paid", {}, w.admin).status_code, 409)
        self.assertEqual(len(w.mails_to(email, "confirmed")), 1)
        self.assertEqual(w.post(f"/admin/orders/{order['id']}/resend", None, w.admin).status_code, 200)
        self.assertEqual(len(w.mails_to(email, "confirmed")), 2)

    def test_unpaid_card_orders_expire(self):
        w = self.w
        p = w.product(stock=4)
        order = w.place_unpaid(w.email("expire"), [item(p)])["order"]
        w.sql("UPDATE orders SET payment_provider = 'stripe', placed_at = now() - interval '3 hours' WHERE id = :id", id=order["id"])

        async def run(session):
            from app.services.orders import OrderService

            return await OrderService(session).expire_unpaid()

        self.assertGreaterEqual(w.db(run)["cancelled"], 1)
        self.assertEqual(w.value("SELECT status::text FROM orders WHERE id = :id", id=order["id"]), "cancelled")
        self.assertEqual(w.stock(p)["stock_quantity"], 4)


@skip_unless_db
class StripeWebhookTests(unittest.TestCase):
    SECRET = "whsec_ci_only"

    def setUp(self):
        from app.core.config import get_settings

        reset_limits()
        self.w = world()
        self.settings = get_settings()
        self._old = self.settings.stripe_webhook_secret
        self.settings.stripe_webhook_secret = self.SECRET

    def tearDown(self):
        self.settings.stripe_webhook_secret = self._old

    def send(self, event: dict, secret: str | None = None):
        body = json.dumps(event).encode()
        ts = str(int(time.time()))
        sig = hmac.new((secret or self.SECRET).encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        return self.w.client.post("/api/v1/payments/stripe/webhook", content=body,
                                  headers={"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"})

    def test_only_signed_matching_payments_count(self):
        w = self.w
        order = w.place_unpaid(w.email("hook"), [item(w.product("40.00"))])["order"]
        paid = {"type": "checkout.session.completed", "data": {"object": {
            "id": "cs_test_1", "client_reference_id": order["number"], "payment_status": "paid", "amount_total": 4895,
            "currency": "usd", "payment_intent": f"pi_{w.sfx}"}}}
        self.assertEqual(w.client.post("/api/v1/payments/stripe/webhook", content=b"{}").status_code, 422)
        self.assertEqual(self.send(paid, secret="whsec_wrong").status_code, 422)
        wrong = json.loads(json.dumps(paid))
        wrong["data"]["object"]["amount_total"] = 100
        self.send(wrong)
        self.assertEqual(w.value("SELECT payment_status FROM orders WHERE id = :id", id=order["id"]), "unpaid")
        self.assertEqual(self.send(paid).json()["result"], "paid")
        self.assertEqual(self.send(paid).json()["result"], "paid")  # Stripe retries are harmless
        self.assertEqual(w.value("SELECT count(*) FROM payments WHERE order_id = :id AND status = 'succeeded'", id=order["id"]), 1)

        refund = {"type": "charge.refunded", "data": {"object": {"id": "ch_1", "payment_intent": f"pi_{w.sfx}", "amount_refunded": 1000}}}
        self.assertEqual(self.send(refund).json()["result"], "refund recorded")
        self.assertEqual(self.send(refund).json()["result"], "already recorded")
        self.assertEqual(w.value("SELECT payment_status FROM orders WHERE id = :id", id=order["id"]), "partially_refunded")


@skip_unless_db
class NewsletterAndCartTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def test_welcome_offer_and_unsubscribe(self):
        w = self.w
        email = w.email("news")
        self.assertEqual(w.post("/newsletter", {"email": email}).status_code, 202)
        welcome = w.mails_to(email, "welcome")
        self.assertEqual(len(welcome), 1)
        code = re.search(r"\bWELCOME[A-Z0-9]+\b", welcome[0].text).group(0)
        p = w.product("40.00")
        self.assertEqual(w.quote([item(p)], coupon=code, email=email)["discount_total"], 4.0)
        self.assertFalse(w.quote([item(p)], coupon=code, email=w.email())["coupon"]["valid"])
        token = re.search(r"/unsubscribe\?token=([\w-]+)", welcome[0].text).group(1)
        self.assertEqual(w.post("/newsletter/unsubscribe", {"token": token}).status_code, 200)
        self.assertEqual(w.post("/newsletter/unsubscribe", {"token": token}).status_code, 200)
        self.assertEqual(w.post("/newsletter/unsubscribe", {"token": "x" * 20}).status_code, 404)
        w.post("/newsletter", {"email": email})
        self.assertEqual(len(w.mails_to(email, "welcome")), 1)  # coming back gets no second offer

    def test_cart_snapshot_reminder_and_recovery(self):
        w = self.w
        p = w.product("40.00")
        email = w.email("cart")
        r = w.post("/cart/sync", {"items": [item(p, 2)], "email": email, "reminders_ok": True, "locale": "en"})
        token = r.json()["token"]
        self.assertEqual(w.get(f"/cart/recover/{token}").json()["items"][0]["quantity"], 2)
        no_consent = w.post("/cart/sync", {"items": [item(p)], "email": w.email("quiet")}).json()["token"]
        self.assertIsNone(w.value("SELECT email FROM carts WHERE token = :t", t=no_consent))  # no consent, no address kept

        w.sql("UPDATE carts SET last_activity_at = now() - interval '25 hours' WHERE token = :t", t=token)

        async def remind(session):
            from app.services.carts import CartRecoveryJob

            return await CartRecoveryJob(session).run()

        self.assertGreaterEqual(w.db(remind)["sent"], 1)
        mails = w.mails_to(email, "cart")
        self.assertEqual(len(mails), 1)
        self.assertIn(f"/cart?recover={token}", mails[0].text)
        self.assertIn("/unsubscribe?token=", mails[0].text)
        w.db(remind)
        self.assertEqual(len(w.mails_to(email, "cart")), 1)  # the next reminder waits days, not minutes
        self.assertEqual(w.value("SELECT source FROM newsletter_subscribers WHERE email = :e", e=email), "cart_reminder")

        listed = w.get("/admin/carts", w.admin, status="abandoned").json()
        self.assertIn(email, [c["email"] for c in listed["items"]])
        w.place(email, [item(p, 2)], cart_token=token)
        self.assertEqual(w.get(f"/cart/recover/{token}").json()["items"], [])


if __name__ == "__main__":
    unittest.main()
