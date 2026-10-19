"""Orders after they are placed: payment, fulfilment, cancellation, refunds and what the shopper and staff see.

Every state change takes a row lock on the order first, so a Stripe webhook, the shopper's return page and a
staff member clicking at the same moment cannot apply the same payment (or refund) twice.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import FulfillmentStatus, OrderStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.domain import emailtext
from app.domain.carriers import canonical_carrier, tracking_url
from app.domain.coupons import normalize_code
from app.domain.csvsafe import to_csv
from app.domain.money import q2, to_cents
from app.domain.order_flow import (
    CANCELLED,
    DELIVERED,
    PROCESSING,
    REFUNDED,
    SHIPPED,
    can_transition,
    payment_status_after_refund,
    refundable,
)
from app.domain.timeutil import DateRange, resolve_range, to_store_time
from app.models.commerce import CouponRedemption, EmailOutbox, OrderEvent, Payment
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.schemas.orders import (
    CancelIn,
    MarkPaidIn,
    OrderAdminOut,
    OrderEventAdminOut,
    OrderFilters,
    OrderListItem,
    OrderListOut,
    OrderListStats,
    PaymentOut,
    RefundIn,
    ShipIn,
)
from app.schemas.settings import StoreSettings
from app.schemas.shop import OrderEventOut, OrderPublicOut, OrderSummaryOut
from app.services import emails, stock
from app.services.cart_pricing import variant_label
from app.services.payments import ProviderError, get_provider
from app.services.settings import SettingsService
from app.utils.text import escape_like

log = logging.getLogger("wcw.orders")

PAID_STATES = ("paid", "partially_refunded", "refunded")
SORTS = {
    "newest": (Order.placed_at.desc().nulls_last(), Order.id.desc()),
    "oldest": (Order.placed_at.asc().nulls_last(), Order.id.asc()),
    "total_desc": (Order.grand_total.desc(), Order.id.desc()),
    "total_asc": (Order.grand_total.asc(), Order.id.asc()),
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def actor_label(user: User | None, fallback: str = "system") -> str:
    return (user.full_name or user.email) if user else fallback


def address_text(address: dict[str, Any] | None) -> str:
    if not address:
        return ""
    line_city = " ".join(p for p in (f"{address.get('city')}," if address.get("city") else "", address.get("region"), address.get("postal_code")) if p)
    lines = [address.get("full_name"), address.get("company"), address.get("line1"), address.get("line2"), line_city, address.get("country")]
    return "\n".join(str(x) for x in lines if x)


async def localized_titles(session: AsyncSession, items: list[OrderItem], lang: str) -> dict[int, str]:
    """Item titles in the shopper's language when the live product has a translation, else the saved English title."""
    if lang == "en":
        return {}
    ids = {i.product_id for i in items if i.product_id}
    if not ids:
        return {}
    products = {p.id: p for p in (await session.execute(select(Product).where(Product.id.in_(ids)))).scalars().all()}
    parent_ids = {p.parent_id for p in products.values() if p.parent_id}
    parents = {}
    if parent_ids:
        parents = {p.id: p for p in (await session.execute(select(Product).where(Product.id.in_(parent_ids)))).scalars().all()}
    out: dict[int, str] = {}
    for item in items:
        product = products.get(item.product_id) if item.product_id else None
        if product is None:
            continue
        source = parents.get(product.parent_id) if product.parent_id else product
        translated = ((source.translations or {}).get(lang) or {}).get("title") if source else None
        if translated:
            label = variant_label(product)
            out[item.id] = f"{translated} — {label}" if label else translated
    return out


def delivery_estimate(order: Order, settings: StoreSettings, lang: str) -> str:
    base = order.paid_at or order.placed_at or utcnow()
    sh = settings.shipping
    first = to_store_time(base) + timedelta(days=sh.handling_days_min + sh.transit_days_min)
    last = to_store_time(base) + timedelta(days=sh.handling_days_max + sh.transit_days_max)
    return f"{emailtext.long_date(first, lang)} – {emailtext.long_date(last, lang)}"


