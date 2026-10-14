import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from app.pricing.codes import is_valid_code, normalize_code, random_code
from app.pricing.engine import (
    Coupon,
    Destination,
    Line,
    Sale,
    Scope,
    ShippingOption,
    Shopper,
    TaxRate,
    allocate,
    best_sale,
    check_coupon,
    path_within,
    price_cart,
)

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
DAY = timedelta(days=1)


def line(key="a", price="40.00", qty=1, product_id=1, parent_id=None, path="1.2"):
    return Line(key=key, product_id=product_id, unit_price=D(price), quantity=qty, parent_id=parent_id, category_path=path)


STANDARD = ShippingOption("standard", "Standard", D("6.00"), free_over=D("75.00"), min_days=4, max_days=7)
EXPRESS = ShippingOption("express", "Express", D("15.00"), min_days=1, max_days=2)
IL_TAX = TaxRate(1, "Illinois sales tax", "US", D("6.25"), region="IL")
CITY_TAX = TaxRate(2, "Chicago tax", "US", D("1.25"), region="IL", applies_to_shipping=True)


class AllocateTests(unittest.TestCase):
    def test_parts_add_up_exactly(self):
        parts = allocate(D("10.00"), [D("33.33"), D("33.33"), D("33.34")])
        self.assertEqual(sum(parts), D("10.00"))
        self.assertEqual(len(parts), 3)

    def test_proportional(self):
        self.assertEqual(allocate(D("6.00"), [D("10"), D("20")]), [D("2.00"), D("4.00")])

    def test_nothing_to_share(self):
        self.assertEqual(allocate(D("0"), [D("5")]), [D("0.00")])
        self.assertEqual(allocate(D("5"), [D("0")]), [D("0.00")])

    def test_single_cent_goes_somewhere(self):
        self.assertEqual(sum(allocate(D("0.01"), [D("1"), D("1"), D("1")])), D("0.01"))


class PathTests(unittest.TestCase):
    def test_within(self):
        self.assertTrue(path_within("1.4", "1.4"))
        self.assertTrue(path_within("1.4.9", "1.4"))
        self.assertFalse(path_within("1.41", "1.4"))  # not a prefix match on characters
        self.assertFalse(path_within(None, "1.4"))


class SaleTests(unittest.TestCase):
    def test_percent_and_fixed(self):
        self.assertEqual(Sale(1, "s", "percent", D("25")).price_for(D("40.00")), D("30.00"))
        self.assertEqual(Sale(1, "s", "fixed", D("5")).price_for(D("40.00")), D("35.00"))
        self.assertEqual(Sale(1, "s", "fixed", D("500")).price_for(D("40.00")), D("0.00"))
        self.assertEqual(Sale(1, "s", "percent", D("150")).price_for(D("40.00")), D("0.00"))

    def test_window_and_flag(self):
        s = Sale(1, "s", "percent", D("10"), starts_at=NOW - DAY, ends_at=NOW + DAY)
        self.assertTrue(s.is_live(NOW))
        self.assertFalse(s.is_live(NOW + 2 * DAY))
        self.assertFalse(s.is_live(NOW - 2 * DAY))
        self.assertFalse(Sale(1, "s", "percent", D("10"), active=False).is_live(NOW))
        self.assertFalse(Sale(1, "s", "percent", D("10"), ends_at=NOW).is_live(NOW))  # ends exactly now

    def test_naive_datetimes_are_treated_as_utc(self):
        s = Sale(1, "s", "percent", D("10"), ends_at=datetime(2026, 10, 15))
        self.assertTrue(s.is_live(NOW))

    def test_best_sale_wins_and_they_do_not_stack(self):
        sales = [Sale(1, "ten", "percent", D("10")), Sale(2, "five off", "fixed", D("8")), Sale(3, "off", "percent", D("5"))]
        sale, price = best_sale(line(), sales, NOW)
        self.assertEqual((sale.id, price), (2, D("32.00")))

    def test_tie_goes_to_oldest(self):
        sales = [Sale(7, "b", "percent", D("10")), Sale(3, "a", "fixed", D("4"))]
        sale, _ = best_sale(line(), sales, NOW)
        self.assertEqual(sale.id, 3)

    def test_scopes(self):
        by_cat = Sale(1, "c", "percent", D("10"), scope=Scope("category", category_path="1.2"))
        self.assertIsNotNone(best_sale(line(path="1.2.7"), [by_cat], NOW)[0])
        self.assertIsNone(best_sale(line(path="1.3"), [by_cat], NOW)[0])
        by_product = Sale(2, "p", "percent", D("10"), scope=Scope("products", product_ids=frozenset({5})))
        self.assertIsNotNone(best_sale(line(product_id=5), [by_product], NOW)[0])
        self.assertIsNone(best_sale(line(product_id=6), [by_product], NOW)[0])
        # A variant is covered by a sale on its parent.
        self.assertIsNotNone(best_sale(line(product_id=9, parent_id=5), [by_product], NOW)[0])

    def test_no_sale_means_list_price(self):
        sale, price = best_sale(line(), [], NOW)
        self.assertIsNone(sale)
        self.assertEqual(price, D("40.00"))


