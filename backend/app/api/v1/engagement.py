"""Reviews, wishlist and back-in-stock requests (shopper side)."""

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status

from app.api.deps import CurrentUser, OptionalUser, SessionDep
from app.api.v1.auth import client_ip, no_store
from app.core.exceptions import TooManyRequestsError
from app.core.i18n import LANG_PATTERN
from app.core.rate_limit import reviews_by_user, stock_alerts_by_ip
from app.schemas.common import Message
from app.schemas.engagement import (
    MyStockRequest, ReviewIn, ReviewOut, ReviewsOut, ReviewSubmittedOut, StockAlertIn, StockRequestCreated, StockRequestIn,
)
from app.schemas.product import ProductCard
from app.services.engagement import ReviewService, StockAlertService, WishlistService

router = APIRouter(tags=["engagement"])
Lang = Annotated[str, Query(pattern=LANG_PATTERN)]


@router.get("/products/{slug}/reviews", response_model=ReviewsOut)
async def product_reviews(
    slug: str, response: Response, session: SessionDep, user: OptionalUser,
    sort: str = Query("helpful", pattern="^(helpful|newest|highest|lowest)$"), page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50),
):
    no_store(response)
    return await ReviewService(session).list(slug, user, sort, page, page_size)


@router.post("/products/{slug}/reviews", response_model=ReviewSubmittedOut, status_code=status.HTTP_201_CREATED)
async def write_review(slug: str, session: SessionDep, user: CurrentUser, data: ReviewIn):
    """Signed-in shoppers can review a product once. Reviews from verified buyers are marked as such."""
    if reviews_by_user.is_blocked(str(user.id)):
        raise TooManyRequestsError("You've submitted several reviews today. Please try again tomorrow.")
    result = await ReviewService(session).submit(slug, user, data)
    reviews_by_user.hit(str(user.id))
    return result


@router.post("/reviews/{review_id}/helpful", response_model=ReviewOut)
async def mark_helpful(review_id: int, session: SessionDep, user: CurrentUser):
    """Toggle "this review was helpful"."""
    return await ReviewService(session).vote(review_id, user)


@router.get("/account/wishlist", response_model=list[ProductCard])
async def wishlist(response: Response, session: SessionDep, user: CurrentUser, lang: Lang = "en"):
    no_store(response)
    return await WishlistService(session).cards(user, lang)


@router.get("/account/wishlist/ids", response_model=list[int])
async def wishlist_ids(response: Response, session: SessionDep, user: CurrentUser):
    """Just the product ids, for filling the hearts on product cards."""
    no_store(response)
    return await WishlistService(session).ids(user)


@router.put("/account/wishlist/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_to_wishlist(product_id: int, session: SessionDep, user: CurrentUser):
    await WishlistService(session).add(user, product_id)


@router.delete("/account/wishlist/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_wishlist(product_id: int, session: SessionDep, user: CurrentUser):
    await WishlistService(session).remove(user, product_id)


@router.post("/products/{product_id}/stock-requests", response_model=StockRequestCreated, status_code=status.HTTP_201_CREATED)
async def request_stock(product_id: int, request: Request, session: SessionDep, user: CurrentUser, data: StockRequestIn):
    """Signed-in customers only. Ask for a combination: "email me when it's back" when the shop sells it (sent
    automatically), or a special request for one it doesn't make yet (the shop answers). 409 when it can be bought now."""
    ip = client_ip(request)
    if stock_alerts_by_ip.is_blocked(ip):
        raise TooManyRequestsError("Too many requests. Please try again later.")
    stock_alerts_by_ip.hit(ip)
    return await StockAlertService(session).create(product_id, data.options, data.note, data.locale, user)


@router.post("/products/{product_id}/notify-me", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
async def notify_me(product_id: int, request: Request, session: SessionDep, user: CurrentUser, data: StockAlertIn):
    """Older form of the above for a product without options (sign-in required)."""
    ip = client_ip(request)
    if stock_alerts_by_ip.is_blocked(ip):
        raise TooManyRequestsError("Too many requests. Please try again later.")
    stock_alerts_by_ip.hit(ip)
    await StockAlertService(session).create(product_id, {}, None, data.locale, user)
    return Message(detail="Thanks. We'll email you once, when it's available again.")


@router.get("/account/stock-requests", response_model=list[MyStockRequest])
async def my_stock_requests(response: Response, session: SessionDep, user: CurrentUser):
    response.headers["Cache-Control"] = "no-store"
    return await StockAlertService(session).mine(user)


@router.delete("/account/stock-requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_stock_request(request_id: int, session: SessionDep, user: CurrentUser):
    await StockAlertService(session).cancel(user, request_id)
