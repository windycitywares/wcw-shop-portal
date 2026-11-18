"""Order sync against PostgreSQL with Etsy replaced: paid orders arrive once, Etsy fields refresh, team fields survive,
status only moves forward, and every change is in the history."""

import unittest
from decimal import Decimal
from unittest import mock

from tests.integration_support import RUN, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


def money(cents):
    return {"amount": cents, "divisor": 100, "currency_code": "USD"}


def receipt(rid, listing_id, **over):
    base = {
        "receipt_id": rid, "status": "Paid", "is_paid": True, "is_shipped": False, "name": "Sam Buyer", "buyer_user_id": 42,
        "city": "Chicago", "country_iso": "US", "created_timestamp": 1760000000, "message_from_buyer": "Thanks!",
        "grandtotal": money(3300), "total_shipping_cost": money(500), "discount_amt": money(0), "total_tax_cost": money(300),
        "transactions": [{"transaction_id": rid * 10, "listing_id": listing_id, "title": "Mug", "quantity": 2,
                          "price": money(1250), "expected_ship_date": 1760400000}],
    }
    base.update(over)
    return base


@skip_unless_db
class EtsyOrderSyncTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()
        self.w.put("/admin/etsy/credentials", {"client_id": "k", "client_secret": "s"}, self.w.admin)
        self.w.sql("UPDATE etsy_connection SET access_token='x', refresh_token='y', etsy_shop_id=5, "
                   "token_expires_at=now()+interval '1 day'")
        self.base = 7_000_000 + abs(hash(self.w.sfx)) % 1_000_000

    def sync(self, receipts):
        from app.services.etsy_orders import EtsyOrderSync

        async def fake_get(path, **kw):
            return {"results": receipts if kw["params"]["offset"] == 0 else []}

        async def go(session):
            with mock.patch("app.services.etsy_client.get", fake_get), mock.patch("app.core.secretbox.unseal", lambda v: "tok"):
                return await EtsyOrderSync(session).run(force=True)

        return self.w.db(go)

    def order(self, rid):
        return self.w.sql("SELECT * FROM etsy_orders WHERE etsy_receipt_id = :r", r=rid)[0]

    def events(self, rid):
        return self.w.sql("SELECT e.* FROM etsy_order_events e JOIN etsy_orders o ON o.id = e.order_id "
                          "WHERE o.etsy_receipt_id = :r ORDER BY e.id", r=rid)

    def test_paid_order_arrives_once_with_prefilled_cost(self):
        rid, lid = self.base, self.base + 1
        self.w.sql("INSERT INTO etsy_listings (etsy_listing_id, title, internal_supplier, internal_purchase_cost) "
                   "VALUES (:l, 'Mug', 'Acme', 4.00)", l=lid)
        first = self.sync([receipt(rid, lid)])
        self.assertGreaterEqual(first["created"], 1)
        self.sync([receipt(rid, lid)])  # a second pass changes nothing
        o = self.order(rid)
        self.assertEqual(o["status"], "new")
        self.assertEqual(o["items_total"], Decimal("25.00"))
        self.assertEqual(o["purchase_cost"], Decimal("8.00"))  # 2 × 4.00
        self.assertTrue(o["costs_prefilled"])
        self.assertEqual(o["supplier"], "Acme")
        self.assertEqual(o["buyer_note"], "Thanks!")
        self.assertIsNone(o["buyer_email"])
        self.assertEqual(len(self.w.sql("SELECT 1 FROM etsy_order_items WHERE order_id = :i", i=o["id"])), 1)
        self.assertEqual([e["kind"] for e in self.events(rid)], ["created"])

    def test_unpaid_order_is_not_created(self):
        rid = self.base + 2
        self.sync([receipt(rid, None, status="Open", is_paid=False)])
        self.assertEqual(self.w.sql("SELECT 1 FROM etsy_orders WHERE etsy_receipt_id = :r", r=rid), [])

    def test_shipped_on_etsy_moves_forward_and_keeps_team_fields(self):
        rid = self.base + 3
        self.sync([receipt(rid, None)])
        self.w.sql("UPDATE etsy_orders SET status='purchased', purchase_cost=9.99, notes='bought from Acme' WHERE etsy_receipt_id=:r", r=rid)
        self.sync([receipt(rid, None, is_shipped=True, shipments=[{"tracking_code": "9400111", "carrier_name": "usps"}],
                           name="Sam B. Buyer")])
        o = self.order(rid)
        self.assertEqual(o["status"], "shipped")
        self.assertEqual(o["purchase_cost"], Decimal("9.99"))
        self.assertEqual(o["notes"], "bought from Acme")
        self.assertEqual(o["buyer_name"], "Sam B. Buyer")
        self.assertEqual(o["tracking_number"], "9400111")
        self.assertIsNotNone(o["shipped_at"])
        kinds = [(e["kind"], e["source"]) for e in self.events(rid)]
        self.assertIn(("status", "etsy"), kinds)
        self.assertIn(("tracking", "etsy"), kinds)

    def test_order_already_shipped_when_it_arrives_is_a_past_order(self):
        rid = self.base + 6
        self.sync([receipt(rid, None, is_shipped=True)])
        self.assertTrue(self.order(rid)["past_order"])
        listed = self.w.get("/admin/etsy/orders", self.w.publisher, q=str(rid)).json()["items"][0]
        self.assertEqual(listed["attention"], [])
        self.assertEqual(self.w.get("/admin/etsy/orders", self.w.publisher, q=str(rid), attention="true").json()["total"], 0)
        fresh = self.base + 7
        self.sync([receipt(fresh, None)])
        self.assertFalse(self.order(fresh)["past_order"])

    def test_etsy_never_moves_an_order_back_or_off_a_team_status(self):
        rid = self.base + 4
        self.sync([receipt(rid, None)])
        self.w.sql("UPDATE etsy_orders SET status='issue' WHERE etsy_receipt_id=:r", r=rid)
        self.sync([receipt(rid, None, is_shipped=True)])
        self.assertEqual(self.order(rid)["status"], "issue")

    def test_cancelled_on_etsy(self):
        rid = self.base + 5
        self.sync([receipt(rid, None)])
        self.sync([receipt(rid, None, status="Canceled")])
        self.assertEqual(self.order(rid)["status"], "cancelled")

    def test_etsy_failure_is_recorded_on_the_connection(self):
        from app.services.etsy_client import EtsyError
        from app.services.etsy_orders import EtsyOrderSync

        async def boom(path, **kw):
            raise EtsyError("Etsy answered 500.", 500)

        async def go(session):
            with mock.patch("app.services.etsy_client.get", boom), mock.patch("app.core.secretbox.unseal", lambda v: "tok"):
                return await EtsyOrderSync(session).run(force=True)

        self.assertIn("error", self.w.db(go))
        self.assertIn("Order sync", self.w.get("/admin/etsy/connection", self.w.admin).json()["last_error"])


if __name__ == "__main__":
    unittest.main()
