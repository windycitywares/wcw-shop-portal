"""Initial schema: users, categories (materialized path), products (JSONB), orders.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-11
"""
from pathlib import Path

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

SQL_FILE = Path(__file__).resolve().parent.parent / "sql" / "0001_initial.sql"


def upgrade() -> None:
    sql = SQL_FILE.read_text(encoding="utf-8")
    # asyncpg runs one statement per call
    for statement in (s.strip() for s in sql.split(";")):
        lines = [ln for ln in statement.splitlines() if not ln.strip().startswith("--")]
        cleaned = "\n".join(lines).strip()
        if cleaned:
            op.execute(cleaned)


def downgrade() -> None:
    for table in ("order_items", "orders", "products", "categories", "newsletter_subscribers", "users"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for enum in ("fulfillment_status", "order_status", "stock_status", "content_status", "user_role"):
        op.execute(f"DROP TYPE IF EXISTS {enum}")
