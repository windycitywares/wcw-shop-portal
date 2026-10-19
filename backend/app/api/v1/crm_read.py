"""Read-only API for the CRM (docs/CRM_SYNC.md): customers, orders, newsletter consent and the catalog,
paged by id.

Authenticated with `Authorization: Bearer <CRM_API_TOKEN>` (server setting), not a staff login. Answers 404 while
the token isn't configured, so the endpoints don't exist as far as anyone else can tell. Always live data.
"""

from __future__ import annotations

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import or_, select

from app.api.deps import SessionDep
from app.core import appmode
from app.core.config import get_settings
from app.core.enums import ContentStatus, UserRole
from app.core.rate_limit import RateLimiter
from app.models.order import Order
from app.models.product import Product
from app.models.user import NewsletterSubscriber, User
from app.services.crm_sync import customer_payload, newsletter_event, order_payload

router = APIRouter(prefix="/integrations/crm", tags=["integrations"], include_in_schema=False)
_bad_tokens = RateLimiter(max_hits=20, window_seconds=600)
MAX_LIMIT = 500


def _client(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return (forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else ""))[:64]


async def crm_token(request: Request, authorization: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().crm_api_token
    if not expected:
        raise HTTPException(status_code=404, detail="Not Found")
    ip = _client(request)
    if _bad_tokens.is_blocked(ip):
        raise HTTPException(status_code=429, detail="Too many attempts")
    given = (authorization or "").removeprefix("Bearer ").strip()
    if not given or not hmac.compare_digest(given.encode(), expected.encode()):
        _bad_tokens.hit(ip)
        raise HTTPException(status_code=401, detail="Invalid token")


Token = Depends(crm_token)
AfterId = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT)]


def _page(items: list[dict[str, Any]], ids: list[int], limit: int) -> dict[str, Any]:
    return {"items": items, "next_after_id": ids[-1] if len(ids) == limit else None}


def _image(p: Product) -> str | None:
    first = (p.images or [None])[0]
    return first.get("url") if isinstance(first, dict) else None


def product_payload(p: Product) -> dict[str, Any]:
    """A catalog row as the CRM's deal picker reads it: its own `id` becomes the line's `shop_product_id`,
    `title` is the line's `name`, and `price` (the base price) is a starting unit price staff can adjust."""
    return {
        "id": p.id, "parent_id": p.parent_id, "sku": p.sku, "name": p.title, "slug": p.slug,
        "price": f"{p.base_price:.2f}",
        "compare_at_price": f"{p.compare_at_price:.2f}" if p.compare_at_price else None,
        "currency": p.currency, "status": str(p.status), "stock_status": str(p.stock_status),
        "image": _image(p),
    }


@router.get("/customers", dependencies=[Token])
async def customers(session: SessionDep, after_id: AfterId = 0, limit: Limit = 200) -> dict[str, Any]:
    with appmode.use(appmode.LIVE):
        rows = list((await session.execute(
            select(User).where(User.role == UserRole.CUSTOMER, User.id > after_id).order_by(User.id).limit(limit)
        )).scalars())
    return _page([customer_payload(u) for u in rows], [u.id for u in rows], limit)


@router.get("/orders", dependencies=[Token])
async def orders(session: SessionDep, after_id: AfterId = 0, limit: Limit = 200,
                 email: Annotated[str | None, Query(max_length=320)] = None) -> dict[str, Any]:
    stmt = select(Order).where(Order.id > after_id)
    if email:
        stmt = stmt.where(Order.email == email.strip().lower())
    with appmode.use(appmode.LIVE):
        rows = list((await session.execute(stmt.order_by(Order.id).limit(limit))).scalars())
    return _page([order_payload(o) for o in rows], [o.id for o in rows], limit)


@router.get("/newsletter", dependencies=[Token])
async def newsletter(session: SessionDep, after_id: AfterId = 0, limit: Limit = 200) -> dict[str, Any]:
    with appmode.use(appmode.LIVE):
        rows = list((await session.execute(
            select(NewsletterSubscriber).where(NewsletterSubscriber.id > after_id).order_by(NewsletterSubscriber.id).limit(limit)
        )).scalars())
    items = []
    for s in rows:
        found = newsletter_event(s)
        if found:
            items.append({"type": found[0], **found[1]})
    return _page(items, [s.id for s in rows], limit)


@router.get("/products", dependencies=[Token])
async def products(session: SessionDep, after_id: AfterId = 0, limit: Limit = 200,
                   q: Annotated[str | None, Query(max_length=120)] = None) -> dict[str, Any]:
    """The published catalog: what a deal line may name (the CRM's picker searches it with `q`)."""
    stmt = select(Product).where(Product.status == ContentStatus.PUBLISHED, Product.id > after_id)
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(or_(Product.title.ilike(term), Product.sku.ilike(term), Product.slug.ilike(term)))
    with appmode.use(appmode.LIVE):
        rows = list((await session.execute(stmt.order_by(Product.id).limit(limit))).scalars())
    return _page([product_payload(p) for p in rows], [p.id for p in rows], limit)
