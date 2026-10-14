"""Order lifecycle: payment, fulfilment, cancelling and refunds, plus who may see an order."""

import hmac
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import FulfillmentStatus, OrderStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.permissions import Permission, has_permission
from app.models.commerce import CouponRedemption, Refund
from app.models.order import Order
from app.models.user import User
from app.payments import stripe
from app.repositories.commerce import CouponRepository
from app.repositories.order import OrderQuery, OrderRepository
from app.schemas.common import Page
from app.schemas.order import CancelIn, OrderEventOut, OrderListItem, OrderOut, RefundIn, RefundOut, ShipIn
from app.services import order_emails
from app.services.settings import SettingsService

log = logging.getLogger("wcw.orders")

# What a customer sees on their order's timeline (staff notes and payment oddities stay private).
PUBLIC_EVENT_KINDS = {"placed", "paid", "processing", "shipped", "delivered", "cancelled", "refund"}
CANCELLABLE = (OrderStatus.PENDING, OrderStatus.PAID, OrderStatus.PROCESSING)
UNPAID_CARD_ORDER_MINUTES = 45


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _money(value: Decimal) -> str:
    return f"${value:,.2f}"


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = OrderRepository(session)
        self.coupons = CouponRepository(session)

    # -- reading -----------------------------------------------------------------
    async def _out(self, order: Order, staff: bool) -> OrderOut:
        out = OrderOut.model_validate(order)
        events = await self.repo.events(order.id)
        out.events = [OrderEventOut.model_validate(e) for e in events if staff or e.kind in PUBLIC_EVENT_KINDS]
        out.refunds = [RefundOut.model_validate(r) for r in await self.repo.refunds(order.id)]
        # The model carries staff-only fields too; customers get them blanked.
        out.id, out.user_id, out.internal_note, out.payment_ref, out.locale = (
            (order.id, order.user_id, order.internal_note, order.payment_intent_id, order.locale) if staff
            else (None, None, None, None, None)
        )
        return out

    async def view(self, number: str, *, user: User | None, token: str | None) -> OrderOut:
        """The order, for its owner, for anyone holding the secret link from the confirmation email, or for staff."""
        order = await self.repo.get_by_number(number)
        staff = user is not None and has_permission(user.role, Permission.ORDERS_MANAGE)
        owner = user is not None and order is not None and order.user_id == user.id
        by_link = bool(order and token and order.access_token and hmac.compare_digest(token.encode(), order.access_token.encode()))
        if order is None or not (staff or owner or by_link):
            raise NotFoundError("We couldn't find that order.")  # the same answer whether it exists or not
        return await self._out(order, staff)

    @staticmethod
    def _list_item(order: Order) -> OrderListItem:
        item = OrderListItem.model_validate(order)
        item.customer = (order.shipping_address or {}).get("full_name")
        item.item_count = sum(i.quantity for i in order.items)
        return item

    async def search(self, query: OrderQuery) -> Page[OrderListItem]:
        rows, total = await self.repo.search(query)
        return Page[OrderListItem](items=[self._list_item(o) for o in rows], total=total, page=query.page, page_size=query.page_size)

    async def counts(self) -> dict[str, int]:
        return await self.repo.status_counts()

    # -- shared steps (callers commit) -------------------------------------------
    async def mark_paid(self, order: Order, *, actor_id: int | None, note: str | None = None) -> bool:
        if order.status != OrderStatus.PENDING:
            return False
        order.status = OrderStatus.PAID
        order.paid_at = _now()
        self.repo.add_event(order.id, "paid", note or "Payment received", actor_id)
        return True

    async def _give_back_holds(self, order: Order) -> None:
        """Put the stock back and free the coupon use (the order no longer needs them)."""
        for item in sorted(order.items, key=lambda i: i.product_id or 0):
            if item.product_id:
                await self.repo.return_stock(item.product_id, item.quantity)
        row = (await self.session.execute(select(CouponRedemption).where(CouponRedemption.order_id == order.id))).scalar_one_or_none()
        if row is not None:
            await self.session.execute(delete(CouponRedemption).where(CouponRedemption.id == row.id))
            await self.coupons.give_back_use(row.coupon_id)

    async def release_unpaid(self, order: Order, reason: str) -> None:
        """Cancel an order that was never paid and let go of what it was holding."""
        if order.status != OrderStatus.PENDING:
            return
        await self._give_back_holds(order)
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = _now()
        self.repo.add_event(order.id, "cancelled", reason)
        await self.session.commit()

    async def notify_owner(self, order: Order, headline: str | None = None) -> None:
        cfg = await SettingsService(self.session).load()
        s = get_settings()
        to = str(cfg.order_alert_email) if cfg.order_alert_email else (s.contact_to or s.admin_email)
        await order_emails.owner_alert(order, to, headline)

    async def _locked(self, number: str) -> Order:
        order = await self.repo.get_by_number(number, lock=True)
        if order is None:
            raise NotFoundError("Order not found")
        return order

    async def _pay_back(self, order: Order, amount: Decimal, reason: str | None, actor_id: int | None) -> None:
        provider_ref = None
        if order.payment_provider == "stripe":
            intent = order.payment_intent_id or ""
            if not intent.startswith("pi_"):
                raise ConflictError("This card payment hasn't been confirmed by Stripe yet, so it can't be refunded here.")
            try:
                result = await stripe.refund(payment_intent=intent, amount=amount, order_number=order.number,
                                             already_refunded=Decimal(order.refunded_total))
            except (stripe.StripeError, OSError) as exc:
                raise ValidationFailedError(f"Stripe couldn't refund this: {exc}") from exc
            provider_ref = result.get("id")
        self.session.add(Refund(order_id=order.id, amount=amount, reason=reason, provider_ref=provider_ref, created_by_id=actor_id))
        order.refunded_total = Decimal(order.refunded_total) + amount
        note = f"Refunded {_money(amount)}" + (f": {reason}" if reason else "")
        self.repo.add_event(order.id, "refund", note, actor_id, {"amount": str(amount)})

    # -- staff actions -----------------------------------------------------------
    async def set_status(self, number: str, status: str, actor: User) -> OrderOut:
        order = await self._locked(number)
        wanted = {"paid": (OrderStatus.PENDING, OrderStatus.PAID), "processing": (OrderStatus.PAID, OrderStatus.PROCESSING),
                  "delivered": (OrderStatus.SHIPPED, OrderStatus.DELIVERED)}[status]
        if order.status != wanted[0]:
            raise ConflictError(f"This order is {order.status.value}, so it can't be marked {status}.")
        if status == "paid":
            await self.mark_paid(order, actor_id=actor.id, note=f"Marked as paid by {actor.email}")
        elif status == "processing":
            order.status = OrderStatus.PROCESSING
            self.repo.add_event(order.id, "processing", "Being prepared", actor.id)
        else:
            order.status = OrderStatus.DELIVERED
            order.delivered_at = _now()
            self.repo.add_event(order.id, "delivered", "Delivered", actor.id)
        await self.session.commit()
        if status == "paid":
            await order_emails.order_confirmation(order, paid=True)
        return await self._out(order, True)

    async def ship(self, number: str, data: ShipIn, actor: User) -> OrderOut:
        order = await self._locked(number)
        if order.status not in (OrderStatus.PAID, OrderStatus.PROCESSING):
            raise ConflictError("Only a paid order can be shipped. Mark it as paid first.")
        order.status = OrderStatus.SHIPPED
        order.fulfillment_status = FulfillmentStatus.FULFILLED
        order.shipped_at = _now()
        order.carrier, order.tracking_number = data.carrier, data.tracking_number
        detail = " ".join(x for x in [f"via {data.carrier}" if data.carrier else "", f"({data.tracking_number})" if data.tracking_number else ""] if x)
        self.repo.add_event(order.id, "shipped", f"Shipped {detail}".strip(), actor.id)
        await self.session.commit()
        if data.notify:
            await order_emails.order_shipped(order)
        return await self._out(order, True)

    async def cancel(self, number: str, data: CancelIn, actor: User) -> OrderOut:
        order = await self._locked(number)
        if order.status not in CANCELLABLE:
            raise ConflictError("This order has already shipped or been closed. Use a refund instead.")
        refunded = False
        remaining = Decimal(order.grand_total) - Decimal(order.refunded_total)
        if order.paid_at is not None and data.refund and remaining > 0:
            await self._pay_back(order, remaining, data.reason or "Order cancelled", actor.id)
            refunded = True
        await self._give_back_holds(order)
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = _now()
        why = f"Cancelled by {actor.email}" + (f": {data.reason}" if data.reason else "")
        self.repo.add_event(order.id, "cancelled", why, actor.id)
        await self.session.commit()
        await order_emails.order_cancelled(order, refunded)
        return await self._out(order, True)

    async def refund(self, number: str, data: RefundIn, actor: User) -> OrderOut:
        order = await self._locked(number)
        if order.paid_at is None:
            raise ConflictError("Only a paid order can be refunded.")
        remaining = Decimal(order.grand_total) - Decimal(order.refunded_total)
        if data.amount > remaining:
            raise ValidationFailedError(f"You can refund up to {_money(remaining)} on this order.")
        full = data.amount == remaining and Decimal(order.refunded_total) == 0
        if data.restock and not full:
            raise ValidationFailedError("Returning items to stock is only possible when the whole order is refunded.")
        await self._pay_back(order, data.amount, data.reason, actor.id)
        if data.restock:
            await self._restock(order)
        if Decimal(order.refunded_total) >= Decimal(order.grand_total) and order.status != OrderStatus.CANCELLED:
            order.status = OrderStatus.REFUNDED
        await self.session.commit()
        if data.notify:
            await order_emails.order_refunded(order, data.amount, data.reason)
        return await self._out(order, True)

    async def _restock(self, order: Order) -> None:
        for item in sorted(order.items, key=lambda i: i.product_id or 0):
            if item.product_id:
                await self.repo.return_stock(item.product_id, item.quantity)
        for r in await self.repo.refunds(order.id):
            r.restocked = True

    async def set_note(self, number: str, note: str | None, actor: User) -> OrderOut:
        order = await self._locked(number)
        order.internal_note = (note or "").strip() or None
        await self.session.commit()
        return await self._out(order, True)

    # -- card payments (Stripe) --------------------------------------------------
    async def handle_stripe_event(self, event: dict) -> None:
        kind = event.get("type")
        obj = (event.get("data") or {}).get("object") or {}
        if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            await self._card_paid(obj)
        elif kind in ("checkout.session.expired", "checkout.session.async_payment_failed"):
            await self._card_expired(obj)

    async def _order_for_session(self, obj: dict) -> Order | None:
        number = obj.get("client_reference_id") or (obj.get("metadata") or {}).get("order_number")
        if not number:
            return None
        order = await self.repo.get_by_number(str(number), lock=True)
        return order if order is not None and order.payment_provider == "stripe" else None

    async def _card_paid(self, obj: dict) -> None:
        if obj.get("payment_status") != "paid":
            return  # still processing; Stripe sends another event when the money arrives
        order = await self._order_for_session(obj)
        if order is None:
            log.warning("Stripe payment for an unknown order: %s", obj.get("client_reference_id"))
            return
        if order.status != OrderStatus.PENDING:
            if order.status == OrderStatus.CANCELLED:
                self.repo.add_event(order.id, "payment_after_cancel", "A card payment arrived after the order was cancelled. Refund it in Stripe or reopen the order.")
                await self.session.commit()
                await self.notify_owner(order, f"Action needed: payment for cancelled order {order.number}")
            return
        paid_ok = obj.get("amount_total") == stripe.to_cents(Decimal(order.grand_total)) and str(obj.get("currency", "")).lower() == order.currency.lower()
        if not paid_ok:
            self.repo.add_event(order.id, "payment_mismatch", f"Stripe reported {obj.get('amount_total')} {obj.get('currency')}, expected {order.grand_total} {order.currency}. Not marked as paid.")
            await self.session.commit()
            await self.notify_owner(order, f"Action needed: payment amount differs for {order.number}")
            return
        order.payment_intent_id = obj.get("payment_intent") or order.payment_intent_id
        await self.mark_paid(order, actor_id=None, note="Card payment received")
        await self.session.commit()
        await order_emails.order_confirmation(order, paid=True)
        await self.notify_owner(order)

    async def _card_expired(self, obj: dict) -> None:
        order = await self._order_for_session(obj)
        if order is not None:
            await self.release_unpaid(order, "The card payment window closed without a payment")

    async def expire_unpaid_card_orders(self) -> int:
        """Release card orders that were started but never paid (run regularly by the job runner)."""
        cutoff = _now() - timedelta(minutes=UNPAID_CARD_ORDER_MINUTES)
        stale = await self.repo.stale_pending("stripe", cutoff)
        for order in stale:
            locked = await self._locked(order.number)
            await self.release_unpaid(locked, "The card payment window closed without a payment")
        return len(stale)