async def email_context(session: AsyncSession, order: Order, settings: StoreSettings, lang: str | None = None) -> dict[str, Any]:
    lang = emailtext.loc(lang or order.locale)
    titles = await localized_titles(session, order.items, lang)
    instructions = None
    if order.payment_provider == "manual":
        texts = settings.payments.manual_instructions
        instructions = texts.get(lang) or texts.get("en")
    return {
        "name": order.customer_name, "number": order.number, "locale": lang,
        "items": [{"title": titles.get(i.id, i.title), "qty": i.quantity, "total": emailtext.money(i.line_total, lang)} for i in order.items],
        "subtotal": emailtext.money(order.subtotal, lang),
        "discount": emailtext.money(order.discount_total, lang) if order.discount_total > 0 else "",
        "shipping": emailtext.money(order.shipping_total, lang) if order.shipping_total > 0 else "",
        "tax": emailtext.money(order.tax_total, lang) if order.tax_total > 0 else "",
        "total": emailtext.money(order.grand_total, lang),
        "address": address_text(order.shipping_address),
        "link": emails.site_link(f"/order/{order.access_token}", lang),
        "instructions": instructions, "carrier": order.carrier, "tracking_number": order.tracking_number,
        "tracking_url": order.tracking_url, "delivery_estimate": delivery_estimate(order, settings, lang),
    }


def admin_recipient(settings: StoreSettings) -> str | None:
    app = get_settings()
    return settings.general.order_alert_email or app.contact_to or app.admin_email


# ---------------------------------------------------------------------------------------------
# What shoppers and staff are shown
# ---------------------------------------------------------------------------------------------


def _timeline(order: Order) -> list[OrderEventOut]:
    entries = [("placed", order.placed_at), ("paid", order.paid_at), ("shipped", order.shipped_at),
               ("delivered", order.delivered_at), ("cancelled", order.cancelled_at)]
    return [OrderEventOut(type=kind, message=None, created_at=when) for kind, when in entries if when]


async def public_out(session: AsyncSession, order: Order, lang: str | None = "en") -> OrderPublicOut:
    out = OrderPublicOut.model_validate(order)
    out.timeline = _timeline(order)
    out.access_token = order.access_token
    titles = await localized_titles(session, order.items, lang or "en")
    for item_out, item in zip(out.items, order.items, strict=True):
        item_out.title = titles.get(item.id, item_out.title)
    return out


