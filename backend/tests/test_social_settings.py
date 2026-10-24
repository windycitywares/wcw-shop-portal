"""Social media accounts: https only, and each address must belong to its network."""

import unittest

from pydantic import ValidationError

from app.schemas.settings import GROUPS, PublicConfig, SocialAccount, SocialSettings, StoreSettings


def acct(**kw):
    return SocialAccount(**{"id": "a", "platform": "instagram", "handle": "@windycityware", "url": "https://www.instagram.com/windycityware/", **kw})


class SocialTests(unittest.TestCase):
    def test_nothing_is_shown_by_default(self):
        self.assertEqual(SocialSettings().accounts, [])
        self.assertIs(GROUPS["social"], SocialSettings)
        self.assertEqual(StoreSettings().social.accounts, [])
        self.assertEqual(PublicConfig.model_fields["social"].default_factory(), [])

    def test_good_accounts(self):
        self.assertEqual(acct(handle="  @windy   city ").handle, "@windy city")
        acct(platform="facebook", url="https://facebook.com/windycitywares")
        acct(platform="x", url="https://twitter.com/windy")
        acct(platform="whatsapp", url="https://wa.me/15551234567")
        acct(platform="youtube", url="https://youtu.be/abc")
        acct(handle="")

    def test_bad_accounts(self):
        for bad in (
            {"url": "http://www.instagram.com/x"},
            {"url": "javascript:alert(1)"},
            {"url": "#"},
            {"url": "https://u:p@instagram.com/x"},
            {"url": "https://instagram.com.evil.example/x"},
            {"platform": "facebook", "url": "https://www.instagram.com/x"},
            {"platform": "myspace"},
            {"handle": "x" * 61},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                acct(**bad)

    def test_ids_unique_and_capped(self):
        with self.assertRaises(ValidationError):
            SocialSettings(accounts=[acct().model_dump(), acct().model_dump()])
        with self.assertRaises(ValidationError):
            SocialSettings(accounts=[acct(id=f"s{i}").model_dump() for i in range(13)])


if __name__ == "__main__":
    unittest.main()
