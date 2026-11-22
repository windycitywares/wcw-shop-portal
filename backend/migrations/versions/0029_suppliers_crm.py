"""Suppliers mirror the CRM (crm_id, crm_synced_at).

The DDL lives in migrations/sql/0029_suppliers_crm.sql (and .down.sql).

Revision ID: 0029_suppliers_crm
Revises: 0028_suppliers
Create Date: 2026-11-17
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0029_suppliers_crm"
down_revision = "0028_suppliers"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0029_suppliers_crm.sql")


def downgrade() -> None:
    _run("0029_suppliers_crm.down.sql")
