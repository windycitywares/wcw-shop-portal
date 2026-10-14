"""Order management payloads for staff."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import Money, ORMModel
from app.schemas.shop import OrderItemOut, OrderOut


class OrderListItem(ORMModel):
    id: int
    number: str
    email: str
    customer_name: str | None
    status: str
    payment_status: str
    fulfillment_status: str
    payment_provider: str | None
    grand_total: Money
    refunded_total: Money
    coupon_code: str | None
    channel: str | None
    item_count: int = 0
    placed_at: datetime | None
    paid_at: datetime | None


class OrderListStats(BaseModel):
    orders: int
    revenue: Money  # paid orders in the filter, net of refunds
    open_orders: int  # need action: unpaid, paid but not shipped


class OrderListOut(BaseModel):
    items: list[OrderListItem]
    total: int
    page: int
    page_size: int
    stats: OrderListStats


class OrderItemAdminOut(OrderItemOut):
    unit_cost: Money | None
    refunded_quantity: int
    sale_id: int | None


class PaymentOut(ORMModel):
    id: int
    provider: str
    kind: str
    status: str
    amount: Money
    provider_ref: str | None
    error: str | None
    created_at: datetime


class OrderEventAdminOut(ORMModel):
    id: int
    type: str
    message: str | None
    actor: str | None
    created_at: datetime


class OrderAdminOut(OrderOut):
    items: list[OrderItemAdminOut]  # type: ignore[assignment]
    user_id: int | None
    locale: str | None
    tax_rate: Money
    channel: str | None
    device: str | None
    marketing_opt_in: bool
    payments: list[PaymentOut] = []
    events: list[OrderEventAdminOut] = []
    customer_order_count: int = 1
    cost_total: Money | None = None  # None when some item has no cost price
    profit: Money | None = None


class MarkPaidIn(BaseModel):
    reference: str | None = Field(default=None, max_length=200, description="Bank transfer or check number, for your records")
    note: str | None = Field(default=None, max_length=500)


class ShipIn(BaseModel):
    carrier: str | None = Field(default=None, max_length=60)
    tracking_number: str | None = Field(default=None, max_length=100)
    tracking_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://")
    notify_customer: bool = True


class StatusIn(BaseModel):
    status: Literal["processing", "delivered"]
    note: str | None = Field(default=None, max_length=500)


class CancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)
    refund: bool = True  # refund what the customer paid, if anything
    notify_customer: bool = True


class RefundItemIn(BaseModel):
    item_id: int
    quantity: int = Field(ge=1, le=1000)


class RefundIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reason: str | None = Field(default=None, max_length=300)
    items: list[RefundItemIn] = Field(default_factory=list, max_length=100)
    restock: bool = False  # put the refunded items back on the shelf
    notify_customer: bool = True


class NoteIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def _clean(cls, v: str) -> str:
        return v.strip()


class OrderFilters(BaseModel):
    q: str | None = None
    status: str | None = None
    payment_status: str | None = None
    channel: str | None = None
    coupon: str | None = None
    start: date | None = None
    end: date | None = None
    needs_action: bool = False
    sort: str = "newest"
    page: int = 1
    page_size: int = 25

