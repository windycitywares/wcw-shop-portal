"""Audit log entries for the admin."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class AuditOut(ORMModel):
    id: int
    actor_email: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    summary: str | None
    created_at: datetime


class AuditListOut(BaseModel):
    items: list[AuditOut]
    total: int
    page: int
    page_size: int
    actions: list[str]
