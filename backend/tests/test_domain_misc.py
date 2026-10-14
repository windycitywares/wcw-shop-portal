import unittest
from datetime import date, datetime, timezone
from decimal import Decimal as D

from app.domain import csvsafe
from app.domain.coupons import MAX_BATCH, generate_code, generate_codes, is_valid_code, normalize_code
from app.domain.order_flow import can_transition, payment_status_after_refund, refundable
from app.domain.timeutil import DateRange, _UsCentral, day_start_utc, resolve_range, store_today


class CouponCodeTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_code(" welcome-10 "), "WELCOME10")
        self.assertEqual(normalize_code(None), "")
        self.assertTrue(is_valid_code("ABC"))
        self.assertFalse(is_valid_code("AB"))
        self.assertFalse(is_valid_code("a b"))

    def test_generate(self):
        code = generate_code("thanks-", 8)
        self.assertTrue(code.startswith("THANKS"))
        self.assertEqual(len(code), 14)
        self.assertTrue(is_valid_code(code))
        self.assertTrue(all(c not in "01OI" for c in code[6:]))

    def test_generate_many_unique_and_avoid_taken(self):
        taken = {generate_code("X") for _ in range(50)}
        codes = generate_codes(2000, "X", 8, taken)
        self.assertEqual(len(codes), len(set(codes)))
        self.assertFalse(set(codes) & taken)

    def test_limits(self):
        with self.assertRaises(ValueError):
            generate_codes(0)
        with self.assertRaises(ValueError):
            generate_codes(MAX_BATCH + 1)


class OrderFlowTests(unittest.TestCase):
    def test_transitions(self):
        self.assertTrue(can_transition("pending", "paid"))
        self.assertTrue(can_transition("paid", "shipped"))
        self.assertTrue(can_transition("shipped", "delivered"))
        self.assertFalse(can_transition("pending", "shipped"))
        self.assertFalse(can_transition("delivered", "paid"))
        self.assertFalse(can_transition("cancelled", "paid"))
        self.assertFalse(can_transition("nonsense", "paid"))

    def test_refund_status(self):
        self.assertEqual(payment_status_after_refund(D("100"), D("0")), "paid")
        self.assertEqual(payment_status_after_refund(D("100"), D("25.50")), "partially_refunded")
        self.assertEqual(payment_status_after_refund(D("100"), D("100")), "refunded")
        self.assertEqual(refundable(D("100"), D("40")), D("60.00"))
        self.assertEqual(refundable(D("100"), D("140")), D("0.00"))


class CsvTests(unittest.TestCase):
    def test_formula_injection_is_neutralised(self):
        self.assertEqual(csvsafe.cell("=HYPERLINK(\"http://x\")"), "'=HYPERLINK(\"http://x\")")
        self.assertEqual(csvsafe.cell("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(csvsafe.cell("+1 555"), "'+1 555")
        self.assertEqual(csvsafe.cell("-5"), "-5")  # a real negative number stays a number
        self.assertEqual(csvsafe.cell("-cmd|calc"), "'-cmd|calc")
        self.assertEqual(csvsafe.cell(None), "")
        self.assertEqual(csvsafe.cell(D("3.5")), "3.50")
        self.assertEqual(csvsafe.cell(True), "yes")
        self.assertEqual(csvsafe.cell(date(2026, 10, 14)), "2026-10-14")

    def test_to_csv(self):
        text = csvsafe.to_csv(["a", "b"], [[1, "x,y"], [None, '"q"']])
        self.assertEqual(text, 'a,b\r\n1,"x,y"\r\n,"""q"""\r\n')


class TimeTests(unittest.TestCase):
    def test_fallback_central_matches_dst_rules(self):
        tz = _UsCentral()
        self.assertEqual(datetime(2026, 7, 4, 12, tzinfo=tz).utcoffset().total_seconds(), -5 * 3600)
        self.assertEqual(datetime(2026, 1, 4, 12, tzinfo=tz).utcoffset().total_seconds(), -6 * 3600)
        self.assertEqual(datetime(2026, 3, 8, 1, 59, tzinfo=tz).utcoffset().total_seconds(), -6 * 3600)  # before the jump
        self.assertEqual(datetime(2026, 3, 8, 3, 0, tzinfo=tz).utcoffset().total_seconds(), -5 * 3600)
        self.assertEqual(datetime(2026, 11, 1, 1, 0, tzinfo=tz).utcoffset().total_seconds(), -5 * 3600)
        self.assertEqual(datetime(2026, 11, 1, 3, 0, tzinfo=tz).utcoffset().total_seconds(), -6 * 3600)

    def test_fallback_agrees_with_zoneinfo_when_available(self):
        try:
            from zoneinfo import ZoneInfo

            real = ZoneInfo("America/Chicago")
        except Exception:
            self.skipTest("no tz database")
        fallback = _UsCentral()
        for month in range(1, 13):
            for day in (1, 10, 15, 28):
                d = datetime(2026, month, day, 12)
                self.assertEqual(d.replace(tzinfo=real).utcoffset(), d.replace(tzinfo=fallback).utcoffset(), d)

    def test_day_bounds_in_utc(self):
        self.assertEqual(day_start_utc(date(2026, 10, 14)), datetime(2026, 10, 14, 5, 0, tzinfo=timezone.utc))  # CDT = UTC-5
        self.assertEqual(day_start_utc(date(2026, 12, 1)), datetime(2026, 12, 1, 6, 0, tzinfo=timezone.utc))  # CST = UTC-6

    def test_ranges(self):
        r = resolve_range(None, None, 30, today=date(2026, 10, 14))
        self.assertEqual((r.start, r.end, r.days), (date(2026, 9, 15), date(2026, 10, 14), 30))
        prev = r.previous()
        self.assertEqual((prev.start, prev.end, prev.days), (date(2026, 8, 16), date(2026, 9, 14), 30))
        swapped = resolve_range(date(2026, 10, 10), date(2026, 10, 1), today=date(2026, 10, 14))
        self.assertEqual((swapped.start, swapped.end), (date(2026, 10, 1), date(2026, 10, 10)))
        self.assertEqual(resolve_range(date(2020, 1, 1), None, today=date(2026, 10, 14)).days, 800)
        self.assertEqual(resolve_range(None, date(2030, 1, 1), 7, today=date(2026, 10, 14)).end, date(2026, 10, 15))
        self.assertEqual(DateRange(date(2026, 1, 1), date(2026, 1, 31)).granularity(), "day")
        self.assertEqual(DateRange(date(2026, 1, 1), date(2026, 6, 30)).granularity(), "week")
        self.assertEqual(DateRange(date(2025, 1, 1), date(2026, 6, 30)).granularity(), "month")
        self.assertEqual(len(r.each_day()), 30)
        self.assertIsInstance(store_today(), date)


if __name__ == "__main__":
    unittest.main()
