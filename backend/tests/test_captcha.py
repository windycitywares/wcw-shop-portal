import unittest
from types import SimpleNamespace

from app.core.captcha import public_site_key


class PublicSiteKeyTests(unittest.TestCase):
    def test_shown_only_when_the_secret_is_set_too(self):
        self.assertEqual(public_site_key(SimpleNamespace(turnstile_site_key="0xKEY", turnstile_secret="s3cret")), "0xKEY")
        # A site key on its own: the server can't verify, so the widget would only get in the way.
        self.assertIsNone(public_site_key(SimpleNamespace(turnstile_site_key="0xKEY", turnstile_secret=None)))
        self.assertIsNone(public_site_key(SimpleNamespace(turnstile_site_key=None, turnstile_secret="s3cret")))


if __name__ == "__main__":
    unittest.main()
