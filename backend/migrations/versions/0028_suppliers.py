"""The supplier list (picked on listings, orders and supplier logins).

The DDL lives in migrations/sql/0028_suppliers.sql (and .down.sql).

Revision ID: 0028_suppliers
Revises: 0027_supplier_users
Create Date: 2026-11-17
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0028_suppliers"
down_revision = "0027_supplier_users"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0028_suppliers.sql")


def downgrade() -> None:
    _run("0028_suppliers.down.sql")
