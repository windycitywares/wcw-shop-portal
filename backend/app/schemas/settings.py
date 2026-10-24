"""Store settings, grouped. Each group is saved as one JSON document (table store_settings)."""

import re
from decimal import Decimal
from urllib.parse import urlsplit
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.timezones import DEFAULT_TIMEZONE, TIMEZONE_IDS
from app.schemas.common import Money

LANGS = ("en", "es", "nl")


class _Group(BaseModel):
    """Base for a settings group. Unknown stored keys are ignored when loading."""


class GeneralSettings(_Group):
    announcement_enabled: bool = False
    announcement: dict[str, str] = Field(default_factory=dict, description="Banner text per language (en, es, nl)")
    order_alert_email: str | None = Field(default=None, max_length=320, description="Who is emailed about new orders")
    low_stock_threshold: int = Field(default=3, ge=0, le=1000)
    max_quantity_per_line: int = Field(default=10, ge=1, le=100)
    guest_checkout: bool = True
    timezone: str = Field(default=DEFAULT_TIMEZONE, description="The store's time zone: report days, scheduled jobs and deploy times follow it")

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, v: str) -> str:
        if v not in TIMEZONE_IDS:
            raise ValueError("Pick a time zone from the list")
        return v

    @field_validator("announcement")
    @classmethod
    def _clean_announcement(cls, v: dict[str, str]) -> dict[str, str]:
        return {k: t.strip()[:200] for k, t in v.items() if k in LANGS and isinstance(t, str) and t.strip()}


class ShippingSettings(_Group):
    flat_rate: Money = Field(default=Decimal("8.95"), ge=0, max_digits=8, decimal_places=2)
    free_threshold: Money | None = Field(default=Decimal("100.00"), ge=0, max_digits=10, decimal_places=2)
    international_rate: Money | None = Field(default=None, ge=0, max_digits=8, decimal_places=2)
    allowed_countries: list[str] = Field(default_factory=lambda: ["US"])
    handling_days_min: int = Field(default=1, ge=0, le=60)
    handling_days_max: int = Field(default=3, ge=0, le=60)
    transit_days_min: int = Field(default=3, ge=0, le=60)
    transit_days_max: int = Field(default=7, ge=0, le=60)

    @field_validator("allowed_countries")
    @classmethod
    def _countries(cls, v: list[str]) -> list[str]:
        out = sorted({c.strip().upper() for c in v if len(c.strip()) == 2})
        return out or ["US"]


class TaxSettings(_Group):
    enabled: bool = False
    rate_percent: Money = Field(default=Decimal("0"), ge=0, le=30, max_digits=6, decimal_places=3)
    regions: list[str] = Field(default_factory=lambda: ["IL"], description="States where sales tax is collected")
    shipping_taxable: bool = False
    label: str = Field(default="Sales tax", max_length=40)

    @field_validator("regions")
    @classmethod
    def _regions(cls, v: list[str]) -> list[str]:
        return sorted({r.strip().upper() for r in v if r.strip()})


class PaymentSettings(_Group):
    # "Pay later" is gone from checkout. The instructions stay so an order placed while it was offered
    # still tells the customer how to pay.
    manual_instructions: dict[str, str] = Field(default_factory=dict, description="Shown on older orders that wait for payment")

    @field_validator("manual_instructions")
    @classmethod
    def _clean(cls, v: dict[str, str]) -> dict[str, str]:
        return {k: t.strip()[:1000] for k, t in v.items() if k in LANGS and isinstance(t, str) and t.strip()}


class WelcomeSettings(_Group):
    enabled: bool = True
    percent: int = Field(default=10, ge=1, le=60)
    expires_days: int = Field(default=30, ge=1, le=365)
    min_subtotal: Money = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)


class CartRecoverySettings(_Group):
    enabled: bool = True
    email_everyone: bool = Field(
        default=False,
        description="Email every shopper who leaves an address at checkout, not only those who tick the reminder box",
    )
    remind_signed_in: bool = Field(
        default=True,
        description="Remind signed-in customers without asking (they have an account; every reminder can be unsubscribed)",
    )
    first_delay_hours: int = Field(default=24, ge=1, le=720)
    second_delay_hours: int = Field(default=96, ge=2, le=1440)
    max_reminders: int = Field(default=2, ge=0, le=3)
    second_offer_percent: int = Field(default=0, ge=0, le=40, description="0 = no coupon in the second reminder")


