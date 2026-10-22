"""The shopper's side of buying: store config, cart price quotes, checkout and orders."""

import json
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status

from app.api.deps import CurrentUser, OptionalUser, SessionDep
from app.api.v1.auth import client_ip, no_store
from app.core import captcha
from app.core.config import get_settings
from app.core.exceptions import TooManyRequestsError, ValidationFailedError
from app.core.i18n import LANG_PATTERN
from app.core.rate_limit import cart_sync_by_ip, checkout_by_ip, coupon_failures_by_ip, order_lookup_by_ip, quotes_by_ip
from app.schemas.common import Message, Page
from app.schemas.settings import PublicConfig
from app.schemas.shop import (
    CartSyncIn,
    CartSyncOut,
    CheckoutIn,
    CheckoutOut,
    ConfirmPaymentIn,
    OrderLookupIn,
    OrderNotificationsOut,
    OrderPublicOut,
    OrderSummaryOut,
    PaymentActionOut,
    QuoteIn,
    QuoteOut,
)
from app.services.account_notifications import AccountNotificationService
from app.services.cart_pricing import CartPricer, to_out
from app.services.carts import CartService
from app.services.checkout import CheckoutService
from app.services.orders import OrderService, public_out, summary_out
from app.services.payments.stripe import verify_signature
from app.services.settings import SettingsService, public_config

router = APIRouter(tags=["shop"])
Lang = Annotated[str, Query(pattern=LANG_PATTERN)]
MAX_WEBHOOK_BYTES = 1_000_000


@router.get("/shop/config", response_model=PublicConfig)
async def shop_config(response: Response, session: SessionDep, lang: Lang = "en"):
    """Prices, shipping promise, banner text and payment choices. Safe to cache briefly."""
    response.headers["Cache-Control"] = "public, max-age=30"
    return public_config(await SettingsService(session).load(), lang)


@router.post("/cart/quote", response_model=QuoteOut)
async def quote(request: Request, response: Response, session: SessionDep, user: OptionalUser, data: QuoteIn):
    """Price a cart: sale prices, offers, coupon, shipping and tax, plus notes about anything that changed."""
    no_store(response)
    ip = client_ip(request)
    if quotes_by_ip.is_blocked(ip) or (data.coupon and coupon_failures_by_ip.is_blocked(ip)):
        raise TooManyRequestsError("Too many requests. Please wait a moment and try again.")
    quotes_by_ip.hit(ip)
    priced = await CartPricer(session).price(
        data.items, coupon_code=data.coupon, email=data.email, destination=data.destination, lang=data.lang, user=user,
    )
    outcome = priced.quote.coupon
    if outcome is not None and outcome.reason in ("unknown", "wrong_customer"):
        coupon_failures_by_ip.hit(ip)  # slows down anyone guessing codes
    return to_out(priced)


@router.post("/cart/sync", response_model=CartSyncOut)
async def sync_cart(request: Request, response: Response, session: SessionDep, user: OptionalUser, data: CartSyncIn):
    no_store(response)
    ip = client_ip(request)
    if cart_sync_by_ip.is_blocked(ip):
        raise TooManyRequestsError("Too many requests. Please wait a moment and try again.")
    cart_sync_by_ip.hit(ip)
    return CartSyncOut(token=await CartService(session).sync(data, user))


@router.get("/cart/recover/{token}")
async def recover_cart(token: str, response: Response, session: SessionDep):
    """The items of a cart from a reminder email, so the shopper can pick up where they left off."""
    no_store(response)
    return await CartService(session).recover(token[:40])


@router.post("/checkout", response_model=CheckoutOut, status_code=status.HTTP_201_CREATED)
async def checkout(request: Request, response: Response, session: SessionDep, user: OptionalUser, data: CheckoutIn):
    no_store(response)
    ip = client_ip(request)
    if checkout_by_ip.is_blocked(ip):
        raise TooManyRequestsError("Too many orders from this network. Please try again in a little while.")
    if user is None:
        await captcha.verify(data.captcha_token, ip, action="checkout")
    result = await CheckoutService(session).place(data, user=user, user_agent=request.headers.get("user-agent"))
    checkout_by_ip.hit(ip)
    return result


# ---- orders by their private link ---------------------------------------------------------


def _private(response: Response) -> None:
    no_store(response)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


@router.get("/orders/by-token/{token}", response_model=OrderPublicOut)
async def order_by_token(token: str, response: Response, session: SessionDep, lang: Lang = "en"):
    _private(response)
    return await public_out(session, await OrderService(session).by_token(token[:64]), lang)


