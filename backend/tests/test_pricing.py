import random
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from app.domain.money import allocate, from_cents, q2, to_cents
from app.domain.pricing import (
    CartRuleDef,
    CouponDef,
    Customer,
    Destination,
    Line,
    ProductFacts,
    SaleRule,
    Scope,
    ShippingConfig,
    TaxConfig,
    best_sale,
    build_quote,
    coupon_problem,
    coupon_saving,
    evaluate_rule,
    next_rewards,
    region_code,
    shipping_for,
    tax_for,
)

NOW = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)


def line(pid=1, qty=1, price="50.00", list_price=None, category="1.2", parent=None, sale_id=None):
    return Line(pid, qty, D(price), D(list_price or price), parent_id=parent, category_path=category, sale_id=sale_id)


def quote(lines, rules=(), coupon=None, code=None, customer=None, ship=None, tax=None, dest=None):
    return build_quote(
        list(lines), now=NOW, rules=list(rules), coupon=coupon, coupon_code=code,
        customer=customer or Customer(email="a@example.com"),
        shipping_cfg=ship or ShippingConfig(), tax_cfg=tax or TaxConfig(), destination=dest or Destination("US", "IL"),
    )


class MoneyTests(unittest.TestCase):
    def test_rounding_is_half_up(self):
        self.assertEqual(q2(D("2.675")), D("2.68"))
        self.assertEqual(q2(2.675), D("2.68"))
        self.assertEqual(to_cents(D("19.99")), 1999)
        self.assertEqual(from_cents(1999), D("19.99"))

    def test_allocate_adds_up_exactly(self):
        self.assertEqual(allocate(D("10.00"), [D(1), D(1), D(1)]), [D("3.34"), D("3.33"), D("3.33")])
        self.assertEqual(allocate(D("0.01"), [D(5), D(3)]), [D("0.01"), D("0.00")])
        self.assertEqual(allocate(D("5.00"), []), [])
        self.assertEqual(allocate(D("5.00"), [D(0), D(0)]), [D("0.00"), D("0.00")])

    def test_allocate_property(self):
        rng = random.Random(7)
        for _ in range(500):
            total = D(rng.randint(0, 100000)) / 100
            weights = [D(rng.randint(0, 5000)) / 100 for _ in range(rng.randint(1, 8))]
            parts = allocate(total, weights)
            if sum(weights) == 0:
                self.assertEqual(sum(parts), 0)
                continue
            self.assertEqual(sum(parts), q2(total))
            self.assertTrue(all(p >= 0 for p in parts))
            for w, p in zip(weights, parts):
                if w == 0:
                    self.assertEqual(p, 0)


class SaleTests(unittest.TestCase):
    def sale(self, **kw):
        base = dict(id=1, name="Autumn", kind="percent", value=D("20"))
        return SaleRule(**{**base, **kw})

    def product(self, **kw):
        base = dict(id=10, base_price=D("49.99"), category_path="1.4.9")
        return ProductFacts(**{**base, **kw})

    def test_percent_and_fixed(self):
        sp = best_sale(self.product(), [self.sale()], NOW)
        self.assertEqual((sp.price, sp.list_price, sp.percent_off), (D("39.99"), D("49.99"), 20))
        sp = best_sale(self.product(), [self.sale(kind="fixed", value=D("5"))], NOW)
        self.assertEqual(sp.price, D("44.99"))
        self.assertEqual(best_sale(self.product(base_price=D("3")), [self.sale(kind="fixed", value=D("5"))], NOW).price, D("0.00"))

    def test_window_and_active(self):
        self.assertIsNone(best_sale(self.product(), [self.sale(starts_at=NOW + HOUR)], NOW))
        self.assertIsNone(best_sale(self.product(), [self.sale(ends_at=NOW)], NOW))  # ends_at is exclusive
        self.assertIsNone(best_sale(self.product(), [self.sale(is_active=False)], NOW))
        self.assertIsNotNone(best_sale(self.product(), [self.sale(starts_at=NOW - HOUR, ends_at=NOW + HOUR)], NOW))

    def test_scopes(self):
        cat = self.sale(scope="category", category_paths=("1.4",))
        self.assertIsNotNone(best_sale(self.product(category_path="1.4.9"), [cat], NOW))
        self.assertIsNotNone(best_sale(self.product(category_path="1.4"), [cat], NOW))
        self.assertIsNone(best_sale(self.product(category_path="1.40"), [cat], NOW))  # not a prefix match on digits
        self.assertIsNone(best_sale(self.product(category_path=None), [cat], NOW))
        prod = self.sale(scope="products", product_ids=frozenset({10}))
        self.assertIsNotNone(best_sale(self.product(), [prod], NOW))
        self.assertIsNotNone(best_sale(self.product(id=11, parent_id=10), [prod], NOW))  # variants follow the parent
        self.assertIsNone(best_sale(self.product(id=12), [prod], NOW))
        excl = self.sale(exclude_product_ids=frozenset({10}))
        self.assertIsNone(best_sale(self.product(), [excl], NOW))

    def test_best_of_several(self):
        a, b = self.sale(id=1, value=D("10")), self.sale(id=2, value=D("30"))
        self.assertEqual(best_sale(self.product(), [a, b], NOW).sale.id, 2)
        same = best_sale(self.product(), [self.sale(id=5), self.sale(id=3)], NOW)
        self.assertEqual(same.sale.id, 3)  # ties: oldest sale wins