class CouponCheckTests(unittest.TestCase):
    def coupon(self, **kw):
        return Coupon(id=1, code="HELLO", kind="percent", value=D("10"), **kw)

    def code(self, coupon, shopper=Shopper()):
        problem = check_coupon(coupon, shopper, NOW)
        return problem.code if problem else None

    def test_ok(self):
        self.assertIsNone(self.code(self.coupon()))

    def test_inactive_looks_like_unknown(self):
        self.assertEqual(self.code(self.coupon(active=False)), "invalid")

    def test_dates(self):
        self.assertEqual(self.code(self.coupon(starts_at=NOW + DAY)), "not_started")
        self.assertEqual(self.code(self.coupon(expires_at=NOW - DAY)), "expired")
        self.assertIsNone(self.code(self.coupon(starts_at=NOW - DAY, expires_at=NOW + DAY)))

    def test_usage_limits(self):
        self.assertEqual(self.code(self.coupon(usage_limit=5, used_count=5)), "used_up")
        self.assertIsNone(self.code(self.coupon(usage_limit=5, used_count=4)))
        self.assertEqual(self.code(self.coupon(per_customer_limit=1), Shopper(coupon_uses=1)), "already_used")
        self.assertIsNone(self.code(self.coupon(per_customer_limit=2), Shopper(coupon_uses=1)))

    def test_first_order_only(self):
        c = self.coupon(first_order_only=True)
        self.assertIsNone(self.code(c, Shopper(prior_orders=0)))
        self.assertEqual(self.code(c, Shopper(prior_orders=1)), "first_order_only")

    def test_personal_by_email_or_account(self):
        c = self.coupon(email="ana@example.com")
        self.assertIsNone(self.code(c, Shopper(email="Ana@Example.com")))
        self.assertEqual(self.code(c, Shopper(email="bob@example.com")), "invalid")
        self.assertEqual(self.code(c, Shopper()), "needs_email")
        by_user = self.coupon(user_id=7)
        self.assertIsNone(self.code(by_user, Shopper(user_id=7)))
        self.assertEqual(self.code(by_user, Shopper(user_id=8)), "invalid")
        self.assertEqual(self.code(by_user, Shopper()), "invalid")


