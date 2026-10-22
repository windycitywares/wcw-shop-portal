"""Subscriber pause: staff can hold campaign email for a subscriber without unsubscribing them.

The DDL lives in migrations/sql/0018_subscriber_pause.sql (and .down.sql).

Revision ID: 0018_subscriber_pause
Revises: 0017_contacts
Create Date: 2026-10-22
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0018_subscriber_pause"
down_revision = "0017_contacts"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0018_subscriber_pause.sql")


def downgrade() -> None:
    _run("0018_subscriber_pause.down.sql")
