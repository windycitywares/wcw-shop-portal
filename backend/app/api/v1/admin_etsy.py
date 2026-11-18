"""Etsy connection: credentials, "Allow access" and disconnect. Orders and listings come in later batches (docs/ETSY.md)."""

from decimal import Decimal
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, require
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.permissions import Permission
from app.models.etsy import EtsyListing
from app.models.user import User
from app.services import audit, etsy_listings
from app.services.etsy_client import EtsyError
from app.services.etsy_connection import EtsyConnectionService

router = APIRouter(prefix="/admin/etsy", tags=["admin: etsy"])
callback_router = APIRouter(prefix="/integrations/etsy", tags=["etsy"])
Team = Annotated[User, Depends(require(Permission.ETSY_MANAGE))]
Admin = Annotated[User, Depends(require(Permission.ETSY_SETTINGS))]


class CredentialsIn(BaseModel):
    client_id: str | None = Field(default=None, max_length=100)
    client_secret: str | None = Field(default=None, max_length=200)


@router.get("/connection")
async def connection(response: Response, session: SessionDep, user: Team) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await EtsyConnectionService(session).status()


@router.put("/credentials")
async def save_credentials(body: CredentialsIn, session: SessionDep, user: Admin) -> dict[str, Any]:
    service = EtsyConnectionService(session)
    await service.save_credentials(user, body.client_id, body.client_secret)
    return await service.status()


@router.post("/connect")
async def connect(session: SessionDep, user: Admin) -> dict[str, str]:
    """The address of Etsy's "Allow access" screen; the browser goes there and Etsy sends it back to the callback."""
    return {"url": await EtsyConnectionService(session).start(user)}


@router.post("/disconnect")
async def disconnect(session: SessionDep, user: Admin) -> dict[str, Any]:
    service = EtsyConnectionService(session)
    await service.disconnect(user)
    return await service.status()


@callback_router.get("/callback", include_in_schema=False)
async def callback(
    session: SessionDep,
    state: Annotated[str | None, Query(max_length=200)] = None,
    code: Annotated[str | None, Query(max_length=2000)] = None,
    error: Annotated[str | None, Query(max_length=200)] = None,
) -> RedirectResponse:
    """Etsy sends the browser here. The one-time `state` we stored when it left is the only check, so nothing else
    is trusted from the request. The person is then sent on to the settings page with the outcome."""
    base = get_settings().site_url.rstrip("/") + "/admin/settings?tab=external_shops&"
    if error or not (state and code):
        return RedirectResponse(f"{base}etsy=failed&reason={quote(error or 'Etsy did not allow access')}")
    try:
        name = await EtsyConnectionService(session).finish(state, code)
    except (EtsyError, ValidationFailedError) as exc:
        return RedirectResponse(f"{base}etsy=failed&reason={quote(str(exc)[:200])}")
    return RedirectResponse(f"{base}etsy=connected&shop={quote(name)}")


# ---- listings (read-only mirror of Etsy; the team edits only the internal_* fields) ----


class ListingInternalIn(BaseModel):
    internal_supplier: str | None = Field(default=None, max_length=200)
    internal_purchase_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    internal_notes: str | None = Field(default=None, max_length=5000)


def _listing(r: EtsyListing) -> dict[str, Any]:
    return {
        "id": r.id, "etsy_listing_id": r.etsy_listing_id, "title": r.title, "state": r.state, "price": r.price,
        "currency": r.currency, "quantity": r.quantity, "skus": r.skus, "url": r.url, "image": (r.images or [None])[0],
        "variations": r.variations, "tags": r.tags, "description": r.description, "synced_at": r.synced_at,
        "internal_supplier": r.internal_supplier, "internal_purchase_cost": r.internal_purchase_cost,
        "internal_notes": r.internal_notes,
    }


@router.get("/listings")
async def listings(
    response: Response, session: SessionDep, user: Team,
    q: Annotated[str | None, Query(max_length=100)] = None,
    state: Annotated[str | None, Query(max_length=20)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    rows, total = await etsy_listings.search(session, q, state, page, page_size)
    return {"items": [_listing(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.patch("/listings/{listing_id}")
async def update_listing(listing_id: int, body: ListingInternalIn, session: SessionDep, user: Team) -> dict[str, Any]:
    """Only the team's own fields. Anything from Etsy is read-only and is ignored here by design."""
    row = await session.get(EtsyListing, listing_id)
    if row is None:
        raise NotFoundError("Listing not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    audit.record(session, user, "etsy.listing.internal", "etsy_listing", row.id, f"Internal info for {row.title[:80]}")
    await session.commit()
    await session.refresh(row)
    return _listing(row)


@router.post("/sync")
async def sync_now(session: SessionDep, user: Team) -> dict[str, Any]:
    return await etsy_listings.EtsyListingSync(session).run(force=True)