class RuleTests(unittest.TestCase):
    def rule(self, **kw):
        base = dict(id=1, name="Spend 100 save 10%", kind="spend_percent", value=D("10"), threshold_amount=D("100"))
        return CartRuleDef(**{**base, **kw})

    def test_spend_threshold(self):
        self.assertIsNone(evaluate_rule(self.rule(), [line(price="99.99")], NOW))
        r = evaluate_rule(self.rule(), [line(price="100.00")], NOW)
        self.assertEqual(r.discount, D("10.00"))

    def test_qty_rules_and_cap(self):
        r = self.rule(kind="qty_percent", threshold_amount=None, threshold_qty=3, value=D("15"), max_discount=D("20"))
        self.assertIsNone(evaluate_rule(r, [line(qty=2, price="40")], NOW))
        self.assertEqual(evaluate_rule(r, [line(qty=3, price="40")], NOW).discount, D("18.00"))
        self.assertEqual(evaluate_rule(r, [line(qty=3, price="100")], NOW).discount, D("20.00"))  # capped
        fixed = self.rule(kind="qty_fixed", threshold_amount=None, threshold_qty=2, value=D("5"))
        self.assertEqual(evaluate_rule(fixed, [line(qty=2, price="3")], NOW).discount, D("5.00"))  # goods total 6.00

    def test_fixed_never_exceeds_goods(self):
        r = self.rule(kind="spend_fixed", threshold_amount=D("1"), value=D("500"))
        self.assertEqual(evaluate_rule(r, [line(price="20")], NOW).discount, D("20.00"))

    def test_free_shipping_rule(self):
        r = self.rule(kind="free_shipping", value=D("0"), threshold_amount=None)
        res = evaluate_rule(r, [line(price="5")], NOW)
        self.assertTrue(res.free_shipping)
        self.assertEqual(res.discount, 0)

    def test_scoped_rule_only_counts_matching_lines(self):
        r = self.rule(scope=Scope("category", category_paths=("1.2",)), threshold_amount=D("60"))
        mixed = [line(1, price="40", category="1.2"), line(2, price="40", category="3.1")]
        self.assertIsNone(evaluate_rule(r, mixed, NOW))
        both = [line(1, price="70", category="1.2"), line(2, price="40", category="3.1")]
        self.assertEqual(evaluate_rule(r, both, NOW).discount, D("7.00"))  # 10% of the matching 70 only

    def test_exclude_sale_items(self):
        r = self.rule(scope=Scope(exclude_sale_items=True), threshold_amount=D("50"))
        on_sale = line(price="40", list_price="60")
        self.assertIsNone(evaluate_rule(r, [on_sale], NOW))

    def test_next_rewards(self):
        rules = [self.rule(id=1), self.rule(id=2, kind="qty_percent", threshold_amount=None, threshold_qty=3, value=D("5"))]
        rewards = next_rewards(rules, [line(price="80")], NOW)
        by_id = {r.rule.id: r for r in rewards}
        self.assertEqual(by_id[1].remaining_amount, D("20.00"))
        self.assertEqual(by_id[2].remaining_qty, 2)
        self.assertEqual(next_rewards(rules, [], NOW), [])  # nothing to suggest for an empty cart
        self.assertEqual([r.rule.id for r in next_rewards(rules, [line(price="200")], NOW)], [2])  # rule 1 already met


