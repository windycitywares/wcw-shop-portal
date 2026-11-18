"""The supplier list against PostgreSQL: add, pick, rename everywhere, switch off."""

import unittest
from datetime import datetime, timezone

from tests.integration_support import RUN, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class SupplierListTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()
        self.key = f"{self.w.sfx}-{self._testMethodName}"

    def test_add_pick_rename_and_switch_off(self):
        w, name = self.w, f"Bee Co {self.key}"
        r = w.post("/admin/suppliers", {"name": f"  {name} ", "email": "bee@example.com"}, w.publisher)
        self.assertEqual(r.status_code, 201, r.text)
        sid = r.json()["id"]
        self.assertEqual(w.post("/admin/suppliers", {"name": name.upper()}, w.publisher).status_code, 409)

        rid = 3_000_000 + abs(hash(self.key)) % 1_000_000
        oid = w.sql("INSERT INTO etsy_orders (etsy_receipt_id, status, ordered_at, paid_at, purchase_cost) "
                    "VALUES (:r, 'new', :t, :t, 9) RETURNING id", r=rid, t=datetime.now(timezone.utc))[0]["id"]
        self.assertEqual(w.client.patch(w.url(f"/admin/etsy/orders/{oid}"), json={"supplier": name.lower()}, headers=w.publisher).json()["supplier"], name)

        row = next(s for s in w.get("/admin/suppliers", w.publisher).json() if s["id"] == sid)
        self.assertEqual((row["open_orders"], row["owed"]), (1, "9.00"))

        new = f"Bee & Co {self.key}"
        self.assertEqual(w.client.patch(w.url(f"/admin/suppliers/{sid}"), json={"name": new}, headers=w.publisher).status_code, 200)
        self.assertEqual(w.get(f"/admin/etsy/orders/{oid}", w.publisher).json()["supplier"], new)  # renamed on the order too

        w.client.patch(w.url(f"/admin/suppliers/{sid}"), json={"is_active": False}, headers=w.publisher)
        r = w.client.patch(w.url(f"/admin/etsy/orders/{oid}"), json={"supplier": new}, headers=w.publisher)
        self.assertEqual(r.status_code, 200)  # unchanged value: nothing to check
        self.assertEqual(w.client.patch(w.url(f"/admin/etsy/orders/{oid}"), json={"supplier": None}, headers=w.publisher).status_code, 200)
        self.assertEqual(w.client.patch(w.url(f"/admin/etsy/orders/{oid}"), json={"supplier": new}, headers=w.publisher).status_code, 422)

    def test_team_only(self):
        _, shopper = self.w.register("supplier-list-shopper")
        self.assertEqual(self.w.get("/admin/suppliers", shopper).status_code, 403)


if __name__ == "__main__":
    unittest.main()
