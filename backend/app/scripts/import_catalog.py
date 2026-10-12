"""Load a curated catalog file (e.g. data/etsy_catalog.json) into the store.

    python -m app.scripts.import_catalog --file data/etsy_catalog.json --replace

* Downloads every product photo into MEDIA_ROOT/products/<slug>/NN.jpg (skips files already
  there), so the store serves its own copies from MEDIA_URL.
* --replace deletes ALL existing products and categories first (sample data included).
* Re-running without --replace updates products matched by (source, source_ref).
* --dry-run shows what would happen without changing anything.
* Translations: every <lang>.json in --translations (default: data/translations next to the
  catalog file) is merged in — {"categories": {slug: {"name", "description"}},
  "products": {source_ref: {"title", "description", ...}}}.

Catalog file format: {"categories": [...], "products": [...]} — see data/README.md.
"""

import argparse
import asyncio
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, func, select, text

from app.core.config import get_settings
from app.core.database import SessionFactory, engine
from app.core.enums import ContentStatus, StockStatus, UserRole
from app.models.category import Category
from app.models.product import Product
from app.models.user import User

USER_AGENT = "WindyCityWares-catalog-import/1.0 (+https://shop.windycitywares.com)"


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


# -- images -----------------------------------------------------------------
def _download(url: str, dest: Path) -> tuple[str, str]:
    if dest.exists() and dest.stat().st_size > 0:
        return "kept", url
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as fh:
                ctype = resp.headers.get("Content-Type", "")
                if not ctype.startswith("image/"):
                    raise ValueError(f"not an image ({ctype})")
                fh.write(resp.read())
            tmp.replace(dest)
            return "downloaded", url
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                tmp.unlink(missing_ok=True)
                return f"failed: {exc}", url
            time.sleep(2 * (attempt + 1))
    return "failed", url


def mirror_images(products: list[dict], media_root: Path, media_url: str, workers: int = 6) -> dict[str, str]:
    """Download all photos; return {source url: public url} for the ones we have."""
    jobs = []
    for p in products:
        for i, img in enumerate(p.get("images", []), start=1):
            dest = media_root / "products" / p["slug"] / f"{i:02d}.jpg"
            jobs.append((img["url"], dest))
    log(f"photos: {len(jobs)} to check in {media_root}")
    mapping: dict[str, str] = {}
    counts: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for n, ((url, dest), (status, _)) in enumerate(
            zip(jobs, pool.map(lambda j: _download(*j), jobs)), start=1
        ):
            key = status.split(":")[0]
            counts[key] = counts.get(key, 0) + 1
            if key != "failed":
                mapping[url] = f"{media_url.rstrip('/')}/{dest.relative_to(media_root).as_posix()}"
            else:
                log(f"  ! {url}: {status}")
            if n % 100 == 0:
                log(f"  {n}/{len(jobs)} {counts}")
    log(f"photos done: {counts}")
    return mapping


# -- database ---------------------------------------------------------------
async def wipe_catalog(session) -> None:
    n_products = (await session.execute(select(func.count()).select_from(Product))).scalar_one()
    n_categories = (await session.execute(select(func.count()).select_from(Category))).scalar_one()
    await session.execute(delete(Product).where(Product.parent_id.is_not(None)))
    await session.execute(delete(Product))
    # Delete leaves first (parent_id is ON DELETE RESTRICT).
    while True:
        leaves = (
            await session.execute(
                select(Category.id).where(~Category.id.in_(select(Category.parent_id).where(Category.parent_id.is_not(None))))
            )
        ).scalars().all()
        if not leaves:
            break
        await session.execute(delete(Category).where(Category.id.in_(leaves)))
    log(f"removed {n_products} products and {n_categories} categories")


def load_translations(folder: Path) -> dict[str, dict]:
    """{"es": {"categories": {...}, "products": {...}}, ...} from <folder>/<lang>.json."""
    out: dict[str, dict] = {}
    if folder.is_dir():
        for f in sorted(folder.glob("*.json")):
            out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return out


def translations_for(all_tr: dict[str, dict], kind: str, key: str) -> dict[str, dict]:
    return {
        lang: {k: v for k, v in entry.items() if v}
        for lang, data in all_tr.items()
        if (entry := data.get(kind, {}).get(key))
    }


async def upsert_categories(session, categories: list[dict]) -> dict[str, Category]:
    by_slug: dict[str, Category] = {}
    existing = {c.slug: c for c in (await session.execute(select(Category))).scalars()}
    # Parents first
    for spec in sorted(categories, key=lambda c: c.get("parent") is not None):
        parent = by_slug.get(spec["parent"]) if spec.get("parent") else None
        cat = existing.get(spec["slug"])
        if cat is None:
            new_id = (await session.execute(text("SELECT nextval('categories_id_seq')"))).scalar_one()
            cat = Category(
                id=new_id,
                parent_id=parent.id if parent else None,
                path=f"{parent.path}.{new_id}" if parent else str(new_id),
                slug=spec["slug"],
                name=spec["name"],
            )
            session.add(cat)
        cat.name = spec["name"]
        cat.description = spec.get("description")
        cat.sort_order = spec.get("sort_order", 0)
        cat.image_url = spec.get("image_url")
        cat.is_active = True
        cat.translations = spec.get("translations", {})
        await session.flush()
        by_slug[spec["slug"]] = cat
    log(f"categories ready: {len(by_slug)}")
    return by_slug


