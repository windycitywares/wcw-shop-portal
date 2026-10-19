"""Contacts: a superset of customers and users, importable into the CRM.

The DDL lives in migrations/sql/0017_contacts.sql (and .down.sql).

Revision ID: 0017_contacts
Revises: 0016_test_logins
Create Date: 2026-10-19
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0017_contacts"
down_revision = "0016_test_logins"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0017_contacts.sql")


def downgrade() -> None:
    _run("0017_contacts.down.sql")
