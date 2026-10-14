import unittest

from app.domain import catalog_health as ch

GOOD = {"id": 1, "title": "Oak Urn", "slug": "oak-urn", "description": "x" * 200, "base_price": 100, "cost_price": 40, "category_id": 3,
        "seo_description": "A handsome oak urn", "images": 4, "tags": 5}


class CatalogHealthTests(unittest.TestCase):
    def test_complete_listing_scores_100(self):
        score, failed = ch.product_score(GOOD)
        self.assertEqual((score, failed), (100, []))

    def test_each_rule_fires_on_its_own(self):
        cases = {
            "no_price": {"base_price": 0},
            "no_photos": {"images": 0},
            "few_photos": {"images": 2},
            "short_description": {"description": "short"},
            "no_category": {"category_id": None},
            "no_tags": {"tags": 0},
            "no_seo": {"seo_description": "  "},
            "no_cost": {"cost_price": None},
        }
        for key, change in cases.items():
            _, failed = ch.product_score({**GOOD, **change})
            self.assertEqual([c.key for c in failed], [key], key)

    def test_a_cost_of_zero_counts_as_entered(self):
        self.assertEqual(ch.product_score({**GOOD, "cost_price": 0})[0], 100)

    def test_weights_drive_the_score(self):
        no_photos, _ = ch.product_score({**GOOD, "images": 0})
        no_cost, _ = ch.product_score({**GOOD, "cost_price": None})
        self.assertLess(no_photos, no_cost)
        self.assertEqual(no_photos, round(100 * (ch.TOTAL_WEIGHT - 3) / ch.TOTAL_WEIGHT))

    def test_assess_averages_and_lists_the_worst_first(self):
        rows = [GOOD, {**GOOD, "id": 2, "title": "Bare", "images": 0, "description": None, "category_id": None, "tags": 0}]
        result = ch.assess(rows)
        self.assertEqual(result["products"], 2)
        self.assertEqual([w["id"] for w in result["worst"]], [2])
        self.assertEqual(result["issues"]["listings without photos"], 1)
        self.assertNotIn("listings with no price", result["issues"])
        self.assertTrue(50 < result["score"] < 100)
        self.assertIn("Add product photos", result["worst"][0]["problems"])

    def test_empty_catalog_has_no_score(self):
        self.assertIsNone(ch.assess([])["score"])

    def test_ties_break_by_id_so_the_list_is_stable(self):
        rows = [{**GOOD, "id": i, "tags": 0} for i in (5, 2, 9)]
        self.assertEqual([w["id"] for w in ch.assess(rows)["worst"]], [9, 5, 2])


if __name__ == "__main__":
    unittest.main()
