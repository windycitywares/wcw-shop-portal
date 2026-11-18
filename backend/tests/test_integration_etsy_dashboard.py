"""The Etsy dashboard endpoint against PostgreSQL: filters, KPIs with the previous period, who may see it."""

import unittest
from datetime import datetime, timedelta, timezone

from tests.integration_support import RUN, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class EtsyDashboardTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()
        key = f"{self.w.sfx}-{self._testMethodName}"  # each test its own orders: the world is shared
        self.sup = f"Dash {key}"
        base = 6_000_000 + abs(hash(key)) % 3_000_000
        when = datetime.now(timezone.utc) - timedelta(days=1)
        for i, cost in enumerate(("10.00", None)):
            oid = self.w.sql(
                "INSERT INTO etsy_orders (etsy_receipt_id, status, ordered_at, paid_at, items_total, shipping_charged, discounts, "
                "tax, grand_total, purchase_cost, supplier, ship_address) VALUES (:r, 'new', :t, :t, 30, 5, 0, 2, 37, :c, :s, "
                "'{\"state\": \"IL\", \"country_iso\": \"US\"}') RETURNING id",
                r=base + i, t=when, c=cost, s=self.sup)[0]["id"]
            self.w.sql("INSERT INTO etsy_order_items (order_id, etsy_transaction_id, etsy_listing_id, title, quantity, unit_price) "
                       "VALUES (:o, :t, :l, 'Dash mug', 2, 15)", o=oid, t=(base + i) * 10, l=base)
        self.listing = base

    def test_dashboard_for_one_supplier(self):
        w = self.w
        r = w.get("/admin/etsy/dashboard", w.publisher, supplier=self.sup.lower())
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual(d["totals"]["orders"], 2)
        self.assertEqual(d["totals"]["units"], 4)
        self.assertEqual(d["totals"]["revenue"], 70.0)
        self.assertEqual(d["totals"]["profit"], 25.0)
        self.assertEqual(d["totals"]["cost_coverage"], 0.5)
        self.assertEqual([k["key"] for k in d["kpis"]], ["orders", "items", "revenue", "profit", "margin", "days_to_ship"])
        self.assertEqual(d["range"]["granularity"], "day")
        self.assertEqual(sum(s["orders"] for s in d["series"]), 2)
        self.assertIn(self.sup, d["options"]["suppliers"])
        self.assertIn(self.listing, [p["listing_id"] for p in d["options"]["products"]])

    def test_product_filter_and_empty_range(self):
        w = self.w
        self.assertEqual(w.get("/admin/etsy/dashboard", w.publisher, listing_id=self.listing).json()["totals"]["orders"], 2)
        self.assertEqual(w.get("/admin/etsy/dashboard", w.publisher, supplier=self.sup, listing_id=1).json()["totals"]["orders"], 0)
        old = w.get("/admin/etsy/dashboard", w.publisher, supplier=self.sup, start="2020-01-01", end="2020-01-31").json()
        self.assertEqual(old["totals"]["orders"], 0)

    def test_team_only(self):
        _, shopper = self.w.register("dash-shopper")
        self.assertEqual(self.w.get("/admin/etsy/dashboard", shopper).status_code, 403)


if __name__ == "__main__":
    unittest.main()
