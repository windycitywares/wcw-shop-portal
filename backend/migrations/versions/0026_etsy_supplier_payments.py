"""Supplier payments on Etsy orders (pending / settled).

The DDL lives in migrations/sql/0026_etsy_supplier_payments.sql (and .down.sql).

Revision ID: 0026_etsy_supplier_payments
Revises: 0025_etsy_past_orders
Create Date: 2026-11-17
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0026_etsy_supplier_payments"
down_revision = "0025_etsy_past_orders"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0026_etsy_supplier_payments.sql")


def downgrade() -> None:
    _run("0026_etsy_supplier_payments.down.sql")
