import unittest

from app.domain.variants import next_variant_sku


class NextVariantSkuTests(unittest.TestCase):
    def test_continues_the_numbering(self):
        existing = [f"ETSY-4519546536-{n}" for n in range(1, 7)]
        self.assertEqual(next_variant_sku("ETSY-4519546536", existing), "ETSY-4519546536-7")

    def test_first_variant_and_gaps(self):
        self.assertEqual(next_variant_sku("OAK-URN", []), "OAK-URN-1")
        self.assertEqual(next_variant_sku("OAK-URN", ["OAK-URN-1", "OAK-URN-4", "OAK-URN-LARGE"]), "OAK-URN-5")

    def test_never_returns_a_taken_sku_and_ignores_case(self):
        self.assertEqual(next_variant_sku("oak", ["OAK-2", "oak-3"]), "oak-4")


if __name__ == "__main__":
    unittest.main()
