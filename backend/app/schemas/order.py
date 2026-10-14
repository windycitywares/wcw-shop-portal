"""Request and response shapes for the cart quote, checkout and orders."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.enums import FulfillmentStatus, OrderStatus
from app.core.i18n import LANG_PATTERN
from app.schemas.account import AddressFields
from app.schemas.common import Money, ORMModel

MAX_LINES = 50
MAX_QTY = 99


class CartItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=MAX_QTY)


class QuoteIn(BaseModel):
    items: list[CartItemIn] = Field(max_length=MAX_LINES)
    coupon_code: str | None = Field(default=None, max_length=60)
    shipping_method: str | None = Field(default=None, max_length=40)
    # Not validated as an address: this is called while the customer is still typing it.
    email: str | None = Field(default=None, max_length=320)
    country: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    region: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)


class QuoteLineOut(BaseModel):
    product_id: int
    quantity: int
    list_price: Money
    unit_price: Money
    line_total: Money
    discount: Money
    sale_label: str | None
    issue: Literal["sold_out", "limited"] | None = None
    max_quantity: int | None = None


class AppliedCouponOut(BaseModel):
    code: str
    discount: Money
    free_shipping: bool


class ProblemOut(BaseModel):
    code: str
    message: str
    data: dict[str, str] = {}


class ShippingOptionOut(BaseModel):
    code: str
    name: str
    description: str | None
    base_price: Money
    price: Money
    free: bool
    min_days: int | None
    max_days: int | None


class TaxLineOut(BaseModel):
    name: str
    rate: Money
    amount: Money


class QuoteOut(BaseModel):
    currency: str
    lines: list[QuoteLineOut]
    unavailable: list[int]  # product ids that can't be bought any more
    list_subtotal: Money
    sale_savings: Money
    subtotal: Money
    coupon: AppliedCouponOut | None
    coupon_problem: ProblemOut | None
    shipping_options: list[ShippingOptionOut]
    shipping_method: str | None
    shipping_total: Money
    shipping_discount: Money
    tax_lines: list[TaxLineOut]
    tax_total: Money
    total: Money
    free_shipping_threshold: Money | None
    free_shipping_remaining: Money | None


class CheckoutIn(BaseModel):
    items: list[CartItemIn] = Field(min_length=1, max_length=MAX_LINES)
    coupon_code: str | None = Field(default=None, max_length=60)
    shipping_method: str = Field(min_length=1, max_length=40)
    email: EmailStr
    shipping_address: AddressFields
    billing_address: AddressFields | None = None  # None = same as shipping
    notes: str | None = Field(default=None, max_length=1000)
    payment_provider: Literal["stripe", "offline", "test"]
    # The total the customer saw. If prices moved since, the order isn't placed and they're asked to review.
    expected_total: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    locale: str = Field(default="en", pattern=LANG_PATTERN)
    captcha_token: str | None = Field(default=None, max_length=4096)
    subscribe: bool = False

    @field_validator("notes")
    @classmethod
    def _notes(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None


class OrderItemOut(ORMModel):
    id: int
    product_id: int | None
    sku: str
    title: str
    unit_price: Money
    list_price: Money | None
    quantity: int
    line_total: Money
    discount: Money
    attributes: dict[str, Any]


class OrderEventOut(ORMModel):
    id: int
    kind: str
    message: str
    created_at: datetime


class RefundOut(ORMModel):
    id: int
    amount: Money
    reason: str | None
    restocked: bool
    created_at: datetime


class OrderOut(ORMModel):
    number: str
    status: OrderStatus
    fulfillment_status: FulfillmentStatus
    email: str
    currency: str
    subtotal: Money
    sale_savings: Money
    discount_total: Money  # coupon
    shipping_total: Money
    shipping_discount: Money
    tax_total: Money
    tax_lines: list[dict[str, Any]]
    grand_total: Money
    refunded_total: Money
    coupon_code: str | None
    shipping_address: dict[str, Any] | None
    billing_address: dict[str, Any] | None
    shipping_method: str | None
    carrier: str | None
    tracking_number: str | None
    payment_provider: str | None
    notes: str | None
    placed_at: datetime | None
    paid_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None
    items: list[OrderItemOut]
    events: list[OrderEventOut] = []
    refunds: list[RefundOut] = []
    # Staff only (null for customers)
    id: int | None = None
    user_id: int | None = None
    internal_note: str | None = None
    payment_ref: str | None = None
    locale: str | None = None


class OrderListItem(ORMModel):
    number: str
    status: OrderStatus
    fulfillment_status: FulfillmentStatus
    email: str
    customer: str | None = None
    grand_total: Money
    refunded_total: Money
    item_count: int = 0
    payment_provider: str | None
    coupon_code: str | None
    placed_at: datetime | None


class OrderPlaced(BaseModel):
    number: str
    access_token: str
    status: OrderStatus
    total: Money
    # What happens next: "paid" (done), "pay" (go to payment_url) or "offline" (pay as instructed)
    next: Literal["paid", "pay", "offline"]
    payment_url: str | None = None
    instructions: str | None = None


class StatusIn(BaseModel):
    status: Literal["paid", "processing", "delivered"]


class ShipIn(BaseModel):
    carrier: str | None = Field(default=None, max_length=50)
    tracking_number: str | None = Field(default=None, max_length=100)
    notify: bool = True

    @field_validator("carrier", "tracking_number")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        v = " ".join((v or "").split())
        return v or None


class CancelIn(BaseModel):
    refund: bool = True  # a paid order is refunded in full
    reason: str | None = Field(default=None, max_length=300)


class RefundIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reason: str | None = Field(default=None, max_length=300)
    restock: bool = False
    notify: bool = True


class NoteIn(BaseModel):
    internal_note: str | None = Field(default=None, max_length=4000)


class OrderCounts(BaseModel):
    counts: dict[str, int]
