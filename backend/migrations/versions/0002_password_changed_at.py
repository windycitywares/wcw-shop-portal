"""Track password changes so older sign-in tokens can be revoked.

Revision ID: 0002_password_changed_at
Revises: 0001_initial
Create Date: 2026-10-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_password_changed_at"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
