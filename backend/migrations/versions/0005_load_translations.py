"""Load the Spanish and Dutch catalog translations (backend/data/translations/*.json).

Same data `python -m app.scripts.import_catalog` loads, applied by the automatic deploy so nobody
has to run the script on the server. Only fills rows whose translations are still empty, so edits
made later in the admin are never overwritten.

Revision ID: 0005_load_translations
Revises: 0004_accounts
Create Date: 2026-10-12
"""
import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0005_load_translations"
down_revision = "0004_accounts"
branch_labels = None
depends_on = None

DATA = Path(__file__).resolve().parents[2] / "data" / "translations"


def _by_key(kind: str) -> dict[str, dict]:
    """{key: {"es": {...}, "nl": {...}}} with empty values dropped."""
    out: dict[str, dict] = {}
    for f in sorted(DATA.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for key, entry in data.get(kind, {}).items():
            fields = {k: v for k, v in entry.items() if v}
            if fields:
                out.setdefault(key, {})[f.stem] = fields
    return out


def upgrade() -> None:
    if not DATA.is_dir():
        return
    conn = op.get_bind()
    products = sa.text(
        "UPDATE products SET translations = CAST(:tr AS jsonb) "
        "WHERE source = 'etsy' AND source_ref = :ref AND translations = '{}'::jsonb"
    )
    for ref, tr in _by_key("products").items():
        conn.execute(products, {"tr": json.dumps(tr, ensure_ascii=False), "ref": ref})
    categories = sa.text(
        "UPDATE categories SET translations = CAST(:tr AS jsonb) WHERE slug = :slug AND translations = '{}'::jsonb"
    )
    for slug, tr in _by_key("categories").items():
        conn.execute(categories, {"tr": json.dumps(tr, ensure_ascii=False), "slug": slug})


def downgrade() -> None:
    pass  # data only; translations stay (they can be edited in the admin)