class ReviewSettings(_Group):
    auto_approve_verified: bool = False
    request_enabled: bool = True
    request_after_days: int = Field(default=10, ge=1, le=90)


class AnalyticsSettings(_Group):
    enabled: bool = True
    retention_days: int = Field(default=400, ge=30, le=1100)


class Snippet(BaseModel):
    """One piece of tracking or widget code (Google Analytics, a pixel, a chat box) the owner added."""

    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=80)
    placement: Literal["head", "body"] = "head"  # head = top of every page, body = end of every page
    code: str = Field(min_length=1, max_length=20000)
    enabled: bool = True
    require_consent: bool = True  # wait for the visitor to accept the cookie banner

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Give the snippet a name")
        return v


class ScriptSettings(_Group):
    """Snippets added to every storefront page, each with a name, a place (header or footer) and its code."""

    snippets: list[Snippet] = Field(default_factory=list, max_length=30)

    @model_validator(mode="before")
    @classmethod
    def _from_the_two_boxes(cls, data):
        """Settings saved while this was two plain boxes (head_code / body_code) become two named snippets."""
        if isinstance(data, dict) and "snippets" not in data and (data.get("head_code") or data.get("body_code")):
            old = []
            for key, name, place in (("head_code", "Header code", "head"), ("body_code", "Footer code", "body")):
                if (data.get(key) or "").strip():
                    old.append({"id": place + "-1", "name": name, "placement": place, "code": data[key].strip(),
                                "require_consent": data.get("require_consent", True)})
            return {"snippets": old}
        return data

    @model_validator(mode="after")
    def _unique_ids(self):
        ids = [x.id for x in self.snippets]
        if len(ids) != len(set(ids)):
            raise ValueError("Two snippets share an id")
        return self


class PublicSnippet(BaseModel):
    id: str
    placement: Literal["head", "body"]
    code: str
    require_consent: bool


PLATFORMS = ("etsy", "amazon", "ebay", "walmart", "shopify", "facebook", "instagram", "tiktok", "other")
# A pasted link must belong to the platform picked, so an Etsy tile cannot point somewhere else by mistake.
_PLATFORM_HOSTS = {
    "etsy": ("etsy.com",), "amazon": ("amazon.", "amzn."), "ebay": ("ebay.",), "walmart": ("walmart.com",),
    "facebook": ("facebook.com", "fb.com", "fb.me"), "instagram": ("instagram.com",), "tiktok": ("tiktok.com",),
    "shopify": ("myshopify.com", "shop.app"),
}


class ShopLink(BaseModel):
    """One of the owner's other shops (Etsy, Amazon, ...) shown to visitors as a tile."""

    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    platform: Literal["etsy", "amazon", "ebay", "walmart", "shopify", "facebook", "instagram", "tiktok", "other"] = "other"
    name: str = Field(min_length=1, max_length=60)
    url: str = Field(min_length=1, max_length=500, description="https:// address, or # while the shop is not ready (shown as Coming soon)")
    blurb: str | None = Field(default=None, max_length=160, description="Shown when a visitor hovers the tile")
    image_url: str | None = Field(default=None, max_length=500, description="Optional logo or shop picture (https)")
    enabled: bool = True

    @field_validator("name", "blurb")
    @classmethod
    def _tidy(cls, v: str | None) -> str | None:
        v = " ".join((v or "").split())
        return v or None

    @field_validator("url", "image_url")
    @classmethod
    def _https(cls, v: str | None, info) -> str | None:
        v = (v or "").strip() or None
        if v is None:
            return None
        if v == "#" and info.field_name == "url":  # a shop that is not open yet
            return v
        parsed = urlsplit(v)
        if parsed.scheme != "https" or not parsed.hostname or "." not in parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Use the full https:// address")
        return v

    @model_validator(mode="after")
    def _belongs(self):
        if not self.name:
            raise ValueError("Give the shop a name")
        if self.url == "#":
            return self
        hosts = _PLATFORM_HOSTS.get(self.platform)
        host = (urlsplit(self.url).hostname or "").lower()
        if hosts and not any(
            (host.startswith(h) or "." + h in host) if h.endswith(".") else (host == h or host.endswith("." + h)) for h in hosts
        ):
            raise ValueError(f"That address doesn't look like a {self.platform.title()} link")
        return self


class ShopLinkSettings(_Group):
    """Links to the owner's shops on other marketplaces, shown on the home page and in the footer."""

    links: list[ShopLink] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _unique_ids(self):
        ids = [x.id for x in self.links]
        if len(ids) != len(set(ids)):
            raise ValueError("Two shops share an id")
        return self


