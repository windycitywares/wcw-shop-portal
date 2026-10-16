import unittest

from app.services.notifications import present


def order(state):
    return {"type": "order", "ref": "7", "title": "WCW-1007", "detail": "Ana", "extra": "120.00", "state": state}


class OrderItemTests(unittest.TestCase):
    def test_title_follows_the_payment_now(self):
        self.assertTrue(present(order("unpaid"))["title"].startswith("Order waiting for payment"))
        # Paid, then (partly) refunded: still an order that was paid for, not one waiting for payment.
        for state in ("paid", "partially_refunded", "refunded"):
            self.assertTrue(present(order(state))["title"].startswith("New order"), state)
        self.assertTrue(present(order("cancelled"))["title"].startswith("Cancelled order"))
        self.assertEqual(present(order("cancelled"))["href"], "/admin/orders/7")


if __name__ == "__main__":
    unittest.main()
