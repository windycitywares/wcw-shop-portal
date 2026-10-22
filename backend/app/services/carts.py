"""Server-side cart snapshots: abandoned-cart reports and (only with permission) gentle reminders.

The shopper's real cart lives in their browser. We keep a copy so we can measure where people drop off and, if
they allowed it, send at most two quiet emails. Permission is the ticked "remind me" box; a shop set to "email
every shopper" also takes the address left at checkout as permission. Without permission no address is kept.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import coupons as codes
from app.domain import emailtext
from app.domain.cart_rules import ACTIVE_WINDOW
from app.models.analytics import AnalyticsSession
from app.models.commerce import Cart
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.schemas.carts import CartLineOut, CartListOut, CartRowOut, CartSummaryOut
from app.schemas.shop import CartItemIn, CartSyncIn
from app.services import emails
from app.services.auth import NewsletterService
from app.services.cart_pricing import CartPricer, localized_title
from app.services.promotions import issue_coupon
from app.services.settings import SettingsService

log = logging.getLogger("wcw.carts")
STALE_DAYS = 30


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _signature(items: list[dict]) -> list[tuple]:
    return sorted((i["product_id"], i["quantity"], tuple(sorted((i.get("options") or {}).items()))) for i in items)


class CartService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def sync(self, data: CartSyncIn, user: User | None) -> str:
        """Save the cart snapshot and return its token (new when the old cart was already ordered)."""
        now = utcnow()
        cart: Cart | None = None
        if data.token:
            cart = (await self.session.execute(select(Cart).where(Cart.token == data.token))).scalar_one_or_none()
        if cart is not None and cart.converted_order_id is not None:
            cart = None  # that cart became an order: a new one starts
        if cart is None and not data.items:
            return data.token or secrets.token_urlsafe(24)  # nothing to save for an empty cart
        priced = await CartPricer(self.session).price(data.items, coupon_code=None, lang=data.locale or "en", user=user, now=now)
        items = [{"product_id": pl.product.id, "quantity": pl.quantity, "options": pl.options} for pl in priced.lines]
        if cart is None:
            cart = Cart(token=secrets.token_urlsafe(24), created_at=now)
            self.session.add(cart)
        elif _signature(cart.items or []) != _signature(items):
            cart.reminder_count, cart.last_reminder_at, cart.recovery_coupon = 0, None, None  # a different cart: start over
        cart.items = items
        cart.item_count = sum(i["quantity"] for i in items)
        cart.subtotal = priced.quote.subtotal
        cart.coupon_code = codes.normalize_code(data.coupon) or None
        cart.locale = data.locale
        cart.user_id = user.id if user else cart.user_id
        # Permission: the ticked box, or (when the shop emails every shopper) the address given at checkout.
        # Signed in: the customer's own account address counts too (Settings → Cart reminders "remind signed-in
        # customers", on by default; every reminder carries an unsubscribe link).
        cfg = (await SettingsService(self.session).load()).cart_recovery
        email = str(data.email).lower() if data.email else (user.email if user else None)
        own_account = user is not None and email == user.email.lower() and cfg.remind_signed_in
        allowed = bool(email) and (bool(data.reminders_ok) or cfg.email_everyone or own_account)
        cart.reminders_ok = allowed
        cart.email = email if allowed else None  # no permission, no email address kept
        cart.last_activity_at = now
        if data.checkout_started and cart.checkout_started_at is None:
            cart.checkout_started_at = now
        if data.session_id and cart.session_id != data.session_id:
            visit = await self.session.get(AnalyticsSession, data.session_id)
            cart.session_id = visit.id if visit is not None else cart.session_id
        await self.session.commit()
        return cart.token

    async def recover(self, token: str) -> dict:
        cart = (await self.session.execute(select(Cart).where(Cart.token == token))).scalar_one_or_none()
        if cart is None or cart.converted_order_id is not None or not cart.items:
            return {"items": [], "coupon": None}
        return {"items": [CartItemIn(**i).model_dump() for i in cart.items], "coupon": cart.recovery_coupon or cart.coupon_code}


class CartRecoveryJob:
    """Cron: send the reminders that are due (see Settings > Cart reminders)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(self, limit: int = 100) -> dict[str, int]:
        settings = await SettingsService(self.session).load()
        cfg = settings.cart_recovery
        result = {"sent": 0, "skipped": 0}
        if not cfg.enabled or cfg.max_reminders < 1:
            return result
        now = utcnow()
        first = and_(Cart.reminder_count == 0, Cart.last_activity_at <= now - timedelta(hours=cfg.first_delay_hours))
        second = and_(Cart.reminder_count == 1, Cart.last_activity_at <= now - timedelta(hours=cfg.second_delay_hours),
                      Cart.last_reminder_at <= now - timedelta(hours=24))
        due = (await self.session.execute(
            select(Cart).where(
                Cart.reminders_ok.is_(True), Cart.email.is_not(None), Cart.item_count > 0, Cart.converted_order_id.is_(None),
                Cart.reminder_count < cfg.max_reminders, Cart.last_activity_at > now - timedelta(days=STALE_DAYS),
                or_(first, second),
            ).order_by(Cart.id).limit(limit).with_for_update(skip_locked=True)
        )).scalars().all()
        queued = []
        for cart in due:
            email = cart.email or ""
            locale = emailtext.loc(cart.locale)
            sub = await NewsletterService(self.session).contact(email, locale, "cart_reminder")
            if sub.unsubscribed_at is not None:
                cart.reminders_ok, cart.email = False, None
                result["skipped"] += 1
                continue
            if await self._ordered_since(cart, email):
                # They checked out another way (another device, a new cart): "you left something" would be wrong.
                cart.reminders_ok = False
                result["skipped"] += 1
                continue
            items = [CartItemIn(**i) for i in cart.items]
            priced = await CartPricer(self.session).price(items, coupon_code=None, lang=locale, now=now)
            if not priced.lines:
                cart.item_count = 0
                result["skipped"] += 1
                continue
            step = cart.reminder_count + 1
            ctx = {
                "name": None, "step": step, "link": emails.site_link(f"/cart?recover={cart.token}", locale),
                "items": [{"title": localized_title(pl.product, pl.parent, locale), "qty": pl.quantity} for pl in priced.lines],
                "unsubscribe_url": emails.unsubscribe_url(sub.unsubscribe_token, locale),
            }
            if step >= 2 and cfg.second_offer_percent > 0:
                coupon = await issue_coupon(
                    self.session, email=email, kind="percent", value=Decimal(cfg.second_offer_percent), expires_days=7,
                    source="abandoned_cart", prefix="BACK", campaign="cart-recovery", name="Cart reminder offer",
                )
                cart.recovery_coupon = coupon.code
                ctx.update(code=coupon.code, percent=cfg.second_offer_percent)
            queued.append(emails.enqueue(self.session, "abandoned_cart", email, ctx, locale=locale, related_type="cart", related_id=cart.id))
            cart.reminder_count, cart.last_reminder_at = step, now
            result["sent"] += 1
        await self.session.commit()
        await emails.deliver(self.session, queued)
        return result

    async def _ordered_since(self, cart: Cart, email: str) -> bool:
        """Has this shopper (by address, or by account) placed an order since they last touched the cart?"""
        who = Order.email == email if cart.user_id is None else or_(Order.email == email, Order.user_id == cart.user_id)
        found = await self.session.execute(select(Order.id).where(who, Order.created_at >= cart.last_activity_at).limit(1))
        return found.first() is not None




