"""The cart quote and placing an order."""

import logging
import secrets
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import captcha
from app.core.config import get_settings
from app.core.enums import FulfillmentStatus, OrderStatus
from app.core.exceptions import ConflictError, ServiceUnavailableError, TooManyRequestsError, ValidationFailedError
from app.core.rate_limit import checkouts_by_ip, coupon_misses_by_ip
from app.models.commerce import CouponRedemption
from app.models.order import Order, OrderItem
from app.models.user import User
from app.payments import stripe
from app.pricing import engine
from app.repositories.commerce import CouponRepository
from app.repositories.order import OrderRepository
from app.schemas.order import (
    AppliedCouponOut,
    CheckoutIn,
    OrderPlaced,
    ProblemOut,
    QuoteIn,
    QuoteLineOut,
    QuoteOut,
    ShippingOptionOut,
    TaxLineOut,
)
from app.services import order_emails
from app.services.account import localized_path
from app.services.auth import NewsletterService
from app.services.orders import OrderService
from app.services.pricing import CartPricer, Priced
from app.services.settings import SettingsService

log = logging.getLogger("wcw.checkout")


def quote_out(priced: Priced) -> QuoteOut:
    q = priced.quote
    descriptions = {m.code: m.description for m in priced.shipping}
    lines = []
    for item, line in zip(priced.items, q.lines):
        limit = priced.issues.get(item.product.id)
        lines.append(QuoteLineOut(
            key=item.key, product_id=item.product.id, quantity=line.quantity, list_price=line.list_price, unit_price=line.unit_price,
            line_total=line.line_total, discount=line.coupon_discount, sale_label=line.sale_label,
            issue="limited" if item.product.id in priced.issues else None, max_quantity=limit,
        ))
    return QuoteOut(
        currency=q.currency, lines=lines, unavailable=priced.unavailable, list_subtotal=q.list_subtotal,
        sale_savings=q.sale_savings, subtotal=q.subtotal,
        coupon=AppliedCouponOut(code=q.coupon_code, discount=q.coupon_discount, free_shipping=q.coupon_free_shipping)
        if q.coupon_code else None,
        coupon_problem=ProblemOut(code=q.coupon_problem.code, message=q.coupon_problem.message, data=q.coupon_problem.data)
        if q.coupon_problem else None,
        shipping_options=[
            ShippingOptionOut(code=o.code, name=o.name, description=descriptions.get(o.code), base_price=o.base_price,
                              price=o.price, free=o.free, min_days=o.min_days, max_days=o.max_days)
            for o in q.shipping_options
        ],
        shipping_method=q.shipping_method, shipping_total=q.shipping_total, shipping_discount=q.shipping_discount,
        tax_lines=[TaxLineOut(name=t.name, rate=t.rate, amount=t.amount) for t in q.tax_lines], tax_total=q.tax_total,
        total=q.total, free_shipping_threshold=q.free_shipping_threshold, free_shipping_remaining=q.free_shipping_remaining,
    )


