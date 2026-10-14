"""Shared helpers for the API tests that run against PostgreSQL (TEST_DATABASE_URL).

Not a test module itself. Import `RUN`, `skip_unless_db` and `world()`; the world is created once per test process
(app client, recording mailer, an admin and a publisher) and makes products, users and orders with unique names.
Point TEST_DATABASE_URL at a throwaway database: the tests leave their rows behind.
"""

from __future__ import annotations

import asyncio
import os
import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

RUN = bool(os.environ.get("TEST_DATABASE_URL"))
if RUN:
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ.setdefault("DB_USE_NULL_POOL", "true")

skip_unless_db = unittest.skipUnless(RUN, "TEST_DATABASE_URL not set")
API = "/api/v1"
PASSWORD = "first-password-1"
IPHONE = {"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                        "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"}


def reset_limits() -> None:
    """Forget all rate-limit counters (every TestClient request comes from the same address)."""
    from app.core import rate_limit

    for value in vars(rate_limit).values():
        if isinstance(value, rate_limit.RateLimiter):
            with value._lock:
                value._hits.clear()


class World:
    def __init__(self) -> None:
        from fastapi.testclient import TestClient

        from app.core import mailer
        from app.main import create_app

        self.sent: list[Any] = []

        async def fake_send(mail: Any) -> None:
            self.sent.append(mail)

        self._mailer, self._real_send = mailer, mailer.send
        mailer.send = fake_send
        self.client = TestClient(create_app())
        self.sfx = uuid.uuid4().hex[:8]
        self._n = 0
        self.admin_email = f"admin-{self.sfx}@example.com"
        self.publisher_email = f"publisher-{self.sfx}@example.com"
        self._staff()
        self.admin = self.login(self.admin_email, "admin-password-1")
        self.publisher = self.login(self.publisher_email, "publisher-password-1")
        self.customer_email, self.customer = self.register("customer")

    def close(self) -> None:
        self._mailer.send = self._real_send

    # ---- database ---------------------------------------------------------------------------
    def db(self, fn):
        async def go():
            from app.core.database import SessionFactory

            async with SessionFactory() as session:
                return await fn(session)

        return asyncio.run(go())

    def sql(self, statement: str, **params: Any) -> list[dict[str, Any]]:
        """Run SQL and commit. Returns the rows (as dicts) when there are any."""
        async def go(session):
            from sqlalchemy import text

            result = await session.execute(text(statement), params)
            rows = [dict(r) for r in result.mappings().all()] if result.returns_rows else []
            await session.commit()
            return rows

        return self.db(go)

    def value(self, statement: str, **params: Any) -> Any:
        rows = self.sql(statement, **params)
        return next(iter(rows[0].values())) if rows else None

    # ---- people ----------------------------------------------------------------------------
    def email(self, tag: str = "shopper") -> str:
        return f"{tag}-{uuid.uuid4().hex[:10]}@example.com"

    def _staff(self) -> None:
        async def go(session):
            from app.core.enums import UserRole
            from app.core.security import hash_password
            from app.models.user import User

            session.add_all([
                User(email=self.admin_email, hashed_password=hash_password("admin-password-1"), full_name="Ada Admin", role=UserRole.ADMIN),
                User(email=self.publisher_email, hashed_password=hash_password("publisher-password-1"), full_name="Pat Publisher",
                     role=UserRole.PUBLISHER),
            ])
            await session.commit()

        self.db(go)

    def login(self, email: str, password: str) -> dict[str, str]:
        reset_limits()
        r = self.client.post(f"{API}/auth/login", data={"username": email, "password": password})
        if r.status_code != 200:
            raise AssertionError(f"login failed: {r.status_code} {r.text}")
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def register(self, tag: str = "shopper", name: str = "Test Person") -> tuple[str, dict[str, str]]:
        reset_limits()
        email = self.email(tag)
        r = self.client.post(f"{API}/auth/register", json={"email": email, "password": PASSWORD, "full_name": name})
        if r.status_code != 201:
            raise AssertionError(f"register failed: {r.status_code} {r.text}")
        return email, {"Authorization": f"Bearer {r.json()['access_token']}"}

    # ---- catalog -----------------------------------------------------------------------------
    def product(self, price: str = "40.00", stock: int | None = 30, cost: str | None = "15.00", *,
                out_of_stock: bool = False, title: str = "Test urn") -> dict[str, Any]:
        self._n += 1
        n = self._n

        async def go(session):
            from app.core.enums import ContentStatus, StockStatus
            from app.models.product import Product

            p = Product(
                sku=f"CT-{self.sfx}-{n}".upper(), slug=f"ct-{self.sfx}-{n}", title=f"{title} {self.sfx} {n}",
                description="Made by the automated tests.", base_price=Decimal(price),
                stock_status=StockStatus.OUT_OF_STOCK if out_of_stock else StockStatus.IN_STOCK,
                stock_quantity=0 if out_of_stock else stock, cost_price=Decimal(cost) if cost else None,
                status=ContentStatus.PUBLISHED, images=[{"url": "https://media.example.com/test.jpg", "alt": title}],
                published_at=datetime.now(timezone.utc),
            )
            session.add(p)
            await session.commit()
            return {"id": p.id, "slug": p.slug, "title": p.title, "price": float(price)}

        return self.db(go)

    # ---- HTTP ------------------------------------------------------------------------------
    @staticmethod
    def url(path: str) -> str:
        return path if path.startswith(API) else f"{API}{path}"

    def get(self, path: str, headers: dict | None = None, **params: Any):
        return self.client.get(self.url(path), headers=headers, params={k: v for k, v in params.items() if v is not None})

    def post(self, path: str, body: Any = None, headers: dict | None = None):
        return self.client.post(self.url(path), json=body, headers=headers)

    def put(self, path: str, body: Any = None, headers: dict | None = None):
        return self.client.put(self.url(path), json=body, headers=headers)

    def delete(self, path: str, headers: dict | None = None):
        return self.client.delete(self.url(path), headers=headers)

    def quote(self, items: list[dict], **body: Any) -> dict[str, Any]:
        reset_limits()
        r = self.post("/cart/quote", {"items": items, **body})
        if r.status_code != 200:
            raise AssertionError(f"quote failed: {r.status_code} {r.text}")
        return r.json()

    # ---- checkout -------------------------------------------------------------------------
    @staticmethod
    def address(**over: Any) -> dict[str, Any]:
        return {"full_name": "Ana Ruiz", "line1": "1 Main St", "city": "Chicago", "region": "IL", "postal_code": "60601",
                "country": "US", **over}

    def checkout_body(self, email: str, items: list[dict], **over: Any) -> dict[str, Any]:
        return {"items": items, "email": email, "shipping_address": self.address(), "payment_method": "test", "locale": "en", **over}

    def place(self, email: str, items: list[dict], headers: dict | None = None, expect: int = 201, **over: Any) -> dict[str, Any]:
        """Check out (test payment unless `payment_method` is given) and return the response body."""
        reset_limits()
        r = self.post("/checkout", self.checkout_body(email, items, **over), headers)
        if r.status_code != expect:
            raise AssertionError(f"checkout answered {r.status_code}, expected {expect}: {r.text}")
        return r.json()

    def stock(self, product: dict[str, Any]) -> dict[str, Any]:
        return self.sql("SELECT stock_quantity, stock_status::text AS status, units_sold FROM products WHERE id = :id", id=product["id"])[0]

    def mails_to(self, email: str, subject_part: str | None = None) -> list[Any]:
        found = [m for m in self.sent if m.to == email.lower()]
        return [m for m in found if subject_part.lower() in m.subject.lower()] if subject_part else found


def item(product: dict[str, Any], quantity: int = 1) -> dict[str, Any]:
    return {"product_id": product["id"], "quantity": quantity}


_WORLD: World | None = None


def world() -> World:
    global _WORLD
    if _WORLD is None:
        _WORLD = World()
    return _WORLD
