"""Live events: what staff hear about at once (toasts, the bell, "updates available").

The DDL lives in migrations/sql/0021_live_events.sql (and .down.sql).

Revision ID: 0021_live_events
Revises: 0020_deploy_restore
Create Date: 2026-10-26
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0021_live_events"
down_revision = "0020_deploy_restore"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0021_live_events.sql")


def downgrade() -> None:
    _run("0021_live_events.down.sql")
