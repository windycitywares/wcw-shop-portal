"""Create the first admin and (on an empty catalog) placeholder categories/products.

    python -m app.seed

Safe to run more than once. Placeholder products are tagged "sample" and use
source="sample" so they can be found and removed once real products are imported.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from app.core.config import get_settings
from app.core.database import SessionFactory, engine
from app.core.enums import ContentStatus, StockStatus, UserRole
from app.core.security import hash_password
from app.models.product import Product
from app.models.user import User
from app.repositories.product import ProductRepository
from app.repositories.user import UserRepository
from app.services.category import CategoryService

CATEGORIES: list[list[str]] = [
    ["Home", "Decor", "Vases"],
    ["Home", "Decor", "Candles & Holders"],
    ["Home", "Wall Art"],
    ["Kitchen", "Serving Boards"],
    ["Kitchen", "Drinkware"],
    ["Gifts", "For Him"],
    ["Gifts", "For Her"],
]

SAMPLES = [
    ("Ceramic Bud Vase", ["Home", "Decor", "Vases"], "28.00", {"Material": "Ceramic", "Color": ["White", "Sage"]}),
    ("Hand-Poured Soy Candle", ["Home", "Decor", "Candles & Holders"], "22.00", {"Scent": ["Cedar", "Lake Breeze"]}),
    ("Brass Taper Holder", ["Home", "Decor", "Candles & Holders"], "34.00", {"Material": "Brass"}),
    ("City Skyline Print", ["Home", "Wall Art"], "45.00", {"Size": ["8x10", "11x14", "16x20"]}),
    ("Walnut Serving Board", ["Kitchen", "Serving Boards"], "68.00", {"Material": "Walnut", "Engraving": "Optional"}),
    ("Stoneware Coffee Mug", ["Kitchen", "Drinkware"], "24.00", {"Material": "Stoneware", "Color": ["Navy", "Sand"]}),
    ("Leather Valet Tray", ["Gifts", "For Him"], "52.00", {"Material": "Leather", "Color": ["Tan", "Black"]}),
    ("Linen Tea Towel Set", ["Gifts", "For Her"], "26.00", {"Material": "Linen"}),
]


async def seed() -> None:
    settings = get_settings()
    async with SessionFactory() as session:
        users = UserRepository(session)
        admin = None
        if settings.admin_email and settings.admin_password:
            admin = await users.get_by_email(settings.admin_email)
            if not admin:
                admin = users.add(
                    User(
                        email=settings.admin_email.lower(),
                        hashed_password=hash_password(settings.admin_password),
                        full_name="Site Admin",
                        role=UserRole.ADMIN,
                    )
                )
                await session.flush()
                print(f"Created admin {admin.email}")
        else:
            print("ADMIN_EMAIL / ADMIN_PASSWORD not set — skipping admin user")

        products = ProductRepository(session)
        if await products.count() > 0:
            await session.commit()
            print("Catalog not empty — skipping sample products")
            return

        categories = CategoryService(session)
        for path in CATEGORIES:
            await categories.ensure_path(path)

        now = datetime.now(timezone.utc)
        for i, (title, path, price, attrs) in enumerate(SAMPLES, start=1):
            category = await categories.ensure_path(path)
            products.add(
                Product(
                    sku=f"SAMPLE-{i:03d}",
                    slug=await products.unique_slug(title),
                    title=title,
                    description=(
                        f"Placeholder description for {title.lower()}. "
                        "Replace with your real listing via Admin → Import."
                    ),
                    base_price=Decimal(price),
                    category_id=category.id if category else None,
                    stock_status=StockStatus.IN_STOCK,
                    stock_quantity=10,
                    attributes=attrs,
                    images=[],
                    tags=["sample"],
                    status=ContentStatus.PUBLISHED,
                    published_at=now,
                    source="sample",
                    source_ref=f"sample-{i}",
                    created_by_id=admin.id if admin else None,
                )
            )
            await session.flush()
        await session.commit()
        print(f"Created {len(CATEGORIES)} category paths and {len(SAMPLES)} sample products")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
