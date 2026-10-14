"""Request and response shapes for the store settings, shipping, tax, sales and coupons."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.pricing.codes import PREFIX_PATTERN, is_valid_code, normalize_code
from app.schemas.common import Money, ORMModel

Scope = Literal["all", "category", "products"]
CouponKind = Literal["percent", "fixed", "free_shipping"]


# ---------- store settings ----------


class StoreSettings(BaseModel):
    """Every setting with its default. Only changed values are stored in the database."""

    model_config = ConfigDict(extra="forbid")

    checkout_enabled: bool = False
    offline_enabled: bool = False
    offline_label: str = Field(default="Pay by check or bank transfer", min_length=1, max_length=80)
    offline_instructions: str = Field(default="", max_length=2000)
    stripe_enabled: bool = True
    low_stock_threshold: int = Field(default=3, ge=0, le=1000)
    welcome_enabled: bool = True
    welcome_kind: Literal["percent", "fixed"] = "percent"
    welcome_value: Decimal = Field(default=Decimal("10"), gt=0, le=10000, max_digits=12, decimal_places=2)
    welcome_valid_days: int = Field(default=30, ge=1, le=365)
    welcome_min_subtotal: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    order_alert_email: EmailStr | None = None

    @model_validator(mode="after")
    def _welcome_percent_limit(self) -> "StoreSettings":
        if self.welcome_kind == "percent" and self.welcome_value > 100:
            raise ValueError("A welcome discount can't be more than 100%")
        return self


class StoreSettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkout_enabled: bool | None = None
    offline_enabled: bool | None = None
    offline_label: str | None = Field(default=None, min_length=1, max_length=80)
    offline_instructions: str | None = Field(default=None, max_length=2000)
    stripe_enabled: bool | None = None
    low_stock_threshold: int | None = Field(default=None, ge=0, le=1000)
    welcome_enabled: bool | None = None
    welcome_kind: Literal["percent", "fixed"] | None = None
    welcome_value: Decimal | None = Field(default=None, gt=0, le=10000, max_digits=12, decimal_places=2)
    welcome_valid_days: int | None = Field(default=None, ge=1, le=365)
    welcome_min_subtotal: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    order_alert_email: EmailStr | None = None


class ReadinessItem(BaseModel):
    id: str
    ok: bool
    required: bool = True  # required items must be done before checkout can be switched on
    text: str


class StoreSettingsOut(StoreSettings):
    stripe_configured: bool
    test_payments_available: bool
    readiness: list[ReadinessItem]


class PaymentOption(BaseModel):
    id: str  # stripe | offline | test
    label: str
    description: str | None = None


class WelcomeOffer(BaseModel):
    kind: Literal["percent", "fixed"]
    value: Money
    min_subtotal: Money


class ShopConfig(BaseModel):
    """Public settings the storefront needs to render the cart and checkout."""

    currency: str = "USD"
    checkout_enabled: bool
    payment_options: list[PaymentOption]
    free_shipping_threshold: Money | None
    shipping_countries: list[str] | None  # None = every country
    welcome_offer: WelcomeOffer | None  # set while the newsletter welcome code is on


# ---------- shipping and tax ----------


class ShippingMethodIn(BaseModel):
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,39}$")
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=300)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    free_over: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    min_days: int | None = Field(default=None, ge=0, le=365)
    max_days: int | None = Field(default=None, ge=0, le=365)
    countries: list[str] = []
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=1000)

    @field_validator("countries")
    @classmethod
    def _countries(cls, v: list[str]) -> list[str]:
        out = []
        for c in v:
            c = c.strip().upper()
            if len(c) != 2 or not c.isalpha():
                raise ValueError("Countries are two-letter codes such as US or NL")
            if c not in out:
                out.append(c)
        return out

    @model_validator(mode="after")
    def _days(self) -> "ShippingMethodIn":
        if self.min_days is not None and self.max_days is not None and self.max_days < self.min_days:
            raise ValueError("The longest delivery time can't be shorter than the shortest")
        return self


class ShippingMethodOut(ORMModel):
    id: int
    code: str
    name: str
    description: str | None
    price: Money
    free_over: Money | None
    min_days: int | None
    max_days: int | None
    countries: list[str]
    is_active: bool
    sort_order: int


class TaxRateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    country: str = Field(pattern=r"^[A-Za-z]{2}$")
    region: str | None = Field(default=None, max_length=100)
    rate: Decimal = Field(ge=0, le=100, max_digits=6, decimal_places=3)
    applies_to_shipping: bool = False
    is_active: bool = True

    @field_validator("country")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("region")
    @classmethod
    def _blank_region(cls, v: str | None) -> str | None:
        v = " ".join((v or "").split())
        return v or None


class TaxRateOut(ORMModel):
    id: int
    name: str
    country: str
    region: str | None
    rate: Money
    applies_to_shipping: bool
    is_active: bool


# ---------- sales ----------


class _Targeting(BaseModel):
    scope: Scope = "all"
    category_id: int | None = None
    product_ids: list[int] = Field(default=[], max_length=500)

    @model_validator(mode="after")
    def _scope_needs_target(self):
        if self.scope == "category" and not self.category_id:
            raise ValueError("Choose a category")
        if self.scope == "products" and not self.product_ids:
            raise ValueError("Choose at least one product")
        return self


class SaleIn(_Targeting):
    name: str = Field(min_length=1, max_length=120)
    label: str | None = Field(default=None, max_length=40)
    kind: Literal["percent", "fixed"] = "percent"
    value: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _rules(self):
        if self.kind == "percent" and self.value > 100:
            raise ValueError("A percentage can't be more than 100")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("A sale has to end after it starts")
        return self


class SaleOut(ORMModel):
    id: int
    name: str
    label: str | None
    kind: str
    value: Money
    scope: str
    category_id: int | None
    product_ids: list[int]
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    created_at: datetime
    status: str = ""  # live | scheduled | ended | paused
    category_name: str | None = None
    products: list[str] = []  # titles of the covered products (scope "products")


# ---------- coupons ----------


class CouponRules(_Targeting):
    description: str | None = Field(default=None, max_length=300)
    kind: CouponKind = "percent"
    value: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    min_subtotal: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    max_discount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    exclude_sale_items: bool = False
    first_order_only: bool = False
    per_customer_limit: int | None = Field(default=None, ge=1, le=1000)
    starts_at: datetime | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _discount(self):
        if self.kind == "percent" and not (0 < self.value <= 100):
            raise ValueError("A percentage has to be between 0 and 100")
        if self.kind == "fixed" and self.value <= 0:
            raise ValueError("Enter the amount to take off")
        if self.kind == "free_shipping":
            self.value = Decimal("0")
            self.max_discount = None
        if self.starts_at and self.expires_at and self.expires_at <= self.starts_at:
            raise ValueError("A code has to expire after it starts")
        return self


class CouponIn(CouponRules):
    code: str = Field(min_length=3, max_length=40)
    usage_limit: int | None = Field(default=None, ge=1, le=1_000_000)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        code = normalize_code(v)
        if not is_valid_code(code):
            raise ValueError("Use 3 to 40 letters, numbers, dashes or underscores")
        return code


class CouponUpdate(CouponRules):
    """Editing keeps the code as it is."""

    usage_limit: int | None = Field(default=None, ge=1, le=1_000_000)
    is_active: bool = True


class CouponGenerate(CouponRules):
    count: int = Field(ge=1, le=500)
    prefix: str = Field(default="", max_length=12)
    campaign: str = Field(min_length=1, max_length=80)
    usage_limit: int = Field(default=1, ge=1, le=1_000_000)  # per generated code

    @field_validator("prefix")
    @classmethod
    def _prefix(cls, v: str) -> str:
        v = normalize_code(v)
        if v and not PREFIX_PATTERN.match(v):
            raise ValueError("The prefix can use letters and numbers only")
        return v


class CouponSend(CouponRules):
    """A personal code for one customer, sent by email."""

    email: EmailStr
    message: str | None = Field(default=None, max_length=500)
    locale: str = Field(default="en", pattern=r"^(en|es|nl)$")
    valid_days: int | None = Field(default=30, ge=1, le=730)


class CouponOut(ORMModel):
    id: int
    code: str
    description: str | None
    kind: str
    value: Money
    min_subtotal: Money | None
    max_discount: Money | None
    scope: str
    category_id: int | None
    product_ids: list[int]
    exclude_sale_items: bool
    first_order_only: bool
    usage_limit: int | None
    per_customer_limit: int | None
    used_count: int
    starts_at: datetime | None
    expires_at: datetime | None
    is_active: bool
    user_id: int | None
    email: str | None
    issued_to: str | None
    campaign: str | None
    source: str
    created_at: datetime
    status: str = ""  # active | scheduled | expired | used_up | paused
    discount_given: Money = Decimal("0")
    orders: int = 0


class GenerateResult(BaseModel):
    campaign: str
    count: int
    codes: list[str]


class CampaignOut(BaseModel):
    campaign: str
    codes: int
    used: int
    discount_given: Money
    created_at: datetime
