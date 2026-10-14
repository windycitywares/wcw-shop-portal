import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from app.domain.rfm import SEGMENTS, CustomerStats, segment_all, segment_of, vip_cutoff

NOW = datetime(2026, 10, 14, tzinfo=timezone.utc)


def stats(orders, days_ago, revenue="100", key="a@x.com"):
    return CustomerStats(key, orders, D(revenue), NOW - timedelta(days=days_ago))


class RfmTests(unittest.TestCase):
    def test_segments(self):
        self.assertEqual(segment_of(stats(1, 10), NOW), "new")
        self.assertEqual(segment_of(stats(1, 100), NOW), "needs_nudge")
        self.assertEqual(segment_of(stats(1, 200), NOW), "lapsed")
        self.assertEqual(segment_of(stats(1, 400), NOW), "lapsed")
        self.assertEqual(segment_of(stats(2, 90), NOW), "active")
        self.assertEqual(segment_of(stats(2, 250), NOW), "at_risk")
        self.assertEqual(segment_of(stats(2, 500), NOW), "lapsed")
        self.assertEqual(segment_of(stats(3, 30), NOW), "loyal")
        self.assertEqual(segment_of(stats(5, 300), NOW), "at_risk")

    def test_vip_overlay(self):
        self.assertEqual(segment_of(stats(1, 10, "900"), NOW, vip_cutoff=D("500")), "vip")
        self.assertEqual(segment_of(stats(1, 10, "100"), NOW, vip_cutoff=D("500")), "new")

    def test_vip_cutoff_needs_enough_customers(self):
        self.assertIsNone(vip_cutoff([D(i) for i in range(1, 9)]))
        cut = vip_cutoff([D(i) for i in range(1, 51)])
        self.assertEqual(cut, D(46))  # top 5 of 50 customers (10%)... but never fewer than 3

    def test_segment_all_uses_only_known_labels(self):
        customers = [stats(1 + i % 4, 5 + i * 9, str(20 + i * 7), key=f"c{i}@x.com") for i in range(60)]
        result = segment_all(customers, NOW)
        self.assertEqual(len(result), 60)
        self.assertTrue(set(result.values()) <= set(SEGMENTS))
        self.assertIn("vip", result.values())


if __name__ == "__main__":
    unittest.main()
