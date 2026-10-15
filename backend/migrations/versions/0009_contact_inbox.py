"""Contact inbox: message status, staff notes and replies sent from the admin.

The DDL lives in migrations/sql/0009_contact_inbox.sql (and .down.sql) so it can be read and tried in plain psql.

Revision ID: 0009_contact_inbox
Revises: 0008_analytics
Create Date: 2026-10-15
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0009_contact_inbox"
down_revision = "0008_analytics"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0009_contact_inbox.sql")


def downgrade() -> None:
    _run("0009_contact_inbox.down.sql")
