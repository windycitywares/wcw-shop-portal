"""Cart quote, checkout and order payloads for shoppers."""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.i18n import LANG_PATTERN
from app.schemas.account import AddressFields
from app.schemas.common import Money, ORMModel

_KEY = re.compile(r"^[A-Za-z0-9_.:-]{8,64}$")


class CartItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=100)
    options: dict[str, str] = Field(default_factory=dict)

    @field_validator("options")
    @classmethod
    def _options(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 12:
            raise ValueError("Too many options")
        return {str(k).strip()[:60]: str(val).strip()[:120] for k, val in v.items() if str(k).strip() and str(val).strip()}


class DestinationIn(BaseModel):
    country: str = Field(default="US", pattern=r"^[A-Za-z]{2}$")
    region: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)

    @field_validator("country")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class QuoteIn(BaseModel):
    items: list[CartItemIn] = Field(default_factory=list, max_length=50)
    coupon: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=320)
    destination: DestinationIn | None = None
    lang: str | None = Field(default=None, pattern=LANG_PATTERN)


class QuoteLineOut(BaseModel):
    product_id: int
    parent_id: int | None
    slug: str
    sku: str
    title: str
    variant: str | None = None  # e.g. "10 inch Large" (as stored; the storefront translates known names)
    image: str | None
    options: dict[str, str]
    quantity: int
    unit_price: Money
    list_price: Money
    line_total: Money
    line_discount: Money
    on_sale: bool
    sale_label: str | None = None
    stock_left: int | None = None  # only when tracked stock is running low


class DiscountOut(BaseModel):
    type: Literal["rule", "coupon", "free_shipping"]
    label: str
    amount: Money
    code: str | None = None


class ShippingOut(BaseModel):
    amount: Money
    free: bool
    reason: str
    free_threshold: Money | None
    remaining_for_free: Money | None
    deliverable: bool


class TaxOut(BaseModel):
    label: str
    rate_percent: Money
    amount: Money


class CouponStatusOut(BaseModel):
    code: str
    valid: bool
    applied: bool
    message: str | None = None
    reason: str | None = None


class RewardOut(BaseModel):
    name: str
    kind: str
    value: Money
    remaining_amount: Money | None
    remaining_qty: int | None


class QuoteOut(BaseModel):
    currency: str = "USD"
    lines: list[QuoteLineOut]
    item_count: int
    subtotal: Money
    list_subtotal: Money
    sale_savings: Money
    discounts: list[DiscountOut]
    discount_total: Money
    shipping: ShippingOut
    tax: TaxOut | None
    tax_pending: bool
    total: Money
    coupon: CouponStatusOut | None
    rewards: list[RewardOut]
    messages: list[str]
    blocking: bool = Field(description="True when something in the cart can't be bought as it is")


class CartSyncIn(BaseModel):
    """Snapshot of the cart for abandoned-cart reminders. Sent (debounced) when the cart changes."""

    token: str | None = Field(default=None, min_length=16, max_length=40)
    items: list[CartItemIn] = Field(default_factory=list, max_length=50)
    coupon: str | None = Field(default=None, max_length=60)
    email: EmailStr | None = None
    reminders_ok: bool = False
    checkout_started: bool = False
    session_id: str | None = Field(default=None, max_length=40)
    locale: str | None = Field(default=None, pattern=LANG_PATTERN)


class CartSyncOut(BaseModel):
    token: str


class CheckoutIn(BaseModel):
    items: list[CartItemIn] = Field(min_length=1, max_length=50)
    coupon: str | None = Field(default=None, max_length=60)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40, pattern=r"^[0-9+()\-.\s]*$")
    shipping_address: AddressFields
    billing_address: AddressFields | None = None
    notes: str | None = Field(default=None, max_length=500)
    payment_method: Literal["stripe", "manual", "test"]
    locale: str = Field(default="en", pattern=LANG_PATTERN)
    captcha_token: str | None = Field(default=None, max_length=4096)
    idempotency_key: str | None = Field(default=None, max_length=64)
    cart_token: str | None = Field(default=None, max_length=40)
    session_id: str | None = Field(default=None, max_length=40)
    marketing_opt_in: bool = False
    reminders_ok: bool = False
    save_address: bool = False

    @field_validator("idempotency_key")
    @classmethod
    def _key(cls, v: str | None) -> str | None:
        if v is not None and not _KEY.match(v):
            raise ValueError("Invalid idempotency key")
        return v

    @field_validator("notes")
    @classmethod
    def _notes(cls, v: str | None) -> str | None:
        return " ".join(v.split()) or None if v else None


class PaymentActionOut(BaseModel):
    provider: str
    status: Literal["paid", "pending", "redirect"]
    redirect_url: str | None = None
    instructions: str | None = None


class OrderItemOut(ORMModel):
    id: int
    product_id: int | None
    slug: str | None
    sku: str
    title: str
    image_url: str | None
    unit_price: Money
    list_price: Money | None
    quantity: int
    line_total: Money
    discount_total: Money
    attributes: dict[str, Any]


class OrderEventOut(ORMModel):
    type: str
    message: str | None
    created_at: datetime


class OrderOut(ORMModel):
    id: int
    number: str
    email: str
    customer_name: str | None
    phone: str | None
    status: str
    payment_status: str
    fulfillment_status: str
    currency: str
    subtotal: Money
    discount_total: Money
    shipping_total: Money
    tax_total: Money
    grand_total: Money
    refunded_total: Money
    coupon_code: str | None
    discounts: list[dict[str, Any]]
    shipping_address: dict[str, Any] | None
    billing_address: dict[str, Any] | None
    shipping_method: str | None
    carrier: str | None
    tracking_number: str | None
    tracking_url: str | None
    payment_provider: str | None
    notes: str | None
    placed_at: datetime | None
    paid_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None
    items: list[OrderItemOut]


class OrderPublicOut(OrderOut):
    """The order as its owner sees it (account page or the emailed link), with the customer-visible timeline."""

    timeline: list[OrderEventOut] = []
    access_token: str | None = None


class OrderSummaryOut(ORMModel):
    id: int
    number: str
    status: str
    payment_status: str
    fulfillment_status: str
    grand_total: Money
    placed_at: datetime | None
    item_count: int = 0
    first_item_title: str | None = None
    first_item_image: str | None = None
    access_token: str | None = None


class OrderNotificationOut(BaseModel):
    """One order milestone for the shopper's bell. The storefront turns `kind` into words."""

    id: str  # "shipped:42": kind and order, stable across reloads
    kind: Literal["placed", "paid", "shipped", "delivered", "cancelled", "refunded"]
    order_id: int
    number: str
    token: str | None = None
    at: datetime
    amount: float | None = None  # the refunded amount, for `refunded`
    unread: bool


class OrderNotificationsOut(BaseModel):
    items: list[OrderNotificationOut]
    unread: int


class CheckoutOut(BaseModel):
    order: OrderPublicOut
    payment: PaymentActionOut


class OrderLookupIn(BaseModel):
    number: str = Field(min_length=3, max_length=32)
    email: EmailStr


class ConfirmPaymentIn(BaseModel):
    session_id: str | None = Field(default=None, max_length=255)
