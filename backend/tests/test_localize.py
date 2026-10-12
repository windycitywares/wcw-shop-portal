import unittest
from datetime import datetime, timezone

from app.schemas.category import CategoryNode
from app.schemas.product import ProductOut
from app.services import localize

NOW = datetime.now(timezone.utc)


def product(**kw) -> ProductOut:
    base = dict(
        id=1, parent_id=None, category_id=None, sku="S1", slug="star-urn", title="Star Urn",
        description="A star.", base_price=10, compare_at_price=None, currency="USD",
        stock_status="in_stock", stock_quantity=1, attributes={}, images=[], tags=[],
        status="published", source="etsy", seo_title="Star Urn for ashes", seo_description="English SEO",
        created_by_id=None, published_at=NOW, created_at=NOW, updated_at=NOW,
        translations={"es": {"title": "Urna Estrella", "description": "Una estrella."}},
    )
    base.update(kw)
    return ProductOut(**base)


class LocalizeTests(unittest.TestCase):
    def test_translated_fields_replace_english_and_seo_is_cleared(self):
        p = product()
        localize.product(p, "es")
        self.assertEqual(p.title, "Urna Estrella")
        self.assertEqual(p.description, "Una estrella.")
        self.assertIsNone(p.seo_title)
        self.assertEqual(p.translations, {})

    def test_missing_language_falls_back_to_english(self):
        p = product()
        localize.product(p, "nl")
        self.assertEqual(p.title, "Star Urn")
        self.assertEqual(p.seo_title, "Star Urn for ashes")

    def test_english_and_keep(self):
        p = product()
        localize.product(p, "en", keep=True)
        self.assertEqual(p.title, "Star Urn")
        self.assertIn("es", p.translations)

    def test_category_tree_is_localized_recursively(self):
        child = CategoryNode(id=2, parent_id=1, name="Pet Urns", slug="pet-urns", description=None, image_url=None,
                             sort_order=0, is_active=True, depth=2, translations={"nl": {"name": "Urnen voor huisdieren"}})
        root = CategoryNode(id=1, parent_id=None, name="Cremation Urns", slug="cremation-urns", description="x",
                            image_url=None, sort_order=0, is_active=True, depth=1,
                            translations={"nl": {"name": "Crematie-urnen"}}, children=[child])
        localize.category(root, "nl")
        self.assertEqual(root.name, "Crematie-urnen")
        self.assertEqual(root.description, "x")
        self.assertEqual(root.children[0].name, "Urnen voor huisdieren")


if __name__ == "__main__":
    unittest.main()