class CouponTests(unittest.TestCase):
    def coupon(self, **kw):
        base = dict(id=1, code="SAVE10", kind="percent", value=D("10"))
        return CouponDef(**{**base, **kw})

    def problem(self, coupon, lines=None, customer=None):
        return coupon_problem(coupon, lines or [line(price="60")], customer or Customer("a@example.com"), NOW)

    def test_ok(self):
        self.assertIsNone(self.problem(self.coupon()))

    def test_basic_problems(self):
        self.assertEqual(self.problem(self.coupon(is_active=False)), "inactive")
        self.assertEqual(self.problem(self.coupon(starts_at=NOW + HOUR)), "not_started")
        self.assertEqual(self.problem(self.coupon(expires_at=NOW)), "expired")
        self.assertEqual(self.problem(self.coupon(usage_limit=5, used_count=5)), "used_up")
        self.assertEqual(self.problem(self.coupon(min_subtotal=D("100"))), "min_subtotal")
        self.assertEqual(self.problem(self.coupon(scope=Scope("products", product_ids=frozenset({99})))), "no_eligible_items")

    def test_customer_rules(self):
        assigned = self.coupon(assigned_email="Ana@Example.com")
        self.assertIsNone(self.problem(assigned, customer=Customer(" ana@example.com ")))
        self.assertEqual(self.problem(assigned, customer=Customer("bob@example.com")), "wrong_customer")
        self.assertEqual(self.problem(assigned, customer=Customer(None)), "needs_email")
        self.assertEqual(self.problem(self.coupon(per_customer_limit=1), customer=Customer(None)), "needs_email")
        self.assertEqual(self.problem(self.coupon(per_customer_limit=1), customer=Customer("a@x.com", coupon_uses=1)), "per_customer_limit")
        self.assertEqual(self.problem(self.coupon(first_order_only=True), customer=Customer("a@x.com", prior_orders=2)), "first_order_only")
        self.assertIsNone(self.problem(self.coupon(first_order_only=True), customer=Customer("a@x.com", prior_orders=0)))

    def test_saving(self):
        ls = [line(price="60")]
        self.assertEqual(coupon_saving(self.coupon(), ls), D("6.00"))
        self.assertEqual(coupon_saving(self.coupon(max_discount=D("4")), ls), D("4.00"))
        self.assertEqual(coupon_saving(self.coupon(kind="fixed", value=D("15")), ls), D("15.00"))
        self.assertEqual(coupon_saving(self.coupon(kind="fixed", value=D("150")), ls), D("60.00"))
        self.assertEqual(coupon_saving(self.coupon(kind="free_shipping"), ls), D("0.00"))
        self.assertEqual(coupon_saving(self.coupon(scope=Scope(exclude_sale_items=True)), [line(price="40", list_price="60")]), D("0.00"))