@router.post("/orders/by-token/{token}/confirm", response_model=OrderPublicOut)
async def confirm_payment(token: str, response: Response, session: SessionDep, data: ConfirmPaymentIn, lang: Lang = "en"):
    """The shopper is back from Stripe: ask Stripe whether the order was paid, then show it."""
    _private(response)
    service = OrderService(session)
    order = await service.by_token(token[:64])
    order = await service.confirm_stripe(order, data.session_id)
    return await public_out(session, order, lang)


@router.post("/orders/by-token/{token}/pay", response_model=PaymentActionOut)
async def pay_again(token: str, response: Response, session: SessionDep, lang: Lang = "en"):
    """Open the card payment again for an order that was left unpaid."""
    _private(response)
    return await CheckoutService(session).resume_payment(token[:64], lang)


@router.post("/orders/lookup", response_model=Message)
async def lookup_order(request: Request, response: Response, session: SessionDep, data: OrderLookupIn):
    """Find an order by number and email. The answer is the private link, which is also emailed to the address."""
    _private(response)
    ip = client_ip(request)
    if order_lookup_by_ip.is_blocked(ip):
        raise TooManyRequestsError("Too many attempts. Please wait a few minutes and try again.")
    order_lookup_by_ip.hit(ip)
    order = await OrderService(session).lookup(data.number, str(data.email))
    return Message(detail=order.access_token)


# ---- signed-in shoppers ---------------------------------------------------------------------


@router.get("/account/orders", response_model=Page[OrderSummaryOut])
async def my_orders(response: Response, session: SessionDep, user: CurrentUser, page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50)):
    no_store(response)
    rows, total = await OrderService(session).list_for_user(user, page, page_size)
    return Page[OrderSummaryOut](items=[summary_out(o) for o in rows], total=total, page=page, page_size=page_size)


@router.get("/account/orders/{order_id}", response_model=OrderPublicOut)
async def my_order(order_id: int, response: Response, session: SessionDep, user: CurrentUser, lang: Lang = "en"):
    no_store(response)
    service = OrderService(session)
    return await public_out(session, await service.for_user(user, order_id), lang)


@router.get("/account/notifications", response_model=OrderNotificationsOut)
async def my_notifications(response: Response, session: SessionDep, user: CurrentUser, limit: int = Query(20, ge=1, le=50)):
    """Order milestones for the bell in the header: placed, paid, shipped, delivered, cancelled, refunded."""
    no_store(response)
    return await AccountNotificationService(session).feed(user, limit)


@router.post("/account/notifications/seen", status_code=status.HTTP_204_NO_CONTENT)
async def my_notifications_seen(session: SessionDep, user: CurrentUser):
    await AccountNotificationService(session).mark_seen(user)


# ---- Stripe ---------------------------------------------------------------------------------


async def _test_copy_exists() -> bool:
    from sqlalchemy import text

    from app.core import appmode
    from app.core.database import engine

    async with engine.connect() as conn:
        found = await conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = :s)"), {"s": appmode.TEST_SCHEMA})
        return bool(found.scalar_one())


@router.post("/payments/stripe/webhook", include_in_schema=False)
async def stripe_webhook(request: Request):
    """Stripe tells us a payment succeeded or a refund happened. Only requests signed with our secret are accepted."""
    settings = get_settings()
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_WEBHOOK_BYTES:
        raise ValidationFailedError("Request too large")
    body = await request.body()
    signature = request.headers.get("stripe-signature")
    # Live events always update the live data and test events the test copy, whichever mode the shop is in now.
    if len(body) > MAX_WEBHOOK_BYTES:
        raise ValidationFailedError("Request too large")
    if settings.stripe_webhook_secret and verify_signature(body, signature, settings.stripe_webhook_secret):
        target = "live"
    elif settings.stripe_test_webhook_secret and verify_signature(body, signature, settings.stripe_test_webhook_secret):
        target = "test"
    else:
        raise ValidationFailedError("Invalid signature")
    if target == "test" and not await _test_copy_exists():
        return {"received": True, "result": "ignored: there is no test copy"}
    try:
        event = json.loads(body)
    except ValueError as exc:
        raise ValidationFailedError("Invalid payload") from exc
    from app.core import appmode
    from app.core.database import SessionFactory

    with appmode.use(target):  # every connection and email in this block follows the event's mode
        async with SessionFactory() as scoped:
            result = await OrderService(scoped).handle_stripe_event(event)
    return {"received": True, "result": result}

