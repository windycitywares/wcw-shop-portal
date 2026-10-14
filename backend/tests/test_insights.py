import unittest

from app.domain import insights as ins


def keys(metrics):
    return [i.key for i in ins.generate(metrics)]


class InsightTests(unittest.TestCase):
    def test_empty_metrics_produce_nothing_and_do_not_crash(self):
        self.assertEqual(ins.generate({}), [])
        self.assertEqual(ins.generate({"sessions": 0, "orders": 0, "carts": {}, "devices": {"mobile": {}}}), [])
        self.assertEqual(ins.generate({"carts": "garbage", "setup": "x"}), [])

    def test_small_samples_stay_quiet(self):
        self.assertEqual(keys({"sessions": 40, "session_orders": 0, "conversion_rate": 0.0}), [])
        self.assertEqual(keys({"carts": {"started": 4, "abandonment_rate": 1.0, "abandoned_value": 100}}), [])
        self.assertEqual(keys({"orders": 3, "discount_share": 0.9}), [])

    def test_setup_gaps_critical_without_payments(self):
        out = ins.generate({"setup": {"payments_live": False, "tax_configured": False, "email_configured": True}})
        self.assertEqual(out[0].key, "setup_gaps")
        self.assertEqual(out[0].severity, "critical")
        self.assertEqual(len(out[0].metrics["missing"]), 2)
        ok = ins.generate({"setup": {"payments_live": True, "tax_configured": False, "email_configured": True}})
        self.assertEqual(ok[0].severity, "warning")
        self.assertEqual(ins.generate({"setup": {"payments_live": True, "tax_configured": True}}), [])

    def test_funnel_rules(self):
        self.assertIn("low_conversion", keys({"sessions": 500, "session_orders": 2, "conversion_rate": 0.004}))
        self.assertNotIn("low_conversion", keys({"sessions": 500, "session_orders": 10, "conversion_rate": 0.02}))
        self.assertIn("cart_abandonment", keys({"carts": {"started": 40, "abandonment_rate": 0.82, "abandoned_value": 2400}}))
        self.assertNotIn("cart_abandonment", keys({"carts": {"started": 40, "abandonment_rate": 0.6}}))
        self.assertIn("checkout_drop", keys({"checkout": {"started": 20, "completed": 5}}))
        self.assertNotIn("checkout_drop", keys({"checkout": {"started": 20, "completed": 15}}))
        gap = {"devices": {"mobile": {"sessions": 400, "orders": 1}, "desktop": {"sessions": 300, "orders": 9}}}
        self.assertIn("mobile_gap", keys(gap))
        fine = {"devices": {"mobile": {"sessions": 400, "orders": 8}, "desktop": {"sessions": 300, "orders": 9}}}
        self.assertNotIn("mobile_gap", keys(fine))

    def test_catalog_and_stock_rules(self):
        self.assertIn("low_stock", keys({"low_stock": [{"title": "Oak urn", "stock": 2, "sold_30d": 6}]}))
        self.assertIn("stockout_demand", keys({"stockout_demand": [{"title": "Vase", "requests": 4}]}))
        self.assertIn("dead_stock", keys({"dead_stock": {"count": 5, "value": 420.0}}))
        self.assertNotIn("dead_stock", keys({"dead_stock": {"count": 2, "value": 40.0}}))
        self.assertIn("catalog_health", keys({"catalog_score": 62, "catalog_issues": {"products without photos": 4, "missing translations": 20}}))
        self.assertNotIn("catalog_health", keys({"catalog_score": 92, "catalog_issues": {}}))
        self.assertIn("zero_results", keys({"zero_result_searches": [{"q": "cat urn", "n": 4}, {"q": "tiny", "n": 1}]}))
        self.assertNotIn("zero_results", keys({"zero_result_searches": [{"q": "x", "n": 1}]}))
        self.assertIn("viewed_not_bought", keys({"viewed_not_bought": [{"title": "Teak urn", "views": 80, "orders": 0}]}))

    def test_money_rules(self):
        self.assertIn("discount_dependency", keys({"orders": 40, "discount_share": 0.6}))
        self.assertIn("refund_rate", keys({"orders": 40, "refund_rate": 0.1}))
        self.assertIn("free_shipping_nudge", keys({"free_shipping": {"threshold": 100, "near_share": 0.3, "aov": 82.0}}))
        self.assertIn("repeat_rate", keys({"customers": 100, "repeat_rate": 0.03}))
        self.assertIn("channel_concentration", keys({"orders": 30, "channel_share": {"marketplace": 0.85, "direct": 0.15}}))
        self.assertNotIn("channel_concentration", keys({"orders": 30, "channel_share": {"marketplace": 0.5, "direct": 0.5}}))

    def test_engagement_and_quality_rules(self):
        self.assertIn("pending_reviews", keys({"pending_reviews": 3}))
        self.assertIn("review_rate", keys({"orders": 60, "review_rate": 0.01}))
        out = ins.generate({"unshipped_over_2d": 4})
        self.assertEqual((out[0].key, out[0].severity), ("unshipped_orders", "critical"))
        self.assertIn("newsletter_capture", keys({"newsletter": {"signups": 2, "sessions": 900}}))
        self.assertIn("slow_lcp", keys({"web_vitals": {"lcp_p75_ms": 3600}}))
        self.assertIn("layout_shift", keys({"web_vitals": {"lcp_p75_ms": 1800, "cls_p75": 0.25}}))
        self.assertIn("low_consent", keys({"consent_rate": 0.2, "consent_decisions": 200}))
        self.assertIn("healthy_conversion", keys({"sessions": 600, "conversion_rate": 0.03}))

    def test_sorted_by_severity_and_limit(self):
        m = {"setup": {"payments_live": False}, "pending_reviews": 2, "sessions": 600, "conversion_rate": 0.03,
             "low_stock": [{"title": "A", "stock": 1, "sold_30d": 2}]}
        out = ins.generate(m)
        order = [ins.SEVERITY_ORDER[i.severity] for i in out]
        self.assertEqual(order, sorted(order))
        self.assertEqual(out[0].severity, "critical")
        self.assertEqual(len(ins.generate(m, limit=2)), 2)
        self.assertIsInstance(out[0].as_dict()["metrics"], dict)

    def test_every_insight_has_text_and_a_known_severity(self):
        m = {
            "setup": {"payments_live": False, "tax_configured": False}, "sessions": 800, "session_orders": 2, "conversion_rate": 0.0025,
            "carts": {"started": 30, "abandonment_rate": 0.9, "abandoned_value": 900}, "checkout": {"started": 20, "completed": 3},
            "orders": 50, "discount_share": 0.7, "refund_rate": 0.12, "customers": 80, "repeat_rate": 0.02,
            "low_stock": [{"title": "A", "stock": 1, "sold_30d": 3}], "stockout_demand": [{"title": "B", "requests": 3}],
            "dead_stock": {"count": 9, "value": 800.0}, "catalog_score": 50, "catalog_issues": {"x": 3},
            "zero_result_searches": [{"q": "q", "n": 5}], "viewed_not_bought": [{"title": "T", "views": 90, "orders": 0}],
            "pending_reviews": 2, "review_rate": 0.0, "unshipped_over_2d": 1, "web_vitals": {"lcp_p75_ms": 4000},
            "newsletter": {"signups": 1, "sessions": 1000}, "consent_rate": 0.1, "consent_decisions": 400,
            "free_shipping": {"threshold": 100, "near_share": 0.4, "aov": 70}, "channel_share": {"direct": 0.9},
        }
        out = ins.generate(m)
        self.assertGreaterEqual(len(out), 15)
        self.assertEqual(len({i.key for i in out}), len(out))
        for i in out:
            self.assertIn(i.severity, ins.SEVERITY_ORDER)
            self.assertTrue(i.title and i.detail)
            if i.href:
                self.assertTrue(i.href.startswith("/admin"))


if __name__ == "__main__":
    unittest.main()