class ShippingTaxTests(unittest.TestCase):
    def test_shipping(self):
        cfg = ShippingConfig(flat_rate=D("8.95"), free_threshold=D("100"))
        dest = Destination("US", "IL")
        flat = shipping_for(cfg, dest, D("60"), False)
        self.assertEqual((flat.amount, flat.free, flat.remaining_for_free), (D("8.95"), False, D("40.00")))
        self.assertTrue(shipping_for(cfg, dest, D("100"), False).free)
        self.assertEqual(shipping_for(cfg, dest, D("10"), True).reason, "offer")
        self.assertTrue(shipping_for(cfg, dest, D("0"), False, has_items=False).free)
        no_intl = shipping_for(cfg, Destination("CA"), D("50"), False)
        self.assertFalse(no_intl.deliverable)
        intl = ShippingConfig(international_rate=D("24"), allowed_countries=("US", "CA"))
        self.assertEqual(shipping_for(intl, Destination("ca"), D("50"), False).amount, D("24.00"))
        no_threshold = ShippingConfig(free_threshold=None)
        self.assertIsNone(shipping_for(no_threshold, dest, D("10"), False).remaining_for_free)

    def test_tax(self):
        cfg = TaxConfig(enabled=True, rate_percent=D("10.25"), regions=("IL",))
        self.assertEqual(tax_for(cfg, Destination("US", "Illinois"), D("100"), D("9")).amount, D("10.25"))
        self.assertEqual(tax_for(cfg, Destination("US", "il"), D("100"), D("9")).amount, D("10.25"))
        self.assertIsNone(tax_for(cfg, Destination("US", "WI"), D("100"), D("9")))
        self.assertIsNone(tax_for(cfg, Destination("US", None), D("100"), D("9")))
        self.assertIsNone(tax_for(cfg, Destination("CA", "ON"), D("100"), D("9")))
        self.assertIsNone(tax_for(TaxConfig(enabled=False, rate_percent=D("10")), Destination("US", "IL"), D("100"), D("0")))
        with_ship = TaxConfig(enabled=True, rate_percent=D("10"), shipping_taxable=True)
        self.assertEqual(tax_for(with_ship, Destination("US", "IL"), D("100"), D("10")).amount, D("11.00"))
        self.assertEqual(region_code("New York"), "NY")


