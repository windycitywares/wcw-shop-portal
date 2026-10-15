"""Contact inbox: messages from the Contact page, with status, notes and email replies."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.inbox import InboxListOut, InboxMessageOut, InboxReplyIn, InboxReplyOut, InboxUpdateIn
from app.services.inbox import InboxService

router = APIRouter(prefix="/admin/messages", tags=["admin: inbox"])
Staff = Annotated[User, Depends(require(Permission.MESSAGES_MANAGE))]


@router.get("", response_model=InboxListOut)
async def list_messages(
    response: Response, session: SessionDep, _: Staff,
    status_: str | None = Query(None, alias="status", pattern="^(active|all|new|open|replied|closed|spam)$"),
    q: str | None = Query(None, max_length=100), page: int = Query(1, ge=1, le=10_000), page_size: int = Query(25, ge=1, le=100),
):
    """Default view: messages that still need a person (new and open), new ones first."""
    response.headers["Cache-Control"] = "no-store"
    return await InboxService(session).list(status_, q, page, page_size)


@router.get("/{message_id}", response_model=InboxMessageOut)
async def get_message(message_id: int, response: Response, session: SessionDep, _: Staff):
    """Opening a new message marks it as open (read)."""
    response.headers["Cache-Control"] = "no-store"
    return await InboxService(session).detail(message_id)


@router.patch("/{message_id}", response_model=InboxMessageOut)
async def update_message(message_id: int, session: SessionDep, user: Staff, data: InboxUpdateIn):
    """Change the status (open, closed, spam…) or the private staff note."""
    return await InboxService(session).update(message_id, data, user)


@router.post("/{message_id}/reply", response_model=InboxReplyOut)
async def reply_to_message(message_id: int, session: SessionDep, user: Staff, data: InboxReplyIn):
    """Email a reply to the sender (their message is quoted underneath) and mark the message replied or closed."""
    return await InboxService(session).reply(message_id, data, user)


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(message_id: int, session: SessionDep, user: Staff):
    await InboxService(session).delete(message_id, user)
