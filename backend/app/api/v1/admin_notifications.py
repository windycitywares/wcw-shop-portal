"""The admin bell: recent activity the signed-in staff member can act on, and marking it as read."""

import asyncio
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, WebSocket, WebSocketDisconnect, status

from app.api.deps import SessionDep, get_optional_user, require
from app.core.config import get_settings
from app.core.database import SessionFactory
from app.core.exceptions import DomainError
from app.core.permissions import Permission, has_permission
from app.models.user import User
from app.services.notifications import SOURCES, NotificationService

router = APIRouter(prefix="/admin/notifications", tags=["admin: notifications"])
Staff = Annotated[User, Depends(require(Permission.CATALOG_VIEW_UNPUBLISHED))]  # any staff role


@router.get("")
async def notifications(
    response: Response, session: SessionDep, user: Staff,
    limit: int = Query(20, ge=1, le=100),
    kind: Annotated[list[str] | None, Query(max_length=10)] = None,
    before: datetime | None = None,
) -> dict[str, Any]:
    """Newest first. `kind` filters (order, refund, message, stock_request, review, signup, backup_failed); `before` pages."""
    response.headers["Cache-Control"] = "no-store"
    kinds = [k for k in (kind or []) if k in SOURCES] or None
    return await NotificationService(session).feed(user, limit, kinds, before)


@router.post("/seen", status_code=status.HTTP_204_NO_CONTENT)
async def mark_seen(session: SessionDep, user: Staff):
    """Everything up to now counts as read (called when the bell is opened)."""
    await NotificationService(session).mark_seen(user)


@router.get("/pulse")
async def pulse(response: Response, session: SessionDep, user: Staff) -> dict[str, Any]:
    """Unread count + newest activity time. Cheap; the bell asks every few seconds when it has no WebSocket."""
    response.headers["Cache-Control"] = "no-store"
    return await NotificationService(session).pulse(user)


LIVE_TICK_SECONDS = 2
LIVE_AUTH_SECONDS = 8


@router.websocket("/live")
async def live(ws: WebSocket) -> None:
    """Instant updates for the bell, where the server can hold a WebSocket open (the shared-hosting WSGI adapter cannot:
    the bell then falls back to /pulse). The first message must be {"token": "<JWT>"}; after that the server sends
    {"type": "pulse", unread, latest} whenever either changes, and the client may send any text as a heartbeat."""
    origin = ws.headers.get("origin")
    if origin and origin not in get_settings().cors_origins:
        await ws.close(code=4403)
        return
    await ws.accept()
    try:
        first = await asyncio.wait_for(ws.receive_json(), LIVE_AUTH_SECONDS)
        async with SessionFactory() as session:
            user = await get_optional_user(session, first.get("token") if isinstance(first, dict) else None)
        if user is None or not has_permission(user.role, Permission.CATALOG_VIEW_UNPUBLISHED):
            await ws.close(code=4401)
            return
    except (asyncio.TimeoutError, ValueError, DomainError, WebSocketDisconnect, RuntimeError):
        try:
            await ws.close(code=4401)
        except RuntimeError:
            pass
        return

    await ws.send_json({"type": "hello"})
    last: dict[str, Any] | None = None
    try:
        while True:
            async with SessionFactory() as session:
                fresh = await session.get(type(user), user.id)  # picks up a "seen" made in another tab
                if fresh is None or not fresh.is_active:
                    await ws.close(code=4401)
                    return
                now = await NotificationService(session).pulse(fresh)
            if now != last:
                last = now
                await ws.send_json({"type": "pulse", **now})
            try:  # waits for the next tick; anything the client sends is just a heartbeat
                await asyncio.wait_for(ws.receive_text(), LIVE_TICK_SECONDS)
            except asyncio.TimeoutError:
                pass
    except (WebSocketDisconnect, RuntimeError):
        return
