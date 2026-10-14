"""Shop API tests against a real PostgreSQL database: prices, coupons, checkout, orders, refunds, card payments.

Runs only when TEST_DATABASE_URL is set (GitHub Actions starts PostgreSQL 13 for this).
"""

import asyncio
import json
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone

RUN = bool(os.environ.get("TEST_DATABASE_URL"))
if RUN:
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ.setdefault("DB_USE_NULL_POOL", "true")

ADDRESS = {"full_name": "Ana Ruiz", "line1": "1 Main St", "city": "Chicago", "region": "IL", "postal_code": "60601", "country": "US"}


def iso(delta_days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=delta_days)).isoformat()


@unittest.skipUnless(RUN, "TEST_DATABASE_URL not set")
class CommerceTests(unittest.TestCase):
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
        cls.admin = cls.make_admin()

    @classmethod
    def tearDownClass(cls):
        from app.core import mailer

        mailer.send = cls._real_send

    def setUp(self):
        from app.core import rate_limit

        # All tests share one "visitor" (the test client) and one process, so the per-address limits are cleared.
        for limiter in (rate_limit.checkouts_by_ip, rate_limit.coupon_misses_by_ip, rate_limit.newsletter_by_ip,
                        rate_limit.registrations_by_ip, rate_limit.contact_by_ip):
            limiter.reset("testclient")
        self.sent.clear()
        self.open_checkout()

    # -- helpers ------------------------------------------------------------------
    @classmethod
    def make_admin(cls):
        from app.core.database import SessionFactory
        from app.core.enums import UserRole
        from app.core.security import hash_password
        from app.models.user import User

        email = f"admin-{uuid.uuid4().hex[:8]}@example.com"

        async def go():
            async with SessionFactory() as s:
                s.add(User(email=email, hashed_password=hash_password("admin-password-1"), role=UserRole.ADMIN, full_name="Admin"))
                await s.commit()

        asyncio.run(go())
        r = cls.client.post(f"{cls.api}/auth/login", data={"username": email, "password": "admin-password-1"})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def signup(self):
        email = f"c-{uuid.uuid4().hex[:10]}@example.com"
        r = self.client.post(f"{self.api}/auth/register", json={"email": email, "password": "first-password-1", "full_name": "Cust Omer"})
        self.assertEqual(r.status_code, 201, r.text)
        return email, {"Authorization": f"Bearer {r.json()['access_token']}"}

    def open_checkout(self):
        r = self.client.patch(f"{self.api}/settings", json={"checkout_enabled": True}, headers=self.admin)
        self.assertEqual(r.status_code, 200, r.text)

    def use_settings(self, **changes):
        """Change store settings for one test; they go back to what they were afterwards."""
        before = self.client.get(f"{self.api}/settings", headers=self.admin).json()
        r = self.client.patch(f"{self.api}/settings", json=changes, headers=self.admin)
        self.assertEqual(r.status_code, 200, r.text)
        self.addCleanup(lambda: self.client.patch(f"{self.api}/settings", json={k: before[k] for k in changes}, headers=self.admin))

    @staticmethod
    def lines(items):
        """[(product, quantity)] or [(product, quantity, {"Color": "Red"})] -> request items."""
        out = []
        for i, (product, quantity, *rest) in enumerate(items):
            out.append({"product_id": product["id"], "quantity": quantity, "options": rest[0] if rest else {}, "key": f"line-{i}"})
        return out

    def product(self, price="40.00", stock=5, status="published", stock_status="in_stock", **extra):
        sku = f"T-{uuid.uuid4().hex[:10]}"
        body = {"sku": sku, "title": f"Test urn {sku}", "base_price": price, "status": status, "stock_quantity": stock, "stock_status": stock_status, **extra}
        r = self.client.post(f"{self.api}/products", json=body, headers=self.admin)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def stock_of(self, product):
        return self.client.get(f"{self.api}/products/by-id/{product['id']}", headers=self.admin).json()["stock_quantity"]

    def quote(self, items, **kw):
        body = {"items": self.lines(items), "country": "US", "region": "IL", **kw}
        r = self.client.post(f"{self.api}/checkout/quote", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def place(self, items, headers=None, **over):
        body = {
            "items": self.lines(items),
            "shipping_method": "standard", "email": "buyer@example.com", "shipping_address": ADDRESS,
            "payment_provider": "test", **over,
        }
        return self.client.post(f"{self.api}/checkout", json=body, headers=headers or {})

    def coupon(self, **over):
        body = {"code": f"T{uuid.uuid4().hex[:8].upper()}", "kind": "percent", "value": "10", **over}
        r = self.client.post(f"{self.api}/promotions/coupons", json=body, headers=self.admin)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def order(self, number, token=None, headers=None):
        url = f"{self.api}/orders/{number}" + (f"?token={token}" if token else "")
        return self.client.get(url, headers=headers or {})

    def paid_order(self, items, **over):
        r = self.place(items, **over)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    # -- access -----------------------------------------------------------------------
    def test_staff_endpoints_need_the_right_role(self):
        _, customer = self.signup()
        for method, path in [("get", "/promotions/coupons"), ("get", "/promotions/sales"), ("get", "/settings"),
                             ("get", "/orders"), ("get", "/messages"), ("get", "/settings/shipping")]:
            self.assertEqual(getattr(self.client, method)(f"{self.api}{path}").status_code, 401, path)
            self.assertEqual(getattr(self.client, method)(f"{self.api}{path}", headers=customer).status_code, 403, path)
            self.assertEqual(getattr(self.client, method)(f"{self.api}{path}", headers=self.admin).status_code, 200, path)

    # -- settings, shipping, tax -------------------------------------------------------------
    def test_settings_and_readiness(self):
        r = self.client.get(f"{self.api}/settings", headers=self.admin)
        data = r.json()
        self.assertTrue(data["test_payments_available"])
        self.assertTrue({"shipping", "payment", "alerts", "tax"} <= {i["id"] for i in data["readiness"]})
        r = self.client.patch(f"{self.api}/settings", json={"welcome_value": "150", "welcome_kind": "percent"}, headers=self.admin)
        self.assertEqual(r.status_code, 422)
        before = data["low_stock_threshold"]
        r = self.client.patch(f"{self.api}/settings", json={"low_stock_threshold": before + 2}, headers=self.admin)
        self.assertEqual(r.json()["low_stock_threshold"], before + 2)
        self.client.patch(f"{self.api}/settings", json={"low_stock_threshold": before}, headers=self.admin)
        r = self.client.patch(f"{self.api}/settings", json={"made_up": 1}, headers=self.admin)
        self.assertEqual(r.status_code, 422)
        public = self.client.get(f"{self.api}/shop-config").json()
        self.assertTrue(public["checkout_enabled"])
        self.assertIn("test", [o["id"] for o in public["payment_options"]])
        self.assertEqual(public["free_shipping_threshold"], 75.0)

    def test_shipping_and_tax_crud(self):
        code = f"x{uuid.uuid4().hex[:6]}"
        body = {"code": code, "name": "Courier", "price": "9.50", "free_over": "120", "min_days": 1, "max_days": 3, "countries": ["us", "ca"]}
        made = self.client.post(f"{self.api}/settings/shipping", json=body, headers=self.admin)
        self.assertEqual(made.status_code, 201, made.text)
        method = made.json()
        self.addCleanup(lambda: self.client.delete(f"{self.api}/settings/shipping/{method['id']}", headers=self.admin))
        self.assertEqual(method["countries"], ["US", "CA"])
        self.assertEqual(self.client.post(f"{self.api}/settings/shipping", json=body, headers=self.admin).status_code, 409)
        bad = self.client.post(f"{self.api}/settings/shipping", json={**body, "code": "y" + code, "max_days": 0}, headers=self.admin)
        self.assertEqual(bad.status_code, 422)
        upd = self.client.put(f"{self.api}/settings/shipping/{method['id']}", json={**body, "price": "11.00", "is_active": False}, headers=self.admin)
        self.assertEqual(upd.status_code, 200, upd.text)
        self.assertEqual((upd.json()["price"], upd.json()["is_active"]), (11.0, False))
        listed = self.client.get(f"{self.api}/settings/shipping", headers=self.admin).json()
        self.assertIn(code, [m["code"] for m in listed])
        self.assertEqual(self.client.delete(f"{self.api}/settings/shipping/{method['id']}", headers=self.admin).status_code, 204)
        self.assertEqual(self.client.delete(f"{self.api}/settings/shipping/{method['id']}", headers=self.admin).status_code, 404)

        rate = self.client.post(f"{self.api}/settings/tax", json={"name": "Test tax", "country": "us", "region": "ZZ", "rate": "7.5"}, headers=self.admin)
        self.assertEqual(rate.status_code, 201, rate.text)
        self.addCleanup(lambda: self.client.delete(f"{self.api}/settings/tax/{rate.json()['id']}", headers=self.admin))
        self.assertEqual((rate.json()["country"], rate.json()["rate"]), ("US", 7.5))
        self.assertEqual(self.client.post(f"{self.api}/settings/tax", json={"name": "Bad", "country": "US", "rate": "101"}, headers=self.admin).status_code, 422)
        changed = self.client.put(f"{self.api}/settings/tax/{rate.json()['id']}", json={"name": "Test tax", "country": "US", "region": "ZZ", "rate": "8"}, headers=self.admin)
        self.assertEqual(changed.json()["rate"], 8.0)
        self.assertEqual(self.client.delete(f"{self.api}/settings/tax/{rate.json()['id']}", headers=self.admin).status_code, 204)
        self.assertEqual(self.client.put(f"{self.api}/settings/tax/{rate.json()['id']}", json={"name": "x", "country": "US", "rate": "1"}, headers=self.admin).status_code, 404)

    # -- sales on the storefront ---------------------------------------------------------
    def test_sale_changes_the_storefront_price_only_while_live(self):
        p = self.product("40.00")
        sale_body = {"name": f"Autumn {uuid.uuid4().hex[:5]}", "label": "Autumn sale", "kind": "percent", "value": "25", "scope": "products", "product_ids": [p["id"]]}
        sale = self.client.post(f"{self.api}/promotions/sales", json=sale_body, headers=self.admin)
        self.assertEqual(sale.status_code, 201, sale.text)
        sale_id = sale.json()["id"]
        try:
            self.assertEqual(sale.json()["status"], "live")
            self.assertEqual(sale.json()["products"], [p["title"]])
            detail = self.client.get(f"{self.api}/products/{p['slug']}").json()
            self.assertEqual(detail["sale_price"], 30.0)
            self.assertEqual(detail["sale_label"], "Autumn sale")
            self.assertEqual(detail["base_price"], 40.0)  # the list price stays as it was
            listing = self.client.get(f"{self.api}/products?q={p['sku']}").json()
            self.assertEqual(listing["items"][0]["sale_price"], 30.0)
            q = self.quote([(p, 2)])
            self.assertEqual(q["subtotal"], 60.0)
            self.assertEqual(q["sale_savings"], 20.0)
            self.assertEqual(q["lines"][0]["sale_label"], "Autumn sale")

            later = {**sale_body, "starts_at": iso(1), "ends_at": iso(3)}
            self.assertEqual(self.client.put(f"{self.api}/promotions/sales/{sale_id}", json=later, headers=self.admin).json()["status"], "scheduled")
            self.assertIsNone(self.client.get(f"{self.api}/products/{p['slug']}").json()["sale_price"])
            ended = {**sale_body, "starts_at": iso(-3), "ends_at": iso(-1)}
            self.assertEqual(self.client.put(f"{self.api}/promotions/sales/{sale_id}", json=ended, headers=self.admin).json()["status"], "ended")
            self.assertIsNone(self.client.get(f"{self.api}/products/{p['slug']}").json()["sale_price"])
            paused = {**sale_body, "is_active": False}
            self.assertEqual(self.client.put(f"{self.api}/promotions/sales/{sale_id}", json=paused, headers=self.admin).json()["status"], "paused")
        finally:
            self.assertEqual(self.client.delete(f"{self.api}/promotions/sales/{sale_id}", headers=self.admin).status_code, 204)

    def test_sale_validation(self):
        bad = [
            {"name": "x", "kind": "percent", "value": "120"},
            {"name": "x", "kind": "percent", "value": "10", "scope": "category"},
            {"name": "x", "kind": "percent", "value": "10", "scope": "products", "product_ids": []},
            {"name": "x", "kind": "percent", "value": "10", "starts_at": iso(2), "ends_at": iso(1)},
            {"name": "x", "kind": "percent", "value": "10", "scope": "category", "category_id": 99999999},
        ]
        for body in bad:
            r = self.client.post(f"{self.api}/promotions/sales", json=body, headers=self.admin)
            self.assertIn(r.status_code, (404, 422), body)

    # -- the quote ---------------------------------------------------------------------
    def test_quote_with_coupon_shipping_and_tax(self):
        p = self.product("40.00", stock=None)
        region = "Q" + uuid.uuid4().hex[:5].upper()
        rate = self.client.post(f"{self.api}/settings/tax", json={"name": "Test tax", "country": "US", "region": region, "rate": "10", "applies_to_shipping": True}, headers=self.admin).json()
        try:
            c = self.coupon(value="10")
            q = self.quote([(p, 1)], coupon_code=c["code"].lower(), shipping_method="standard", region=region)
            self.assertEqual(q["coupon"]["code"], c["code"])
            self.assertEqual(q["subtotal"], 40.0)
            self.assertEqual(q["coupon"]["discount"], 4.0)
            self.assertEqual(q["shipping_total"], 6.95)
            # tax = 10% of (40 - 4 + 6.95)
            self.assertEqual(q["tax_total"], 4.30)
            self.assertAlmostEqual(q["total"], 47.25, places=2)
            self.assertEqual(q["free_shipping_threshold"], 75.0)
            self.assertAlmostEqual(q["free_shipping_remaining"], 75.0 - 36.0)
            self.assertEqual([o["code"] for o in q["shipping_options"]][:2], ["standard", "express"])

            over = self.quote([(self.product("80.00", stock=None), 1)], shipping_method="standard")
            self.assertEqual(over["shipping_total"], 0.0)
            self.assertTrue(over["shipping_options"][0]["free"])
            self.assertEqual(over["free_shipping_remaining"], 0.0)
        finally:
            self.client.delete(f"{self.api}/settings/tax/{rate['id']}", headers=self.admin)

    def test_quote_coupon_problems(self):
        p = self.product("40.00", stock=None)
        q = self.quote([(p, 1)], coupon_code="NOSUCHCODE")
        self.assertEqual(q["coupon_problem"]["code"], "invalid")
        self.assertIsNone(q["coupon"])
        self.assertEqual(q["total"], 40.0)
        big = self.coupon(min_subtotal="100")
        q = self.quote([(p, 1)], coupon_code=big["code"])
        self.assertEqual(q["coupon_problem"]["code"], "min_subtotal")
        self.assertEqual(q["coupon_problem"]["data"]["min"], "100.00")
        old = self.coupon(starts_at=iso(-5), expires_at=iso(-1))
        self.assertEqual(self.quote([(p, 1)], coupon_code=old["code"])["coupon_problem"]["code"], "expired")
        soon = self.coupon(starts_at=iso(2))
        self.assertEqual(self.quote([(p, 1)], coupon_code=soon["code"])["coupon_problem"]["code"], "not_started")
        other = self.product("10.00", stock=None)
        only = self.coupon(scope="products", product_ids=[other["id"]])
        self.assertEqual(self.quote([(p, 1)], coupon_code=only["code"])["coupon_problem"]["code"], "no_eligible_items")
        self.assertEqual(self.quote([(p, 1), (other, 1)], coupon_code=only["code"])["coupon"]["discount"], 1.0)

    def test_guessing_codes_is_slowed_down(self):
        p = self.product("40.00", stock=None)
        statuses = []
        for i in range(17):
            r = self.client.post(f"{self.api}/checkout/quote", json={"items": [{"product_id": p["id"], "quantity": 1}], "coupon_code": f"GUESS{i}"})
            statuses.append(r.status_code)
        self.assertEqual(statuses[:15], [200] * 15)
        self.assertEqual(statuses[15], 429)

    def test_free_shipping_coupon(self):
        p = self.product("20.00", stock=None)
        c = self.coupon(kind="free_shipping")
        q = self.quote([(p, 1)], coupon_code=c["code"], shipping_method="express")
        self.assertTrue(q["coupon"]["free_shipping"])
        self.assertEqual(q["shipping_total"], 0.0)
        self.assertEqual(q["shipping_discount"], 16.95)
        self.assertEqual(q["total"], 20.0)

    def test_unavailable_and_limited_items(self):
        draft = self.product("10.00", status="draft")
        sold_out = self.product("10.00", stock=0, stock_status="out_of_stock")
        few = self.product("10.00", stock=2)
        q = self.quote([(draft, 1), (sold_out, 1), (few, 5)])
        self.assertEqual(sorted(q["unavailable"]), sorted([draft["id"], sold_out["id"]]))
        self.assertEqual(q["lines"][0]["issue"], "limited")
        self.assertEqual(q["lines"][0]["max_quantity"], 2)

    def test_choices_travel_with_the_order(self):
        p = self.product("20.00", stock=None, attributes={"Color": ["Red", "Blue"], "Material": "Oak"})
        q = self.quote([(p, 1, {"Color": "Red"}), (p, 2, {"Color": "Blue"})])
        self.assertEqual([(line["key"], line["quantity"]) for line in q["lines"]], [("line-0", 1), ("line-1", 2)])
        self.assertEqual(q["subtotal"], 60.0)
        merged = self.quote([(p, 1, {"Color": "Red"}), (p, 2, {"Color": "Red"})])
        self.assertEqual([line["quantity"] for line in merged["lines"]], [3])
        wrong = self.quote([(p, 1, {"Color": "Green"}), (p, 1, {"Size": "L"})])
        self.assertEqual((wrong["lines"], wrong["unavailable"]), ([], [p["id"], p["id"]]))
        self.assertEqual(self.place([(p, 1, {"Color": "Green"})]).status_code, 409)

        placed = self.place([(p, 1, {"Color": "Red"}), (p, 2, {"Color": "Blue"})])
        self.assertEqual(placed.status_code, 201, placed.text)
        order = self.order(placed.json()["number"], placed.json()["access_token"]).json()
        self.assertEqual([i["title"] for i in order["items"]], [f"{p['title']} (Color: Red)", f"{p['title']} (Color: Blue)"])
        self.assertEqual(order["items"][0]["attributes"], {"Color": "Red", "Material": "Oak"})
        self.assertEqual(order["items"][1]["attributes"]["Color"], "Blue")

    def test_stock_is_checked_on_the_total_across_choices(self):
        p = self.product("20.00", stock=2, attributes={"Color": ["Red", "Blue"]})
        items = [(p, 2, {"Color": "Red"}), (p, 1, {"Color": "Blue"})]
        q = self.quote(items)
        self.assertEqual([(line["issue"], line["max_quantity"]) for line in q["lines"]], [("limited", 2), ("limited", 2)])
        self.assertEqual(self.place(items).status_code, 409)
        self.assertEqual(self.stock_of(p), 2)
        self.assertEqual(self.place([(p, 1, {"Color": "Red"}), (p, 1, {"Color": "Blue"})]).status_code, 201)
        self.assertEqual(self.stock_of(p), 0)

    # -- placing an order --------------------------------------------------------------------
    def test_order_with_test_payment_and_coupon(self):
        p = self.product("40.00", stock=5)
        c = self.coupon(value="10", usage_limit=3)
        r = self.place([(p, 2)], coupon_code=c["code"], notes="Please wrap as a gift")
        self.assertEqual(r.status_code, 201, r.text)
        placed = r.json()
        self.assertTrue(placed["number"].startswith("WCW-"))
        self.assertEqual(placed["status"], "paid")
        self.assertEqual(placed["next"], "paid")
        self.assertAlmostEqual(placed["total"], 78.95, places=2)
        self.assertEqual(self.stock_of(p), 3)
        self.assertEqual(self.client.get(f"{self.api}/promotions/coupons/{c['id']}", headers=self.admin).json()["used_count"], 1)
        # Emails: one to the buyer, one to the shop.
        self.assertEqual(sorted(m.to for m in self.sent), sorted(["buyer@example.com", "shop@example.com"]))
        confirmation = next(m for m in self.sent if m.to == "buyer@example.com")
        self.assertIn(placed["number"], confirmation.subject)
        self.assertIn(f"/order/{placed['number']}?token={placed['access_token']}", confirmation.text)

        # The link in the email opens the order; the bare number does not.
        view = self.order(placed["number"], placed["access_token"])
        self.assertEqual(view.status_code, 200, view.text)
        data = view.json()
        self.assertEqual(data["discount_total"], 8.0)
        self.assertEqual(data["items"][0]["quantity"], 2)
        self.assertEqual(data["items"][0]["discount"], 8.0)
        self.assertEqual(data["coupon_code"], c["code"])
        self.assertIsNone(data["internal_note"])
        self.assertIsNone(data["payment_ref"])
        self.assertEqual(self.order(placed["number"]).status_code, 404)
        self.assertEqual(self.order(placed["number"], "wrong-token").status_code, 404)
        self.assertEqual(self.order(placed["number"], "tökën").status_code, 404)
        staff = self.order(placed["number"], headers=self.admin).json()
        self.assertEqual(staff["email"], "buyer@example.com")
        self.assertIn("paid", [e["kind"] for e in staff["events"]])
        self.assertIn("paid", [e["kind"] for e in data["events"]])

    def test_checkout_refuses_bad_orders(self):
        p = self.product("40.00", stock=2)
        self.assertEqual(self.place([(p, 3)]).status_code, 409)  # only 2 left
        self.assertEqual(self.stock_of(p), 2)
        self.assertEqual(self.place([(p, 1)], expected_total="1.00").status_code, 409)  # price moved
        self.assertEqual(self.place([(p, 1)], shipping_method="nope").status_code, 422)
        self.assertEqual(self.place([(p, 1)], payment_provider="stripe").status_code, 422)  # not set up here
        self.assertEqual(self.place([(p, 1)], coupon_code="NOSUCHCODE").status_code, 422)
        draft = self.product("5.00", status="draft")
        self.assertEqual(self.place([(draft, 1)]).status_code, 409)
        self.assertEqual(self.place([(p, 1)], shipping_address={**ADDRESS, "country": "US", "postal_code": ""}).status_code, 422)
        self.assertEqual(self.place([(p, 1)], email="not-an-email").status_code, 422)
        self.assertEqual(self.stock_of(p), 2)  # nothing was taken by any of the refused orders
        ok = self.place([(p, 1)], expected_total="46.95")
        self.assertEqual(ok.status_code, 201, ok.text)

    def test_checkout_can_be_closed(self):
        p = self.product("40.00")
        self.assertEqual(self.client.patch(f"{self.api}/settings", json={"checkout_enabled": False}, headers=self.admin).status_code, 200)
        try:
            r = self.place([(p, 1)])
            self.assertEqual(r.status_code, 503)
            self.assertIn("isn't open", r.json()["detail"])
        finally:
            self.open_checkout()

    def test_last_item_cannot_be_sold_twice(self):
        p = self.product("40.00", stock=1)
        self.assertEqual(self.place([(p, 1)]).status_code, 201)
        second = self.place([(p, 1)])
        self.assertEqual(second.status_code, 409)
        self.assertEqual(self.stock_of(p), 0)
        detail = self.client.get(f"{self.api}/products/{p['slug']}").json()
        self.assertEqual(detail["stock_status"], "out_of_stock")

    def test_coupon_limits_hold_across_orders(self):
        p = self.product("40.00", stock=None)
        once = self.coupon(usage_limit=1)
        self.assertEqual(self.place([(p, 1)], coupon_code=once["code"]).status_code, 201)
        again = self.place([(p, 1)], coupon_code=once["code"])
        self.assertEqual(again.status_code, 422)
        self.assertIn("used up", again.json()["detail"])

        per_person = self.coupon(per_customer_limit=1)
        self.assertEqual(self.place([(p, 1)], coupon_code=per_person["code"], email="Same@Example.com").status_code, 201)
        self.assertEqual(self.place([(p, 1)], coupon_code=per_person["code"], email="same@example.com").status_code, 422)
        self.assertEqual(self.place([(p, 1)], coupon_code=per_person["code"], email="other@example.com").status_code, 201)

        first_only = self.coupon(first_order_only=True)
        newcomer = f"new-{uuid.uuid4().hex[:6]}@example.com"
        self.assertEqual(self.place([(p, 1)], email=newcomer).status_code, 201)  # now they have an order
        self.assertEqual(self.place([(p, 1)], coupon_code=first_only["code"], email=newcomer).status_code, 422)
        self.assertEqual(self.place([(p, 1)], coupon_code=first_only["code"], email=f"x-{uuid.uuid4().hex[:6]}@example.com").status_code, 201)

    def test_sale_price_is_charged(self):
        p = self.product("40.00", stock=None)
        sale = self.client.post(f"{self.api}/promotions/sales", json={"name": f"s{uuid.uuid4().hex[:5]}", "kind": "fixed", "value": "10", "scope": "products", "product_ids": [p["id"]]}, headers=self.admin).json()
        try:
            r = self.place([(p, 1)])
            self.assertAlmostEqual(r.json()["total"], 36.95, places=2)
            data = self.order(r.json()["number"], r.json()["access_token"]).json()
            self.assertEqual(data["sale_savings"], 10.0)
            self.assertEqual(data["items"][0]["list_price"], 40.0)
            self.assertEqual(data["items"][0]["unit_price"], 30.0)
        finally:
            self.client.delete(f"{self.api}/promotions/sales/{sale['id']}", headers=self.admin)

    def test_signed_in_customers_see_their_orders(self):
        email, auth = self.signup()
        _, other = self.signup()
        p = self.product("40.00", stock=None)
        placed = self.place([(p, 1)], headers=auth, email=email).json()
        mine = self.client.get(f"{self.api}/account/orders", headers=auth).json()
        self.assertEqual([o["number"] for o in mine["items"]], [placed["number"]])
        self.assertEqual(self.order(placed["number"], headers=auth).status_code, 200)  # no token needed for the owner
        self.assertEqual(self.order(placed["number"], headers=other).status_code, 404)
        self.assertEqual(self.client.get(f"{self.api}/account/orders", headers=other).json()["items"], [])
        self.assertEqual(self.client.get(f"{self.api}/account/orders").status_code, 401)

    # -- fulfilment, cancelling and refunds ---------------------------------------------------------
    def test_ship_and_deliver(self):
        p = self.product("40.00", stock=None)
        placed = self.paid_order([(p, 1)])
        n = placed["number"]
        base = f"{self.api}/orders/{n}"
        self.assertEqual(self.client.post(f"{base}/status", json={"status": "delivered"}, headers=self.admin).status_code, 409)
        self.assertEqual(self.client.post(f"{base}/status", json={"status": "processing"}, headers=self.admin).json()["status"], "processing")
        self.sent.clear()
        shipped = self.client.post(f"{base}/ship", json={"carrier": "USPS", "tracking_number": "9400 1111"}, headers=self.admin)
        self.assertEqual(shipped.status_code, 200, shipped.text)
        self.assertEqual(shipped.json()["status"], "shipped")
        self.assertEqual(shipped.json()["tracking_number"], "9400 1111")
        self.assertEqual([m.to for m in self.sent], ["buyer@example.com"])
        self.assertIn("9400 1111", self.sent[0].text)
        self.assertEqual(self.client.post(f"{base}/ship", json={}, headers=self.admin).status_code, 409)
        self.assertEqual(self.client.post(f"{base}/cancel", json={}, headers=self.admin).status_code, 409)  # shipped: refund instead
        self.assertEqual(self.client.post(f"{base}/status", json={"status": "delivered"}, headers=self.admin).json()["status"], "delivered")
        note = self.client.put(f"{base}/note", json={"internal_note": "Gift for a friend"}, headers=self.admin)
        self.assertEqual(note.json()["internal_note"], "Gift for a friend")
        customer_view = self.order(n, placed["access_token"]).json()
        self.assertIsNone(customer_view["internal_note"])
        self.assertEqual(customer_view["carrier"], "USPS")

    def test_cancel_returns_stock_coupon_and_money(self):
        p = self.product("40.00", stock=5)
        c = self.coupon(usage_limit=1)
        placed = self.paid_order([(p, 2)], coupon_code=c["code"])
        self.assertEqual(self.stock_of(p), 3)
        self.sent.clear()
        r = self.client.post(f"{self.api}/orders/{placed['number']}/cancel", json={"reason": "Customer asked"}, headers=self.admin)
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["status"], "cancelled")
        self.assertEqual(data["refunded_total"], placed["total"])
        self.assertEqual(len(data["refunds"]), 1)
        self.assertEqual(self.stock_of(p), 5)
        self.assertEqual(self.client.get(f"{self.api}/promotions/coupons/{c['id']}", headers=self.admin).json()["used_count"], 0)
        self.assertEqual([m.to for m in self.sent], ["buyer@example.com"])
        # The code can be used again, and the order can't be cancelled twice.
        self.assertEqual(self.place([(p, 1)], coupon_code=c["code"]).status_code, 201)
        self.assertEqual(self.client.post(f"{self.api}/orders/{placed['number']}/cancel", json={}, headers=self.admin).status_code, 409)

    def test_refunds(self):
        p = self.product("40.00", stock=4)
        placed = self.paid_order([(p, 1)])
        n, total = placed["number"], placed["total"]
        url = f"{self.api}/orders/{n}/refund"
        r = self.client.post(url, json={"amount": "5.00", "reason": "Small chip"}, headers=self.admin)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "paid")
        self.assertEqual(r.json()["refunded_total"], 5.0)
        self.assertEqual(self.client.post(url, json={"amount": str(total)}, headers=self.admin).status_code, 422)  # more than is left
        self.assertEqual(self.client.post(url, json={"amount": "1.00", "restock": True}, headers=self.admin).status_code, 422)  # partial + restock
        self.assertEqual(self.client.post(url, json={"amount": "0"}, headers=self.admin).status_code, 422)
        rest = round(total - 5.0, 2)
        done = self.client.post(url, json={"amount": str(rest)}, headers=self.admin)
        self.assertEqual(done.json()["status"], "refunded")
        self.assertEqual(done.json()["refunded_total"], total)
        self.assertEqual(len(done.json()["refunds"]), 2)
        self.assertEqual(self.client.post(url, json={"amount": "0.01"}, headers=self.admin).status_code, 422)

        whole = self.paid_order([(p, 2)])
        self.assertEqual(self.stock_of(p), 1)
        full = self.client.post(f"{self.api}/orders/{whole['number']}/refund", json={"amount": str(whole["total"]), "restock": True}, headers=self.admin)
        self.assertEqual(full.json()["status"], "refunded")
        self.assertEqual(self.stock_of(p), 3)

    def test_pay_by_invoice_order(self):
        self.use_settings(offline_enabled=True, offline_instructions="Zelle to pay@example.com")
        p = self.product("40.00", stock=None)
        r = self.place([(p, 1)], payment_provider="offline")
        self.assertEqual(r.status_code, 201, r.text)
        placed = r.json()
        self.assertEqual((placed["status"], placed["next"]), ("pending", "offline"))
        self.assertEqual(placed["instructions"], "Zelle to pay@example.com")
        mail = next(m for m in self.sent if m.to == "buyer@example.com")
        self.assertIn("Zelle to pay@example.com", mail.text)
        n = placed["number"]
        waiting = self.order(n, placed["access_token"]).json()
        self.assertEqual(waiting["payment_instructions"], "Zelle to pay@example.com")
        self.assertEqual(self.client.post(f"{self.api}/orders/{n}/ship", json={}, headers=self.admin).status_code, 409)  # not paid yet
        self.assertEqual(self.client.post(f"{self.api}/orders/{n}/refund", json={"amount": "1"}, headers=self.admin).status_code, 409)
        paid = self.client.post(f"{self.api}/orders/{n}/status", json={"status": "paid"}, headers=self.admin)
        self.assertEqual(paid.json()["status"], "paid")
        self.assertIsNone(paid.json()["payment_instructions"])  # nothing left to pay
        self.assertIn("@", " ".join(e["message"] for e in paid.json()["events"]))  # staff see who marked it paid
        public = self.order(n, placed["access_token"]).json()["events"]
        self.assertEqual([e["message"] for e in public], ["Order placed", "Payment received"])  # customers see neither names nor emails
        self.assertEqual(self.client.post(f"{self.api}/orders/{n}/status", json={"status": "paid"}, headers=self.admin).status_code, 409)
        listing = self.client.get(f"{self.api}/orders?q={n}&status=paid", headers=self.admin).json()
        self.assertEqual([o["number"] for o in listing["items"]], [n])
        self.assertEqual(listing["items"][0]["customer"], "Ana Ruiz")
        counts = self.client.get(f"{self.api}/orders/counts", headers=self.admin).json()["counts"]
        self.assertGreaterEqual(counts.get("paid", 0), 1)

    def test_unpaid_order_can_be_cancelled_without_a_refund(self):
        self.use_settings(offline_enabled=True)
        p = self.product("40.00", stock=3)
        placed = self.place([(p, 2)], payment_provider="offline").json()
        self.assertEqual(self.stock_of(p), 1)
        r = self.client.post(f"{self.api}/orders/{placed['number']}/cancel", json={}, headers=self.admin)
        self.assertEqual((r.json()["status"], r.json()["refunded_total"]), ("cancelled", 0.0))
        self.assertEqual(self.stock_of(p), 3)

    # -- card payments ----------------------------------------------------------------------
    def _stripe_on(self):
        from app.core.config import get_settings
        from app.payments import stripe

        settings = get_settings()
        saved = (settings.stripe_secret_key, settings.stripe_webhook_secret, stripe._request)
        settings.stripe_secret_key, settings.stripe_webhook_secret = "sk_test_x", "whsec_test_secret"
        calls = []

        def fake(method, path, form, secret, key):
            calls.append((method, path, dict(form), key))
            if path == "/checkout/sessions":
                return {"id": f"cs_test_{len(calls)}", "url": "https://checkout.stripe.test/pay"}
            if path == "/refunds":
                return {"id": f"re_test_{len(calls)}"}
            raise AssertionError(path)

        stripe._request = fake

        def restore():
            settings.stripe_secret_key, settings.stripe_webhook_secret, stripe._request = saved

        self.addCleanup(restore)
        return calls

    def _webhook(self, kind, order, *, session_id, amount, intent="pi_test_1", status="paid", secret="whsec_test_secret"):
        import time

        from app.payments import stripe

        event = {"type": kind, "data": {"object": {
            "id": session_id, "client_reference_id": order["number"], "payment_status": status,
            "amount_total": amount, "currency": "usd", "payment_intent": intent,
        }}}
        body = json.dumps(event).encode()
        header = stripe.sign(body, secret, int(time.time()))
        return self.client.post(f"{self.api}/payments/stripe/webhook", content=body, headers={"Stripe-Signature": header, "Content-Type": "application/json"})

    def test_card_payment_from_start_to_refund(self):
        calls = self._stripe_on()
        public = self.client.get(f"{self.api}/shop-config").json()
        self.assertIn("stripe", [o["id"] for o in public["payment_options"]])
        p = self.product("40.00", stock=3)
        r = self.place([(p, 1)], payment_provider="stripe", locale="es")
        self.assertEqual(r.status_code, 201, r.text)
        placed = r.json()
        self.assertEqual((placed["status"], placed["next"]), ("pending", "pay"))
        self.assertEqual(placed["payment_url"], "https://checkout.stripe.test/pay")
        self.assertEqual(self.stock_of(p), 2)  # held while the customer pays
        form = calls[0][2]
        self.assertEqual(form["line_items[0][price_data][unit_amount]"], "4695")
        self.assertIn(f"/es/order/{placed['number']}?token=", form["success_url"])
        self.assertEqual(self.sent, [])  # no confirmation until the money arrives

        n = placed["number"]
        sid = self.order(n, headers=self.admin).json()["payment_ref"]
        self.assertTrue(sid.startswith("cs_test_"))
        bad = self._webhook("checkout.session.completed", placed, session_id=sid, amount=4695, secret="whsec_wrong")
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.order(n, placed["access_token"]).json()["status"], "pending")

        short = self._webhook("checkout.session.completed", placed, session_id=sid, amount=100)
        self.assertEqual(short.status_code, 200)
        staff = self.order(n, headers=self.admin).json()
        self.assertEqual(staff["status"], "pending")  # wrong amount: not marked paid
        self.assertIn("payment_mismatch", [e["kind"] for e in staff["events"]])
        self.assertNotIn("payment_mismatch", [e["kind"] for e in self.order(n, placed["access_token"]).json()["events"]])

        self.sent.clear()
        ok = self._webhook("checkout.session.completed", placed, session_id=sid, amount=4695)
        self.assertEqual(ok.status_code, 200, ok.text)
        paid = self.order(n, headers=self.admin).json()
        self.assertEqual((paid["status"], paid["payment_ref"]), ("paid", "pi_test_1"))
        self.assertEqual(sorted(m.to for m in self.sent), sorted(["buyer@example.com", "shop@example.com"]))
        self.assertIn("Gracias", next(m for m in self.sent if m.to == "buyer@example.com").text)
        before = len(self.sent)
        self.assertEqual(self._webhook("checkout.session.completed", placed, session_id=sid, amount=4695).status_code, 200)
        self.assertEqual(len(self.sent), before)  # a repeated delivery does nothing

        refund = self.client.post(f"{self.api}/orders/{n}/refund", json={"amount": "10.00"}, headers=self.admin)
        self.assertEqual(refund.status_code, 200, refund.text)
        method, path, data, key = calls[-1]
        self.assertEqual((path, data["payment_intent"], data["amount"]), ("/refunds", "pi_test_1", "1000"))
        self.assertEqual(refund.json()["refunds"][0]["amount"], 10.0)

    def test_card_payment_window_closing_releases_the_order(self):
        self._stripe_on()
        p = self.product("40.00", stock=3)
        c = self.coupon(usage_limit=1)
        placed = self.place([(p, 2)], payment_provider="stripe", coupon_code=c["code"]).json()
        self.assertEqual(self.stock_of(p), 1)
        sid = self.order(placed["number"], headers=self.admin).json()["payment_ref"]
        r = self._webhook("checkout.session.expired", placed, session_id=sid, amount=0, status="unpaid")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.order(placed["number"], placed["access_token"]).json()["status"], "cancelled")
        self.assertEqual(self.stock_of(p), 3)
        self.assertEqual(self.client.get(f"{self.api}/promotions/coupons/{c['id']}", headers=self.admin).json()["used_count"], 0)
        # Money arriving after that is flagged for a person to look at, not silently accepted.
        self.sent.clear()
        late = self._webhook("checkout.session.completed", placed, session_id=sid, amount=round(placed["total"] * 100))
        self.assertEqual(late.status_code, 200)
        events = [e["kind"] for e in self.order(placed["number"], headers=self.admin).json()["events"]]
        self.assertIn("payment_after_cancel", events)
        self.assertEqual([m.to for m in self.sent], ["shop@example.com"])

    def test_card_payment_that_cannot_start_leaves_nothing_behind(self):
        from app.payments import stripe

        self._stripe_on()

        def failing(*args):
            raise stripe.StripeError("boom", 500)

        stripe._request = failing
        p = self.product("40.00", stock=3)
        r = self.place([(p, 1)], payment_provider="stripe")
        self.assertEqual(r.status_code, 503, r.text)
        self.assertEqual(self.stock_of(p), 3)

    def test_stale_card_orders_are_released(self):
        from app.core.database import SessionFactory
        from app.services.orders import OrderService

        self._stripe_on()
        p = self.product("40.00", stock=3)
        placed = self.place([(p, 1)], payment_provider="stripe").json()
        self.assertEqual(self.stock_of(p), 2)

        async def age_and_expire():
            async with SessionFactory() as s:
                order = await OrderService(s).repo.get_by_number(placed["number"])
                order.placed_at = datetime.now(timezone.utc) - timedelta(hours=2)
                await s.commit()
                return await OrderService(s).expire_unpaid_card_orders()

        self.assertGreaterEqual(asyncio.run(age_and_expire()), 1)
        self.assertEqual(self.order(placed["number"], placed["access_token"]).json()["status"], "cancelled")
        self.assertEqual(self.stock_of(p), 3)

    # -- coupons: generating, sending, welcome ---------------------------------------------------------
    def test_coupon_crud_and_validation(self):
        c = self.coupon(value="15", description="Spring")
        dup = self.client.post(f"{self.api}/promotions/coupons", json={"code": c["code"].lower(), "kind": "percent", "value": "5"}, headers=self.admin)
        self.assertEqual(dup.status_code, 409)
        bad = [
            {"code": "ab", "kind": "percent", "value": "5"},
            {"code": "GOODCODE", "kind": "percent", "value": "0"},
            {"code": "GOODCODE", "kind": "percent", "value": "101"},
            {"code": "GOODCODE", "kind": "fixed", "value": "0"},
            {"code": "has space", "kind": "percent", "value": "5"},
            {"code": "GOODCODE", "kind": "percent", "value": "5", "scope": "category"},
        ]
        for body in bad:
            self.assertEqual(self.client.post(f"{self.api}/promotions/coupons", json=body, headers=self.admin).status_code, 422, body)
        upd = self.client.put(f"{self.api}/promotions/coupons/{c['id']}", json={"kind": "fixed", "value": "3", "usage_limit": 10, "is_active": False}, headers=self.admin)
        self.assertEqual(upd.status_code, 200, upd.text)
        self.assertEqual((upd.json()["kind"], upd.json()["status"]), ("fixed", "paused"))
        found = self.client.get(f"{self.api}/promotions/coupons?q={c['code']}&status=paused", headers=self.admin).json()
        self.assertEqual([x["code"] for x in found["items"]], [c["code"]])
        self.assertEqual(self.client.get(f"{self.api}/promotions/coupons?q={c['code']}&status=active", headers=self.admin).json()["total"], 0)
        self.assertEqual(self.client.delete(f"{self.api}/promotions/coupons/{c['id']}", headers=self.admin).status_code, 204)

        used = self.coupon()
        p = self.product("40.00", stock=None)
        self.place([(p, 1)], coupon_code=used["code"])
        self.assertEqual(self.client.delete(f"{self.api}/promotions/coupons/{used['id']}", headers=self.admin).status_code, 409)
        low = self.client.put(f"{self.api}/promotions/coupons/{used['id']}", json={"kind": "percent", "value": "10", "usage_limit": 1, "is_active": True}, headers=self.admin)
        self.assertEqual(low.status_code, 200)
        detail = self.client.get(f"{self.api}/promotions/coupons/{used['id']}", headers=self.admin).json()
        self.assertEqual((detail["orders"], detail["status"]), (1, "used_up"))
        self.assertEqual(detail["discount_given"], 4.0)

    def test_generate_codes_in_bulk(self):
        campaign = f"Flyers {uuid.uuid4().hex[:6]}"
        body = {"campaign": campaign, "count": 25, "prefix": "fall", "kind": "percent", "value": "15", "expires_at": iso(30)}
        r = self.client.post(f"{self.api}/promotions/coupons/generate", json=body, headers=self.admin)
        self.assertEqual(r.status_code, 201, r.text)
        codes = r.json()["codes"]
        self.assertEqual(len(codes), 25)
        self.assertEqual(len(set(codes)), 25)
        self.assertTrue(all(c.startswith("FALL-") for c in codes))
        self.assertEqual(self.client.post(f"{self.api}/promotions/coupons/generate", json=body, headers=self.admin).status_code, 409)
        self.assertEqual(self.client.post(f"{self.api}/promotions/coupons/generate", json={**body, "campaign": "x", "count": 501}, headers=self.admin).status_code, 422)
        listed = self.client.get(f"{self.api}/promotions/coupons?campaign={campaign}&page_size=100", headers=self.admin).json()
        self.assertEqual(listed["total"], 25)
        self.assertEqual({c["usage_limit"] for c in listed["items"]}, {1})
        csv_text = self.client.get(f"{self.api}/promotions/campaigns/{campaign}/codes.csv", headers=self.admin)
        self.assertEqual(csv_text.status_code, 200)
        self.assertIn(codes[0], csv_text.text)
        stats = {c["campaign"]: c for c in self.client.get(f"{self.api}/promotions/campaigns", headers=self.admin).json()}
        self.assertEqual((stats[campaign]["codes"], stats[campaign]["used"]), (25, 0))
        # One of the codes works, once.
        p = self.product("40.00", stock=None)
        self.assertEqual(self.place([(p, 1)], coupon_code=codes[0]).status_code, 201)
        self.assertEqual(self.place([(p, 1)], coupon_code=codes[0]).status_code, 422)

    def test_personal_coupon_is_emailed_and_only_works_for_that_person(self):
        target = f"ana-{uuid.uuid4().hex[:6]}@example.com"
        r = self.client.post(f"{self.api}/promotions/coupons/send", json={"email": target, "kind": "percent", "value": "20", "locale": "nl", "message": "Bedankt!"}, headers=self.admin)
        self.assertEqual(r.status_code, 201, r.text)
        coupon = r.json()
        self.assertEqual((coupon["source"], coupon["email"], coupon["usage_limit"]), ("personal", target, 1))
        mail = self.sent[-1]
        self.assertEqual(mail.to, target)
        self.assertIn(coupon["code"], mail.text)
        self.assertIn("korting", mail.text)
        p = self.product("40.00", stock=None)
        stranger = self.quote([(p, 1)], coupon_code=coupon["code"], email="stranger@example.com")
        self.assertEqual(stranger["coupon_problem"]["code"], "invalid")  # same answer as an unknown code
        anonymous = self.quote([(p, 1)], coupon_code=coupon["code"])
        self.assertEqual(anonymous["coupon_problem"]["code"], "needs_email")
        mine = self.quote([(p, 1)], coupon_code=coupon["code"], email=target.upper())
        self.assertEqual(mine["coupon"]["discount"], 8.0)
        self.assertEqual(self.place([(p, 1)], coupon_code=coupon["code"], email="stranger@example.com").status_code, 422)
        self.assertEqual(self.place([(p, 1)], coupon_code=coupon["code"], email=target).status_code, 201)

    def test_welcome_code_for_new_subscribers(self):
        email = f"new-{uuid.uuid4().hex[:6]}@example.com"
        r = self.client.post(f"{self.api}/newsletter", json={"email": email, "locale": "es"})
        self.assertEqual(r.status_code, 202, r.text)
        self.assertTrue(r.json()["welcome_sent"])
        mail = next(m for m in self.sent if m.to == email)
        code = next(w for w in mail.text.split() if w.startswith("WELCOME-"))
        self.assertIn("descuento", mail.text)
        # Signing up again doesn't make a second code.
        again = self.client.post(f"{self.api}/newsletter", json={"email": email})
        self.assertFalse(again.json()["welcome_sent"])
        p = self.product("40.00", stock=None)
        q = self.quote([(p, 1)], coupon_code=code, email=email)
        self.assertEqual(q["coupon"]["discount"], 4.0)
        found = self.client.get(f"{self.api}/promotions/coupons?source=welcome&q={email}", headers=self.admin).json()
        self.assertEqual(found["total"], 1)
        self.assertEqual(found["items"][0]["issued_to"], email)
        # Switched off: no code.
        self.client.patch(f"{self.api}/settings", json={"welcome_enabled": False}, headers=self.admin)
        try:
            off = self.client.post(f"{self.api}/newsletter", json={"email": f"x-{uuid.uuid4().hex[:6]}@example.com"})
            self.assertFalse(off.json()["welcome_sent"])
        finally:
            self.client.patch(f"{self.api}/settings", json={"welcome_enabled": True}, headers=self.admin)

    def test_welcome_code_is_not_offered_to_existing_customers(self):
        p = self.product("40.00", stock=None)
        buyer = f"buyer-{uuid.uuid4().hex[:6]}@example.com"
        self.assertEqual(self.place([(p, 1)], email=buyer).status_code, 201)
        r = self.client.post(f"{self.api}/newsletter", json={"email": buyer})
        self.assertEqual(r.status_code, 202)
        self.assertFalse(r.json()["welcome_sent"])

    # -- the inbox -------------------------------------------------------------------------------
    def test_contact_inbox(self):
        subject = f"Question {uuid.uuid4().hex[:6]}"
        r = self.client.post(f"{self.api}/contact", json={"name": "Ana", "email": "ana@example.com", "subject": subject, "message": "Do you ship the keepsake set to Canada?"})
        self.assertEqual(r.status_code, 202, r.text)
        found = self.client.get(f"{self.api}/messages?q={subject}", headers=self.admin).json()
        self.assertEqual(found["total"], 1)
        msg = found["items"][0]
        self.assertEqual(msg["status"], "new")
        done = self.client.patch(f"{self.api}/messages/{msg['id']}", json={"status": "answered", "admin_note": "Replied by email"}, headers=self.admin)
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual((done.json()["status"], done.json()["admin_note"]), ("answered", "Replied by email"))
        self.assertIsNotNone(done.json()["handled_at"])
        self.assertEqual(self.client.get(f"{self.api}/messages?status=new&q={subject}", headers=self.admin).json()["total"], 0)
        counts = self.client.get(f"{self.api}/messages/counts", headers=self.admin).json()["counts"]
        self.assertEqual(set(counts), {"new", "answered", "archived"})
        self.assertEqual(self.client.patch(f"{self.api}/messages/{msg['id']}", json={"status": "bogus"}, headers=self.admin).status_code, 422)


if __name__ == "__main__":
    unittest.main()
