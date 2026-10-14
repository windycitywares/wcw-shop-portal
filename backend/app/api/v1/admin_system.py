"""Store settings and the audit log (the review queue follows with reviews)."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query, Response

from app.api.deps import SessionDep, require
from app.core import mailer
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.audit import AuditListOut, AuditOut
from app.schemas.common import Message
from app.schemas.settings import AdminSettingsOut
from app.services import audit
from app.services.settings import SettingsService

router = APIRouter(prefix="/admin", tags=["admin: system"])
SettingsStaff = Annotated[User, Depends(require(Permission.SETTINGS_MANAGE))]
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
async def send_test_email(session: SessionDep, user: SettingsStaff):
    """Send a short message to your own address to check that outgoing email works."""
    await mailer.send(mailer.Mail(
        to=user.email, subject="Test email from WindyCityWares",
        text="If you can read this, outgoing email from the shop works.\n\nYou can delete this message.",
    ))
    return Message(detail=f"Test email sent to {user.email}")


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
