import unittest

from app.domain.carriers import canonical_carrier, tracking_url


class Carriers(unittest.TestCase):
    def test_canonical_names(self):
        self.assertEqual(canonical_carrier(" usps "), "USPS")
        self.assertEqual(canonical_carrier("fedex"), "FedEx")
        self.assertEqual(canonical_carrier("Local courier"), "Local courier")
        self.assertIsNone(canonical_carrier("  "))
        self.assertIsNone(canonical_carrier(None))

    def test_tracking_links(self):
        self.assertEqual(tracking_url("UPS", "1Z 999 AA1"), "https://www.ups.com/track?tracknum=1Z999AA1")
        self.assertIsNone(tracking_url("Local courier", "123"))
        self.assertIsNone(tracking_url("USPS", ""))
        self.assertIn("a%26b", tracking_url("USPS", "a&b"))


if __name__ == "__main__":
    unittest.main()
