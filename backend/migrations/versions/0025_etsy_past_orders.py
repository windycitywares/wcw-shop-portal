"""Etsy orders already shipped when Etsy was connected: kept, not flagged.

The DDL lives in migrations/sql/0025_etsy_past_orders.sql (and .down.sql).

Revision ID: 0025_etsy_past_orders
Revises: 0024_etsy_credentials
Create Date: 2026-11-17
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0025_etsy_past_orders"
down_revision = "0024_etsy_credentials"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0025_etsy_past_orders.sql")


def downgrade() -> None:
    _run("0025_etsy_past_orders.down.sql")
