"""Stock movements. Each is one conditional UPDATE, so two shoppers can never buy the last unit twice."""

from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Take units only while enough are on the shelf. Reaching zero marks the product out of stock.
_TAKE = text(
    """
    UPDATE products
    SET stock_quantity = stock_quantity - :qty,
        stock_status = CASE WHEN stock_quantity - :qty <= 0 THEN 'out_of_stock'::stock_status ELSE stock_status END,
        updated_at = now()
    WHERE id = :id AND stock_status = 'in_stock' AND stock_quantity IS NOT NULL AND stock_quantity >= :qty
      AND NOT EXISTS (SELECT 1 FROM products par WHERE par.id = products.parent_id AND par.stock_status = 'out_of_stock')
    """
)

# Put units back. A product we sold out comes back in stock (one that staff marked out of stock by hand does not).
_GIVE_BACK = text(
    """
    UPDATE products
    SET stock_quantity = stock_quantity + :qty,
        stock_status = CASE WHEN stock_status = 'out_of_stock' AND stock_quantity = 0 THEN 'in_stock'::stock_status ELSE stock_status END,
        updated_at = now()
    WHERE id = :id AND stock_quantity IS NOT NULL
    """
)

# A product with variants is in stock while any of its variants is.
_SYNC_PARENTS = text(
    """
    WITH calc AS (
        SELECT p.id,
               CASE WHEN EXISTS (
                        SELECT 1 FROM products c
                        WHERE c.parent_id = p.id AND c.status = 'published'
                          AND ((c.stock_status = 'in_stock' AND (c.stock_quantity IS NULL OR c.stock_quantity > 0))
                               OR c.stock_status IN ('backorder', 'preorder'))
                    ) THEN 'in_stock' ELSE 'out_of_stock' END AS new_status
        FROM products p
        WHERE p.id = ANY(:ids) AND p.stock_status IN ('in_stock', 'out_of_stock')
          AND EXISTS (SELECT 1 FROM products c WHERE c.parent_id = p.id)
    )
    UPDATE products p
    SET stock_status = calc.new_status::stock_status, updated_at = now()
    FROM calc
    WHERE p.id = calc.id AND p.stock_status::text <> calc.new_status
    """
)

_UNITS_SOLD = text("UPDATE products SET units_sold = GREATEST(units_sold + :n, 0) WHERE id = :id")


async def take(session: AsyncSession, product_id: int, quantity: int) -> bool:
    """True when the units were reserved."""
    result = await session.execute(_TAKE, {"id": product_id, "qty": quantity})
    return result.rowcount == 1


async def give_back(session: AsyncSession, product_id: int, quantity: int) -> None:
    if quantity > 0:
        await session.execute(_GIVE_BACK, {"id": product_id, "qty": quantity})


async def sync_parents(session: AsyncSession, parent_ids: Iterable[int]) -> None:
    ids = sorted({i for i in parent_ids if i})
    if ids:
        await session.execute(_SYNC_PARENTS, {"ids": ids})


async def add_units_sold(session: AsyncSession, product_id: int, parent_id: int | None, quantity: int) -> None:
    """Count units on the product and, for a variant, on its parent too (best sellers are ranked by parent)."""
    for pid in {product_id, parent_id} - {None}:
        await session.execute(_UNITS_SOLD, {"id": pid, "n": quantity})
