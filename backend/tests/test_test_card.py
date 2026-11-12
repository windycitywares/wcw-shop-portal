"""Test mode's pretend card payment: the card rules, and an order paid through the card page."""

import unittest
from datetime import date

from app.services.payments.test_card import check_card
from tests.integration_support import RUN, item, reset_limits, skip_unless_db, world

TODAY = date(2026, 11, 12)


class CardRuleTests(unittest.TestCase):
    def test_the_visa_test_number_pays(self):
        self.assertTrue(check_card("4242 4242 4242 4242", 12, 2030, "123", TODAY).paid)

    def test_amex_needs_four_digits(self):
        self.assertTrue(check_card("3782 822463 10005", 1, 2031, "1234", TODAY).paid)
        self.assertFalse(check_card("3782 822463 10005", 1, 2031, "123", TODAY).paid)

    def test_declines_say_why(self):
        self.assertEqual(check_card("4000 0000 0000 0002", 12, 2030, "123", TODAY).message, "Your card was declined.")
        self.assertIn("insufficient", check_card("4000000000009995", 12, 2030, "123", TODAY).message)

    def test_a_real_looking_number_is_not_a_test_card(self):
        r = check_card("4111 1111 1111 1111", 12, 2030, "123", TODAY)
        self.assertFalse(r.paid)
        self.assertIn("test card", r.message)

    def test_expiry_and_cvc_are_checked(self):
        self.assertFalse(check_card("4242424242424242", 10, 2026, "123", TODAY).paid)  # last month
        self.assertTrue(check_card("4242424242424242", 11, 26, "123", TODAY).paid)  # this month, two-digit year
        self.assertFalse(check_card("4242424242424242", 12, 2030, "12", TODAY).paid)
        self.assertFalse(check_card("4242424242424242", 13, 2030, "123", TODAY).paid)


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class TestCardOrderTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    CARD = {"exp_month": 12, "exp_year": 2035, "cvc": "123"}

    def test_order_waits_for_the_card_page_then_is_paid(self):
        w = self.w
        out = w.place(w.email("card"), [item(w.product("20.00"))], payment_method="test_card")
        self.assertEqual(out["payment"]["status"], "redirect")
        self.assertIn("/test-payment", out["payment"]["redirect_url"])
        token = out["order"]["access_token"]
        self.assertIsNone(w.get(f"/orders/by-token/{token}").json()["paid_at"])

        declined = w.post(f"/orders/by-token/{token}/test-payment", {"number": "4000000000000002", **self.CARD})
        self.assertEqual(declined.json()["status"], "declined")
        self.assertIsNone(w.get(f"/orders/by-token/{token}").json()["paid_at"])

        paid = w.post(f"/orders/by-token/{token}/test-payment", {"number": "4242424242424242", **self.CARD})
        self.assertEqual(paid.json()["status"], "paid")
        self.assertIsNotNone(w.get(f"/orders/by-token/{token}").json()["paid_at"])

    def test_the_card_page_is_for_test_card_orders_only(self):
        w = self.w
        out = w.place(w.email("card-other"), [item(w.product("20.00"))])  # the instant test payment
        r = w.post(f"/orders/by-token/{out['order']['access_token']}/test-payment", {"number": "4242424242424242", **self.CARD})
        self.assertEqual(r.status_code, 409)


if __name__ == "__main__":
    unittest.main()
