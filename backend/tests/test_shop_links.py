"""Links to the owner's other shops: https only, and each must belong to its platform."""

import unittest

from pydantic import ValidationError

from app.schemas.settings import GROUPS, PublicConfig, ShopLink, ShopLinkSettings, StoreSettings


def link(**kw):
    return ShopLink(**{"id": "a", "name": "My shop", "platform": "etsy", "url": "https://www.etsy.com/shop/WindyCityWaresUS", **kw})


class ShopLinkTests(unittest.TestCase):
    def test_nothing_is_shown_by_default(self):
        self.assertEqual(ShopLinkSettings().links, [])
        self.assertIs(GROUPS["shop_links"], ShopLinkSettings)
        self.assertEqual(StoreSettings().shop_links.links, [])
        self.assertEqual(PublicConfig.model_fields["shop_links"].default_factory(), [])

    def test_good_links_are_kept_and_text_is_tidied(self):
        s = link(name="  Windy   City Wares ", blurb="  Handmade\nurns ")
        self.assertEqual((s.name, s.blurb, s.enabled), ("Windy City Wares", "Handmade urns", True))
        link(platform="amazon", url="https://www.amazon.com/stores/page/123")
        link(platform="amazon", url="https://amazon.co.uk/stores/x")
        link(platform="ebay", url="https://www.ebay.com/str/shop")
        link(platform="other", url="https://example.org/shop")

    def test_bad_links_are_refused(self):
        for bad in (
            {"url": "http://www.etsy.com/shop/x"},  # not https
            {"url": "javascript:alert(1)"},
            {"url": "https://user:pw@www.etsy.com/shop/x"},
            {"url": "https://etsy.com.evil.example/shop"},  # looks like Etsy, is not
            {"platform": "amazon", "url": "https://evil-amazon.com/x"},
            {"platform": "ebay", "url": "https://www.etsy.com/shop/x"},  # wrong platform
            {"image_url": "http://img.example/x.png"},
            {"name": " "},
            {"blurb": "x" * 161},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                link(**bad)

    def test_ids_are_unique_and_the_list_is_capped(self):
        with self.assertRaises(ValidationError):
            ShopLinkSettings(links=[link().model_dump(), link().model_dump()])
        with self.assertRaises(ValidationError):
            ShopLinkSettings(links=[link(id=f"s{i}").model_dump() for i in range(21)])


if __name__ == "__main__":
    unittest.main()
