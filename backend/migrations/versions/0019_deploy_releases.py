"""Deploy releases: the versions the server has run, for Admin → Deployments.

The DDL lives in migrations/sql/0019_deploy_releases.sql (and .down.sql).

Revision ID: 0019_deploy_releases
Revises: 0018_subscriber_pause
Create Date: 2026-10-24
"""
from pathlib import Path

from alembic import op

from app.utils.sqlfile import statements

revision = "0019_deploy_releases"
down_revision = "0018_subscriber_pause"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    for statement in statements((SQL / name).read_text(encoding="utf-8")):
        op.execute(statement)


def upgrade() -> None:
    _run("0019_deploy_releases.sql")


def downgrade() -> None:
    _run("0019_deploy_releases.down.sql")
