"""Supplier logins (role supplier, supplier name, allowed external shops).

The DDL lives in migrations/sql/0027_supplier_users.sql (and .down.sql).

Revision ID: 0027_supplier_users
Revises: 0026_etsy_supplier_payments
Create Date: 2026-11-17
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0027_supplier_users"
down_revision = "0026_etsy_supplier_payments"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0027_supplier_users.sql")


def downgrade() -> None:
    _run("0027_supplier_users.down.sql")
