"""Deploy control (Admin → Deployments): automatic / scheduled / paused updates and "Deploy now".

The DDL lives in migrations/sql/0015_deploy_control.sql (and .down.sql) so it can be read and tried in plain psql.

Revision ID: 0015_deploy_control
Revises: 0014_crm_outbox
Create Date: 2026-10-17
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0015_deploy_control"
down_revision = "0014_crm_outbox"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0015_deploy_control.sql")


def downgrade() -> None:
    _run("0015_deploy_control.down.sql")
