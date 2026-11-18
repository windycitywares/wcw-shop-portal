"""Etsy orders for the team against PostgreSQL: list filters, costs and tracking entry, status changes, history, profit,
and who may do it."""

import unittest
from datetime import datetime, timedelta, timezone

from tests.integration_support import RUN, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class EtsyOrderAdminTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()
        self.rid = 8_000_000 + abs(hash(self.w.sfx + self._testMethodName)) % 1_000_000
        paid = datetime.now(timezone.utc) - timedelta(days=2)
        self.id = self.w.sql(
            "INSERT INTO etsy_orders (etsy_receipt_id, status, ordered_at, paid_at, buyer_name, items_total, shipping_charged, "
            "discounts, tax, grand_total) VALUES (:r, 'new', :p, :p, :b, 30, 5, 0, 2, 37) RETURNING id",
            r=self.rid, p=paid, b=f"Buyer {self.w.sfx}")[0]["id"]
        self.w.sql("INSERT INTO etsy_order_items (order_id, etsy_transaction_id, etsy_listing_id, title, sku, quantity, unit_price) "
                   "VALUES (:o, :t, 4242, 'Blue mug', 'MUG-B', 2, 15)", o=self.id, t=self.rid * 10)

    def url(self, tail=""):
        return f"/admin/etsy/orders/{self.id}{tail}"

    def test_only_team_members(self):
        w = self.w
        _, shopper = w.register("etsy-shopper")
        self.assertEqual(w.get("/admin/etsy/orders", shopper).status_code, 403)
        self.assertEqual(w.get("/admin/etsy/orders").status_code, 401)
        self.assertEqual(w.get("/admin/etsy/orders", w.publisher).status_code, 200)

    def test_needs_attention_then_costs_clear_it(self):
        w = self.w
        listed = w.get("/admin/etsy/orders", w.publisher, q=str(self.rid)).json()
        self.assertEqual(listed["total"], 1)
        row = listed["items"][0]
        self.assertIn("not_purchased", row["attention"])
        self.assertIn("cost_missing", row["attention"])
        self.assertIn(self.id, [r["id"] for r in w.get("/admin/etsy/orders", w.publisher, attention="true", page_size=100, q=str(self.rid)).json()["items"]])

        r = w.client.patch(w.url(self.url()), json={"purchase_cost": "12.00", "supplier": "Acme", "supplier_order_number": "AC-1"},
                           headers=w.publisher)
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual(d["profit"]["revenue"], "35.00")
        self.assertEqual(d["profit"]["net_profit"], "23.00")
        self.assertEqual(d["profit"]["missing"], ["shipping_cost", "etsy_fees"])
        r = w.post(self.url("/status"), {"status": "purchased", "note": "ordered from Acme"}, w.publisher)
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual(d["status"], "purchased")
        self.assertIsNotNone(d["purchased_at"])
        self.assertEqual(d["attention"], [])
        self.assertEqual(w.get("/admin/etsy/orders", w.publisher, attention="true", q=str(self.rid)).json()["total"], 0)

        kinds = [(h["kind"], h["source"], h["actor_name"]) for h in d["history"]]
        self.assertIn(("costs", "team", "Pat Publisher"), kinds)
        self.assertIn(("status", "team", "Pat Publisher"), kinds)
        self.assertIn("ordered from Acme", d["history"][0]["message"])
        audit = w.sql("SELECT action FROM audit_log WHERE entity_type='etsy_order' AND entity_id=:i", i=str(self.id))
        self.assertEqual({a["action"] for a in audit}, {"etsy.order.update", "etsy.order.status"})

    def test_etsy_fields_cannot_be_edited(self):
        r = self.w.client.patch(self.w.url(self.url()), json={"items_total": "1.00", "buyer_name": "X"}, headers=self.w.publisher)
        self.assertEqual(r.status_code, 200)  # unknown fields are ignored by the schema…
        d = self.w.get(self.url(), self.w.publisher).json()
        self.assertEqual(d["items_total"], "30.00")  # …and nothing changed
        self.assertEqual(d["history"], [])

    def test_negative_profit_and_shipping_time(self):
        w = self.w
        w.client.patch(w.url(self.url()), json={"purchase_cost": "40.00", "shipping_cost": "6.00"}, headers=w.publisher)
        d = w.post(self.url("/status"), {"status": "shipped"}, w.publisher).json()
        self.assertIn("negative_profit", d["attention"])
        self.assertEqual(d["profit"]["net_profit"], "-11.00")
        self.assertEqual(d["profit"]["days_to_ship"], 2)

    def test_bad_status(self):
        w = self.w
        self.assertEqual(w.post(self.url("/status"), {"status": "nope"}, w.publisher).status_code, 422)
        self.assertEqual(w.post(self.url("/status"), {"status": "new"}, w.publisher).status_code, 422)

    def test_filters(self):
        w = self.w
        w.client.patch(w.url(self.url()), json={"supplier": f"Sup {self.w.sfx}"}, headers=w.publisher)
        self.assertEqual(w.get("/admin/etsy/orders", w.publisher, supplier=f"sup {self.w.sfx}").json()["total"], 1)
        self.assertGreaterEqual(w.get("/admin/etsy/orders", w.publisher, q="MUG-B").json()["total"], 1)
        self.assertGreaterEqual(w.get("/admin/etsy/orders", w.publisher, listing_id=4242).json()["total"], 1)
        self.assertEqual(w.get("/admin/etsy/orders", w.publisher, q=str(self.rid), status="shipped").json()["total"], 0)
        self.assertEqual(w.get("/admin/etsy/orders", w.publisher, q=str(self.rid), status="open").json()["total"], 1)
        future = (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat()
        self.assertEqual(w.get("/admin/etsy/orders", w.publisher, q=str(self.rid), date_from=future).json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
