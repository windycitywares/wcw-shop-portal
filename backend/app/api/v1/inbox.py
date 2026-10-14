"""The contact-form inbox (staff)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.account import MessageOut, MessageUpdate
from app.schemas.common import Page
from app.services.inbox import InboxService

router = APIRouter(prefix="/messages", tags=["messages"])
Staff = Annotated[User, Depends(require(Permission.ORDERS_MANAGE))]


@router.get("", response_model=Page[MessageOut])
async def list_messages(
    session: SessionDep, _: Staff,
    status: str | None = Query(default=None, pattern=r"^(new|answered|archived)$"),
    q: str | None = Query(default=None, max_length=100),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    return await InboxService(session).search(status=status, q=q, page=page, page_size=page_size)


@router.get("/counts")
async def message_counts(session: SessionDep, _: Staff):
    return {"counts": await InboxService(session).counts()}


@router.patch("/{message_id}", response_model=MessageOut)
async def update_message(message_id: int, session: SessionDep, user: Staff, data: MessageUpdate):
    return await InboxService(session).update(message_id, data, user)
