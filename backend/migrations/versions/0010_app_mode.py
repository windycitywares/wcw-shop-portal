"""Live / Test switch: the app_mode row.

The DDL lives in migrations/sql/0010_app_mode.sql (and .down.sql) so it can be read and tried in plain psql.

Revision ID: 0010_app_mode
Revises: 0009_contact_inbox
Create Date: 2026-10-15
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0010_app_mode"
down_revision = "0009_contact_inbox"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0010_app_mode.sql")


def downgrade() -> None:
    _run("0010_app_mode.down.sql")
