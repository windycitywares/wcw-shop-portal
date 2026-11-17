"""Etsy connection: credentials, "Allow access" and disconnect. Orders and listings come in later batches (docs/ETSY.md)."""

from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, require
from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError
from app.core.permissions import Permission
from app.models.user import User
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
    base = get_settings().site_url.rstrip("/") + "/admin/settings?tab=etsy"
    if error or not (state and code):
        return RedirectResponse(f"{base}&etsy=failed&reason={quote(error or 'Etsy did not allow access')}")
    try:
        name = await EtsyConnectionService(session).finish(state, code)
    except (EtsyError, ValidationFailedError) as exc:
        return RedirectResponse(f"{base}&etsy=failed&reason={quote(str(exc)[:200])}")
    return RedirectResponse(f"{base}&etsy=connected&shop={quote(name)}")
