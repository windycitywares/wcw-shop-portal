import unittest
from datetime import datetime, timezone
from decimal import Decimal

from app.domain import etsy_profit as p
from app.domain import etsy_status as s


class ProfitTests(unittest.TestCase):
    def test_revenue_excludes_tax_and_subtracts_discounts(self):
        self.assertEqual(p.revenue("30.00", "5.00", "2.50"), Decimal("32.50"))

    def test_net_and_margin(self):
        r = p.compute(items_total=30, shipping_charged=5, discounts=0, purchase_cost=12, shipping_cost=4, etsy_fees=3.5)
        self.assertEqual(r.total_cost, Decimal("19.50"))
        self.assertEqual(r.net_profit, Decimal("15.50"))
        self.assertEqual(r.margin_pct, Decimal("44.29"))
        self.assertEqual(r.missing, ())

    def test_missing_figures_are_reported_not_guessed(self):
        r = p.compute(items_total=20, shipping_charged=0, discounts=0, purchase_cost=8)
        self.assertEqual(r.missing, ("shipping_cost", "etsy_fees"))
        self.assertEqual(r.net_profit, Decimal("12.00"))

    def test_replacements_and_refunds_reduce_profit(self):
        r = p.compute(items_total=20, shipping_charged=0, discounts=0, purchase_cost=8, shipping_cost=3, etsy_fees=2, extra_costs=11)
        self.assertEqual(r.net_profit, Decimal("-4.00"))

    def test_zero_revenue_has_no_margin(self):
        self.assertIsNone(p.compute(items_total=0, shipping_charged=0, discounts=0).margin_pct)

    def test_days_to_ship(self):
        a = datetime(2026, 11, 1, tzinfo=timezone.utc)
        self.assertEqual(p.days_to_ship(a, datetime(2026, 11, 4, 5, tzinfo=timezone.utc)), 3)
        self.assertIsNone(p.days_to_ship(a, None))


class StatusTests(unittest.TestCase):
    def test_implied(self):
        self.assertEqual(s.etsy_status(canceled=False, shipped=False, delivered=False), s.NEW)
        self.assertEqual(s.etsy_status(canceled=False, shipped=True, delivered=False), s.SHIPPED)
        self.assertEqual(s.etsy_status(canceled=False, shipped=True, delivered=True), s.DELIVERED)
        self.assertEqual(s.etsy_status(canceled=True, shipped=True, delivered=True), s.CANCELLED)

    def test_sync_moves_forward_only(self):
        self.assertEqual(s.sync_target(s.NEW, s.SHIPPED), s.SHIPPED)
        self.assertEqual(s.sync_target(s.PURCHASED, s.NEW), s.PURCHASED)
        self.assertEqual(s.sync_target(s.DELIVERED, s.SHIPPED), s.DELIVERED)

    def test_sync_leaves_team_exceptions_alone(self):
        self.assertEqual(s.sync_target(s.ISSUE, s.SHIPPED), s.ISSUE)
        self.assertEqual(s.sync_target(s.REFUNDED, s.CANCELLED), s.REFUNDED)

    def test_cancel_wins_on_open_order(self):
        self.assertEqual(s.sync_target(s.PURCHASED, s.CANCELLED), s.CANCELLED)

    def test_team_rules(self):
        self.assertTrue(s.can_set_by_team(s.NEW, s.PURCHASED))
        self.assertFalse(s.can_set_by_team(s.NEW, s.NEW))
        self.assertFalse(s.can_set_by_team(s.NEW, "bogus"))


if __name__ == "__main__":
    unittest.main()


class OAuthTests(unittest.TestCase):
    def test_pkce_challenge_matches_the_rfc_example(self):
        from app.domain import etsy_oauth as o

        self.assertEqual(o.challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"), "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")

    def test_authorize_url_carries_state_and_scopes(self):
        from app.domain import etsy_oauth as o

        url = o.authorize_url(client_id="abc", redirect_uri="https://x.test/cb", state="st", verifier="v" * 50)
        self.assertIn("client_id=abc", url)
        self.assertIn("state=st", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("transactions_w", url)

    def test_user_id_from_token(self):
        from app.domain import etsy_oauth as o

        self.assertEqual(o.user_id_from_token("12345.abcdef"), 12345)
        self.assertIsNone(o.user_id_from_token("nope"))
