"""Stock requests, pure rules: option groups, validating a choice, and restock vs special request."""

import unittest

from app.domain import stock_requests as sr


class GroupTests(unittest.TestCase):
    def test_from_variants_or_list_attributes(self):
        variants = [{"Size": "Small", "Wood": "Oak"}, {"Size": "Large", "Wood": "Oak"}, {"Size": "Small", "Wood": "Walnut"}]
        self.assertEqual(sr.option_groups({}, variants), {"Size": ["Small", "Large"], "Wood": ["Oak", "Walnut"]})
        self.assertEqual(sr.option_groups({"Size": ["S", "L"], "Material": "Brass", "One": ["Only"]}, []), {"Size": ["S", "L"]})

    def test_clean_options(self):
        groups = {"Size": ["Small", "Large"]}
        self.assertEqual(sr.clean_options(groups, {"Size": " Large "}), {"Size": "Large"})
        for bad in ({}, {"Size": "Huge"}, {"Size": "Large", "Color": "Red"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                sr.clean_options(groups, bad)
        self.assertEqual(sr.clean_options({}, {}), {})


class ResolveTests(unittest.TestCase):
    variants = [(11, {"Size": "Small", "Wood": "Oak"}, True), (12, {"Size": "Large", "Wood": "Oak"}, False)]

    def test_variants(self):
        self.assertEqual(sr.resolve(1, True, self.variants, {"Size": "Small", "Wood": "Oak"}), sr.Target(11, "restock", True))
        self.assertEqual(sr.resolve(1, True, self.variants, {"Size": "Large", "Wood": "Oak"}), sr.Target(12, "restock", False))
        self.assertEqual(sr.resolve(1, True, self.variants, {"Size": "Large", "Wood": "Walnut"}), sr.Target(1, "request", False))

    def test_single_product(self):
        self.assertEqual(sr.resolve(5, False, [], {"Size": "Large"}), sr.Target(5, "restock", False))
        self.assertTrue(sr.resolve(5, True, [], {}).available)

    def test_describe(self):
        self.assertEqual(sr.describe({"Size": "Large", "Wood": "Oak"}), "Size: Large, Wood: Oak")
        self.assertEqual(sr.describe({}), "")


if __name__ == "__main__":
    unittest.main()
