"""Etsy → shop: connection, listings, orders, items and order history.

The DDL lives in migrations/sql/0023_etsy.sql (and .down.sql).

Revision ID: 0023_etsy
Revises: 0022_notification_prefs
Create Date: 2026-11-17
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0023_etsy"
down_revision = "0022_notification_prefs"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0023_etsy.sql")


def downgrade() -> None:
    _run("0023_etsy.down.sql")