def _money(v) -> Decimal | None:
    return None if v in (None, "") else Decimal(str(v)).quantize(Decimal("0.01"))


async def upsert_products(session, products: list[dict], categories: dict[str, Category], photo_urls: dict[str, str], owner_id):
    now = datetime.now(timezone.utc)
    created = updated = variants = 0
    # The file lists products newest-first (Etsy's order); stagger published_at so the
    # store's "Newest" sort keeps that order.
    for position, spec in enumerate(products):
        published_at = now - timedelta(seconds=position)
        images = [
            {"url": photo_urls.get(img["url"], img["url"]), "alt": img.get("alt") or spec["title"]}
            for img in spec.get("images", [])
        ]
        category = categories.get(spec.get("category"))
        product = (
            await session.execute(
                select(Product).where(Product.source == spec["source"], Product.source_ref == spec["source_ref"])
            )
        ).scalar_one_or_none()
        fields = dict(
            title=spec["title"][:300],
            slug=spec["slug"],
            sku=spec["sku"],
            description=spec.get("description"),
            base_price=_money(spec["price"]),
            compare_at_price=_money(spec.get("compare_at_price")),
            currency=spec.get("currency", "USD"),
            stock_quantity=spec.get("quantity"),
            stock_status=StockStatus.IN_STOCK if (spec.get("quantity") or 0) > 0 else StockStatus.OUT_OF_STOCK,
            category_id=category.id if category else None,
            attributes=spec.get("attributes", {}),
            images=images,
            tags=spec.get("tags", []),
            status=ContentStatus.PUBLISHED,
            published_at=published_at,
            seo_title=spec.get("seo_title"),
            seo_description=spec.get("seo_description"),
            translations=spec.get("translations", {}),
        )
        if product is None:
            product = Product(source=spec["source"], source_ref=spec["source_ref"], created_by_id=owner_id, **fields)
            session.add(product)
            created += 1
        else:
            for k, v in fields.items():
                setattr(product, k, v)
            updated += 1
        await session.flush()

        # Variants (e.g. sizes) are replaced wholesale.
        await session.execute(delete(Product).where(Product.parent_id == product.id))
        for i, v in enumerate(spec.get("variants", []), start=1):
            session.add(
                Product(
                    parent_id=product.id,
                    category_id=product.category_id,
                    sku=f"{spec['sku']}-{i}",
                    slug=f"{spec['slug']}-size-{i}",  # never collides with product slugs
                    title=f"{spec['title'][:250]} — {v['name']}",
                    base_price=_money(v["price"]),
                    compare_at_price=_money(v.get("compare_at_price")),
                    currency=product.currency,
                    stock_quantity=spec.get("quantity"),
                    stock_status=product.stock_status,
                    attributes={k: val for k, val in v.items() if k not in ("name", "price", "compare_at_price")}
                    or {"Size": v["name"]},
                    images=[],
                    tags=[],
                    status=ContentStatus.PUBLISHED,
                    source=spec["source"],
                    source_ref=f"{spec['source_ref']}-{i}",
                    created_by_id=owner_id,
                    published_at=published_at,
                )
            )
            variants += 1
        await session.flush()
    log(f"products: {created} created, {updated} updated, {variants} size variants")


async def run(args) -> int:
    settings = get_settings()
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    products, categories = data["products"], data["categories"]
    log(f"catalog file: {len(categories)} categories, {len(products)} products")
    tr_dir = Path(args.translations) if args.translations else Path(args.file).resolve().parent / "translations"
    all_tr = load_translations(tr_dir)
    for c in categories:
        c["translations"] = translations_for(all_tr, "categories", c["slug"])
    for p in products:
        p["translations"] = translations_for(all_tr, "products", p["source_ref"])
    for lang in all_tr:
        n = sum(1 for p in products if lang in p["translations"])
        log(f"translations {lang}: {n}/{len(products)} products, "
            f"{sum(1 for c in categories if lang in c['translations'])}/{len(categories)} categories")
    if args.dry_run:
        for c in categories:
            log(f"  category {c['slug']} ({sum(1 for p in products if p.get('category') == c['slug'])} products)")
        return 0

    photo_urls = {} if args.skip_images else mirror_images(products, Path(settings.media_root), settings.media_url)

    async with SessionFactory() as session:
        owner_id = (
            await session.execute(select(User.id).where(User.role == UserRole.ADMIN).order_by(User.id).limit(1))
        ).scalar_one_or_none()
        if args.replace:
            await wipe_catalog(session)
        cats = await upsert_categories(session, categories)
        await upsert_products(session, products, cats, photo_urls, owner_id)
        await session.commit()
    log("done")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", required=True)
    parser.add_argument("--replace", action="store_true", help="delete all existing products and categories first")
    parser.add_argument("--skip-images", action="store_true", help="link the original photo URLs instead of copying")
    parser.add_argument("--translations", help="folder of <lang>.json files (default: translations/ next to --file)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    async def _main() -> int:
        try:
            return await run(args)
        finally:
            await engine.dispose()

    sys.exit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
