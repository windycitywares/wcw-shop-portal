"""Suppliers from the CRM against PostgreSQL: the CRM sends suppliers (create, link by name, rename everywhere, switch
off), the shop's list turns read-only, and the CRM reads a supplier's figures."""

import unittest
from datetime import datetime, timedelta, timezone

from tests.integration_support import RUN, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class CrmSupplierTests(unittest.TestCase):
    TOKEN = "s" * 40

    def setUp(self):
        from app.core.config import get_settings

        reset_limits()
        self.w = world()
        self.cfg = get_settings()
        self.cfg.crm_api_token = self.TOKEN
        self.auth = {"Authorization": f"Bearer {self.TOKEN}"}
        self.key = f"{self.w.sfx}-{self._testMethodName}"
        self.crm_id = 900_000 + abs(hash(self.key)) % 100_000

    def tearDown(self):
        self.cfg.crm_api_token = None
        # Other tests add suppliers through the admin screen, which is closed while the CRM manages the list.
        self.w.sql("UPDATE suppliers SET crm_id = NULL WHERE crm_id IS NOT NULL")

    def send(self, **body):
        return self.w.client.post(self.w.url("/integrations/crm/suppliers"), json=body, headers=self.auth)

    def test_token_required(self):
        self.assertEqual(self.w.client.post(self.w.url("/integrations/crm/suppliers"), json={"crm_id": 1, "name": "x"}).status_code, 401)
        self.assertEqual(self.w.get("/integrations/crm/suppliers/stats", self.w.admin, name="x").status_code, 401)

    def test_link_by_name_rename_everywhere_and_read_only(self):
        w, name = self.w, f"Crm Co {self.key}"
        w.supplier(name)
        rid = 2_000_000 + abs(hash(self.key)) % 1_000_000
        paid = datetime.now(timezone.utc) - timedelta(days=5)
        w.sql("INSERT INTO etsy_orders (etsy_receipt_id, status, ordered_at, paid_at, ship_by, shipped_at, purchase_cost, shipping_cost, supplier) "
              "VALUES (:r, 'shipped', :p, :p, :b, :s, 10, 2, :n)", r=rid, p=paid, b=paid + timedelta(days=3), s=paid + timedelta(days=2), n=name)

        r = self.send(crm_id=self.crm_id, name=name.upper(), email="crm@example.com")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["result"], "linked")

        # The shop's own list is now read-only.
        meta = w.get("/admin/suppliers/meta", w.publisher).json()
        self.assertTrue(meta["managed_by_crm"])
        self.assertEqual(w.post("/admin/suppliers", {"name": f"New {self.key}"}, w.publisher).status_code, 409)

        new = f"Crm & Co {self.key}"
        self.assertEqual(self.send(crm_id=self.crm_id, name=new).json()["result"], "updated")
        self.assertEqual(w.value("SELECT supplier FROM etsy_orders WHERE etsy_receipt_id = :r", r=rid), new)

        stats = w.get("/integrations/crm/suppliers/stats", self.auth, name=new.lower()).json()
        self.assertEqual((stats["orders"], stats["owed"], stats["avg_days_to_ship_90d"], stats["on_time_rate_90d"]), (1, "12.00", 2.0, 1.0))

        self.send(crm_id=self.crm_id, name=new, is_active=False)
        row = next(s for s in w.get("/admin/suppliers", w.publisher).json() if s["crm_id"] == self.crm_id)
        self.assertFalse(row["is_active"])
        listed = w.get("/integrations/crm/suppliers", self.auth).json()["items"]
        self.assertIn(self.crm_id, [s["crm_id"] for s in listed])

    def test_new_supplier_from_the_crm(self):
        r = self.send(crm_id=self.crm_id, name=f"Brand new {self.key}")
        self.assertEqual(r.json()["result"], "created")


if __name__ == "__main__":
    unittest.main()
