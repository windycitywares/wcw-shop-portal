import unittest

from app.domain.channels import classify_channel, is_bot, parse_user_agent, referrer_host

OWN = ("windycitywares.com",)
CHROME_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
PIXEL = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
ANDROID_TABLET = "Mozilla/5.0 (Linux; Android 13; SM-X700) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
IPAD = "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
MAC_SAFARI = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
FIREFOX_LINUX = "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0"
EDGE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"


class ChannelTests(unittest.TestCase):
    def test_referrers(self):
        cases = {
            "google.com": "organic_search", "google.co.uk": "organic_search", "bing.com": "organic_search",
            "search.brave.com": "organic_search", "duckduckgo.com": "organic_search",
            "l.facebook.com": "social", "t.co": "social", "pinterest.com": "social", "instagram.com": "social",
            "etsy.com": "marketplace", "www.etsy.com": "marketplace", "amazon.com": "marketplace",
            "mail.google.com": "email", "outlook.live.com": "email",
            "example.org": "referral", "notgoogle.com": "referral", "fakeetsy.com": "referral", "mybing.com": "referral",
        }
        for host, want in cases.items():
            self.assertEqual(classify_channel(host), want, host)

    def test_direct_and_own_site(self):
        self.assertEqual(classify_channel(None), "direct")
        self.assertEqual(classify_channel("shop.windycitywares.com", own_hosts=OWN), "direct")
        self.assertEqual(classify_channel("windycitywares.com", own_hosts=OWN), "direct")
        self.assertEqual(classify_channel("evilwindycitywares.com", own_hosts=OWN), "referral")

    def test_utm_wins(self):
        self.assertEqual(classify_channel("google.com", "google", "cpc"), "paid_search")
        self.assertEqual(classify_channel(None, "facebook", "cpc"), "paid_social")
        self.assertEqual(classify_channel("l.facebook.com", "fb", "paid_social"), "paid_social")
        self.assertEqual(classify_channel(None, "newsletter", "email"), "email")
        self.assertEqual(classify_channel("example.org", "spring", "email"), "email")
        self.assertEqual(classify_channel(None, "fb", "social"), "social")
        self.assertEqual(classify_channel(None, "partner1", "affiliate"), "affiliate")
        self.assertEqual(classify_channel(None, "banner1", "display"), "display")
        self.assertEqual(classify_channel(None, "instagram", None), "social")
        self.assertEqual(classify_channel(None, "somesite", None), "referral")

    def test_referrer_host(self):
        self.assertEqual(referrer_host("https://www.Google.com/search?q=urn"), "google.com")
        self.assertEqual(referrer_host("http://m.facebook.com/"), "m.facebook.com")
        self.assertIsNone(referrer_host(""))
        self.assertIsNone(referrer_host("android-app://com.google.android.gm"))
        self.assertIsNone(referrer_host("not a url"))
        self.assertIsNone(referrer_host(None))


class UserAgentTests(unittest.TestCase):
    def test_devices(self):
        self.assertEqual(parse_user_agent(CHROME_WIN), ("desktop", "Chrome", "Windows"))
        self.assertEqual(parse_user_agent(IPHONE), ("mobile", "Safari", "iOS"))
        self.assertEqual(parse_user_agent(PIXEL), ("mobile", "Chrome", "Android"))
        self.assertEqual(parse_user_agent(ANDROID_TABLET)[0], "tablet")
        self.assertEqual(parse_user_agent(IPAD)[0], "tablet")
        self.assertEqual(parse_user_agent(MAC_SAFARI), ("desktop", "Safari", "macOS"))
        self.assertEqual(parse_user_agent(FIREFOX_LINUX), ("desktop", "Firefox", "Linux"))
        self.assertEqual(parse_user_agent(EDGE)[1], "Edge")
        self.assertEqual(parse_user_agent(None), ("desktop", "Other", "Other"))

    def test_bots(self):
        for ua in (
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
            "python-requests/2.31.0", "curl/8.4.0", "Mozilla/5.0 HeadlessChrome/126.0.0.0", "", None, "x",
            "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
        ):
            self.assertTrue(is_bot(ua), ua)
        for ua in (CHROME_WIN, IPHONE, PIXEL, MAC_SAFARI, FIREFOX_LINUX):
            self.assertFalse(is_bot(ua), ua)


if __name__ == "__main__":
    unittest.main()