def summary_out(order: Order) -> OrderSummaryOut:
    first = order.items[0] if order.items else None
    return OrderSummaryOut(
        id=order.id, number=order.number, status=order.status.value, payment_status=order.payment_status,
        fulfillment_status=order.fulfillment_status.value, grand_total=order.grand_total, placed_at=order.placed_at,
        item_count=sum(i.quantity for i in order.items), first_item_title=first.title if first else None,
        first_item_image=first.image_url if first else None, access_token=order.access_token,
    )


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -- loading ---------------------------------------------------------------------------
    async def get(self, order_id: int) -> Order:
        order = await self.session.get(Order, order_id)
        if order is None:
            raise NotFoundError("Order not found")
        return order

    async def _lock(self, order_id: int) -> Order:
        stmt = select(Order).where(Order.id == order_id).with_for_update().execution_options(populate_existing=True)
        order = (await self.session.execute(stmt)).scalar_one_or_none()
        if order is None:
            raise NotFoundError("Order not found")
        return order

    async def by_token(self, token: str) -> Order:
        order = (await self.session.execute(select(Order).where(Order.access_token == token))).scalar_one_or_none()
        if order is None:
            raise NotFoundError("We couldn't find that order.")
        return order

    async def lookup(self, number: str, email: str) -> Order:
        """Find an order from the number and email on the confirmation. The answer is the same for either mistake."""
        cleaned = number.strip().upper()
        if cleaned.isdigit():
            cleaned = f"WCW-{cleaned}"
        order = (await self.session.execute(
            select(Order).where(Order.number == cleaned, Order.email == email.strip().lower())
        )).scalar_one_or_none()
        if order is None:
            raise NotFoundError("We couldn't find an order with that number and email.")
        return order

    async def list_for_user(self, user: User, page: int, page_size: int) -> tuple[list[Order], int]:
        where = Order.user_id == user.id
        total = (await self.session.execute(select(func.count()).select_from(Order).where(where))).scalar_one()
        rows = await self.session.execute(
            select(Order).where(where).order_by(Order.placed_at.desc().nulls_last(), Order.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
        return list(rows.scalars().all()), total

    async def for_user(self, user: User, order_id: int) -> Order:
        order = await self.get(order_id)
        if order.user_id != user.id:
            raise NotFoundError("Order not found")
        return order

    # -- staff views -----------------------------------------------------------------------
    def _filtered(self, f: OrderFilters):
        stmt = select(Order)
        if f.q:
            like = f"%{escape_like(f.q.strip())}%"
            stmt = stmt.where(or_(Order.number.ilike(like), Order.email.ilike(like), Order.customer_name.ilike(like)))
        if f.status:
            try:
                stmt = stmt.where(Order.status == OrderStatus(f.status))
            except ValueError:
                raise ValidationFailedError("Unknown order status") from None
        if f.payment_status:
            stmt = stmt.where(Order.payment_status == f.payment_status)
        if f.channel:
            stmt = stmt.where(Order.channel == f.channel)
        if f.coupon:
            stmt = stmt.where(Order.coupon_code == normalize_code(f.coupon))
        if f.start or f.end:
            rng: DateRange = resolve_range(f.start, f.end, default_days=3650)
            stmt = stmt.where(Order.placed_at >= rng.start_utc, Order.placed_at < rng.end_utc)
        if f.needs_action:
            stmt = stmt.where(Order.status.in_([OrderStatus.PENDING, OrderStatus.PAID, OrderStatus.PROCESSING]))
        return stmt

    async def search(self, f: OrderFilters) -> OrderListOut:
        base = self._filtered(f)
        sub = base.subquery()
        stats_row = (await self.session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(sub.c.grand_total - sub.c.refunded_total).filter(
                    sub.c.paid_at.is_not(None), sub.c.status.notin_([OrderStatus.CANCELLED, OrderStatus.REFUNDED])), 0),
                func.count().filter(sub.c.status.in_([OrderStatus.PENDING, OrderStatus.PAID, OrderStatus.PROCESSING])),
            ).select_from(sub)
        )).one()
        order = SORTS.get(f.sort, SORTS["newest"])
        rows = (await self.session.execute(
            base.order_by(*order).offset((f.page - 1) * f.page_size).limit(f.page_size)
        )).scalars().all()
        items = []
        for o in rows:
            item = OrderListItem.model_validate(o)
            item.item_count = sum(i.quantity for i in o.items)
            items.append(item)
        return OrderListOut(
            items=items, total=stats_row[0], page=f.page, page_size=f.page_size,
            stats=OrderListStats(orders=stats_row[0], revenue=q2(stats_row[1]), open_orders=stats_row[2]),
        )

    async def rows_for_export(self, f: OrderFilters, limit: int = 5000) -> list[Order]:
        order = SORTS.get(f.sort, SORTS["newest"])
        return list((await self.session.execute(self._filtered(f).order_by(*order).limit(limit))).scalars().all())

    async def export_csv(self, f: OrderFilters) -> str:
        """Orders as a spreadsheet-safe CSV (one row per order; times in store time)."""
        header = [
            "Order", "Placed", "Status", "Payment", "Method", "Customer", "Email", "Items", "Subtotal", "Discount", "Shipping", "Tax",
            "Total", "Refunded", "Coupon", "Channel", "Ship to", "Carrier", "Tracking",
        ]
        rows = []
        for o in await self.rows_for_export(f):
            addr = o.shipping_address or {}
            ship_to = ", ".join(p for p in (addr.get("city"), addr.get("region"), addr.get("country")) if p)
            placed = to_store_time(o.placed_at).strftime("%Y-%m-%d %H:%M") if o.placed_at else ""
            rows.append((
                o.number, placed, o.status.value, o.payment_status, o.payment_provider, o.customer_name, o.email,
                sum(i.quantity for i in o.items), o.subtotal, o.discount_total, o.shipping_total, o.tax_total, o.grand_total,
                o.refunded_total, o.coupon_code, o.channel, ship_to, o.carrier, o.tracking_number,
            ))
        return to_csv(header, rows)

    async def admin_detail(self, order_id: int) -> OrderAdminOut:
        order = await self.get(order_id)
        out = OrderAdminOut.model_validate(order)
        payments = (await self.session.execute(select(Payment).where(Payment.order_id == order.id).order_by(Payment.id))).scalars().all()
        events = (await self.session.execute(select(OrderEvent).where(OrderEvent.order_id == order.id).order_by(OrderEvent.id.desc()))).scalars().all()
        out.payments = [PaymentOut.model_validate(p) for p in payments]
        out.events = [OrderEventAdminOut.model_validate(e) for e in events]
        out.customer_order_count = (await self.session.execute(
            select(func.count()).select_from(Order).where(Order.email == order.email)
        )).scalar_one()
        if order.items and all(i.unit_cost is not None for i in order.items):
            cost = sum((i.unit_cost * i.quantity for i in order.items), Decimal(0))
            out.cost_total = q2(cost)
            out.profit = q2(order.subtotal - order.discount_total - cost)
        return out

    # -- helpers ---------------------------------------------------------------------------
    def _event(self, order: Order, kind: str, message: str | None, actor: User | None = None, data: dict | None = None,
               actor_name: str | None = None) -> None:
        self.session.add(OrderEvent(
            order_id=order.id, type=kind, message=message, data=data or {}, actor_id=actor.id if actor else None,
            actor=actor_name or actor_label(actor),
        ))

    async def _parents(self, product_ids: set[int]) -> dict[int, int | None]:
        if not product_ids:
            return {}
        rows = await self.session.execute(select(Product.id, Product.parent_id).where(Product.id.in_(product_ids)))
        return {pid: parent for pid, parent in rows.all()}

    async def customer_mail(self, order: Order, kind: str, settings: StoreSettings, **extra: Any) -> EmailOutbox:
        ctx = await email_context(self.session, order, settings)
        return emails.enqueue(self.session, kind, order.email, {**ctx, **extra}, locale=order.locale, related_type="order", related_id=order.id)

    async def admin_mail(self, order: Order, settings: StoreSettings) -> EmailOutbox | None:
        to = admin_recipient(settings)
        if not to:
            return None
        ctx = await email_context(self.session, order, settings, "en")
        provider = {"stripe": "Card (Stripe)", "manual": "Pay later (awaiting payment)", "test": "Test payment"}.get(order.payment_provider or "", order.payment_provider or "")
        link = f"{get_settings().site_url.rstrip('/')}/admin/orders/{order.id}"
        return emails.enqueue(self.session, "admin_new_order", to, {
            "number": order.number, "customer": f"{order.customer_name or ''} <{order.email}>".strip(), "items": ctx["items"],
            "total": ctx["total"], "payment": provider, "link": link,
        }, locale="en", related_type="order", related_id=order.id)

    async def pending_charge(self, order_id: int) -> Payment | None:
        return (await self.session.execute(
            select(Payment).where(Payment.order_id == order_id, Payment.kind == "charge", Payment.status == "pending")
            .order_by(Payment.id.desc()).limit(1)
        )).scalar_one_or_none()

    # -- payment ---------------------------------------------------------------------------
    async def mark_paid(
        self, order_id: int, *, provider: str, reference: str | None = None, payment_intent: str | None = None,
        actor: User | None = None, note: str | None = None, notify_admin: bool | None = None,
    ) -> Order:
        order = await self._lock(order_id)
        if order.payment_status in PAID_STATES:
            return order  # the webhook and the return page both report the same payment
        settings = await SettingsService(self.session).load()
        rows: list[EmailOutbox] = []
        if order.status == OrderStatus.CANCELLED:
            self._event(order, "payment_after_cancel",
                        f"A payment of {order.grand_total} arrived after this order was cancelled. Refund it in the payment provider or reopen the order.",
                        actor)
            to = admin_recipient(settings)
            if to:
                rows.append(emails.enqueue(self.session, "digest", to, {
                    "subject": f"Payment received for cancelled order {order.number}",
                    "intro": f"A payment arrived for order {order.number}, which was already cancelled. Please refund it or contact the customer.",
                    "kpis": [("Order", order.number), ("Amount", emailtext.money(order.grand_total)), ("Customer", order.email)],
                    "link": f"{get_settings().site_url.rstrip('/')}/admin/orders/{order.id}",
                }, locale="en", related_type="order", related_id=order.id))
            await self.session.commit()
            await emails.deliver(self.session, rows)
            return order

        now = utcnow()
        order.payment_status, order.paid_at = "paid", now
        if order.status == OrderStatus.PENDING:
            order.status = OrderStatus.PAID
        if payment_intent:
            order.payment_intent_id = payment_intent
        charge = await self.pending_charge(order.id)
        if charge is not None:
            charge.status, charge.provider = "succeeded", provider
            charge.provider_ref = reference or charge.provider_ref
        else:
            self.session.add(Payment(order_id=order.id, provider=provider, kind="charge", status="succeeded", amount=order.grand_total,
                                     currency=order.currency, provider_ref=reference, created_by_id=actor.id if actor else None))
        parents = await self._parents({i.product_id for i in order.items if i.product_id})
        for item in order.items:
            if item.product_id:
                await stock.add_units_sold(self.session, item.product_id, parents.get(item.product_id), item.quantity)
        self._event(order, "paid", note or (f"Payment received via {provider}" + (f" ({reference})" if reference else "")), actor,
                    {"provider": provider, "reference": reference})
        await self.session.flush()
        rows.append(await self.customer_mail(order, "order_confirmation", settings))
        if notify_admin if notify_admin is not None else order.payment_provider != "manual":
            admin_row = await self.admin_mail(order, settings)
            if admin_row is not None:
                rows.append(admin_row)
        await self.session.commit()
        await emails.deliver(self.session, rows)
        return order

    async def _apply_stripe_session(self, order: Order, data: dict[str, Any]) -> Order:
        if data.get("client_reference_id") != order.number:
            log.error("Stripe session %s does not belong to order %s", data.get("id"), order.number)
            return order
        if data.get("payment_status") != "paid":
            return order
        if data.get("amount_total") != to_cents(order.grand_total) or str(data.get("currency", "")).lower() != order.currency.lower():
            log.error("Stripe amount mismatch for %s: %s %s", order.number, data.get("amount_total"), data.get("currency"))
            self._event(order, "payment_mismatch", "Stripe reports a payment whose amount does not match the order. Check it in Stripe before shipping.")
            await self.session.commit()
            return order
        return await self.mark_paid(order.id, provider="stripe", reference=data.get("id"), payment_intent=data.get("payment_intent"))

    async def confirm_stripe(self, order: Order, session_id: str | None) -> Order:
        """The shopper came back from Stripe: check with Stripe (not the URL) whether the order was paid."""
        if order.payment_provider != "stripe" or order.payment_status != "unpaid":
            return order
        charge = (await self.session.execute(
            select(Payment).where(Payment.order_id == order.id, Payment.kind == "charge").order_by(Payment.id.desc()).limit(1)
        )).scalar_one_or_none()
        ref = (charge.provider_ref if charge else None) or session_id
        if not ref:
            return order
        try:
            data = await get_provider("stripe").retrieve_session(ref)
        except ProviderError as exc:
            log.warning("Could not check Stripe session for %s: %s", order.number, exc)
            return order
        return await self._apply_stripe_session(order, data)

    async def staff_mark_paid(self, order_id: int, data: MarkPaidIn, actor: User) -> Order:
        """Staff confirm money that arrived outside the card flow (a bank transfer, cash, a check)."""
        order = await self.get(order_id)
        if order.payment_status != "unpaid":
            raise ConflictError("This order is already marked as paid.")
        if order.status == OrderStatus.CANCELLED:
            raise ConflictError("This order was cancelled.")
        if order.payment_provider == "stripe":
            raise ConflictError("Card payments are confirmed by Stripe. Use “Check payment” to ask Stripe right now.")
        return await self.mark_paid(
            order_id, provider=order.payment_provider or "manual", reference=data.reference, actor=actor, note=data.note, notify_admin=False
        )

    async def check_payment(self, order_id: int) -> Order:
        """Ask Stripe whether an unpaid card order was paid (the webhook may have been missed)."""
        order = await self.get(order_id)
        if order.payment_provider != "stripe" or order.payment_status != "unpaid":
            raise ConflictError("There is no open card payment on this order.")
        return await self.confirm_stripe(order, None)

    async def handle_stripe_event(self, event: dict[str, Any]) -> str:
        """Apply a verified Stripe webhook event. Returns a short result for the log. Safe to receive twice."""
        kind = event.get("type", "")
        obj = (event.get("data") or {}).get("object") or {}
        if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            order = await self._order_from_metadata(obj)
            if order is None:
                return "unknown order"
            await self._apply_stripe_session(order, obj)
            return "paid" if order.payment_status in PAID_STATES else "not paid"
        if kind == "checkout.session.async_payment_failed":
            order = await self._order_from_metadata(obj)
            if order is not None:
                self._event(order, "payment_failed", "The bank declined the payment.")
                await self.session.commit()
            return "failed"
        if kind == "charge.refunded":
            return await self._external_refund(obj)
        return "ignored"

    async def _order_from_metadata(self, obj: dict[str, Any]) -> Order | None:
        meta = obj.get("metadata") or {}
        number = obj.get("client_reference_id") or meta.get("order_number")
        if not number:
            return None
        return (await self.session.execute(select(Order).where(Order.number == number))).scalar_one_or_none()

    async def _external_refund(self, charge: dict[str, Any]) -> str:
        """A refund made in the Stripe dashboard: record the part we don't know about yet."""
        intent = charge.get("payment_intent")
        if not intent:
            return "ignored"
        found = (await self.session.execute(select(Order.id).where(Order.payment_intent_id == intent))).scalar_one_or_none()
        if found is None:
            return "unknown order"
        order = await self._lock(found)
        total_cents = int(charge.get("amount_refunded") or 0)
        new_cents = total_cents - to_cents(order.refunded_total)
        if new_cents <= 0:
            return "already recorded"
        amount = Decimal(new_cents) / 100
        self.session.add(Payment(order_id=order.id, provider="stripe", kind="refund", status="succeeded", amount=q2(amount),
                                 currency=order.currency, provider_ref=charge.get("id")))
        self._apply_refund_totals(order, q2(amount))
        self._event(order, "refund", f"Refund of {q2(amount)} made in the Stripe dashboard", actor_name="Stripe")
        await self.session.commit()
        return "refund recorded"

    # -- fulfilment ------------------------------------------------------------------------
    async def start_processing(self, order_id: int, actor: User, note: str | None = None) -> Order:
        order = await self._lock(order_id)
        if not can_transition(order.status.value, PROCESSING):
            raise ConflictError("Only paid orders can be moved to processing.")
        order.status = OrderStatus.PROCESSING
        self._event(order, "processing", note or "Order is being prepared", actor)
        await self.session.commit()
        return order

    async def ship(self, order_id: int, data: ShipIn, actor: User) -> Order:
        order = await self._lock(order_id)
        if not can_transition(order.status.value, SHIPPED):
            raise ConflictError("Only paid orders can be shipped.")
        carrier = canonical_carrier(data.carrier)
        number = " ".join((data.tracking_number or "").split()) or None
        order.status, order.fulfillment_status, order.shipped_at = OrderStatus.SHIPPED, FulfillmentStatus.FULFILLED, utcnow()
        order.carrier, order.tracking_number = carrier, number
        order.tracking_url = data.tracking_url or tracking_url(carrier, number)
        label = " ".join(p for p in (carrier, number) if p)
        self._event(order, "shipped", f"Shipped{': ' + label if label else ''}", actor)
        rows = []
        if data.notify_customer:
            rows.append(await self.customer_mail(order, "order_shipped", await SettingsService(self.session).load()))
        await self.session.commit()
        await emails.deliver(self.session, rows)
        return order

    async def mark_delivered(self, order_id: int, actor: User, note: str | None = None) -> Order:
        order = await self._lock(order_id)
        if not can_transition(order.status.value, DELIVERED):
            raise ConflictError("Only shipped orders can be marked delivered.")
        order.status, order.delivered_at = OrderStatus.DELIVERED, utcnow()
        self._event(order, "delivered", note or "Delivered", actor)
        row = await self.customer_mail(order, "order_delivered", await SettingsService(self.session).load())
        await self.session.commit()
        await emails.deliver(self.session, [row])
        return order

    async def add_note(self, order_id: int, message: str, actor: User) -> None:
        order = await self.get(order_id)
        self._event(order, "note", message, actor)
        await self.session.commit()

    async def resend_confirmation(self, order_id: int, actor: User) -> None:
        order = await self.get(order_id)
        settings = await SettingsService(self.session).load()
        kind = "order_confirmation" if order.payment_status in PAID_STATES else "order_received"
        row = await self.customer_mail(order, kind, settings)
        self._event(order, "email", f"Confirmation email sent again to {order.email}", actor)
        await self.session.commit()
        await emails.deliver(self.session, [row])

    # -- cancel and refund -----------------------------------------------------------------
    def _apply_refund_totals(self, order: Order, amount: Decimal) -> None:
        order.refunded_total = q2(order.refunded_total + amount)
        order.payment_status = payment_status_after_refund(order.grand_total, order.refunded_total)
        if order.payment_status == "refunded" and can_transition(order.status.value, REFUNDED):
            order.status = OrderStatus.REFUNDED

    async def _refund_via_provider(self, order: Order, amount: Decimal, reason: str | None, actor: User | None) -> None:
        provider_name = order.payment_provider or "manual"
        try:
            result = await get_provider(provider_name).refund(order, amount, reason)
        except ProviderError as exc:
            log.error("Refund for %s failed: %s", order.number, exc)
            raise ConflictError(f"The payment provider could not refund this order ({exc}). Nothing was changed.") from exc
        self.session.add(Payment(
            order_id=order.id, provider=provider_name, kind="refund", status="succeeded", amount=amount, currency=order.currency,
            provider_ref=str(result.get("refund") or "") or None, raw=result, created_by_id=actor.id if actor else None,
        ))
        self._apply_refund_totals(order, amount)

    async def refund(self, order_id: int, data: RefundIn, actor: User) -> Order:
        order = await self._lock(order_id)
        if order.payment_status not in ("paid", "partially_refunded"):
            raise ConflictError("This order has no payment to refund.")
        amount = q2(data.amount)
        limit = refundable(order.grand_total, order.refunded_total)
        if amount > limit:
            raise ValidationFailedError(f"You can refund at most {limit} on this order.")
        by_id = {i.id: i for i in order.items}
        for entry in data.items:
            item = by_id.get(entry.item_id)
            if item is None:
                raise ValidationFailedError("That item isn't part of this order.")
            if entry.quantity > item.quantity - item.refunded_quantity:
                raise ValidationFailedError(f"Only {item.quantity - item.refunded_quantity} of “{item.title}” can still be refunded.")
        await self._refund_via_provider(order, amount, data.reason, actor)
        restocked: set[int] = set()
        parents = await self._parents({by_id[e.item_id].product_id for e in data.items if by_id[e.item_id].product_id})
        for entry in data.items:
            item = by_id[entry.item_id]
            item.refunded_quantity += entry.quantity
            if data.restock and item.product_id:
                await stock.give_back(self.session, item.product_id, entry.quantity)
                if parents.get(item.product_id):
                    restocked.add(parents[item.product_id])
        await stock.sync_parents(self.session, restocked)
        self._event(order, "refund", f"Refunded {amount}" + (f": {data.reason}" if data.reason else ""), actor, {"amount": str(amount)})
        rows = []
        if data.notify_customer:
            settings = await SettingsService(self.session).load()
            rows.append(await self.customer_mail(order, "order_refunded", settings, amount=emailtext.money(amount, order.locale)))
        await self.session.commit()
        await emails.deliver(self.session, rows)
        return order

    async def _release(self, order: Order) -> None:
        """Give back what an unfulfilled order was holding: stock, units sold, the coupon use and an open payment."""
        parents = await self._parents({i.product_id for i in order.items if i.product_id})
        touched: set[int] = set()
        for item in order.items:
            if not item.product_id:
                continue
            await stock.give_back(self.session, item.product_id, item.quantity - item.refunded_quantity)
            if order.paid_at is not None:
                await stock.add_units_sold(self.session, item.product_id, parents.get(item.product_id), -item.quantity)
            if parents.get(item.product_id):
                touched.add(parents[item.product_id])
        await stock.sync_parents(self.session, touched)
        redemptions = (await self.session.execute(select(CouponRedemption).where(CouponRedemption.order_id == order.id))).scalars().all()
        for redemption in redemptions:
            await self.session.execute(
                text("UPDATE coupons SET used_count = GREATEST(used_count - 1, 0), updated_at = now() WHERE id = :id"), {"id": redemption.coupon_id}
            )
            await self.session.delete(redemption)
        for charge in (await self.session.execute(
            select(Payment).where(Payment.order_id == order.id, Payment.kind == "charge", Payment.status == "pending")
        )).scalars().all():
            charge.status = "cancelled"

    async def cancel(self, order_id: int, data: CancelIn, actor: User | None, *, quiet: bool = False) -> Order:
        order = await self._lock(order_id)
        if not can_transition(order.status.value, CANCELLED):
            raise ConflictError("This order can't be cancelled any more. Use a refund instead.")
        open_session: str | None = None
        if order.payment_provider == "stripe" and order.payment_status == "unpaid":
            pending = await self.pending_charge(order.id)
            open_session = pending.provider_ref if pending else None
        if order.payment_status in ("paid", "partially_refunded"):
            remaining = refundable(order.grand_total, order.refunded_total)
            if remaining > 0:
                if not data.refund:
                    raise ConflictError("This order is paid. Cancel it together with a refund, or refund it first.")
                await self._refund_via_provider(order, remaining, data.reason or "Order cancelled", actor)
        await self._release(order)
        order.status, order.cancelled_at = OrderStatus.CANCELLED, utcnow()
        self._event(order, "cancelled", "Cancelled" + (f": {data.reason}" if data.reason else ""), actor)
        rows = []
        if data.notify_customer and not quiet:
            settings = await SettingsService(self.session).load()
            rows.append(await self.customer_mail(order, "order_cancelled", settings, refund_note=order.paid_at is not None))
        await self.session.commit()
        if open_session:
            await get_provider("stripe").expire_session(open_session)
        await emails.deliver(self.session, rows)
        return order

    async def expire_unpaid(self, older_than: timedelta = timedelta(minutes=90), limit: int = 50) -> dict[str, int]:
        """Cron: card orders nobody paid release their stock. A payment Stripe confirms late is still honoured."""
        cutoff = utcnow() - older_than
        ids = (await self.session.execute(
            select(Order.id).where(Order.status == OrderStatus.PENDING, Order.payment_status == "unpaid", Order.payment_provider == "stripe",
                                   Order.placed_at < cutoff).order_by(Order.id).limit(limit)
        )).scalars().all()
        result = {"paid": 0, "cancelled": 0}
        for order_id in ids:
            order = await self.get(order_id)
            before = order.payment_status
            order = await self.confirm_stripe(order, None)
            if order.payment_status != before:
                result["paid"] += 1
                continue
            try:
                await self.cancel(order_id, CancelIn(reason="Payment was not completed", refund=False, notify_customer=False), None, quiet=True)
                result["cancelled"] += 1
            except ConflictError:
                await self.session.rollback()
        return result

