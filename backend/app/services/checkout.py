"""Placing an order: price the cart once more, reserve stock, use the coupon, save the order, start the payment.

The order is committed before the payment provider is called, so no database locks are held while we wait for
Stripe. If the provider then refuses, the order is cancelled and everything it held is released.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import OrderStatus
from app.core.exceptions import AuthenticationError, ConflictError, ValidationFailedError
from app.domain.coupons import normalize_code
from app.models.account import Address
from app.models.analytics import AnalyticsSession
from app.models.commerce import Cart, CouponRedemption, OrderEvent, Payment
from app.models.order import Order, OrderItem
from app.models.user import User
from app.schemas.orders import CancelIn
from app.schemas.settings import StoreSettings
from app.schemas.shop import CheckoutIn, CheckoutOut, DestinationIn, PaymentActionOut
from app.services import emails
from app.services.cart_pricing import CartPricer, tracked_stock
from app.services.messages import t
from app.services.auth import NewsletterService
from app.services.orders import PAID_STATES, OrderService, public_out
from app.services.payments import ProviderError, get_provider
from app.services import stock
from app.services.settings import SettingsService, payment_methods

log = logging.getLogger("wcw.checkout")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CheckoutService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _by_key(self, key: str) -> Order | None:
        return (await self.session.execute(select(Order).where(Order.idempotency_key == key))).scalar_one_or_none()

    async def place(self, data: CheckoutIn, *, user: User | None, user_agent: str | None = None) -> CheckoutOut:
        lang = data.locale
        settings = await SettingsService(self.session).load()
        if user is None and not settings.general.guest_checkout:
            raise AuthenticationError(t("checkout.account_required", lang))
        if data.payment_method not in payment_methods(settings):
            raise ValidationFailedError(t("checkout.payment_unavailable", lang))
        email = str(data.email).strip().lower()
        ship = data.shipping_address

        # One checkout at a time per email: a double click or a retry waits here, then sees the first order.
        await self.session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"checkout:{email}"})
        if data.idempotency_key:
            existing = await self._by_key(data.idempotency_key)
            if existing is not None:
                if existing.email != email:
                    raise ConflictError(t("checkout.changed", lang))
                return await self._existing_response(existing, lang)

        priced = await CartPricer(self.session).price(
            data.items, coupon_code=data.coupon, email=email, lang=lang, user=user,
            destination=DestinationIn(country=ship.country, region=ship.region, postal_code=ship.postal_code),
        )
        if not priced.lines:
            raise ValidationFailedError(t("checkout.empty", lang))
        if priced.blocking:
            raise ConflictError(t("checkout.changed", lang))
        quote = priced.quote
        if not quote.shipping.deliverable:
            raise ValidationFailedError(t("shipping.undeliverable", lang))
        if normalize_code(data.coupon) and (quote.coupon is None or not quote.coupon.valid):
            raise ValidationFailedError(t(f"coupon.{quote.coupon.reason if quote.coupon else 'unknown'}", lang))

        channel = device = session_id = None
        if data.session_id:
            visit = await self.session.get(AnalyticsSession, data.session_id)
            if visit is not None:
                session_id, channel, device = visit.id, visit.channel, visit.device

        now = utcnow()
        sequence = (await self.session.execute(text("SELECT nextval('order_number_seq')"))).scalar_one()
        number = f"WCW-{sequence}"
        billing = data.billing_address or ship
        order = Order(
            number=number, user_id=user.id if user else None, email=email, currency="USD", subtotal=quote.subtotal,
            tax_total=quote.tax.amount if quote.tax else 0, shipping_total=quote.shipping.amount, discount_total=quote.discount_total,
            grand_total=quote.total, tax_rate=quote.tax.rate_percent if quote.tax else 0,
            shipping_address=ship.model_dump(), billing_address=billing.model_dump(), shipping_method="standard",
            payment_provider=data.payment_method, payment_status="unpaid", notes=data.notes, placed_at=now,
            access_token=secrets.token_urlsafe(32), customer_name=ship.full_name, phone=data.phone or ship.phone, locale=lang,
            discounts=[{"type": d.type, "label": d.label, "code": d.code, "amount": float(d.amount)} for d in quote.discounts],
            session_id=session_id, channel=channel, device=device, idempotency_key=data.idempotency_key,
            marketing_opt_in=data.marketing_opt_in,
        )
        for line, pl, share in zip(quote.lines, priced.lines, quote.line_discounts, strict=True):
            product, parent = pl.product, pl.parent
            image_source = product if product.images else parent
            images = (image_source.images if image_source else None) or []
            attributes = {k: v for k, v in (product.attributes or {}).items() if isinstance(v, (str, int, float, bool))} if product.parent_id else {}
            attributes.update(pl.options)
            cost = product.cost_price if product.cost_price is not None else (parent.cost_price if parent else None)
            order.items.append(OrderItem(
                product_id=product.id, sku=product.sku, title=product.title, unit_price=line.unit_price, quantity=line.quantity,
                line_total=line.total, attributes=attributes, slug=(parent or product).slug,
                image_url=images[0].get("url") if images else None, list_price=line.list_price, unit_cost=cost,
                sale_id=line.sale_id, discount_total=share,
            ))
        self.session.add(order)
        await self.session.flush()

        # Reserve stock in a fixed order (by product id) so two checkouts can't wait on each other.
        for pl in sorted(priced.lines, key=lambda x: x.product.id):
            if tracked_stock(pl.product) is not None and not await stock.take(self.session, pl.product.id, pl.quantity):
                title = next((i.title for i in order.items if i.product_id == pl.product.id), pl.product.title)
                raise ConflictError(t("checkout.sold_out", lang, title=title))
        await stock.sync_parents(self.session, {pl.parent.id for pl in priced.lines if pl.parent})

        if priced.coupon_row is not None:
            used = next((d for d in quote.discounts if d.id == priced.coupon_row.id and d.code), None)
            if used is not None:
                taken = await self.session.execute(
                    text("UPDATE coupons SET used_count = used_count + 1, updated_at = now() "
                         "WHERE id = :id AND is_active AND (usage_limit IS NULL OR used_count < usage_limit)"),
                    {"id": priced.coupon_row.id},
                )
                if taken.rowcount != 1:
                    raise ConflictError(t("checkout.code_used_up", lang))
                self.session.add(CouponRedemption(coupon_id=priced.coupon_row.id, order_id=order.id, user_id=user.id if user else None,
                                                  email=email, amount=used.amount))
                order.coupon_code = priced.coupon_row.code

        self.session.add(Payment(order_id=order.id, provider=data.payment_method, kind="charge", status="pending",
                                 amount=order.grand_total, currency=order.currency))
        self.session.add(OrderEvent(order_id=order.id, type="placed", actor="customer",
                                    message=f"Order placed ({data.payment_method})", data={"ip_country": ship.country}))
        await self._conversions(data, order, email, lang, user, now)
        await self.session.commit()
        return await self._start_payment(order, lang, settings)

    async def _conversions(self, data: CheckoutIn, order: Order, email: str, lang: str, user: User | None, now: datetime) -> None:
        if data.cart_token:
            cart = (await self.session.execute(select(Cart).where(Cart.token == data.cart_token))).scalar_one_or_none()
            if cart is not None:
                cart.converted_order_id, cart.converted_at = order.id, now
        if data.marketing_opt_in:
            await NewsletterService(self.session).add(email, lang, source="checkout", welcome=False, commit=False)
        if data.save_address and user is not None:
            ship = data.shipping_address
            have = (await self.session.execute(select(Address).where(Address.user_id == user.id))).scalars().all()
            same = any(a.line1.lower() == ship.line1.lower() and a.postal_code.lower() == ship.postal_code.lower() and a.country == ship.country for a in have)
            if not same and len(have) < get_settings().max_addresses_per_user:
                fields = ship.model_dump()
                self.session.add(Address(user_id=user.id, **fields, is_default=not have))

    # -- paying ----------------------------------------------------------------------------
    def _return_urls(self, order: Order, lang: str) -> dict[str, str]:
        base = emails.site_link(f"/order/{order.access_token}", lang)
        return {"success": f"{base}?paid=1&session_id={{CHECKOUT_SESSION_ID}}", "cancel": f"{base}?payment=cancelled"}

    def _instructions(self, settings: StoreSettings, lang: str) -> str | None:
        texts = settings.payments.manual_instructions
        return texts.get(lang) or texts.get("en")

    async def _start_payment(self, order: Order, lang: str, settings: StoreSettings, attempt: int = 1) -> CheckoutOut:
        service = OrderService(self.session)
        provider = get_provider(order.payment_provider or "manual")
        try:
            start = await provider.start(order, self._return_urls(order, lang), lang, attempt)
        except ProviderError as exc:
            log.error("Could not start %s payment for %s: %s", order.payment_provider, order.number, exc)
            await service.cancel(order.id, CancelIn(reason="The payment could not be started", refund=False, notify_customer=False), None, quiet=True)
            raise ValidationFailedError(t("checkout.payment_failed", lang)) from exc

        charge = await service.pending_charge(order.id)
        if charge is not None and start.provider_ref:
            charge.provider_ref, charge.raw = start.provider_ref, start.raw
        if start.status == "paid":
            await self.session.commit()
            order = await service.mark_paid(order.id, provider=order.payment_provider or "test", reference=start.provider_ref)
            return CheckoutOut(order=await public_out(self.session, order, lang), payment=PaymentActionOut(provider=order.payment_provider or "", status="paid"))
        rows = []
        if start.status == "pending":  # pay later: tell the customer how, and the owner that an order is waiting
            rows.append(await service.customer_mail(order, "order_received", settings))
            admin_row = await service.admin_mail(order, settings)
            if admin_row is not None:
                rows.append(admin_row)
        await self.session.commit()
        await emails.deliver(self.session, rows)
        action = PaymentActionOut(
            provider=order.payment_provider or "", status=start.status, redirect_url=start.redirect_url,  # type: ignore[arg-type]
            instructions=self._instructions(settings, lang) if order.payment_provider == "manual" else None,
        )
        return CheckoutOut(order=await public_out(self.session, order, lang), payment=action)

    async def _existing_response(self, order: Order, lang: str) -> CheckoutOut:
        """Same request sent twice: show the order we already made instead of making another."""
        settings = await SettingsService(self.session).load()
        action = await self._payment_action(order, lang, settings)
        return CheckoutOut(order=await public_out(self.session, order, lang), payment=action)

    async def _payment_action(self, order: Order, lang: str, settings: StoreSettings) -> PaymentActionOut:
        provider = order.payment_provider or ""
        if order.payment_status in PAID_STATES:
            return PaymentActionOut(provider=provider, status="paid")
        if provider == "stripe" and order.status == OrderStatus.PENDING:
            charge = (await self.session.execute(
                select(Payment).where(Payment.order_id == order.id, Payment.kind == "charge").order_by(Payment.id.desc()).limit(1)
            )).scalar_one_or_none()
            if charge is not None and charge.provider_ref:
                try:
                    current = await get_provider("stripe").retrieve_session(charge.provider_ref)
                except ProviderError:
                    current = {}
                if current.get("status") == "open" and current.get("url"):
                    return PaymentActionOut(provider=provider, status="redirect", redirect_url=current["url"])
        return PaymentActionOut(provider=provider, status="pending",
                                instructions=self._instructions(settings, lang) if provider == "manual" else None)

    async def resume_payment(self, token: str, lang: str) -> PaymentActionOut:
        """"Complete your payment" for a card order that was left unpaid: the same Stripe page, or a fresh one."""
        service = OrderService(self.session)
        order = await service.by_token(token)
        settings = await SettingsService(self.session).load()
        if order.payment_provider != "stripe" or order.status != OrderStatus.PENDING or order.payment_status != "unpaid":
            return await self._payment_action(order, lang, settings)
        action = await self._payment_action(order, lang, settings)
        if action.status == "redirect":
            return action
        attempts = (await self.session.execute(
            select(func.count()).select_from(Payment).where(Payment.order_id == order.id, Payment.kind == "charge")
        )).scalar_one()
        try:
            start = await get_provider("stripe").start(order, self._return_urls(order, lang), lang, attempts + 1)
        except ProviderError as exc:
            log.error("Could not restart payment for %s: %s", order.number, exc)
            raise ValidationFailedError(t("checkout.payment_failed", lang)) from exc
        self.session.add(Payment(order_id=order.id, provider="stripe", kind="charge", status="pending", amount=order.grand_total,
                                 currency=order.currency, provider_ref=start.provider_ref, raw=start.raw))
        await self.session.commit()
        return PaymentActionOut(provider="stripe", status="redirect", redirect_url=start.redirect_url)

