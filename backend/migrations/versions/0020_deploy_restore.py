"""Deploy restore: pin an earlier version, for Admin → Deployments.

The DDL lives in migrations/sql/0020_deploy_restore.sql (and .down.sql).

Revision ID: 0020_deploy_restore
Revises: 0019_deploy_releases
Create Date: 2026-10-24
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0020_deploy_restore"
down_revision = "0019_deploy_releases"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0020_deploy_restore.sql")


def downgrade() -> None:
    _run("0020_deploy_restore.down.sql")
