"""Password-reset tokens, saved shipping addresses and contact-form messages.

Revision ID: 0004_accounts
Revises: 0003_translations
Create Date: 2026-10-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_accounts"
down_revision = "0003_translations"
branch_labels = None
depends_on = None

NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])

    op.create_table(
        "addresses",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(50)),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("company", sa.String(200)),
        sa.Column("line1", sa.String(200), nullable=False),
        sa.Column("line2", sa.String(200)),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("region", sa.String(100)),
        sa.Column("postal_code", sa.String(20), nullable=False),
        sa.Column("country", sa.String(2), server_default="US", nullable=False),
        sa.Column("phone", sa.String(40)),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    )
    op.create_index("ix_addresses_user_id", "addresses", ["user_id"])
    # At most one default address per customer.
    op.create_index("uq_addresses_one_default", "addresses", ["user_id"], unique=True,
                    postgresql_where=sa.text("is_default"))

    op.create_table(
        "contact_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("order_number", sa.String(32)),
        sa.Column("locale", sa.String(5)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("emailed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("contact_messages")
    op.drop_index("uq_addresses_one_default", table_name="addresses")
    op.drop_table("addresses")
    op.drop_table("password_reset_tokens")
