"""The admin bell: recent activity the signed-in staff member can act on, and marking it as read."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
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
    """Unread count + newest activity time. Cheap: the storefront's live stream (/api/admin-live) and the bell's fallback both ask it every few seconds."""
    response.headers["Cache-Control"] = "no-store"
    return await NotificationService(session).pulse(user)
