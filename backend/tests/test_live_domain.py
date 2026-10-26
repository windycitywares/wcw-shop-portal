"""What a change is worth telling staff at once — pure, no DB."""

import unittest
from datetime import datetime, timezone

from app.domain.live import PRODUCT_BURST, order_change, products_changed

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


class OrderChangeTests(unittest.TestCase):
    def test_a_placed_order_is_new_even_when_paid_in_the_same_save(self):
        s = order_change("1043", "Lee", "58", {"placed_at": None, "payment_status": "unpaid"},
                         {"placed_at": NOW, "payment_status": "paid", "status": "paid"}, False)
        self.assertEqual((s.kind, s.title, s.detail), ("order.new", "New order #1043", "Lee · $58.00"))

    def test_new_row_already_placed(self):
        self.assertEqual(order_change("1", None, 9, {}, {"placed_at": NOW}, True).kind, "order.new")

    def test_an_unplaced_new_order_is_not_news(self):
        self.assertIsNone(order_change("1", None, 9, {}, {"placed_at": None, "payment_status": "unpaid"}, True))

    def test_paid_refund_and_failure(self):
        base = {"placed_at": NOW}
        self.assertEqual(order_change("2", None, 5, {**base, "payment_status": "unpaid"}, {**base, "payment_status": "paid"}, False).kind, "order.paid")
        self.assertEqual(order_change("2", None, 5, {**base, "payment_status": "paid"}, {**base, "payment_status": "partially_refunded"}, False).kind, "order.refund")
        failed = order_change("2", None, 5, {**base, "payment_status": "unpaid"}, {**base, "payment_status": "failed"}, False)
        self.assertEqual(failed.title, "Payment failed on order #2")

    def test_status_changes_that_matter(self):
        base = {"placed_at": NOW, "payment_status": "paid"}
        self.assertEqual(order_change("3", None, 5, {**base, "status": "paid"}, {**base, "status": "shipped"}, False).title, "Order #3 shipped")
        self.assertIsNone(order_change("3", None, 5, {**base, "status": "pending"}, {**base, "status": "paid"}, False))
        self.assertIsNone(order_change("3", None, 5, base, base, False))


class ProductsTests(unittest.TestCase):
    def test_a_few_products_get_a_line_each(self):
        lines = products_changed([("Mug", True), ("Print", False)])
        self.assertEqual([l.title for l in lines], ["Product added: Mug", "Product updated: Print"])

    def test_a_burst_is_one_line(self):
        lines = products_changed([(f"P{i}", False) for i in range(PRODUCT_BURST + 1)])
        self.assertEqual([l.title for l in lines], [f"{PRODUCT_BURST + 1} products updated"])


if __name__ == "__main__":
    unittest.main()