class PublicShopLink(BaseModel):
    id: str
    platform: str
    name: str
    url: str
    blurb: str | None = None
    image_url: str | None = None


SOCIAL_PLATFORMS = ("instagram", "facebook", "tiktok", "pinterest", "youtube", "x", "linkedin", "whatsapp")
# The address pasted must belong to the network picked, so an Instagram icon cannot point somewhere else.
_SOCIAL_HOSTS = {
    "instagram": ("instagram.com",), "facebook": ("facebook.com", "fb.com", "fb.me"), "tiktok": ("tiktok.com",),
    "pinterest": ("pinterest.com", "pin.it"), "youtube": ("youtube.com", "youtu.be"), "x": ("x.com", "twitter.com"),
    "linkedin": ("linkedin.com",), "whatsapp": ("wa.me", "whatsapp.com"),
}


class SocialAccount(BaseModel):
    """One of the owner's social media accounts, shown as an icon and a Follow us pill."""

    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    platform: Literal["instagram", "facebook", "tiktok", "pinterest", "youtube", "x", "linkedin", "whatsapp"]
    handle: str = Field(default="", max_length=60, description="What visitors see, such as @windycityware")
    url: str = Field(min_length=1, max_length=500)
    enabled: bool = True

    @field_validator("handle")
    @classmethod
    def _tidy(cls, v: str) -> str:
        return " ".join((v or "").split())

    @field_validator("url")
    @classmethod
    def _https(cls, v: str) -> str:
        v = (v or "").strip()
        parsed = urlsplit(v)
        if parsed.scheme != "https" or not parsed.hostname or "." not in parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Use the full https:// address")
        return v

    @model_validator(mode="after")
    def _belongs(self):
        host = (urlsplit(self.url).hostname or "").lower()
        if not any(host == h or host.endswith("." + h) for h in _SOCIAL_HOSTS[self.platform]):
            raise ValueError(f"That address doesn't look like a {self.platform.title()} link")
        return self


class SocialSettings(_Group):
    """Social media accounts shown in the header bar, the footer and as Follow us pills."""

    accounts: list[SocialAccount] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def _unique_ids(self):
        ids = [x.id for x in self.accounts]
        if len(ids) != len(set(ids)):
            raise ValueError("Two accounts share an id")
        return self


class PublicSocial(BaseModel):
    id: str
    platform: str
    handle: str
    url: str


class DigestSettings(_Group):
    enabled: bool = True
    recipients: list[str] = Field(default_factory=list, max_length=10)


_ADDRESS = re.compile(r"^[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+$")
_HOST = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")


