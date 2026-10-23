"""Store settings, the review queue and the audit log."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query, Response, status

from app.api.deps import SessionDep, require
from app.core import mailer
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.audit import AuditListOut, AuditOut
from app.schemas.common import Message
from app.schemas.engagement import ReviewAdminListOut, ReviewAdminOut, ReviewModerateIn
from app.core.exceptions import ValidationFailedError
from app.schemas.settings import _ADDRESS, AdminSettingsOut
from app.services import audit
from app.services.engagement import ReviewService
from app.services.settings import SettingsService

router = APIRouter(prefix="/admin", tags=["admin: system"])
SettingsStaff = Annotated[User, Depends(require(Permission.SETTINGS_MANAGE))]
ReviewStaff = Annotated[User, Depends(require(Permission.REVIEWS_MODERATE))]
AuditStaff = Annotated[User, Depends(require(Permission.AUDIT_VIEW))]


# ---- settings ---------------------------------------------------------------------------------


@router.get("/settings", response_model=AdminSettingsOut)
async def get_settings_(response: Response, session: SessionDep, _: SettingsStaff):
    response.headers["Cache-Control"] = "no-store"
    return await SettingsService(session).admin_view()


@router.put("/settings/{group}", response_model=AdminSettingsOut)
async def update_settings(group: str, session: SessionDep, user: SettingsStaff, patch: Annotated[dict[str, Any], Body()]):
    """Change some fields of one settings group (general, shipping, tax, payments, welcome, ...)."""
    return await SettingsService(session).update(group, patch, user)


@router.post("/settings/test-email", response_model=Message)
async def send_test_email(session: SessionDep, user: SettingsStaff, body: Annotated[dict[str, Any] | None, Body()] = None):
    """Send a short message (to you, or to the `to` address given) to check that outgoing email works, saying what went wrong if it doesn't."""
    to = (body or {}).get("to") or user.email
    if not isinstance(to, str) or not _ADDRESS.match(to.strip()) or len(to) > 320:
        raise ValidationFailedError("to: enter an email address like name@example.com")
    to = to.strip()
    sender = await mailer.effective_settings()
    via = f"{sender.smtp_host}:{sender.smtp_port}" if sender.smtp_host else "no mail server set"
    try:
        await mailer.send(mailer.Mail(
            to=to, subject="Test email from WindyCityWares",
            text="If you can read this, outgoing email from the shop works.\n\nYou can delete this message.",
        ))
    except mailer.MailError as exc:
        raise mailer.MailError(f"Couldn't send through {via}: {exc.reason or exc.message}") from exc
    if not sender.smtp_host:
        return Message(detail="No mail server is set up, so nothing was sent (the message was only logged).")
    return Message(detail=f"Test email sent to {to} through {via}, from {sender.mail_from}")


# ---- reviews ----------------------------------------------------------------------------------


@router.get("/reviews", response_model=ReviewAdminListOut)
async def list_reviews(
    response: Response, session: SessionDep, _: ReviewStaff,
    status_: str | None = Query(None, alias="status", pattern="^(pending|approved|rejected)$"),
    q: str | None = Query(None, max_length=100), page: int = Query(1, ge=1, le=10_000), page_size: int = Query(25, ge=1, le=100),
):
    response.headers["Cache-Control"] = "no-store"
    return await ReviewService(session).admin_list(status_, q, page, page_size)


@router.put("/reviews/{review_id}", response_model=ReviewAdminOut)
async def moderate_review(review_id: int, session: SessionDep, user: ReviewStaff, data: ReviewModerateIn):
    """Approve, reject or move a review back to pending, and optionally answer it publicly."""
    return await ReviewService(session).moderate(review_id, data, user)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(review_id: int, session: SessionDep, user: ReviewStaff):
    await ReviewService(session).delete(review_id, user)


# ---- audit log --------------------------------------------------------------------------------


@router.get("/audit", response_model=AuditListOut)
async def list_audit(
    response: Response, session: SessionDep, _: AuditStaff,
    q: str | None = Query(None, max_length=100), action: str | None = Query(None, max_length=60),
    entity_type: str | None = Query(None, max_length=30), page: int = Query(1, ge=1, le=10_000), page_size: int = Query(50, ge=1, le=100),
):
    response.headers["Cache-Control"] = "no-store"
    rows, total, actions = await audit.search(session, q, action, entity_type, page, page_size)
    return AuditListOut(items=[AuditOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size, actions=actions)
