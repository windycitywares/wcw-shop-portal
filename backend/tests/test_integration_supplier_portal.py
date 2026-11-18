"""Supplier logins against PostgreSQL: an admin creates one; the supplier sees only their own orders on the shops they're
allowed, ships them, sees what they're owed — and nothing of the rest of the admin."""

import unittest
from datetime import datetime, timedelta, timezone

from tests.integration_support import RUN, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class SupplierPortalTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        w = self.w = world()
        key = f"{w.sfx}-{self._testMethodName}"
        self.mine, self.other = f"Acme {key}", f"Other {key}"
        base = 4_000_000 + abs(hash(key)) % 1_000_000
        when = datetime.now(timezone.utc) - timedelta(days=2)
        self.ids = []
        for i, (sup, cost) in enumerate(((self.mine, "12.00"), (self.mine.upper(), None), (self.other, "5.00"))):
            self.ids.append(w.sql(
                "INSERT INTO etsy_orders (etsy_receipt_id, status, ordered_at, paid_at, buyer_name, buyer_email, items_total, "
                "shipping_charged, discounts, tax, grand_total, purchase_cost, shipping_cost, supplier, ship_address, notes) "
                "VALUES (:r, 'new', :t, :t, 'Sam Buyer', 'sam@example.com', 50, 0, 0, 3, 53, :c, 3, :s, "
                "'{\"city\": \"Chicago\"}', 'secret team note') RETURNING id",
                r=base + i, t=when, c=cost, s=sup)[0]["id"])
        # Etsy connected, so the supplier's allowed shop is live.
        w.put("/admin/etsy/credentials", {"client_id": "k", "client_secret": "s"}, w.admin)
        w.sql("UPDATE etsy_connection SET access_token='x', refresh_token='y', etsy_shop_id=5, token_expires_at=now()+interval '1 day'")
        self.email = f"supplier-{key}@example.com".lower()
        r = w.post("/admin/supplier-logins", {"email": self.email, "password": "supplier-pass-1", "full_name": "Sue Supplier",
                                              "supplier_name": f"  {self.mine} ", "channels": ["etsy"]}, w.admin)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["role"], "supplier")
        self.assertEqual(r.json()["supplier_name"], self.mine)
        self.login_id = r.json()["id"]
        self.sup = w.login(self.email, "supplier-pass-1")

    def test_only_admins_manage_supplier_logins(self):
        w = self.w
        body = {"email": "x@example.com", "password": "12345678", "supplier_name": "X", "channels": ["etsy"]}
        self.assertEqual(w.post("/admin/supplier-logins", body, w.publisher).status_code, 403)
        self.assertEqual(w.post("/admin/supplier-logins", {**body, "channels": ["ebay"]}, w.admin).status_code, 422)
        self.assertEqual(w.client.patch(w.url(f"/admin/supplier-logins/{self.login_id}"), json={"channels": []}, headers=w.admin).status_code, 422)

    def test_sees_only_own_orders_and_no_money_of_the_shop(self):
        w = self.w
        me = w.get("/supplier/me", self.sup).json()
        self.assertEqual(me["channels"], ["etsy"])
        listed = w.get("/supplier/etsy/orders", self.sup, view="all").json()
        self.assertEqual(sorted(o["id"] for o in listed["items"]), sorted(self.ids[:2]))  # name matched case-blind
        d = w.get(f"/supplier/etsy/orders/{self.ids[0]}", self.sup).json()
        self.assertEqual(d["owed"], "15.00")
        self.assertEqual(d["ship_address"], {"city": "Chicago"})
        for hidden in ("items_total", "grand_total", "profit", "buyer_email", "notes", "purchase_cost", "supplier"):
            self.assertNotIn(hidden, d)
        self.assertNotIn("sam@example.com", w.get(f"/supplier/etsy/orders/{self.ids[0]}", self.sup).text)
        # Someone else's order looks like a missing one.
        self.assertEqual(w.get(f"/supplier/etsy/orders/{self.ids[2]}", self.sup).status_code, 404)
        # And the rest of the admin is closed.
        for path in ("/admin/etsy/orders", "/admin/etsy/dashboard", "/admin/etsy/supplier-payments/overview", "/admin/reports/overview"):
            self.assertEqual(w.get(path, self.sup).status_code, 403, path)

    def test_ships_an_order(self):
        w = self.w
        self.assertEqual(w.post(f"/supplier/etsy/orders/{self.ids[0]}/shipped", {"tracking_number": " "}, self.sup).status_code, 422)
        r = w.post(f"/supplier/etsy/orders/{self.ids[0]}/shipped", {"carrier": "USPS", "tracking_number": "9400123"}, self.sup)
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual((d["status"], d["tracking_number"], d["carrier"]), ("shipped", "9400123", "USPS"))
        self.assertTrue(any("Sue Supplier" == h["actor_name"] for h in d["history"]))
        team = w.get(f"/admin/etsy/orders/{self.ids[0]}", w.admin).json()
        self.assertEqual(team["status"], "shipped")
        self.assertEqual(w.post(f"/supplier/etsy/orders/{self.ids[0]}/shipped", {"tracking_number": "1"}, self.sup).status_code, 422)
        self.assertEqual(w.get("/supplier/etsy/orders", self.sup, view="to_ship").json()["counts"]["shipped"], 1)

    def test_payments_are_their_own(self):
        w = self.w
        p = w.get("/supplier/etsy/payments", self.sup, state="pending").json()
        self.assertEqual((p["pending_count"], p["pending_amount"]), (1, "15.00"))
        self.assertEqual([r["id"] for r in p["items"]], [self.ids[0]])
        x = w.get("/supplier/etsy/payments/export", self.sup, format="csv")
        self.assertEqual(x.status_code, 200)
        self.assertNotIn(self.other, x.content.decode("utf-8-sig"))

    def test_no_access_without_the_shop_or_when_disconnected(self):
        w = self.w
        w.sql("UPDATE etsy_connection SET access_token=NULL")
        self.assertEqual(w.get("/supplier/me", self.sup).json()["channels"], [])
        self.assertEqual(w.get("/supplier/etsy/orders", self.sup).status_code, 403)


if __name__ == "__main__":
    unittest.main()
