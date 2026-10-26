"""Notification preferences: how each member of staff hears about live updates.

The DDL lives in migrations/sql/0022_notification_prefs.sql (and .down.sql).

Revision ID: 0022_notification_prefs
Revises: 0021_live_events
Create Date: 2026-10-26
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0022_notification_prefs"
down_revision = "0021_live_events"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0022_notification_prefs.sql")


def downgrade() -> None:
    _run("0022_notification_prefs.down.sql")
