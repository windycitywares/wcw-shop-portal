"""Public shop endpoints: settings for the cart, the price quote, placing an order and the Stripe webhook."""

import json

from fastapi import APIRouter, Request, Response, status

from app.api.deps import OptionalUser, SessionDep
from app.api.v1.auth import client_ip, no_store
from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError
from app.payments import stripe
from app.schemas.commerce import ShopConfig
from app.schemas.order import CheckoutIn, OrderPlaced, QuoteIn, QuoteOut
from app.services.checkout import CheckoutService
from app.services.orders import OrderService
from app.services.settings import SettingsService

router = APIRouter(tags=["shop"])
MAX_WEBHOOK_BYTES = 1_000_000


@router.get("/shop-config", response_model=ShopConfig)
async def shop_config(response: Response, session: SessionDep):
    """What the cart and checkout need to know: is checkout open, how can people pay, where do we ship."""
    response.headers["Cache-Control"] = "public, max-age=30"
    return await SettingsService(session).public_config()


@router.post("/checkout/quote", response_model=QuoteOut)
async def quote(request: Request, response: Response, session: SessionDep, user: OptionalUser, data: QuoteIn):
    """Prices a cart: sales, a coupon code, shipping choices and tax. Prices always come from here, never from the browser."""
    no_store(response)
    return await CheckoutService(session).quote(data, user, client_ip(request))


@router.post("/checkout", response_model=OrderPlaced, status_code=status.HTTP_201_CREATED)
async def checkout(request: Request, response: Response, session: SessionDep, user: OptionalUser, data: CheckoutIn):
    no_store(response)
    return await CheckoutService(session).place(data, user, client_ip(request))


@router.post("/payments/stripe/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, session: SessionDep):
    """Stripe tells us a payment went through. Only requests signed with our webhook secret are believed."""
    secret = get_settings().stripe_webhook_secret
    if int(request.headers.get("content-length") or 0) > MAX_WEBHOOK_BYTES:
        raise ValidationFailedError("Request too large")
    payload = await request.body()
    if not secret or not stripe.verify_signature(payload, request.headers.get("stripe-signature"), secret):
        raise ValidationFailedError("Invalid signature")
    try:
        event = json.loads(payload)
    except ValueError as exc:
        raise ValidationFailedError("Invalid payload") from exc
    await OrderService(session).handle_stripe_event(event)
    return {"received": True}