class EmailSettings(_Group):
    """Who the shop's email comes from and which mail server sends it. Empty fields use the server's own setup."""

    from_name: str | None = Field(default=None, max_length=80, description="The name customers see, e.g. Windy City Wares")
    from_address: str | None = Field(default=None, max_length=320, description="The address mail is sent from")
    reply_to: str | None = Field(default=None, max_length=320, description="Where customers' replies go (default: the from address)")
    smtp_host: str | None = Field(default=None, max_length=255, description="Mail server. Empty: use the one set on the server")
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_security: Literal["ssl", "starttls", "none"] | None = None
    smtp_user: str | None = Field(default=None, max_length=320)
    smtp_password_enc: str | None = Field(default=None, max_length=1000)  # sealed (core/secretbox); never sent to the admin

    @field_validator("from_name", "smtp_host", "smtp_user", "from_address", "reply_to", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @field_validator("from_name")
    @classmethod
    def _one_line(cls, v: str | None) -> str | None:
        if v is not None and ("\n" in v or "\r" in v or "<" in v or ">" in v):
            raise ValueError("can't contain line breaks or < >")
        return v

    @field_validator("from_address", "reply_to")
    @classmethod
    def _address(cls, v: str | None) -> str | None:
        if v is not None and not _ADDRESS.match(v):
            raise ValueError("must be an email address like hello@example.com")
        return v

    @field_validator("smtp_host")
    @classmethod
    def _host(cls, v: str | None) -> str | None:
        if v is not None and not _HOST.match(v):
            raise ValueError("must be a server name like smtp.example.com")
        return v

    @field_validator("smtp_user")
    @classmethod
    def _user(cls, v: str | None) -> str | None:
        if v is not None and ("\n" in v or "\r" in v):
            raise ValueError("can't contain line breaks")
        return v


class EmailTemplateSettings(_Group):
    """Wording the owner changed: {email kind: {language: {subject|intro|button|signoff: text}}}. Missing = the built-in wording."""

    templates: dict[str, dict[str, dict[str, str]]] = Field(default_factory=dict)

    @field_validator("templates")
    @classmethod
    def _clean(cls, v):
        from app.domain.emailtext import EDITABLE, FIELDS

        limits = {"subject": 150, "intro": 1500, "button": 40, "signoff": 300}
        out: dict[str, dict[str, dict[str, str]]] = {}
        for kind, langs in (v or {}).items():
            if kind not in EDITABLE or not isinstance(langs, dict):
                raise ValueError(f"unknown email: {kind}")
            for lang, fields in langs.items():
                if lang not in LANGS or not isinstance(fields, dict):
                    raise ValueError(f"unknown language: {lang}")
                for field, text in fields.items():
                    if field not in FIELDS or not isinstance(text, str):
                        raise ValueError(f"unknown part: {field}")
                    text = text.replace("\r\n", "\n").strip()
                    if field in ("subject", "button") and "\n" in text:
                        raise ValueError(f"{field} must be one line")
                    if len(text) > limits[field]:
                        raise ValueError(f"{field} is too long (most {limits[field]} characters)")
                    if text:
                        out.setdefault(kind, {}).setdefault(lang, {})[field] = text
        return out


GROUPS: dict[str, type[_Group]] = {
    "email_templates": EmailTemplateSettings,
    "email": EmailSettings,
    "general": GeneralSettings,
    "shipping": ShippingSettings,
    "tax": TaxSettings,
    "payments": PaymentSettings,
    "welcome": WelcomeSettings,
    "cart_recovery": CartRecoverySettings,
    "reviews": ReviewSettings,
    "analytics": AnalyticsSettings,
    "scripts": ScriptSettings,
    "shop_links": ShopLinkSettings,
    "social": SocialSettings,
    "digest": DigestSettings,
}


class StoreSettings(BaseModel):
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    shipping: ShippingSettings = Field(default_factory=ShippingSettings)
    tax: TaxSettings = Field(default_factory=TaxSettings)
    payments: PaymentSettings = Field(default_factory=PaymentSettings)
    welcome: WelcomeSettings = Field(default_factory=WelcomeSettings)
    cart_recovery: CartRecoverySettings = Field(default_factory=CartRecoverySettings)
    reviews: ReviewSettings = Field(default_factory=ReviewSettings)
    analytics: AnalyticsSettings = Field(default_factory=AnalyticsSettings)
    scripts: ScriptSettings = Field(default_factory=ScriptSettings)
    shop_links: ShopLinkSettings = Field(default_factory=ShopLinkSettings)
    social: SocialSettings = Field(default_factory=SocialSettings)
    digest: DigestSettings = Field(default_factory=DigestSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    email_templates: EmailTemplateSettings = Field(default_factory=EmailTemplateSettings)


class AdminSettingsOut(BaseModel):
    settings: StoreSettings
    # Facts that can't be edited here (they live on the server) but explain what works.
    status: dict[str, bool]


class PublicConfig(BaseModel):
    """What the storefront needs to render prices, banners and payment choices."""

    currency: str = "USD"
    free_shipping_threshold: float | None
    flat_shipping_rate: float
    international_shipping: bool
    shipping_countries: list[str]
    delivery_days: tuple[int, int]
    handling_days: tuple[int, int] = (1, 3)  # preparing the order (business days)
    transit_days: tuple[int, int] = (3, 7)  # with the carrier
    tax_enabled: bool
    tax_label: str
    announcement: str | None
    welcome_percent: int | None
    payment_methods: list[str]
    guest_checkout: bool
    # True: checkout shows "email me a reminder" and only a ticked box may be emailed. False: the shop
    # emails every shopper who leaves an address, so the form says so instead of asking.
    reminders_opt_in: bool = True
    reminders_signed_in: bool = True  # signed-in shoppers are reminded without the tickbox
    max_quantity_per_line: int
    low_stock_threshold: int
    analytics_enabled: bool
    timezone: str = DEFAULT_TIMEZONE
    snippets: list[PublicSnippet] = Field(default_factory=list)
    shop_links: list[PublicShopLink] = Field(default_factory=list)
    social: list[PublicSocial] = Field(default_factory=list)
    turnstile_site_key: str | None