class QuoteTests(unittest.TestCase):
    def test_plain_cart(self):
        q = quote([line(price="40", qty=2)])
        self.assertEqual((q.subtotal, q.discount_total, q.shipping.amount, q.total), (D("80.00"), D("0.00"), D("8.95"), D("88.95")))
        self.assertEqual(q.rewards, [])

    def test_sale_savings_reported(self):
        q = quote([line(price="40", list_price="50", qty=2)])
        self.assertEqual((q.list_subtotal, q.subtotal, q.sale_savings), (D("100.00"), D("80.00"), D("20.00")))

    def test_free_shipping_after_discounts(self):
        coupon = CouponDef(id=1, code="TENOFF", kind="fixed", value=D("10"))
        q = quote([line(price="105")], coupon=coupon, code="TENOFF")
        self.assertEqual(q.goods_after_discounts, D("95.00"))
        self.assertFalse(q.shipping.free)  # 95 is under the 100 threshold once the code is applied
        self.assertEqual(q.shipping.remaining_for_free, D("5.00"))

    def test_rule_vs_coupon_best_offer(self):
        rule = CartRuleDef(id=1, name="Spend 100 save 10%", kind="spend_percent", value=D("10"), threshold_amount=D("100"))
        small = CouponDef(id=1, code="SMALL", kind="fixed", value=D("5"))
        big = CouponDef(id=2, code="BIG", kind="percent", value=D("25"))
        q = quote([line(price="200")], rules=[rule], coupon=small, code="SMALL")
        self.assertEqual([d.type for d in q.discounts], ["rule"])
        self.assertEqual(q.discount_total, D("20.00"))
        self.assertTrue(q.coupon.valid)
        self.assertFalse(q.coupon.applied)
        self.assertEqual(q.coupon.reason, "better_offer")
        q = quote([line(price="200")], rules=[rule], coupon=big, code="BIG")
        self.assertEqual([d.type for d in q.discounts], ["coupon"])
        self.assertEqual(q.discount_total, D("50.00"))
        self.assertTrue(q.coupon.applied)

    def test_stackable_coupon_applies_on_top_of_rule(self):
        rule = CartRuleDef(id=1, name="Spend 100 save 10%", kind="spend_percent", value=D("10"), threshold_amount=D("100"))
        coupon = CouponDef(id=1, code="EXTRA", kind="percent", value=D("10"), stackable=True)
        q = quote([line(price="200")], rules=[rule], coupon=coupon, code="EXTRA")
        self.assertEqual([d.amount for d in q.discounts], [D("20.00"), D("18.00")])  # 10% then 10% of the remaining 180
        self.assertEqual(q.discount_total, D("38.00"))

    def test_invalid_coupon_reports_reason_and_changes_nothing(self):
        expired = CouponDef(id=1, code="OLD", kind="percent", value=D("50"), expires_at=NOW - HOUR)
        q = quote([line(price="60")], coupon=expired, code="OLD")
        self.assertEqual((q.coupon.valid, q.coupon.reason, q.discount_total), (False, "expired", D("0.00")))
        q = quote([line(price="60")], coupon=None, code="NOPE")
        self.assertEqual((q.coupon.valid, q.coupon.reason), (False, "unknown"))

    def test_free_shipping_coupon_and_rule(self):
        coupon = CouponDef(id=1, code="SHIPFREE", kind="free_shipping")
        q = quote([line(price="30")], coupon=coupon, code="SHIPFREE")
        self.assertEqual((q.shipping.amount, q.shipping.free, q.discount_total, q.total), (D("0.00"), True, D("0.00"), D("30.00")))
        self.assertEqual([d.type for d in q.discounts], ["free_shipping"])
        rule = CartRuleDef(id=2, name="Weekend free shipping", kind="free_shipping")
        q = quote([line(price="30")], rules=[rule])
        self.assertTrue(q.shipping.free)
        self.assertEqual(q.discounts[0].label, "Weekend free shipping")

    def test_tax_on_discounted_goods(self):
        coupon = CouponDef(id=1, code="TEN", kind="percent", value=D("10"))
        q = quote([line(price="200")], coupon=coupon, code="TEN", tax=TaxConfig(enabled=True, rate_percent=D("10.25")), dest=Destination("US", "IL"))
        self.assertEqual(q.tax.amount, D("18.45"))  # 10.25% of 180
        self.assertEqual(q.total, D("198.45"))
        q = quote([line(price="200")], tax=TaxConfig(enabled=True, rate_percent=D("10.25")), dest=Destination("US", "WI"))
        self.assertIsNone(q.tax)

    def test_line_discounts_sum_to_total(self):
        coupon = CouponDef(id=1, code="X", kind="fixed", value=D("10"))
        lines = [line(1, price="33.33", qty=1), line(2, price="33.33", qty=1), line(3, price="33.34", qty=1)]
        q = quote(lines, coupon=coupon, code="X")
        self.assertEqual(sum(q.line_discounts), D("10.00"))
        self.assertTrue(all(0 <= d <= l.total for d, l in zip(q.line_discounts, q.lines)))

    def test_empty_cart(self):
        q = quote([])
        self.assertEqual((q.subtotal, q.total, q.shipping.free), (D("0.00"), D("0.00"), True))

    def test_random_carts_keep_invariants(self):
        rng = random.Random(42)
        for _ in range(1500):
            lines = [
                line(i, qty=rng.randint(1, 4), price=f"{rng.randint(1, 30000) / 100:.2f}",
                     list_price=None, category=rng.choice(["1.2", "1.3", "2.1", None]))
                for i in range(1, rng.randint(1, 5) + 1)
            ]
            rules = [CartRuleDef(id=1, name="r", kind=rng.choice(["spend_percent", "spend_fixed", "qty_percent", "qty_fixed", "free_shipping"]),
                                 value=D(rng.randint(1, 40)), threshold_amount=D(rng.randint(10, 300)), threshold_qty=rng.randint(1, 5),
                                 max_discount=rng.choice([None, D("15")]),
                                 scope=rng.choice([Scope(), Scope("category", category_paths=("1.2",))]))]
            coupon = CouponDef(id=1, code="C", kind=rng.choice(["percent", "fixed", "free_shipping"]), value=D(rng.randint(1, 60)),
                               max_discount=rng.choice([None, D("12")]), stackable=rng.random() < 0.5,
                               scope=rng.choice([Scope(), Scope("products", product_ids=frozenset({1, 2}))]))
            q = quote(lines, rules=rules, coupon=coupon, code="C", tax=TaxConfig(enabled=True, rate_percent=D("8.25")),
                      dest=Destination("US", rng.choice(["IL", "WI"])))
            self.assertGreaterEqual(q.discount_total, 0)
            self.assertLessEqual(q.discount_total, q.subtotal)
            self.assertEqual(sum(q.line_discounts), q.discount_total)
            for d, l in zip(q.line_discounts, q.lines):
                self.assertTrue(0 <= d <= l.total, (d, l))
            self.assertEqual(q.total, q.subtotal - q.discount_total + q.shipping.amount + (q.tax.amount if q.tax else 0))
            self.assertGreaterEqual(q.total, 0)


if __name__ == "__main__":
    unittest.main()
