"""Per-language overrides for products and categories (Spanish, Dutch, ...).

Revision ID: 0003_translations
Revises: 0002_password_changed_at
Create Date: 2026-10-11
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_translations"
down_revision = "0002_password_changed_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("products", "categories"):
        op.add_column(
            table,
            sa.Column("translations", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        )


def downgrade() -> None:
    for table in ("products", "categories"):
        op.drop_column(table, "translations")
