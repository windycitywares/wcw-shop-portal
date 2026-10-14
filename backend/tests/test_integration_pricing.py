"""Batch 2 API tests against PostgreSQL: store settings, cart quotes, sales, coupons and automatic cart offers."""

import csv
import io
import unittest

from tests.integration_support import RUN, item, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class SchemaTests(unittest.TestCase):
    def test_models_match_the_migrated_database(self):
        async def check(session):
            from sqlalchemy import text

            import app.models  # noqa: F401  (registers every table)
            from app.models.base import Base

            rows = (await session.execute(text(
                "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = current_schema()"
            ))).all()
            have: dict[str, set[str]] = {}
            for table, column in rows:
                have.setdefault(table, set()).add(column)
            return [f"{name}.{col.name}" for name, table in Base.metadata.tables.items() for col in table.columns
                    if col.name not in have.get(name, set())]

        self.assertEqual(world().db(check), [])

    def test_analytics_tables_hold_no_personal_columns(self):
        cols = world().sql("SELECT column_name FROM information_schema.columns WHERE table_name IN ('analytics_sessions', 'analytics_events')")
        names = {r["column_name"] for r in cols}
        self.assertTrue(names)
        self.assertFalse(names & {"ip", "ip_address", "user_agent", "email"}, names)


@skip_unless_db
class QuoteTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def test_shop_config(self):
        r = self.w.get("/shop/config")
        self.assertEqual(r.status_code, 200)
        cfg = r.json()
        self.assertEqual(cfg["currency"], "USD")
        self.assertEqual(cfg["flat_shipping_rate"], 8.95)
        self.assertEqual(cfg["free_shipping_threshold"], 100.0)
        self.assertIn("manual", cfg["payment_methods"])
        self.assertIn("max-age", r.headers["cache-control"])
        self.assertEqual(self.w.get("/shop/config", lang="es").status_code, 200)
        self.assertEqual(self.w.get("/shop/config", lang="fr").status_code, 422)

    def test_flat_and_free_shipping(self):
        p = self.w.product("40.00")
        q = self.w.quote([item(p)])
        self.assertEqual(q["subtotal"], 40.0)
        self.assertEqual(q["shipping"]["amount"], 8.95)
        self.assertFalse(q["shipping"]["free"])
        self.assertEqual(q["shipping"]["remaining_for_free"], 60.0)
        self.assertEqual(q["total"], 48.95)
        self.assertFalse(q["blocking"])
        q = self.w.quote([item(p, 3)])
        self.assertTrue(q["shipping"]["free"])
        self.assertEqual(q["total"], 120.0)
        self.assertEqual(q["item_count"], 3)

    def test_unavailable_items_block_checkout(self):
        sold_out = self.w.product(out_of_stock=True)
        q = self.w.quote([item(sold_out)])
        self.assertTrue(q["blocking"])
        self.assertEqual(q["lines"], [])
        self.assertEqual(len(q["messages"]), 1)
        last_two = self.w.product(stock=2)
        q = self.w.quote([item(last_two, 5)])
        self.assertTrue(q["blocking"])
        self.assertEqual(q["lines"][0]["quantity"], 2)  # reduced to what's on the shelf
        q = self.w.quote([{"product_id": 987654321, "quantity": 1}])
        self.assertTrue(q["blocking"])

    def test_wrong_codes_are_slowed_down(self):
        p = self.w.product()
        for _ in range(10):
            r = self.w.post("/cart/quote", {"items": [item(p)], "coupon": "NOPE-NOT-REAL"})
            self.assertEqual(r.status_code, 200)
            self.assertFalse(r.json()["coupon"]["valid"])
            self.assertEqual(r.json()["discount_total"], 0.0)
        self.assertEqual(self.w.post("/cart/quote", {"items": [item(p)], "coupon": "ANOTHER-GUESS"}).status_code, 429)
        self.assertEqual(self.w.post("/cart/quote", {"items": [item(p)]}).status_code, 200)  # plain quotes still work


