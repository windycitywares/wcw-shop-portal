"""The shopper's side of buying: store config and cart price quotes (checkout and orders follow in a later batch)."""

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from app.api.deps import OptionalUser, SessionDep
from app.api.v1.auth import client_ip, no_store
from app.core.exceptions import TooManyRequestsError
from app.core.i18n import LANG_PATTERN
from app.core.rate_limit import coupon_failures_by_ip, quotes_by_ip
from app.schemas.settings import PublicConfig
from app.schemas.shop import QuoteIn, QuoteOut
from app.services.cart_pricing import CartPricer, to_out
from app.services.settings import SettingsService, public_config

router = APIRouter(tags=["shop"])
Lang = Annotated[str, Query(pattern=LANG_PATTERN)]


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
