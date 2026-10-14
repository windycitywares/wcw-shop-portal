import unittest

from app.domain import tracking as t


class CleanPathTests(unittest.TestCase):
    def test_drops_query_fragment_and_locale(self):
        self.assertEqual(t.clean_path("/es/product/oak-urn?utm_source=x#reviews"), "/product/oak-urn")
        self.assertEqual(t.clean_path("/nl"), "/")
        self.assertEqual(t.clean_path("/"), "/")

    def test_full_urls_keep_only_the_path(self):
        self.assertEqual(t.clean_path("https://shop.windycitywares.com/shop?page=2"), "/shop")

    def test_private_links_collapse(self):
        self.assertEqual(t.clean_path("/order/abc123SECRET"), "/order/:token")
        self.assertEqual(t.clean_path("/nl/order/abc123SECRET?x=1"), "/order/:token")
        self.assertEqual(t.clean_path("/reset-password?token=zzz"), "/reset-password")
        self.assertEqual(t.clean_path("/unsubscribe?token=zzz"), "/unsubscribe")

    def test_trailing_slash_and_doubles(self):
        self.assertEqual(t.clean_path("//shop//"), "/shop")

    def test_rejects_junk(self):
        self.assertIsNone(t.clean_path(""))
        self.assertIsNone(t.clean_path(None))
        self.assertIsNone(t.clean_path("javascript:alert(1)"))
        self.assertEqual(len(t.clean_path("/" + "a" * 500)), t.MAX_PATH)

    def test_locale_prefix_needs_a_boundary(self):
        self.assertEqual(t.clean_path("/espresso"), "/espresso")
        self.assertEqual(t.clean_path("/nlx/y"), "/nlx/y")


class CleanTermTests(unittest.TestCase):
    def test_normalises(self):
        self.assertEqual(t.clean_term("  Oak   URN "), "oak urn")

    def test_personal_data_is_dropped(self):
        self.assertIsNone(t.clean_term("jane.doe@example.com"))
        self.assertIsNone(t.clean_term("call 312 555 0100"))
        self.assertIsNone(t.clean_term("a"))
        self.assertIsNone(t.clean_term(5))

    def test_short_numbers_are_fine(self):
        self.assertEqual(t.clean_term("urn 200 cubic inch"), "urn 200 cubic inch")


class CleanDataTests(unittest.TestCase):
    def test_keeps_scalars_only(self):
        out = t.clean_data({"qty": 2, "ok": True, "label": "x" * 500, "nested": {"a": 1}, "list": [1], "Bad-Key": 1})
        self.assertEqual(out["qty"], 2)
        self.assertEqual(out["ok"], True)
        self.assertEqual(len(out["label"]), t.MAX_DATA_TEXT)
        self.assertNotIn("nested", out)
        self.assertNotIn("list", out)
        self.assertNotIn("Bad-Key", out)

    def test_emails_in_values_are_dropped(self):
        self.assertEqual(t.clean_data({"note": "me@example.com"}), {})

    def test_limits_the_number_of_keys(self):
        self.assertEqual(len(t.clean_data({f"k{i}": i for i in range(20)})), t.MAX_DATA_KEYS)


class CleanEventTests(unittest.TestCase):
    def test_unknown_type_is_dropped(self):
        self.assertIsNone(t.clean_event({"type": "keylogger"}))
        self.assertIsNone(t.clean_event({}))

    def test_search_needs_a_clean_term(self):
        row = t.clean_event({"type": "search", "path": "/search?q=a", "data": {"q": " Oak Urn ", "results": 4}})
        self.assertEqual(row["data"], {"q": "oak urn", "results": 4})
        self.assertEqual(row["path"], "/search")
        self.assertIsNone(t.clean_event({"type": "search", "data": {"q": "me@example.com"}}))
        self.assertIsNone(t.clean_event({"type": "search", "data": {}}))

    def test_search_results_must_be_a_sane_number(self):
        row = t.clean_event({"type": "search", "data": {"q": "urn", "results": "many"}})
        self.assertIsNone(row["data"]["results"])
        row = t.clean_event({"type": "search", "data": {"q": "urn", "results": True}})
        self.assertIsNone(row["data"]["results"])

    def test_product_events_need_a_product(self):
        self.assertIsNone(t.clean_event({"type": "add_to_cart"}))
        row = t.clean_event({"type": "add_to_cart", "product_id": 7, "value": 49.5, "data": {"qty": 1}})
        self.assertEqual(row["product_id"], 7)

    def test_web_vitals_are_validated(self):
        ok = t.clean_event({"type": "web_vital", "path": "/shop", "value": 1800, "data": {"name": "LCP", "extra": "x"}})
        self.assertEqual(ok["data"], {"name": "LCP"})
        self.assertIsNone(t.clean_event({"type": "web_vital", "value": 5, "data": {"name": "FOO"}}))
        self.assertIsNone(t.clean_event({"type": "web_vital", "value": -1, "data": {"name": "CLS"}}))
        self.assertIsNone(t.clean_event({"type": "web_vital", "value": 99999999, "data": {"name": "LCP"}}))

    def test_client_error_is_shortened(self):
        row = t.clean_event({"type": "client_error", "data": {"message": "x" * 400}})
        self.assertEqual(len(row["data"]["message"]), t.MAX_DATA_TEXT)


if __name__ == "__main__":
    unittest.main()
