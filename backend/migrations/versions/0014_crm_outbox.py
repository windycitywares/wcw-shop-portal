"""CRM sync: outbox of changes to send to the CRM.

The DDL lives in migrations/sql/0014_crm_outbox.sql (and .down.sql) so it can be read and tried in plain psql.

Revision ID: 0014_crm_outbox
Revises: 0013_notifications
Create Date: 2026-10-16
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0014_crm_outbox"
down_revision = "0013_notifications"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0014_crm_outbox.sql")


def downgrade() -> None:
    _run("0014_crm_outbox.down.sql")
