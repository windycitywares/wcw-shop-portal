"""Automatic database backups: settings and run history.

The DDL lives in migrations/sql/0011_backups.sql (and .down.sql) so it can be read and tried in plain psql.

Revision ID: 0011_backups
Revises: 0010_app_mode
Create Date: 2026-10-15
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0011_backups"
down_revision = "0010_app_mode"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0011_backups.sql")


def downgrade() -> None:
    _run("0011_backups.down.sql")