@skip_unless_db
class PromotionTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def test_staff_only(self):
        w = self.w
        for path in ("/admin/promotions/sales", "/admin/promotions/coupons", "/admin/promotions/offers", "/admin/settings", "/admin/audit"):
            self.assertEqual(w.get(path).status_code, 401, path)
            self.assertEqual(w.get(path, w.customer).status_code, 403, path)
            self.assertEqual(w.get(path, w.publisher).status_code, 403, path)
            self.assertEqual(w.get(path, w.admin).status_code, 200, path)

    def test_sale_lowers_the_price_until_paused(self):
        w = self.w
        p = w.product("40.00")
        r = w.post("/admin/promotions/sales", {"name": "Fall sale", "badge": "Fall", "kind": "percent", "value": 25,
                                               "scope": "products", "product_ids": [p["id"]]}, w.admin)
        self.assertEqual(r.status_code, 201, r.text)
        sale = r.json()
        try:
            self.assertEqual(sale["status"], "active")
            self.assertEqual(sale["affected_products"], 1)
            line = w.quote([item(p)])["lines"][0]
            self.assertEqual((line["unit_price"], line["list_price"], line["on_sale"]), (30.0, 40.0, True))
            self.assertEqual(w.quote([item(p)])["sale_savings"], 10.0)
            detail = w.get(f"/products/{p['slug']}").json()
            self.assertEqual(detail["sale_price"], 30.0)
            self.assertIn("sale", detail["badges"])
            listed = w.get("/products", q=w.sfx, on_sale="true").json()["items"]
            self.assertIn(p["id"], [x["id"] for x in listed])
            r = w.post(f"/admin/promotions/sales/{sale['id']}/active", {"is_active": False}, w.admin)
            self.assertEqual(r.json()["status"], "paused")
            self.assertEqual(w.quote([item(p)])["lines"][0]["unit_price"], 40.0)
        finally:
            self.assertEqual(w.delete(f"/admin/promotions/sales/{sale['id']}", w.admin).status_code, 204)
        bad = {"name": "Too much", "kind": "percent", "value": 100, "scope": "all"}
        self.assertEqual(w.post("/admin/promotions/sales", bad, w.admin).status_code, 422)
        backwards = {"name": "Backwards", "value": 10, "starts_at": "2030-01-02T00:00:00Z", "ends_at": "2030-01-01T00:00:00Z"}
        self.assertEqual(w.post("/admin/promotions/sales", backwards, w.admin).status_code, 422)

    def test_coupon_codes(self):
        w = self.w
        p = w.product("40.00")
        code = f"SAVE{w.sfx}".upper()
        r = w.post("/admin/promotions/coupons", {"code": code.lower(), "kind": "percent", "value": 10, "usage_limit": 5}, w.admin)
        self.assertEqual(r.status_code, 201, r.text)
        coupon = r.json()
        self.assertEqual(coupon["code"], code)  # normalised
        q = w.quote([item(p)], coupon=code.lower())
        self.assertTrue(q["coupon"]["applied"])
        self.assertEqual(q["discount_total"], 4.0)
        self.assertEqual(q["total"], 44.95)
        self.assertEqual(w.post("/admin/promotions/coupons", {"code": code, "value": 5}, w.admin).status_code, 409)
        self.assertEqual(w.post("/admin/promotions/coupons", {"code": "X" + code, "value": 150}, w.admin).status_code, 422)

        free = w.post("/admin/promotions/coupons", {"code": f"SHIP{w.sfx}", "kind": "free_shipping"}, w.admin).json()
        q = w.quote([item(p)], coupon=free["code"])
        self.assertEqual(q["shipping"]["amount"], 0.0)
        self.assertEqual(q["total"], 40.0)

        big = w.post("/admin/promotions/coupons", {"code": f"BIG{w.sfx}", "value": 20, "min_subtotal": 100}, w.admin).json()
        self.assertFalse(w.quote([item(p)], coupon=big["code"])["coupon"]["applied"])

        self.assertEqual(w.delete(f"/admin/promotions/coupons/{coupon['id']}", w.admin).json(), {"result": "deleted"})
        self.assertFalse(w.quote([item(p)], coupon=code)["coupon"]["valid"])

    def test_bulk_and_personal_codes(self):
        w = self.w
        p = w.product("40.00")
        campaign = f"ct-{w.sfx}"
        r = w.post("/admin/promotions/coupons/bulk", {"count": 5, "prefix": "t-st", "length": 8, "campaign": campaign,
                                                     "kind": "percent", "value": 15, "usage_limit": 1}, w.admin)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["created"], 5)
        self.assertTrue(all(c.startswith("TST") and len(c) == 11 for c in r.json()["sample"]))
        listed = w.get("/admin/promotions/coupons", w.admin, campaign=campaign).json()
        self.assertEqual(listed["total"], 5)
        self.assertIn(campaign, listed["campaigns"])
        self.assertTrue(all(c["source"] == "bulk" and c["status"] == "active" for c in listed["items"]))
        exported = w.get("/admin/promotions/coupons/export.csv", w.admin, campaign=campaign)
        self.assertTrue(exported.headers["content-type"].startswith("text/csv"))
        rows = list(csv.reader(io.StringIO(exported.text)))
        self.assertEqual(rows[0][0], "Code")
        self.assertEqual(len(rows), 6)

        mine, theirs = w.email("vip"), w.email("other")
        r = w.post("/admin/promotions/coupons/bulk", {"emails": [mine], "campaign": campaign + "-vip", "kind": "percent", "value": 15}, w.admin)
        code = r.json()["sample"][0]
        q = w.quote([item(p)], coupon=code, email=theirs)
        self.assertEqual((q["coupon"]["valid"], q["coupon"]["reason"]), (False, "wrong_customer"))
        self.assertEqual(w.quote([item(p)], coupon=code, email=mine)["discount_total"], 6.0)
        self.assertEqual(w.post("/admin/promotions/coupons/bulk", {"count": 2, "value": 10}, w.admin).status_code, 422)  # campaign required

    def test_cart_offer(self):
        w = self.w
        p = w.product("40.00")
        r = w.post("/admin/promotions/offers", {"name": "Spend $60, save 10%", "kind": "spend_percent", "threshold_amount": 60, "value": 10}, w.admin)
        self.assertEqual(r.status_code, 201, r.text)
        rule = r.json()
        try:
            q = w.quote([item(p, 2)])
            self.assertEqual(q["discount_total"], 8.0)
            self.assertEqual(q["discounts"][0]["type"], "rule")
            q = w.quote([item(p)])
            self.assertEqual(q["discount_total"], 0.0)
            self.assertEqual(q["rewards"][0]["remaining_amount"], 20.0)  # "spend $20 more"
        finally:
            self.assertEqual(w.delete(f"/admin/promotions/offers/{rule['id']}", w.admin).status_code, 204)
        self.assertEqual(w.quote([item(p, 2)])["discount_total"], 0.0)
        self.assertEqual(w.post("/admin/promotions/offers", {"name": "No threshold", "kind": "spend_percent", "value": 10}, w.admin).status_code, 422)


