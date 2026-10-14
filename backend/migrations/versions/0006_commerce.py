"""Checkout, orders, payments, sales, coupons, cart rules, server carts, email outbox, audit log.

The DDL lives in migrations/sql/0006_commerce.sql (and .down.sql) so it can be read and tried in plain psql.

Revision ID: 0006_commerce
Revises: 0005_load_translations
Create Date: 2026-10-14
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0006_commerce"
down_revision = "0005_load_translations"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0006_commerce.sql")


def downgrade() -> None:
    _run("0006_commerce.down.sql")
