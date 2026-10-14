"""Queries for orders, their timeline and refunds, plus the stock counters checkout moves."""

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from sqlalchemy import and_, case, func, or_, select, text, update

from app.core.enums import OrderStatus, StockStatus
from app.models.commerce import OrderEvent, Refund
from app.models.order import Order
from app.models.product import Product
from app.repositories.base import BaseRepository
from app.utils.text import escape_like

# Orders that count as real demand: not cancelled, not fully refunded.
LIVE_STATUSES = (OrderStatus.PENDING, OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.DELIVERED)


@dataclass
class OrderQuery:
    q: str | None = None
    statuses: Sequence[OrderStatus] | None = None
    provider: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    user_id: int | None = None
    page: int = 1
    page_size: int = 25


class OrderRepository(BaseRepository[Order]):
    model = Order

    async def next_number(self) -> str:
        n = (await self.session.execute(text("SELECT nextval('order_number_seq')"))).scalar_one()
        return f"WCW-{n}"

    async def get_by_number(self, number: str, *, lock: bool = False) -> Order | None:
        stmt = select(Order).where(Order.number == number).limit(1)
        if lock:  # populate_existing: re-read the row, so a status changed meanwhile isn't missed
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def stale_pending(self, provider: str, before: datetime) -> list[Order]:
        stmt = select(Order).where(Order.status == OrderStatus.PENDING, Order.payment_provider == provider, Order.placed_at < before)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_payment_ref(self, ref: str) -> Order | None:
        stmt = select(Order).where(Order.payment_intent_id == ref).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def search(self, f: OrderQuery) -> tuple[list[Order], int]:
        where = []
        if f.q:
            like = f"%{escape_like(f.q.strip())}%"
            where.append(or_(
                Order.number.ilike(like), Order.email.ilike(like),
                Order.shipping_address["full_name"].astext.ilike(like),
            ))
        if f.statuses:
            where.append(Order.status.in_(list(f.statuses)))
        if f.provider:
            where.append(Order.payment_provider == f.provider)
        if f.date_from:
            where.append(Order.placed_at >= f.date_from)
        if f.date_to:
            where.append(Order.placed_at < f.date_to)
        if f.user_id is not None:
            where.append(Order.user_id == f.user_id)
        total = (await self.session.execute(select(func.count()).select_from(Order).where(*where))).scalar_one()
        stmt = (
            select(Order).where(*where)
            .order_by(Order.placed_at.desc().nulls_last(), Order.id.desc())
            .offset((f.page - 1) * f.page_size).limit(f.page_size)
        )
        return list((await self.session.execute(stmt)).scalars().all()), total

    async def status_counts(self) -> dict[str, int]:
        rows = await self.session.execute(select(Order.status, func.count()).group_by(Order.status))
        return {status.value: n for status, n in rows.all()}

    async def prior_orders(self, user_id: int | None, email: str) -> int:
        """Orders this person already has that still count (for 'first order only' codes)."""
        who = [func.lower(Order.email) == email.strip().lower()]
        if user_id is not None:
            who.append(Order.user_id == user_id)
        stmt = select(func.count()).select_from(Order).where(or_(*who), Order.status.in_(LIVE_STATUSES))
        return (await self.session.execute(stmt)).scalar_one()

    # -- timeline and refunds -----------------------------------------
    def add_event(self, order_id: int, kind: str, message: str, actor_id: int | None = None, data: dict | None = None) -> OrderEvent:
        event = OrderEvent(order_id=order_id, kind=kind, message=message[:500], actor_id=actor_id, data=data or {})
        self.session.add(event)
        return event

    async def events(self, order_id: int) -> list[OrderEvent]:
        stmt = select(OrderEvent).where(OrderEvent.order_id == order_id).order_by(OrderEvent.created_at, OrderEvent.id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def refunds(self, order_id: int) -> list[Refund]:
        stmt = select(Refund).where(Refund.order_id == order_id).order_by(Refund.created_at, Refund.id)
        return list((await self.session.execute(stmt)).scalars().all())

    # -- stock ---------------------------------------------------------
    async def take_stock(self, product_id: int, quantity: int) -> bool:
        """Lower the count by `quantity` if that many are left; mark the product sold out at zero."""
        left = Product.stock_quantity - quantity
        result = await self.session.execute(
            update(Product)
            .where(Product.id == product_id, Product.stock_quantity.is_not(None), Product.stock_quantity >= quantity)
            .values(
                stock_quantity=left,
                stock_status=case((left <= 0, StockStatus.OUT_OF_STOCK), else_=Product.stock_status),
            )
        )
        return result.rowcount == 1

    async def return_stock(self, product_id: int, quantity: int) -> None:
        more = Product.stock_quantity + quantity
        await self.session.execute(
            update(Product)
            .where(
                Product.id == product_id,
                Product.stock_quantity.is_not(None),
                Product.stock_status.in_([StockStatus.IN_STOCK, StockStatus.OUT_OF_STOCK]),  # not backorder or pre-order
            )
            .values(
                stock_quantity=more,
                stock_status=case(
                    (and_(Product.stock_status == StockStatus.OUT_OF_STOCK, more > 0), StockStatus.IN_STOCK), else_=Product.stock_status
                ),
            )
        )