class PriceCartTests(unittest.TestCase):
    def price(self, lines, **kw):
        kw.setdefault("now", NOW)
        return price_cart(lines, **kw)

    def test_plain_cart(self):
        q = self.price([line(price="40.00", qty=2), line("b", "10.50", product_id=2)])
        self.assertEqual(q.subtotal, D("90.50"))
        self.assertEqual(q.total, D("90.50"))
        self.assertEqual(q.sale_savings, D("0.00"))
        self.assertEqual(q.shipping_method, None)

    def test_sale_lowers_price_and_records_savings(self):
        q = self.price([line(price="40.00", qty=2)], sales=[Sale(1, "Autumn", "percent", D("25"), label="Autumn sale")])
        self.assertEqual(q.list_subtotal, D("80.00"))
        self.assertEqual(q.subtotal, D("60.00"))
        self.assertEqual(q.sale_savings, D("20.00"))
        self.assertEqual(q.lines[0].unit_price, D("30.00"))
        self.assertEqual(q.lines[0].sale_label, "Autumn sale")

    def test_percent_coupon(self):
        c = Coupon(1, "TEN", "percent", D("10"))
        q = self.price([line(price="40.00", qty=2)], coupon=c)
        self.assertEqual(q.coupon_discount, D("8.00"))
        self.assertEqual(q.total, D("72.00"))
        self.assertEqual(q.coupon_code, "TEN")
        self.assertIsNone(q.coupon_problem)

    def test_coupon_cap_and_fixed(self):
        capped = Coupon(1, "BIG", "percent", D("50"), max_discount=D("10"))
        self.assertEqual(self.price([line(price="100.00")], coupon=capped).coupon_discount, D("10.00"))
        fixed = Coupon(2, "FIVE", "fixed", D("5"))
        self.assertEqual(self.price([line(price="100.00")], coupon=fixed).coupon_discount, D("5.00"))
        # A fixed coupon can't take more than the goods are worth.
        self.assertEqual(self.price([line(price="3.00")], coupon=fixed).coupon_discount, D("3.00"))
        self.assertEqual(self.price([line(price="3.00")], coupon=fixed).total, D("0.00"))

    def test_coupon_is_shared_across_lines_to_the_cent(self):
        c = Coupon(1, "SEVEN", "fixed", D("7.00"))
        q = self.price([line("a", "10.00", product_id=1), line("b", "10.00", product_id=2), line("c", "10.00", product_id=3)], coupon=c)
        self.assertEqual(sum(p.coupon_discount for p in q.lines), D("7.00"))
        self.assertEqual(sum(p.net_total for p in q.lines), q.total)

    def test_coupon_scope_and_excluded_sale_items(self):
        c = Coupon(1, "CAT", "percent", D("10"), scope=Scope("category", category_path="1.2"))
        q = self.price([line("a", "50.00", path="1.2"), line("b", "50.00", product_id=2, path="1.9")], coupon=c)
        self.assertEqual(q.coupon_discount, D("5.00"))
        self.assertEqual(q.lines[1].coupon_discount, D("0.00"))

        sale = Sale(1, "s", "percent", D("20"), scope=Scope("products", product_ids=frozenset({1})))
        c2 = Coupon(2, "FULLPRICE", "percent", D("10"), exclude_sale_items=True)
        q2 = self.price([line("a", "50.00"), line("b", "50.00", product_id=2)], sales=[sale], coupon=c2)
        self.assertEqual(q2.coupon_discount, D("5.00"))  # only the full-price item

    def test_coupon_that_cannot_apply(self):
        c = Coupon(1, "CAT", "percent", D("10"), scope=Scope("category", category_path="9"))
        q = self.price([line()], coupon=c)
        self.assertEqual(q.coupon_problem.code, "no_eligible_items")
        self.assertEqual(q.coupon_discount, D("0.00"))
        self.assertIsNone(q.coupon_code)

    def test_minimum_spend(self):
        c = Coupon(1, "BIGSPEND", "percent", D("10"), min_subtotal=D("100"))
        q = self.price([line(price="40.00")], coupon=c)
        self.assertEqual(q.coupon_problem.code, "min_subtotal")
        self.assertIn("$100.00", q.coupon_problem.message)
        q = self.price([line(price="120.00")], coupon=c)
        self.assertIsNone(q.coupon_problem)

    def test_minimum_spend_counts_the_price_after_sales(self):
        c = Coupon(1, "BIGSPEND", "percent", D("10"), min_subtotal=D("100"))
        sale = Sale(1, "s", "percent", D("20"))
        self.assertEqual(self.price([line(price="120.00")], sales=[sale], coupon=c).coupon_problem.code, "min_subtotal")

    def test_shipping_choice_and_free_threshold(self):
        q = self.price([line(price="40.00")], shipping=[STANDARD, EXPRESS], shipping_code="standard", destination=Destination("US"))
        self.assertEqual([o.code for o in q.shipping_options], ["standard", "express"])
        self.assertEqual(q.shipping_total, D("6.00"))
        self.assertEqual(q.total, D("46.00"))
        self.assertEqual(q.free_shipping_threshold, D("75.00"))
        self.assertEqual(q.free_shipping_remaining, D("35.00"))

        q = self.price([line(price="80.00")], shipping=[STANDARD, EXPRESS], shipping_code="standard", destination=Destination("US"))
        self.assertEqual(q.shipping_total, D("0.00"))
        self.assertEqual(q.shipping_discount, D("6.00"))
        self.assertTrue(q.shipping_options[0].free)
        self.assertEqual(q.free_shipping_remaining, D("0.00"))
        # Express has no free-over amount, so it still costs.
        q = self.price([line(price="80.00")], shipping=[STANDARD, EXPRESS], shipping_code="express", destination=Destination("US"))
        self.assertEqual(q.shipping_total, D("15.00"))

    def test_free_shipping_threshold_uses_the_price_after_discounts(self):
        c = Coupon(1, "TEN", "percent", D("10"))
        q = self.price([line(price="80.00")], coupon=c, shipping=[STANDARD], shipping_code="standard", destination=Destination("US"))
        self.assertEqual(q.shipping_total, D("6.00"))  # 72.00 is under 75.00

    def test_free_shipping_coupon(self):
        c = Coupon(1, "SHIPFREE", "free_shipping")
        q = self.price([line(price="20.00")], coupon=c, shipping=[STANDARD, EXPRESS], shipping_code="express", destination=Destination("US"))
        self.assertTrue(q.coupon_free_shipping)
        self.assertEqual(q.coupon_discount, D("0.00"))
        self.assertEqual(q.shipping_total, D("0.00"))
        self.assertEqual(q.shipping_discount, D("15.00"))
        self.assertEqual(q.total, D("20.00"))
        self.assertIsNone(q.free_shipping_remaining)

    def test_shipping_by_country(self):
        us_only = ShippingOption("us", "US post", D("5.00"), countries=frozenset({"US"}))
        world = ShippingOption("world", "International", D("25.00"))
        q = self.price([line()], shipping=[us_only, world], destination=Destination("NL"))
        self.assertEqual([o.code for o in q.shipping_options], ["world"])
        q = self.price([line()], shipping=[us_only, world], shipping_code="us", destination=Destination("NL"))
        self.assertIsNone(q.shipping_method)  # not offered to that country: not chosen

    def test_no_destination_offers_only_worldwide_methods(self):
        us_only = ShippingOption("us", "US post", D("5.00"), countries=frozenset({"US"}))
        q = self.price([line()], shipping=[us_only, EXPRESS])
        self.assertEqual([o.code for o in q.shipping_options], ["express"])

    def test_tax_on_goods_after_discount(self):
        c = Coupon(1, "TEN", "percent", D("10"))
        q = self.price([line(price="100.00")], coupon=c, tax_rates=[IL_TAX], destination=Destination("US", "il"))
        self.assertEqual(q.tax_total, D("5.63"))  # 90.00 * 6.25% = 5.625
        self.assertEqual(q.total, D("95.63"))
        self.assertEqual(q.tax_lines[0].name, "Illinois sales tax")

    def test_tax_rates_stack_and_can_cover_shipping(self):
        q = self.price(
            [line(price="50.00")], shipping=[STANDARD], shipping_code="standard", destination=Destination("US", "IL"),
            tax_rates=[IL_TAX, CITY_TAX],
        )
        # state: 50.00 * 6.25% = 3.125 -> 3.13; city: (50.00 + 6.00) * 1.25% = 0.70
        self.assertEqual([t.amount for t in q.tax_lines], [D("3.13"), D("0.70")])
        self.assertEqual(q.tax_total, D("3.83"))
        self.assertEqual(q.total, D("50.00") + D("6.00") + D("3.83"))

    def test_no_tax_for_other_regions_or_without_a_destination(self):
        self.assertEqual(self.price([line()], tax_rates=[IL_TAX], destination=Destination("US", "WI")).tax_total, D("0.00"))
        self.assertEqual(self.price([line()], tax_rates=[IL_TAX]).tax_total, D("0.00"))
        country_wide = TaxRate(3, "VAT", "NL", D("21"))
        self.assertEqual(self.price([line(price="100.00")], tax_rates=[country_wide], destination=Destination("nl")).tax_total, D("21.00"))

    def test_discount_total_adds_sale_coupon_and_shipping(self):
        sale = Sale(1, "s", "percent", D("50"))
        c = Coupon(2, "FIVE", "fixed", D("5"))
        q = self.price([line(price="100.00")], sales=[sale], coupon=c, shipping=[STANDARD], shipping_code="standard", destination=Destination("US"))
        self.assertEqual(q.sale_savings, D("50.00"))
        self.assertEqual(q.coupon_discount, D("5.00"))
        self.assertEqual(q.discount_total, D("55.00"))
        self.assertEqual(q.total, D("51.00"))  # 50 - 5 + 6 shipping

    def test_empty_cart(self):
        q = self.price([], shipping=[STANDARD], shipping_code="standard", destination=Destination("US"))
        self.assertEqual(q.total, D("6.00"))
        self.assertIsNone(q.free_shipping_remaining)

    def test_rejects_bad_lines(self):
        with self.assertRaises(ValueError):
            self.price([line(qty=0)])
        with self.assertRaises(ValueError):
            self.price([line(price="-1")])

    def test_totals_always_add_up(self):
        c = Coupon(1, "ODD", "percent", D("13"))
        sale = Sale(1, "s", "percent", D("17"))
        lines = [line("a", "19.99", qty=3, product_id=1), line("b", "7.33", qty=5, product_id=2), line("c", "104.17", product_id=3)]
        q = self.price(lines, sales=[sale], coupon=c, shipping=[STANDARD], shipping_code="standard",
                       destination=Destination("US", "IL"), tax_rates=[IL_TAX, CITY_TAX])
        self.assertEqual(sum(p.net_total for p in q.lines), q.subtotal - q.coupon_discount)
        self.assertEqual(q.total, q.subtotal - q.coupon_discount + q.shipping_total + q.tax_total)
        for amount in (q.total, q.tax_total, q.coupon_discount, q.subtotal):
            self.assertEqual(amount, amount.quantize(D("0.01")))


class CodeTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_code("  welcome- ab12 \n"), "WELCOME-AB12")
        self.assertEqual(normalize_code(""), "")

    def test_generated_codes_are_valid_and_readable(self):
        for _ in range(200):
            code = random_code("FALL", 8)
            self.assertTrue(is_valid_code(code), code)
            body = code.split("-", 1)[1]
            self.assertEqual(len(body), 8)
            self.assertFalse(set(body) & set("01OIL"))

    def test_unique_enough(self):
        self.assertEqual(len({random_code("X", 8) for _ in range(500)}), 500)

    def test_validation(self):
        self.assertTrue(is_valid_code("SAVE10"))
        self.assertFalse(is_valid_code("A"))
        self.assertFalse(is_valid_code("has space"))
        self.assertFalse(is_valid_code("lower"))
        self.assertFalse(is_valid_code("X" * 41))


if __name__ == "__main__":
    unittest.main()
