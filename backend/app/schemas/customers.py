"""Customer lists and profiles for staff."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import Money


class CustomerRow(BaseModel):
    email: str
    name: str | None
    orders: int
    revenue: Money  # paid, net of refunds
    average_order: Money
    first_order_at: datetime | None  # None: signed up, never paid
    last_order_at: datetime | None
    segment: str
    subscribed: bool  # agreed to marketing email and hasn't left
    has_account: bool
    account_id: int | None = None  # their shopper account, if they have one (staff accounts are on the Team page)
    account_active: bool | None = None  # False: switched off by staff, cannot sign in
    joined_at: datetime | None = None  # when the account was made


class SegmentSummary(BaseModel):
    key: str
    label: str
    help: str
    customers: int
    revenue: Money


class CustomerListOut(BaseModel):
    items: list[CustomerRow]
    total: int
    page: int
    page_size: int
    segments: list[SegmentSummary]
    total_customers: int  # people who paid
    accounts_without_orders: int = 0
    subscribers_without_orders: int


class CustomerOrder(BaseModel):
    id: int
    number: str
    status: str
    payment_status: str
    grand_total: Money
    refunded_total: Money
    coupon_code: str | None
    placed_at: datetime | None


class CustomerCoupon(BaseModel):
    code: str
    kind: str
    value: Money
    status: str
    source: str
    expires_at: datetime | None


class CustomerDetail(BaseModel):
    summary: CustomerRow
    refunded: Money
    orders: list[CustomerOrder]
    coupons: list[CustomerCoupon]
    subscription: dict | None  # {status, source, since}
    reviews: int
    account_role: str | None
