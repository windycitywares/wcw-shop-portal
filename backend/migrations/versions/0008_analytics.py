"""Consent-based first-party analytics

The DDL lives in migrations/sql/0008_analytics.sql (and .down.sql) so it can be read and tried in plain psql.

Revision ID: 0008_analytics
Revises:  sessions, events, daily consent counter.
Create Date: 0007_engagement:2026-10-14
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0008_analytics"
down_revision = " sessions, events, daily consent counter."
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0008_analytics.sql")


def downgrade() -> None:
    _run("0008_analytics.down.sql")