SUMMARY_SQL = text("""
SELECT count(*)::int AS started,
       count(*) FILTER (WHERE c.converted_order_id IS NOT NULL)::int AS converted,
       count(*) FILTER (WHERE c.converted_order_id IS NULL AND c.last_activity_at <= :active_cutoff)::int AS abandoned,
       count(*) FILTER (WHERE c.converted_order_id IS NULL AND c.last_activity_at > :active_cutoff)::int AS active,
       COALESCE(sum(c.subtotal) FILTER (WHERE c.converted_order_id IS NULL AND c.last_activity_at <= :active_cutoff), 0) AS abandoned_value,
       count(*) FILTER (WHERE c.converted_order_id IS NULL AND c.last_activity_at <= :active_cutoff
                          AND c.reminders_ok AND c.email IS NOT NULL)::int AS reachable,
       COALESCE(sum(c.reminder_count), 0)::int AS reminders_sent,
       count(*) FILTER (WHERE c.converted_order_id IS NOT NULL AND c.reminder_count > 0
                          AND c.converted_at > c.last_reminder_at)::int AS recovered,
       COALESCE(sum(o.grand_total - o.refunded_total) FILTER (WHERE c.converted_order_id IS NOT NULL AND c.reminder_count > 0
                          AND c.converted_at > c.last_reminder_at AND o.paid_at IS NOT NULL), 0) AS recovered_value,
       count(*) FILTER (WHERE c.checkout_started_at IS NOT NULL)::int AS reached_checkout
FROM carts c LEFT JOIN orders o ON o.id = c.converted_order_id
WHERE c.item_count > 0 AND c.created_at >= :start AND c.created_at < :end
""")


