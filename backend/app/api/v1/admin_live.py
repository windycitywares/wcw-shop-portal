"""Live updates for the admin: what happened since the last event the browser saw (toasts, the bell, "updates available").

The storefront's Node server asks this every couple of seconds on behalf of a signed-in staff member and streams the
answer to their browser (frontend/src/app/api/live/route.ts). Each person only gets the kinds their role can act on.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import SessionDep, require
from app.core.permissions import Permission, has_permission
from app.models.user import User
from app.services.live import LiveEventService

router = APIRouter(prefix="/admin/live", tags=["admin: live"])
Staff = Annotated[User, Depends(require(Permission.CATALOG_VIEW_UNPUBLISHED))]  # any staff role


@router.get("/events")
async def live_events(
    response: Response, session: SessionDep, user: Staff,
    after: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    """`after` omitted: just the newest id, to start from ("nothing yet"). Otherwise the events after it, oldest first."""
    response.headers["Cache-Control"] = "no-store"
    allowed = [p.value for p in Permission if has_permission(user.role, p)]
    return await LiveEventService(session).since(after, allowed, limit)
