"""Stock requests: option combinations, notes and special requests.

The DDL lives in migrations/sql/0012_stock_requests.sql (and .down.sql) so it can be read and tried in plain psql.

Revision ID: 0012_stock_requests
Revises: 0011_backups
Create Date: 2026-10-15
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0012_stock_requests"
down_revision = "0011_backups"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0012_stock_requests.sql")


def downgrade() -> None:
    _run("0012_stock_requests.down.sql")
