"""Supplier payments against PostgreSQL: pending → settled (single and bulk), undo, per-supplier totals, exports,
history and who may do it."""

import io
import unittest
from datetime import datetime, timedelta, timezone

from tests.integration_support import RUN, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class SupplierPaymentTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()
        key = f"{self.w.sfx}-{self._testMethodName}"
        self.sup = f"Pay {key}"
        base = 5_000_000 + abs(hash(key)) % 1_000_000
        when = datetime.now(timezone.utc) - timedelta(days=3)
        self.ids = []
        for i, (cost, ship) in enumerate((("10.00", "4.00"), ("20.00", None), (None, None))):
            self.ids.append(self.w.sql(
                "INSERT INTO etsy_orders (etsy_receipt_id, status, ordered_at, paid_at, items_total, shipping_charged, discounts, "
                "tax, grand_total, purchase_cost, shipping_cost, supplier) VALUES (:r, 'purchased', :t, :t, 40, 0, 0, 0, 40, :c, :s, :sup) "
                "RETURNING id", r=base + i, t=when, c=cost, s=ship, sup=self.sup)[0]["id"])

    def get(self, path, **params):
        r = self.w.get(path, self.w.publisher, supplier=self.sup, **params)
        self.assertEqual(r.status_code, 200, r.text)
        return r

    def test_pending_then_settled_in_one_go(self):
        w = self.w
        ov = self.get("/admin/etsy/supplier-payments/overview").json()
        self.assertEqual((ov["pending_count"], ov["pending_amount"], ov["cost_missing"]), (2, "34.00", 1))
        pending = self.get("/admin/etsy/supplier-payments", state="pending").json()["items"]
        self.assertEqual([p["owed"] for p in pending], ["14.00", "20.00"])

        # Staff can see, only an admin can record a payment.
        body = {"order_ids": self.ids[:2], "reference": "PayPal 123"}
        self.assertEqual(w.post("/admin/etsy/supplier-payments/settle", body, w.publisher).status_code, 403)
        r = w.post("/admin/etsy/supplier-payments/settle", body, w.admin)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["total"], "34.00")

        ov = self.get("/admin/etsy/supplier-payments/overview").json()
        self.assertEqual((ov["pending_count"], ov["settled_count"], ov["settled_amount"]), (0, 2, "34.00"))
        settled = self.get("/admin/etsy/supplier-payments", state="settled").json()["items"]
        self.assertEqual({s["payment_ref"] for s in settled}, {"PayPal 123"})
        admin_name = w.value("SELECT coalesce(full_name, email) FROM users WHERE email = :e", e=w.admin_email)
        self.assertEqual({s["paid_by"] for s in settled}, {admin_name})  # other tests may rename the shared admin

        detail = w.get(f"/admin/etsy/orders/{self.ids[0]}", w.publisher).json()
        self.assertEqual(detail["supplier_payment"], "settled")
        self.assertEqual(detail["purchase_cost"], "10.00")  # the cost itself is untouched
        self.assertIn("Supplier paid $14.00", detail["history"][0]["message"])

        # Paying twice is refused; an order without a cost can't be paid.
        self.assertEqual(w.post("/admin/etsy/supplier-payments/settle", {"order_ids": [self.ids[0]]}, w.admin).status_code, 422)
        self.assertEqual(w.post("/admin/etsy/supplier-payments/settle", {"order_ids": [self.ids[2]]}, w.admin).status_code, 422)

    def test_custom_amount_and_undo(self):
        w = self.w
        r = w.post("/admin/etsy/supplier-payments/settle", {"order_ids": [self.ids[1]], "amount": "18.50"}, w.admin)
        self.assertEqual(r.json()["total"], "18.50")
        self.assertEqual(w.post("/admin/etsy/supplier-payments/settle", {"order_ids": self.ids[:1] + [self.ids[1]], "amount": "1"}, w.admin).status_code, 422)
        self.assertEqual(w.post(f"/admin/etsy/supplier-payments/{self.ids[1]}/undo", {"reason": "wrong order"}, w.admin).status_code, 200)
        ov = self.get("/admin/etsy/supplier-payments/overview").json()
        self.assertEqual((ov["pending_count"], ov["settled_count"]), (2, 0))
        kinds = [h["kind"] for h in w.get(f"/admin/etsy/orders/{self.ids[1]}", w.admin).json()["history"]]
        self.assertEqual(kinds[:2], ["payment", "payment"])

    def test_exports(self):
        csv_r = self.get("/admin/etsy/supplier-payments/export", state="pending", format="csv")
        self.assertIn("text/csv", csv_r.headers["content-type"])
        text = csv_r.content.decode("utf-8-sig")
        self.assertTrue(text.startswith("Etsy order,Order date,Supplier"))
        self.assertEqual(text.count(self.sup), 2)

        x = self.get("/admin/etsy/supplier-payments/export", state="all", format="xlsx")
        self.assertIn("spreadsheetml", x.headers["content-type"])
        from openpyxl import load_workbook

        ws = load_workbook(io.BytesIO(x.content)).active
        self.assertEqual(ws["A1"].value, "Etsy order")
        self.assertEqual(ws.max_row, 3)  # header + the two orders that are owed


if __name__ == "__main__":
    unittest.main()
