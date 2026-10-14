"""Reviews, wishlists, stock alerts, newsletter consent registry and email campaigns.

The DDL lives in migrations/sql/0007_engagement.sql (and .down.sql) so it can be read and tried in plain psql.

Revision ID: 0007_engagement
Revises: 0006_commerce
Create Date: 2026-10-14
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0007_engagement"
down_revision = "0006_commerce"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0007_engagement.sql")


def downgrade() -> None:
    _run("0007_engagement.down.sql")
