import json
import unittest
from decimal import Decimal as D
from urllib.parse import parse_qsl

from app.payments import stripe

SECRET = "whsec_test_secret"
BODY = json.dumps({"type": "checkout.session.completed", "data": {"object": {"id": "cs_1"}}}).encode()


class SignatureTests(unittest.TestCase):
    def test_valid_signature(self):
        header = stripe.sign(BODY, SECRET, 1_000_000)
        self.assertTrue(stripe.verify_signature(BODY, header, SECRET, now=1_000_100))

    def test_rejects_wrong_secret_body_and_missing_header(self):
        header = stripe.sign(BODY, SECRET, 1_000_000)
        self.assertFalse(stripe.verify_signature(BODY, header, "whsec_other", now=1_000_000))
        self.assertFalse(stripe.verify_signature(BODY + b" ", header, SECRET, now=1_000_000))
        self.assertFalse(stripe.verify_signature(BODY, None, SECRET, now=1_000_000))
        self.assertFalse(stripe.verify_signature(BODY, "", SECRET, now=1_000_000))
        self.assertFalse(stripe.verify_signature(BODY, header, "", now=1_000_000))

    def test_rejects_old_and_future_timestamps(self):
        header = stripe.sign(BODY, SECRET, 1_000_000)
        self.assertFalse(stripe.verify_signature(BODY, header, SECRET, now=1_000_000 + 301))
        self.assertFalse(stripe.verify_signature(BODY, header, SECRET, now=1_000_000 - 301))
        self.assertTrue(stripe.verify_signature(BODY, header, SECRET, now=1_000_000 + 300))

    def test_any_listed_v1_signature_may_match(self):
        good = stripe.sign(BODY, SECRET, 1_000_000)
        header = good.replace("v1=", "v1=deadbeef,v1=")  # an old signature first, then the real one
        self.assertTrue(stripe.verify_signature(BODY, header, SECRET, now=1_000_000))

    def test_garbage_headers(self):
        for header in ("t=abc,v1=ff", "v1=ff", "t=1000000", "nonsense"):
            self.assertFalse(stripe.verify_signature(BODY, header, SECRET, now=1_000_000), header)


class EncodingTests(unittest.TestCase):
    def test_nested_form(self):
        pairs = dict(stripe.encode_form({"a": 1, "b": {"c": [{"d": "x"}, {"d": "y"}], "e": True}, "skip": None}))
        self.assertEqual(pairs, {"a": "1", "b[c][0][d]": "x", "b[c][1][d]": "y", "b[e]": "true"})

    def test_cents(self):
        self.assertEqual(stripe.to_cents(D("19.99")), 1999)
        self.assertEqual(stripe.to_cents(D("0.005")), 1)
        self.assertEqual(stripe.to_cents(D("100")), 10000)

    def test_checkout_form_carries_the_order_total(self):
        form = dict(stripe.checkout_form(
            order_number="WCW-1001", email="ana@example.com", amount=D("57.83"), currency="USD",
            description="2 items", success_url="https://shop.example/order/WCW-1001?token=x", cancel_url="https://shop.example/checkout",
        ))
        self.assertEqual(form["mode"], "payment")
        self.assertEqual(form["client_reference_id"], "WCW-1001")
        self.assertEqual(form["line_items[0][price_data][unit_amount]"], "5783")
        self.assertEqual(form["line_items[0][price_data][currency]"], "usd")
        self.assertEqual(form["metadata[order_number]"], "WCW-1001")
        self.assertEqual(form["customer_email"], "ana@example.com")
        # And it round-trips through a urlencoded body.
        self.assertTrue(parse_qsl(__import__("urllib.parse").parse.urlencode(list(form.items()))))


if __name__ == "__main__":
    unittest.main()
