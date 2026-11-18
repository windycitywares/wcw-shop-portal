"""Where visitors come from and what they browse with: referrer/UTM -> channel, user agent -> device."""

import re
from urllib.parse import urlsplit

CHANNELS = (
    "direct", "organic_search", "paid_search", "social", "paid_social", "email", "marketplace",
    "referral", "affiliate", "display",
)

_SEARCH = ("google.", "bing.", "duckduckgo.", "yahoo.", "ecosia.", "brave.com", "baidu.", "yandex.", "startpage.", "qwant.", "search.")
_SOCIAL = ("facebook.", "fb.com", "fb.me", "instagram.", "pinterest.", "twitter.", "t.co", "x.com", "linkedin.", "lnkd.in",
           "reddit.", "youtube.", "youtu.be", "tiktok.", "nextdoor.", "tumblr.", "snapchat.", "whatsapp.", "threads.")
_MARKETPLACE = ("etsy.com", "amazon.", "ebay.", "walmart.com", "shopify.com")
_WEBMAIL = ("mail.google.com", "outlook.live.com", "outlook.office.com", "mail.yahoo.com", "mail.proton.me", "mail.aol.com")

_PAID_MEDIUMS = {"cpc", "ppc", "paid", "paidsearch", "paid-search", "sem"}
_PAID_SOCIAL_MEDIUMS = {"paid_social", "paid-social", "paidsocial", "social-paid", "cpm"}


def referrer_host(referrer: str | None) -> str | None:
    """'https://www.Google.com/search?q=x' -> 'google.com'. None when empty or not a web URL."""
    if not referrer:
        return None
    try:
        parts = urlsplit(referrer.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower()
    return host[4:] if host.startswith("www.") else host


def _matches(host: str, needles: tuple[str, ...]) -> bool:
    """'brand.' needles match any label of the host (google.com, google.co.uk, mail.google.com but not
    notgoogle.com). Other needles match the domain itself or any subdomain of it."""
    labels = host.split(".")
    for needle in needles:
        if needle.endswith("."):
            if needle[:-1] in labels:
                return True
        elif host == needle or host.endswith("." + needle):
            return True
    return False


_SOCIAL_SOURCES = {"facebook", "fb", "instagram", "ig", "pinterest", "twitter", "x", "linkedin", "reddit", "youtube",
                   "tiktok", "nextdoor", "snapchat", "threads", "whatsapp"}
_SEARCH_SOURCES = {"google", "bing", "duckduckgo", "yahoo", "ecosia", "brave", "yandex", "baidu"}


def classify_channel(host: str | None, utm_source: str | None = None, utm_medium: str | None = None,
                     own_hosts: tuple[str, ...] = ()) -> str:
    """UTM tags win over the referrer, because someone chose them on purpose."""
    medium = (utm_medium or "").strip().lower()
    source = (utm_source or "").strip().lower()
    if medium in _PAID_SOCIAL_MEDIUMS:
        return "paid_social"
    if medium in _PAID_MEDIUMS:
        return "paid_social" if source in _SOCIAL_SOURCES else "paid_search"
    if medium in ("email", "e-mail", "newsletter") or source in ("email", "newsletter", "klaviyo", "mailchimp"):
        return "email"
    if medium in ("social", "social-network", "sm"):
        return "social"
    if medium == "affiliate":
        return "affiliate"
    if medium in ("display", "banner", "cpm"):
        return "display"
    if medium == "organic":
        return "organic_search"
    if host:
        host = host.lower()
        if own_hosts and any(host == h or host.endswith("." + h) for h in own_hosts):
            return "direct"  # navigating within the site or from our own domain
        if _matches(host, _WEBMAIL):
            return "email"
        if _matches(host, _MARKETPLACE):
            return "marketplace"
        if _matches(host, _SOCIAL):
            return "social"
        if _matches(host, _SEARCH):
            return "organic_search"
        return "referral"
    if source:
        if source in _SOCIAL_SOURCES:
            return "social"
        if source in _SEARCH_SOURCES:
            return "organic_search"
        return "referral"
    return "direct"


_BOT = re.compile(
    r"bot|crawl|spider|slurp|facebookexternalhit|embedly|preview|monitor|uptime|pingdom|lighthouse|headless|phantomjs|"
    r"python-requests|python-urllib|curl/|wget/|httpclient|okhttp|go-http|java/|libwww|scrapy|node-fetch|axios|"
    r"ahrefs|semrush|mj12|dotbot|petalbot|bytespider|gptbot|claudebot|ccbot|yandex|baiduspider|duckduckbot|applebot",
    re.I,
)


def is_bot(user_agent: str | None) -> bool:
    if not user_agent or len(user_agent) < 12:
        return True
    return bool(_BOT.search(user_agent))


def parse_user_agent(user_agent: str | None) -> tuple[str, str, str]:
    """(device, browser, os) with coarse, privacy-friendly labels. device: mobile | tablet | desktop."""
    ua = user_agent or ""
    low = ua.lower()
    if "ipad" in low or "tablet" in low or ("android" in low and "mobile" not in low):
        device = "tablet"
    elif any(k in low for k in ("iphone", "ipod", "mobile", "android")):
        device = "mobile"
    else:
        device = "desktop"

    if "edg/" in low or "edge/" in low:
        browser = "Edge"
    elif "opr/" in low or "opera" in low:
        browser = "Opera"
    elif "samsungbrowser" in low:
        browser = "Samsung Internet"
    elif "firefox/" in low or "fxios" in low:
        browser = "Firefox"
    elif "chrome/" in low or "crios" in low:
        browser = "Chrome"
    elif "safari/" in low:
        browser = "Safari"
    else:
        browser = "Other"

    if "windows" in low:
        os_name = "Windows"
    elif "iphone" in low or "ipad" in low or "ipod" in low:
        os_name = "iOS"
    elif "android" in low:
        os_name = "Android"
    elif "mac os x" in low or "macintosh" in low:
        os_name = "macOS"
    elif "cros" in low:
        os_name = "ChromeOS"
    elif "linux" in low:
        os_name = "Linux"
    else:
        os_name = "Other"
    return device, browser, os_name