class CheckoutService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.pricer = CartPricer(session)
        self.orders = OrderRepository(session)
        self.coupons = CouponRepository(session)
        self.settings = SettingsService(session)

    async def quote(self, data: QuoteIn, user: User | None, ip: str) -> QuoteOut:
        if data.coupon_code and coupon_misses_by_ip.is_blocked(ip):
            raise TooManyRequestsError("Too many codes tried. Please wait a few minutes and try again.")
        priced = await self.pricer.price(
            data.items, coupon_code=data.coupon_code, shipping_code=data.shipping_method,
            destination=engine.Destination(country=data.country, region=data.region, postal_code=data.postal_code),
            email=data.email, user=user,
        )
        if priced.quote.coupon_problem and priced.quote.coupon_problem.code == "invalid":
            coupon_misses_by_ip.hit(ip)
        return quote_out(priced)

    async def place(self, data: CheckoutIn, user: User | None, ip: str) -> OrderPlaced:
        cfg = await self.settings.load()
        if not cfg.checkout_enabled:
            raise ServiceUnavailableError("Checkout isn't open yet. Please contact us and we'll help you order.")
        if data.payment_provider not in {o.id for o in self.settings.payment_options(cfg)}:
            raise ValidationFailedError("That way of paying isn't available.")
        if checkouts_by_ip.is_blocked(ip):
            raise TooManyRequestsError("Too many orders from this network. Please try again in an hour.")
        await captcha.verify(data.captcha_token, ip, action="checkout")

        email = str(data.email).strip().lower()
        address = data.shipping_address
        priced = await self.pricer.price(
            data.items, coupon_code=data.coupon_code, shipping_code=data.shipping_method,
            destination=engine.Destination(country=address.country, region=address.region, postal_code=address.postal_code),
            email=email, user=user, lock_coupon=True,
        )
        q = priced.quote
        if priced.unavailable:
            raise ConflictError("Some items in your cart can't be bought any more. Please review your cart.")
        if not priced.items:
            raise ValidationFailedError("Your cart is empty.")
        for item in priced.items:
            limit = priced.issues.get(item.product.id)
            if item.product.id in priced.issues:
                raise ConflictError(f"Only {limit} left of {item.title}. Please change the quantity.")
        if q.shipping_method is None:
            raise ValidationFailedError("Choose a shipping method that delivers to your address.")
        if data.coupon_code and q.coupon_problem:
            raise ValidationFailedError(q.coupon_problem.message)
        if data.expected_total is not None and data.expected_total != q.total:
            raise ConflictError("The total changed since you last looked. Please review it and place the order again.")

        chosen = next(m for m in priced.shipping if m.code == q.shipping_method)
        now = datetime.now(timezone.utc)
        order = Order(
            number=await self.orders.next_number(), user_id=user.id if user else None, email=email,
            status=OrderStatus.PENDING, fulfillment_status=FulfillmentStatus.UNFULFILLED, currency=q.currency,
            subtotal=q.subtotal, tax_total=q.tax_total, shipping_total=q.shipping_total,
            discount_total=q.coupon_discount, grand_total=q.total, sale_savings=q.sale_savings,
            shipping_discount=q.shipping_discount, shipping_address=address.model_dump(),
            billing_address=(data.billing_address or address).model_dump(), shipping_method=chosen.name,
            payment_provider=data.payment_provider, notes=data.notes, placed_at=now,
            access_token=secrets.token_urlsafe(24), coupon_code=q.coupon_code, locale=data.locale,
            tax_lines=[{"name": t.name, "rate": str(t.rate), "amount": str(t.amount)} for t in q.tax_lines],
            items=[
                OrderItem(
                    product_id=r.product.id, sku=r.product.sku, title=r.title, unit_price=line.unit_price,
                    quantity=line.quantity, line_total=line.line_total, list_price=line.list_price,
                    discount=line.coupon_discount, attributes=r.attributes,
                )
                for r, line in zip(priced.items, q.lines)
            ],
        )
        self.orders.add(order)
        await self.session.flush()

        # Hold the stock. Products are taken in id order so two orders can't wait on each other.
        for r in sorted(priced.items, key=lambda r: r.product.id):
            if r.stock_limit is not None and not await self.orders.take_stock(r.product.id, r.quantity):
                raise ConflictError(f"{r.title} was just bought by someone else. Please review your cart.")

        if priced.coupon is not None:
            if not await self.coupons.take_use(priced.coupon.id):
                raise ConflictError("This code has just been used up.")
            self.session.add(CouponRedemption(
                coupon_id=priced.coupon.id, order_id=order.id, user_id=user.id if user else None, email=email,
                amount=q.coupon_discount,
            ))

        self.orders.add_event(order.id, "placed", f"Order placed ({data.payment_provider})")
        service = OrderService(self.session)
        if data.payment_provider == "test":
            await service.mark_paid(order, actor_id=None, note="Test payment (no charge)")
        await self.session.commit()
        checkouts_by_ip.hit(ip)  # counted once the order exists, so a typo in the form never uses up an hour's allowance

        if data.subscribe:
            try:
                await NewsletterService(self.session).subscribe(email)
            except Exception:  # noqa: BLE001 — a newsletter problem must never lose an order
                log.exception("Newsletter sign-up at checkout failed")

        placed = OrderPlaced(number=order.number, access_token=order.access_token, status=order.status, total=order.grand_total, next="paid")
        if data.payment_provider == "offline":
            placed.next = "offline"
            placed.instructions = cfg.offline_instructions or None
            await order_emails.order_confirmation(order, paid=False, offline_instructions=cfg.offline_instructions or None)
            await service.notify_owner(order)
        elif data.payment_provider == "stripe":
            placed.next = "pay"
            placed.payment_url = await self._start_card_payment(order, service)
        else:
            await order_emails.order_confirmation(order, paid=True)
            await service.notify_owner(order)
        return placed

    async def _start_card_payment(self, order: Order, service: OrderService) -> str:
        """Ask Stripe for a payment page. If that fails the order is released again so nothing is held."""
        page = localized_path(order.locale or "en", f"/order/{order.number}")
        site = get_settings().site_url.rstrip("/")
        try:
            result = await stripe.create_checkout_session(
                order_number=order.number, email=order.email, amount=Decimal(order.grand_total), currency=order.currency,
                description=", ".join(f"{i.quantity} x {i.title}" for i in order.items),
                success_url=f"{site}{page}?token={order.access_token}&paid=1",
                cancel_url=f"{site}{localized_path(order.locale or 'en', '/checkout')}",
            )
        except (stripe.StripeError, OSError, ServiceUnavailableError):
            await service.release_unpaid(order, "Card payment could not be started")
            raise ServiceUnavailableError("We couldn't start the card payment. Nothing was charged. Please try again.")
        order.payment_intent_id = result.get("id")
        await self.session.commit()
        url = result.get("url")
        if not url:
            await service.release_unpaid(order, "Card payment could not be started")
            raise ServiceUnavailableError("We couldn't start the card payment. Nothing was charged. Please try again.")
        return url
