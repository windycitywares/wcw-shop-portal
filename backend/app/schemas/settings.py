"""Store settings, grouped. Each group is saved as one JSON document (table store_settings)."""

import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

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
    turnstile_site_key: str | None
