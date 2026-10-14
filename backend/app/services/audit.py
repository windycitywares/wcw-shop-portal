"""Audit trail for admin actions. `record` only adds the row, so it commits with the change it describes."""

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commerce import AuditLog
from app.models.user import User
from app.utils.text import escape_like


def record(
    session: AsyncSession,
    actor: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | str | None = None,
    summary: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            summary=(summary or "")[:500] or None,
            data=data or {},
        )
    )


async def search(
    session: AsyncSession, q: str | None, action: str | None, entity_type: str | None, page: int, page_size: int,
) -> tuple[list[AuditLog], int, list[str]]:
    """Newest first. Also returns the kinds of action that exist, for the filter."""
    conds = []
    if q:
        like = f"%{escape_like(q.strip())}%"
        conds.append(or_(AuditLog.summary.ilike(like), AuditLog.actor_email.ilike(like), AuditLog.entity_id.ilike(like)))
    if action:
        conds.append(AuditLog.action.like(f"{escape_like(action)}%"))
    if entity_type:
        conds.append(AuditLog.entity_type == entity_type)
    total = (await session.execute(select(func.count()).select_from(AuditLog).where(*conds))).scalar_one()
    rows = (await session.execute(
        select(AuditLog).where(*conds).order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    kinds = (await session.execute(select(AuditLog.action).group_by(AuditLog.action).order_by(AuditLog.action).limit(100))).scalars().all()
    return list(rows), total, list(kinds)
