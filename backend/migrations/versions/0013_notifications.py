"""Admin notifications: when each staff member last opened the activity list.

The DDL lives in migrations/sql/0013_notifications.sql (and .down.sql) so it can be read and tried in plain psql.

Revision ID: 0013_notifications
Revises: 0012_stock_requests
Create Date: 2026-10-15
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0013_notifications"
down_revision = "0012_stock_requests"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0013_notifications.sql")


def downgrade() -> None:
    _run("0013_notifications.down.sql")