@skip_unless_db
class SettingsTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def test_shipping_tax_and_banner(self):
        w = self.w
        p = w.product("40.00")
        view = w.get("/admin/settings", w.admin).json()
        self.assertEqual(view["settings"]["shipping"]["flat_rate"], 8.95)
        self.assertIn("stripe_configured", view["status"])
        try:
            r = w.put("/admin/settings/shipping", {"flat_rate": 5, "free_threshold": 60}, w.admin)
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(w.quote([item(p)])["shipping"]["amount"], 5.0)
            self.assertTrue(w.quote([item(p, 2)])["shipping"]["free"])
            self.assertEqual(w.get("/shop/config").json()["free_shipping_threshold"], 60.0)

            w.put("/admin/settings/tax", {"enabled": True, "rate_percent": 10, "regions": ["il"]}, w.admin)
            q = w.quote([item(p)], destination={"country": "US", "region": "IL"})
            self.assertEqual((q["tax"]["amount"], q["total"]), (4.0, 49.0))
            self.assertIsNone(w.quote([item(p)], destination={"country": "US", "region": "TX"})["tax"])
            self.assertTrue(w.quote([item(p)])["tax_pending"])

            w.put("/admin/settings/general", {"announcement_enabled": True, "announcement": {"en": "Free engraving this week"}}, w.admin)
            self.assertEqual(w.get("/shop/config").json()["announcement"], "Free engraving this week")
        finally:
            w.put("/admin/settings/shipping", {"flat_rate": 8.95, "free_threshold": 100}, w.admin)
            w.put("/admin/settings/tax", {"enabled": False, "rate_percent": 0}, w.admin)
            w.put("/admin/settings/general", {"announcement_enabled": False, "announcement": {}}, w.admin)
        self.assertEqual(w.quote([item(p)])["shipping"]["amount"], 8.95)
        self.assertEqual(w.put("/admin/settings/nope", {}, w.admin).status_code, 404)
        self.assertEqual(w.put("/admin/settings/tax", {"made_up": 1}, w.admin).status_code, 422)
        self.assertEqual(w.put("/admin/settings/tax", {"rate_percent": 99}, w.admin).status_code, 422)
        self.assertEqual(w.put("/admin/settings/tax", {"enabled": True}, w.customer).status_code, 403)
        audit = w.get("/admin/audit", w.admin, action="settings.update").json()
        self.assertGreaterEqual(audit["total"], 3)
        self.assertEqual(audit["items"][0]["actor_email"], w.admin_email)

    def test_cost_price_is_staff_only(self):
        w = self.w
        p = w.product("40.00", cost="12.50")
        self.assertNotIn("cost_price", w.get(f"/products/{p['slug']}", w.admin).json())
        self.assertEqual(w.get(f"/products/by-id/{p['id']}", w.admin).json()["cost_price"], 12.5)


if __name__ == "__main__":
    unittest.main()
