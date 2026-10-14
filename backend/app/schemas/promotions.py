"""Sales, coupons and automatic offers (staff side)."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas.category import Translations
from app.schemas.common import Money, ORMModel

Scope = Literal["all", "category", "products"]
CouponScope = Literal["order", "category", "products"]
Price = Field(max_digits=10, decimal_places=2)


def _check_window(starts_at: datetime | None, ends_at: datetime | None, what: str) -> None:
    if starts_at and ends_at and ends_at <= starts_at:
        raise ValueError(f"{what} must end after it starts")


# ---------------------------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------------------------


class SaleIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    badge: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=1000)
    kind: Literal["percent", "fixed"] = "percent"
    value: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    scope: Scope = "all"
    category_ids: list[int] = Field(default_factory=list, max_length=200)
    product_ids: list[int] = Field(default_factory=list, max_length=2000)
    exclude_product_ids: list[int] = Field(default_factory=list, max_length=2000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    translations: Translations = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.kind == "percent" and self.value >= 100:
            raise ValueError("A percentage sale must be less than 100%")
        if self.scope == "category" and not self.category_ids:
            raise ValueError("Choose at least one category")
        if self.scope == "products" and not self.product_ids:
            raise ValueError("Choose at least one product")
        _check_window(self.starts_at, self.ends_at, "A sale")
        return self


class SaleOut(ORMModel):
    id: int
    name: str
    badge: str | None
    description: str | None
    kind: str
    value: Money
    scope: str
    category_ids: list[int]
    product_ids: list[int]
    exclude_product_ids: list[int]
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    translations: Translations
    created_at: datetime
    status: str = "active"  # active | scheduled | ended | paused
    affected_products: int = 0


# ---------------------------------------------------------------------------------------------
# Coupons
# ---------------------------------------------------------------------------------------------


class CouponTerms(BaseModel):
    """What a coupon does and who may use it. Shared by single and bulk creation."""

    name: str | None = Field(default=None, max_length=120)
    kind: Literal["percent", "fixed", "free_shipping"] = "percent"
    value: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    max_discount: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    min_subtotal: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    scope: CouponScope = "order"
    category_ids: list[int] = Field(default_factory=list, max_length=200)
    product_ids: list[int] = Field(default_factory=list, max_length=2000)
    exclude_sale_items: bool = False
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    usage_limit: int | None = Field(default=None, ge=1, le=1_000_000)
    per_customer_limit: int | None = Field(default=None, ge=1, le=1000)
    first_order_only: bool = False
    campaign: str | None = Field(default=None, max_length=80)
    stackable: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.kind == "percent" and not (0 < self.value <= 100):
            raise ValueError("A percentage coupon needs a value between 0 and 100")
        if self.kind == "fixed" and self.value <= 0:
            raise ValueError("A fixed-amount coupon needs an amount greater than zero")
        if self.scope == "category" and not self.category_ids:
            raise ValueError("Choose at least one category")
        if self.scope == "products" and not self.product_ids:
            raise ValueError("Choose at least one product")
        _check_window(self.starts_at, self.expires_at, "A coupon")
        return self


class CouponIn(CouponTerms):
    code: str | None = Field(default=None, max_length=40, description="Leave empty to generate one")
    assigned_email: EmailStr | None = None


class CouponBulkIn(CouponTerms):
    count: int = Field(default=10, ge=1, le=5000)
    prefix: str = Field(default="", max_length=12)
    length: int = Field(default=8, ge=6, le=20)
    emails: list[EmailStr] = Field(default_factory=list, max_length=5000, description="One personal code per address (count is ignored)")
    campaign: str = Field(min_length=1, max_length=80)

    @field_validator("prefix")
    @classmethod
    def _prefix(cls, v: str) -> str:
        return "".join(ch for ch in v.upper() if ch.isalnum())


class CouponOut(ORMModel):
    id: int
    code: str
    name: str | None
    kind: str
    value: Money
    max_discount: Money | None
    min_subtotal: Money
    scope: str
    category_ids: list[int]
    product_ids: list[int]
    exclude_sale_items: bool
    starts_at: datetime | None
    expires_at: datetime | None
    usage_limit: int | None
    per_customer_limit: int | None
    first_order_only: bool
    assigned_email: str | None
    campaign: str | None
    source: str
    stackable: bool
    is_active: bool
    used_count: int
    created_at: datetime
    status: str = "active"  # active | scheduled | expired | used_up | paused


class CouponListOut(BaseModel):
    items: list[CouponOut]
    total: int
    page: int
    page_size: int
    campaigns: list[str]


class CouponRedemptionOut(BaseModel):
    order_id: int
    order_number: str
    email: str
    amount: Money
    created_at: datetime


class CouponDetailOut(CouponOut):
    redemptions: list[CouponRedemptionOut] = []
    revenue: Money = Decimal("0")  # order totals that used this code, net of refunds


class BulkResultOut(BaseModel):
    created: int
    campaign: str
    sample: list[str]


# ---------------------------------------------------------------------------------------------
# Automatic cart offers
# ---------------------------------------------------------------------------------------------

RuleKind = Literal["spend_percent", "spend_fixed", "qty_percent", "qty_fixed", "free_shipping"]


class CartRuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: RuleKind
    threshold_amount: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    threshold_qty: int | None = Field(default=None, ge=2, le=1000)
    value: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    max_discount: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    scope: CouponScope = "order"
    category_ids: list[int] = Field(default_factory=list, max_length=200)
    product_ids: list[int] = Field(default_factory=list, max_length=2000)
    exclude_sale_items: bool = False
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    priority: int = Field(default=0, ge=-100, le=100)
    translations: Translations = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.kind.startswith("spend_") and self.threshold_amount is None:
            raise ValueError("Set the amount the customer needs to spend")
        if self.kind.startswith("qty_") and self.threshold_qty is None:
            raise ValueError("Set how many items the customer needs to buy")
        if self.kind.endswith("_percent") and not (0 < self.value <= 100):
            raise ValueError("A percentage offer needs a value between 0 and 100")
        if self.kind.endswith("_fixed") and self.value <= 0:
            raise ValueError("A fixed-amount offer needs an amount greater than zero")
        if self.scope == "category" and not self.category_ids:
            raise ValueError("Choose at least one category")
        if self.scope == "products" and not self.product_ids:
            raise ValueError("Choose at least one product")
        _check_window(self.starts_at, self.ends_at, "An offer")
        return self


class CartRuleOut(ORMModel):
    id: int
    name: str
    kind: str
    threshold_amount: Money | None
    threshold_qty: int | None
    value: Money
    max_discount: Money | None
    scope: str
    category_ids: list[int]
    product_ids: list[int]
    exclude_sale_items: bool
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    priority: int
    translations: Translations
    created_at: datetime
    status: str = "active"


def window_status(is_active: bool, starts_at: datetime | None, ends_at: datetime | None, now: datetime) -> str:
    if not is_active:
        return "paused"
    if starts_at and now < starts_at:
        return "scheduled"
    if ends_at and now >= ends_at:
        return "ended"
    return "active"


def as_dict(model: BaseModel, **overrides: Any) -> dict[str, Any]:
    data = model.model_dump()
    data.update(overrides)
    return data
