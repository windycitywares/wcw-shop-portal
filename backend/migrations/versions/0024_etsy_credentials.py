"""Etsy app credentials on the connection row.

The DDL lives in migrations/sql/0024_etsy_credentials.sql (and .down.sql).

Revision ID: 0024_etsy_credentials
Revises: 0023_etsy
Create Date: 2026-11-17
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0024_etsy_credentials"
down_revision = "0023_etsy"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0024_etsy_credentials.sql")


def downgrade() -> None:
    _run("0024_etsy_credentials.down.sql")
