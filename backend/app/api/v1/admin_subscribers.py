"""Newsletter subscribers: see who joined, add, pause, take off the list, export."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.subscribers import SubscriberAdd, SubscriberList, SubscriberOut
from app.services.subscribers import STATUSES, SubscriberService

router = APIRouter(prefix="/admin/subscribers", tags=["admin: subscribers"])
Viewer = Annotated[User, Depends(require(Permission.CUSTOMERS_VIEW))]
Manager = Annotated[User, Depends(require(Permission.PROMOTIONS_MANAGE))]
STATUS_PATTERN = "^(" + "|".join(STATUSES) + ")$"


@router.get("", response_model=SubscriberList)
async def list_subscribers(
    response: Response, session: SessionDep, _: Viewer,
    q: str | None = Query(None, max_length=100), status_: str = Query("all", alias="status", pattern=STATUS_PATTERN),
    page: int = Query(1, ge=1, le=10_000), page_size: int = Query(25, ge=1, le=100),
):
    response.headers["Cache-Control"] = "no-store"
    return await SubscriberService(session).list(q, status_, page, page_size)


@router.get("/export.csv")
async def export_subscribers(
    session: SessionDep, _: Viewer, q: str | None = Query(None, max_length=100),
    status_: str = Query("subscribed", alias="status", pattern=STATUS_PATTERN),
):
    data = await SubscriberService(session).export_csv(q, status_)
    return Response(
        data, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="wcw-subscribers.csv"', "Cache-Control": "no-store"},
    )


@router.post("", response_model=SubscriberOut, status_code=status.HTTP_201_CREATED)
async def add_subscriber(session: SessionDep, user: Manager, data: SubscriberAdd):
    return await SubscriberService(session).add(str(data.email), data.locale, user)


@router.post("/{subscriber_id}/unsubscribe", response_model=SubscriberOut)
async def unsubscribe_subscriber(subscriber_id: int, session: SessionDep, user: Manager):
    return await SubscriberService(session).unsubscribe(subscriber_id, user)


@router.post("/{subscriber_id}/pause", response_model=SubscriberOut)
async def pause_subscriber(subscriber_id: int, session: SessionDep, user: Manager):
    return await SubscriberService(session).pause(subscriber_id, user)


@router.post("/{subscriber_id}/resume", response_model=SubscriberOut)
async def resume_subscriber(subscriber_id: int, session: SessionDep, user: Manager):
    return await SubscriberService(session).resume(subscriber_id, user)


@router.delete("/{subscriber_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscriber(subscriber_id: int, session: SessionDep, user: Manager):
    await SubscriberService(session).delete(subscriber_id, user)
