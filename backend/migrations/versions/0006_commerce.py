"""Commerce: settings, shipping, tax, sales, coupons, refunds, order timeline, inbox status.

Revision ID: 0006_commerce
Revises: 0005_load_translations
Create Date: 2026-10-13
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_commerce"
down_revision = "0005_load_translations"
branch_labels = None
depends_on = None

NOW = sa.text("now()")
TRUE = sa.text("true")
FALSE = sa.text("false")
ZERO = sa.text("0")
EMPTY_LIST = sa.text("'[]'::jsonb")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_by_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
    )

    op.create_table(
        "shipping_methods",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(300)),
        sa.Column("price", sa.Numeric(12, 2), server_default=ZERO, nullable=False),
        sa.Column("free_over", sa.Numeric(12, 2)),
        sa.Column("min_days", sa.Integer()),
        sa.Column("max_days", sa.Integer()),
        sa.Column("countries", postgresql.JSONB(), server_default=EMPTY_LIST, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=TRUE, nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=ZERO, nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_shipping_methods_code"),
        sa.CheckConstraint("price >= 0", name="ck_shipping_methods_price_nonneg"),
    )

    op.create_table(
        "tax_rates",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("region", sa.String(100)),
        sa.Column("rate", sa.Numeric(6, 3), nullable=False),
        sa.Column("applies_to_shipping", sa.Boolean(), server_default=FALSE, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=TRUE, nullable=False),
        *_timestamps(),
        sa.CheckConstraint("rate >= 0 AND rate <= 100", name="ck_tax_rates_rate_range"),
    )

    op.create_table(
        "sales",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("label", sa.String(40)),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("value", sa.Numeric(12, 2), nullable=False),
        sa.Column("scope", sa.String(10), server_default="all", nullable=False),
        sa.Column("category_id", sa.BigInteger(), sa.ForeignKey("categories.id", ondelete="SET NULL")),
        sa.Column("product_ids", postgresql.JSONB(), server_default=EMPTY_LIST, nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), server_default=TRUE, nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_timestamps(),
        sa.CheckConstraint("kind IN ('percent', 'fixed')", name="ck_sales_kind_valid"),
        sa.CheckConstraint("scope IN ('all', 'category', 'products')", name="ck_sales_scope_valid"),
        sa.CheckConstraint("value > 0", name="ck_sales_value_positive"),
    )
    op.create_index("ix_sales_active_window", "sales", ["is_active", "starts_at", "ends_at"])

    op.create_table(
        "coupons",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("description", sa.String(300)),
        sa.Column("kind", sa.String(14), nullable=False),
        sa.Column("value", sa.Numeric(12, 2), server_default=ZERO, nullable=False),
        sa.Column("min_subtotal", sa.Numeric(12, 2)),
        sa.Column("max_discount", sa.Numeric(12, 2)),
        sa.Column("scope", sa.String(10), server_default="all", nullable=False),
        sa.Column("category_id", sa.BigInteger(), sa.ForeignKey("categories.id", ondelete="SET NULL")),
        sa.Column("product_ids", postgresql.JSONB(), server_default=EMPTY_LIST, nullable=False),
        sa.Column("exclude_sale_items", sa.Boolean(), server_default=FALSE, nullable=False),
        sa.Column("first_order_only", sa.Boolean(), server_default=FALSE, nullable=False),
        sa.Column("usage_limit", sa.Integer()),
        sa.Column("per_customer_limit", sa.Integer()),
        sa.Column("used_count", sa.Integer(), server_default=ZERO, nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), server_default=TRUE, nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("email", sa.String(320)),
        sa.Column("issued_to", sa.String(320)),
        sa.Column("campaign", sa.String(80)),
        sa.Column("source", sa.String(12), server_default="manual", nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_coupons_code"),
        sa.CheckConstraint("kind IN ('percent', 'fixed', 'free_shipping')", name="ck_coupons_kind_valid"),
        sa.CheckConstraint("scope IN ('all', 'category', 'products')", name="ck_coupons_scope_valid"),
        sa.CheckConstraint("source IN ('manual', 'generated', 'welcome', 'personal')", name="ck_coupons_source_valid"),
        sa.CheckConstraint("value >= 0", name="ck_coupons_value_nonneg"),
    )
    op.create_index("ix_coupons_issued_to", "coupons", ["issued_to"])
    op.create_index("ix_coupons_campaign", "coupons", ["campaign"])

    # Orders: everything checkout and fulfilment need.
    op.add_column("orders", sa.Column("internal_note", sa.Text()))
    op.add_column("orders", sa.Column("access_token", sa.String(64)))
    op.add_column("orders", sa.Column("coupon_code", sa.String(40)))
    op.add_column("orders", sa.Column("locale", sa.String(5)))
    op.add_column("orders", sa.Column("sale_savings", sa.Numeric(12, 2), server_default=ZERO, nullable=False))
    op.add_column("orders", sa.Column("shipping_discount", sa.Numeric(12, 2), server_default=ZERO, nullable=False))
    op.add_column("orders", sa.Column("refunded_total", sa.Numeric(12, 2), server_default=ZERO, nullable=False))
    op.add_column("orders", sa.Column("carrier", sa.String(50)))
    op.add_column("orders", sa.Column("tax_lines", postgresql.JSONB(), server_default=EMPTY_LIST, nullable=False))
    for col in ("paid_at", "shipped_at", "delivered_at", "cancelled_at"):
        op.add_column("orders", sa.Column(col, sa.DateTime(timezone=True)))
    op.create_unique_constraint("uq_orders_access_token", "orders", ["access_token"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_placed_at", "orders", ["placed_at"])
    op.create_index("ix_orders_email", "orders", ["email"])
    op.add_column("order_items", sa.Column("list_price", sa.Numeric(12, 2)))
    op.add_column("order_items", sa.Column("discount", sa.Numeric(12, 2), server_default=ZERO, nullable=False))
    # Human-friendly order numbers: WCW-1001, WCW-1002, ...
    op.execute("CREATE SEQUENCE order_number_seq START 1001")

    op.create_table(
        "coupon_redemptions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("coupon_id", sa.BigInteger(), sa.ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), server_default=ZERO, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.UniqueConstraint("order_id", name="uq_coupon_redemptions_order_id"),
    )
    op.create_index("ix_coupon_redemptions_coupon_id", "coupon_redemptions", ["coupon_id"])
    op.create_index("ix_coupon_redemptions_email", "coupon_redemptions", ["email"])

    op.create_table(
        "order_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("data", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    )
    op.create_index("ix_order_events_order_id", "order_events", ["order_id"])

    op.create_table(
        "refunds",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.String(300)),
        sa.Column("restocked", sa.Boolean(), server_default=FALSE, nullable=False),
        sa.Column("provider_ref", sa.String(255)),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_refunds_amount_positive"),
    )
    op.create_index("ix_refunds_order_id", "refunds", ["order_id"])

    # Contact inbox
    op.add_column("contact_messages", sa.Column("status", sa.String(12), server_default="new", nullable=False))
    op.add_column("contact_messages", sa.Column("admin_note", sa.Text()))
    op.add_column("contact_messages", sa.Column("handled_by_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")))
    op.add_column("contact_messages", sa.Column("handled_at", sa.DateTime(timezone=True)))
    op.create_check_constraint("ck_contact_messages_status_valid", "contact_messages", "status IN ('new', 'answered', 'archived')")

    # Out of the box the shop offers two shipping methods; the owner edits them in Settings.
    op.execute(
        "INSERT INTO shipping_methods (code, name, description, price, free_over, min_days, max_days, sort_order) VALUES "
        "('standard', 'Standard shipping', 'Tracked delivery with USPS', 6.95, 75.00, 4, 8, 1), "
        "('express', 'Express shipping', 'Priority delivery', 16.95, NULL, 2, 3, 2)"
    )


def downgrade() -> None:
    op.drop_constraint("ck_contact_messages_status_valid", "contact_messages", type_="check")
    op.drop_column("contact_messages", "handled_at")
    op.drop_column("contact_messages", "handled_by_id")
    op.drop_column("contact_messages", "admin_note")
    op.drop_column("contact_messages", "status")

    op.drop_table("refunds")
    op.drop_table("order_events")
    op.drop_table("coupon_redemptions")
    op.execute("DROP SEQUENCE order_number_seq")
    op.drop_column("order_items", "discount")
    op.drop_column("order_items", "list_price")
    op.drop_index("ix_orders_email", table_name="orders")
    op.drop_index("ix_orders_placed_at", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_constraint("uq_orders_access_token", "orders", type_="unique")
    for col in ("cancelled_at", "delivered_at", "shipped_at", "paid_at", "tax_lines", "carrier", "refunded_total",
                "shipping_discount", "sale_savings", "locale", "coupon_code", "access_token", "internal_note"):
        op.drop_column("orders", col)

    op.drop_table("coupons")
    op.drop_index("ix_sales_active_window", table_name="sales")
    op.drop_table("sales")
    op.drop_table("tax_rates")
    op.drop_table("shipping_methods")
    op.drop_table("settings")