class CartAdminService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _status(cart: Cart, now: datetime) -> str:
        if cart.converted_order_id is not None:
            recovered = cart.reminder_count > 0 and cart.converted_at and cart.last_reminder_at and cart.converted_at > cart.last_reminder_at
            return "recovered" if recovered else "converted"
        return "active" if cart.last_activity_at > now - ACTIVE_WINDOW else "abandoned"

    async def summary(self, start: datetime, end: datetime, now: datetime | None = None) -> CartSummaryOut:
        now = now or utcnow()
        row = (await self.session.execute(SUMMARY_SQL, {"active_cutoff": now - ACTIVE_WINDOW, "start": start, "end": end})).mappings().one()
        settled = row["converted"] + row["abandoned"]
        return CartSummaryOut(
            started=row["started"], converted=row["converted"], abandoned=row["abandoned"], active=row["active"],
            abandoned_value=Decimal(row["abandoned_value"]), abandonment_rate=(row["abandoned"] / settled) if settled else None,
            reachable=row["reachable"], reminders_sent=row["reminders_sent"], recovered=row["recovered"],
            recovered_value=Decimal(row["recovered_value"]), reached_checkout=row["reached_checkout"],
        )

    async def list(self, status: str | None, start: datetime, end: datetime, page: int, page_size: int) -> CartListOut:
        now = utcnow()
        cutoff = now - ACTIVE_WINDOW
        conds = [Cart.item_count > 0, Cart.created_at >= start, Cart.created_at < end]
        if status == "abandoned":
            conds += [Cart.converted_order_id.is_(None), Cart.last_activity_at <= cutoff]
        elif status == "active":
            conds += [Cart.converted_order_id.is_(None), Cart.last_activity_at > cutoff]
        elif status == "converted":
            conds.append(Cart.converted_order_id.is_not(None))
        elif status == "recovered":
            conds += [Cart.converted_order_id.is_not(None), Cart.reminder_count > 0, Cart.converted_at > Cart.last_reminder_at]
        total = (await self.session.execute(select(func.count()).select_from(Cart).where(*conds))).scalar_one()
        carts = (await self.session.execute(
            select(Cart).where(*conds).order_by(Cart.last_activity_at.desc(), Cart.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        ids = {int(i["product_id"]) for cart in carts for i in cart.items or []}
        titles = dict((await self.session.execute(select(Product.id, Product.title).where(Product.id.in_(ids)))).all()) if ids else {}
        numbers = {}
        converted = [c.converted_order_id for c in carts if c.converted_order_id]
        if converted:
            numbers = dict((await self.session.execute(select(Order.id, Order.number).where(Order.id.in_(converted)))).all())
        rows = [
            CartRowOut(
                id=c.id, status=self._status(c, now), item_count=c.item_count, subtotal=c.subtotal, coupon_code=c.coupon_code,
                email=c.email, reminders_sent=c.reminder_count, checkout_started=c.checkout_started_at is not None,
                created_at=c.created_at, last_activity_at=c.last_activity_at, order_number=numbers.get(c.converted_order_id),
                items=[CartLineOut(product_id=int(i["product_id"]), title=titles.get(int(i["product_id"]), "Removed product"), quantity=int(i["quantity"]))
                       for i in c.items or []],
            )
            for c in carts
        ]
        return CartListOut(items=rows, total=total, page=page, page_size=page_size, summary=await self.summary(start, end, now))
