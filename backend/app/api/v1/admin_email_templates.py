"""Edit the wording of the customer emails (subscribe, welcome, password reset, order emails)."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.common import Message
from app.services.email_templates import PARTS, EmailTemplateService

router = APIRouter(prefix="/admin/email-templates", tags=["admin: email templates"])
Staff = Annotated[User, Depends(require(Permission.SETTINGS_MANAGE))]
Fields = Annotated[dict[str, Any], Body()]


@router.get("")
async def list_templates(session: SessionDep, _: Staff):
    return {"parts": [{"key": k, "label": v} for k, v in PARTS], "emails": await EmailTemplateService(session).catalog()}


@router.put("/{kind}/{language}")
async def save_template(kind: str, language: str, fields: Fields, session: SessionDep, user: Staff):
    """Save the wording for one email in one language. Empty parts go back to the built-in wording."""
    return {"emails": await EmailTemplateService(session).save(kind, language, fields, user)}


@router.post("/{kind}/{language}/preview")
async def preview_template(kind: str, language: str, fields: Fields, session: SessionDep, _: Staff):
    return EmailTemplateService(session).preview(kind, language, fields)


@router.post("/{kind}/{language}/test", response_model=Message)
async def test_template(kind: str, language: str, fields: Fields, session: SessionDep, user: Staff):
    to = await EmailTemplateService(session).send_test(kind, language, fields, user)
    return Message(detail=f"Test email sent to {to}")
