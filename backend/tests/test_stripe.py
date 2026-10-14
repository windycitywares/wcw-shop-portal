import hashlib
import hmac
import unittest
from decimal import Decimal as D
from types import SimpleNamespace as NS

from app.services.payments.stripe import checkout_line_items, encode_form, verify_signature

SECRET = "whsec_test_secret"


def sign(payload: bytes, ts: int, secret: str = SECRET) -> str:
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


class StripeHelperTests(unittest.TestCase):
    def test_encode_form_nested(self):
        pairs = encode_form({"mode": "payment", "line_items": [{"quantity": 1, "price_data": {"currency": "usd", "unit_amount": 500}}],
                             "metadata": {"order_id": 7}, "skip": None, "flag": True})
        self.assertIn(("line_items[0][quantity]", "1"), pairs)
        self.assertIn(("line_items[0][price_data][unit_amount]", "500"), pairs)
        self.assertIn(("metadata[order_id]", "7"), pairs)
        self.assertIn(("flag", "true"), pairs)
        self.assertNotIn("skip", [k for k, _ in pairs])

    def test_signature_valid_and_invalid(self):
        body = b'{"id":"evt_1"}'
        self.assertTrue(verify_signature(body, sign(body, 1_000), SECRET, now=1_100))
        self.assertFalse(verify_signature(body, sign(body, 1_000), "other", now=1_100))  # wrong secret
        self.assertFalse(verify_signature(b'{"id":"evt_2"}', sign(body, 1_000), SECRET, now=1_100))  # tampered body
        self.assertFalse(verify_signature(body, sign(body, 1_000), SECRET, now=1_000 + 301))  # replayed after the tolerance
        self.assertFalse(verify_signature(body, None, SECRET, now=1_000))
        self.assertFalse(verify_signature(body, "garbage", SECRET, now=1_000))
        self.assertFalse(verify_signature(body, "t=abc,v1=00", SECRET, now=1_000))
        self.assertFalse(verify_signature(body, sign(body, 1_000), "", now=1_100))

    def test_signature_accepts_any_matching_v1(self):
        body = b"{}"
        good = sign(body, 50).split("v1=")[1]
        self.assertTrue(verify_signature(body, f"t=50,v1=deadbeef,v1={good}", SECRET, now=60))

    def order(self, items, shipping="0", tax="0", total=None):
        its = [NS(title=t, quantity=q, line_total=D(lt), discount_total=D(d)) for t, q, lt, d in items]
        grand = total or str(sum((D(lt) - D(d) for _, _, lt, d in items), D(0)) + D(shipping) + D(tax))
        return NS(items=its, shipping_total=D(shipping), tax_total=D(tax), grand_total=D(grand), number="WCW-1001")

    def test_line_items_add_up_to_the_order_total(self):
        order = self.order([("Oak urn", 2, "120.00", "12.00"), ("Keepsake", 1, "25.00", "2.50")], shipping="8.95", tax="10.00")
        lines = checkout_line_items(order, "usd")
        self.assertEqual(sum(l["price_data"]["unit_amount"] for l in lines), 14_945)
        self.assertEqual(lines[0]["price_data"]["product_data"]["name"], "Oak urn × 2")
        self.assertEqual([l["price_data"]["unit_amount"] for l in lines], [10_800, 2_250, 895, 1_000])

    def test_zero_amount_lines_are_skipped_and_mismatch_falls_back(self):
        order = self.order([("Free thing", 1, "10.00", "10.00"), ("Urn", 1, "50.00", "0.00")])
        self.assertEqual(len(checkout_line_items(order, "usd")), 1)
        odd = self.order([("Urn", 1, "50.00", "0.00")], total="99.00")  # items don't add up: single-line fallback
        lines = checkout_line_items(odd, "usd")
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["price_data"]["unit_amount"], 9_900)


if __name__ == "__main__":
    unittest.main()
