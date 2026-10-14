import unittest
from datetime import date
from decimal import Decimal

from app.domain import emailtext
from app.domain.emailtext import LOCALES, money, long_date, render

ITEMS = [{"title": "Oak <b>urn</b>", "qty": 2, "total": "$80.00"}, {"title": "Keepsake", "qty": 1, "total": "$15.00"}]
BASE = {
    "name": "Ana López",
    "number": "WCW-1001",
    "items": ITEMS,
    "subtotal": "$95.00",
    "discount": "$9.50",
    "shipping": "",
    "tax": "$5.88",
    "total": "$91.38",
    "address": "1 Main St\nChicago, IL 60601",
    "link": "https://shop.example/order/abc",
}


class Formatting(unittest.TestCase):
    def test_money_per_locale(self):
        self.assertEqual(money(Decimal("1234.5"), "en"), "$1,234.50")
        self.assertEqual(money(Decimal("1234.5"), "es"), "$1.234,50")
        self.assertEqual(money(Decimal("1234.5"), "nl"), "$ 1.234,50")
        self.assertEqual(money(-3, "en"), "-$3.00")
        self.assertEqual(money(5, "xx"), "$5.00")  # unknown locale falls back to English

    def test_long_date_per_locale(self):
        d = date(2026, 3, 9)
        self.assertEqual(long_date(d, "en"), "March 9, 2026")
        self.assertEqual(long_date(d, "es"), "9 de marzo de 2026")
        self.assertEqual(long_date(d, "nl"), "9 maart 2026")


class Rendering(unittest.TestCase):
    def test_every_template_renders_in_every_locale(self):
        contexts = {
            "order_received": {**BASE, "instructions": "Send a check."},
            "order_confirmation": {**BASE, "delivery_estimate": "Oct 20"},
            "order_shipped": {**BASE, "carrier": "USPS", "tracking_number": "9400", "tracking_url": "https://t.example/9400"},
            "order_cancelled": {**BASE},
            "order_refunded": {**BASE, "amount": "$20.00"},
            "welcome_offer": {"name": "", "percent": 10, "expires": "Nov 1", "code": "WELCOME-ABCD", "shop_url": "https://shop.example", "unsubscribe_url": "https://shop.example/u/1"},
            "abandoned_cart": {"name": "Ana", "items": ITEMS, "link": "https://shop.example/cart", "step": 1, "unsubscribe_url": "https://shop.example/u/1"},
            "review_request": {"name": "Ana", "items": [{"title": "Oak urn", "url": "https://shop.example/p/oak#reviews"}], "unsubscribe_url": "https://shop.example/u/1"},
            "back_in_stock": {"name": "", "title": "Oak urn", "link": "https://shop.example/p/oak"},
            "campaign": {"name": "Ana", "subject": "Spring note", "body": "First para.\n\nSecond para.", "code": "SPRING10", "expires": "May 1", "shop_url": "https://shop.example", "unsubscribe_url": "https://shop.example/u/1"},
        }
        for kind, ctx in contexts.items():
            for lang in LOCALES:
                with self.subTest(kind=kind, lang=lang):
                    out = render(kind, {**ctx, "locale": lang})
                    self.assertTrue(out.subject.strip())
                    self.assertNotIn("\n", out.subject)
                    self.assertTrue(out.text.strip())
                    self.assertIn("<html", out.html)
                    self.assertNotIn("{", out.subject)  # no unformatted placeholders
                    self.assertNotIn("{name}", out.text)

    def test_admin_templates(self):
        out = render("admin_new_order", {"number": "WCW-1", "customer": "Ana", "items": ITEMS, "total": "$91.38", "payment": "Card", "link": "https://x/y"})
        self.assertIn("WCW-1", out.subject)
        out = render("digest", {"subject": "Daily digest", "intro": "Yesterday", "kpis": [("Revenue", "$1")], "sections": [("Top", ["a", "b"])], "link": "https://x/y"})
        self.assertIn("Revenue", out.text)

    def test_html_is_escaped(self):
        out = render("order_confirmation", {**BASE, "locale": "en", "name": "<script>x</script>"})
        self.assertNotIn("<script>", out.html)
        self.assertIn("Oak &lt;b&gt;urn&lt;/b&gt;", out.html)

    def test_header_injection_is_blocked(self):
        out = render("campaign", {"locale": "en", "name": "", "subject": "Hi\r\nBcc: evil@example.com", "body": "x"})
        self.assertNotIn("\n", out.subject)
        self.assertNotIn("\r", out.subject)

    def test_greeting_with_and_without_name(self):
        with_name = render("back_in_stock", {"locale": "es", "name": "Ana López", "title": "Urna", "link": "https://x"})
        self.assertIn("Hola Ana:", with_name.text)
        without = render("back_in_stock", {"locale": "es", "name": "", "title": "Urna", "link": "https://x"})
        self.assertIn("Hola:", without.text)

    def test_unsubscribe_footer_only_when_given(self):
        a = render("campaign", {"locale": "en", "name": "", "subject": "S", "body": "B", "unsubscribe_url": "https://x/u"})
        b = render("campaign", {"locale": "en", "name": "", "subject": "S", "body": "B"})
        self.assertIn("https://x/u", a.text)
        self.assertNotIn("Unsubscribe", b.text)

    def test_free_shipping_label_when_blank(self):
        out = render("order_confirmation", {**BASE, "locale": "en"})
        self.assertIn("Free", out.text)

    def test_second_abandoned_cart_reminder_is_different(self):
        ctx = {"locale": "en", "name": "", "items": ITEMS, "link": "https://x"}
        one = render("abandoned_cart", {**ctx, "step": 1})
        two = render("abandoned_cart", {**ctx, "step": 2})
        self.assertNotEqual(one.text, two.text)

    def test_registry_covers_all_kinds(self):
        self.assertEqual(set(emailtext.RENDERERS), {
            "order_received", "order_confirmation", "order_shipped", "order_cancelled", "order_refunded", "welcome_offer",
            "abandoned_cart", "review_request", "back_in_stock", "campaign", "admin_new_order", "digest",
        })


if __name__ == "__main__":
    unittest.main()
