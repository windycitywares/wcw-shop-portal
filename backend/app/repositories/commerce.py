"""Queries for settings, shipping, tax, sales and coupons."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.models.commerce import Coupon, CouponRedemption, Sale, Setting, ShippingMethod, TaxRate
from app.repositories.base import BaseRepository
from app.utils.text import escape_like

COUPON_STATUSES = ("active", "scheduled", "expired", "used_up", "paused")


class SettingRepository(BaseRepository[Setting]):
    model = Setting

    async def all(self) -> dict[str, Any]:
        rows = (await self.session.execute(select(Setting))).scalars().all()
        return {r.key: r.value for r in rows}

    async def upsert(self, key: str, value: Any, user_id: int | None) -> None:
        stmt = insert(Setting).values(key=key, value=value, updated_by_id=user_id)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Setting.key], set_={"value": stmt.excluded.value, "updated_by_id": user_id, "updated_at": func.now()}
        )
        await self.session.execute(stmt)


class ShippingRepository(BaseRepository[ShippingMethod]):
    model = ShippingMethod

    async def list_all(self, active_only: bool = False) -> list[ShippingMethod]:
        stmt = select(ShippingMethod).order_by(ShippingMethod.sort_order, ShippingMethod.id)
        if active_only:
            stmt = stmt.where(ShippingMethod.is_active.is_(True))
        return list((await self.session.execute(stmt)).scalars().all())


class TaxRepository(BaseRepository[TaxRate]):
    model = TaxRate

    async def list_all(self, active_only: bool = False) -> list[TaxRate]:
        stmt = select(TaxRate).order_by(TaxRate.country, TaxRate.region.nulls_first(), TaxRate.id)
        if active_only:
            stmt = stmt.where(TaxRate.is_active.is_(True))
        return list((await self.session.execute(stmt)).scalars().all())


class SaleRepository(BaseRepository[Sale]):
    model = Sale

    async def list_all(self) -> list[Sale]:
        stmt = select(Sale).order_by(Sale.is_active.desc(), Sale.starts_at.desc().nulls_last(), Sale.id.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def live(self, now: datetime) -> list[Sale]:
        stmt = select(Sale).where(
            Sale.is_active.is_(True),
            or_(Sale.starts_at.is_(None), Sale.starts_at <= now),
            or_(Sale.ends_at.is_(None), Sale.ends_at > now),
        )
        return list((await self.session.execute(stmt)).scalars().all())


def _status_condition(status: str, now: datetime):
    expired = and_(Coupon.expires_at.is_not(None), Coupon.expires_at <= now)
    scheduled = and_(Coupon.starts_at.is_not(None), Coupon.starts_at > now)
    used_up = and_(Coupon.usage_limit.is_not(None), Coupon.used_count >= Coupon.usage_limit)
    on = Coupon.is_active.is_(True)
    return {
        "paused": Coupon.is_active.is_(False),
        "expired": and_(on, expired),
        "scheduled": and_(on, ~expired, scheduled),
        "used_up": and_(on, ~expired, ~scheduled, used_up),
        "active": and_(on, ~expired, ~scheduled, ~used_up),
    }[status]


class CouponRepository(BaseRepository[Coupon]):
    model = Coupon

    async def get_by_code(self, code: str, *, lock: bool = False) -> Coupon | None:
        stmt = select(Coupon).where(Coupon.code == code).limit(1)
        if lock:  # populate_existing: always read the latest used_count
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def existing_codes(self, codes: list[str]) -> set[str]:
        rows = await self.session.execute(select(Coupon.code).where(Coupon.code.in_(codes)))
        return set(rows.scalars().all())

    async def search(
        self, *, q: str | None, status: str | None, campaign: str | None, source: str | None,
        now: datetime, page: int, page_size: int,
    ) -> tuple[list[tuple[Coupon, Decimal, int]], int]:
        where = []
        if q:
            like = f"%{escape_like(q.strip())}%"
            where.append(or_(Coupon.code.ilike(like), Coupon.description.ilike(like), Coupon.issued_to.ilike(like),
                             Coupon.campaign.ilike(like)))
        if status in COUPON_STATUSES:
            where.append(_status_condition(status, now))
        if campaign:
            where.append(Coupon.campaign == campaign)
        if source:
            where.append(Coupon.source == source)
        total = (await self.session.execute(select(func.count()).select_from(Coupon).where(*where))).scalar_one()
        given = func.coalesce(func.sum(CouponRedemption.amount), 0)
        stmt = (
            select(Coupon, given, func.count(CouponRedemption.id))
            .outerjoin(CouponRedemption, CouponRedemption.coupon_id == Coupon.id)
            .where(*where)
            .group_by(Coupon.id)
            .order_by(Coupon.created_at.desc(), Coupon.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(stmt)).all()
        return [(c, Decimal(g), int(n)) for c, g, n in rows], total

    async def usage_totals(self, coupon_id: int) -> tuple[Decimal, int]:
        row = (await self.session.execute(
            select(func.coalesce(func.sum(CouponRedemption.amount), 0), func.count(CouponRedemption.id))
            .where(CouponRedemption.coupon_id == coupon_id)
        )).one()
        return Decimal(row[0]), int(row[1])

    async def uses_by(self, coupon_id: int, user_id: int | None, email: str | None) -> int:
        conds = []
        if user_id is not None:
            conds.append(CouponRedemption.user_id == user_id)
        if email:
            conds.append(func.lower(CouponRedemption.email) == email.strip().lower())
        if not conds:
            return 0
        stmt = select(func.count()).select_from(CouponRedemption).where(CouponRedemption.coupon_id == coupon_id, or_(*conds))
        return (await self.session.execute(stmt)).scalar_one()

    async def take_use(self, coupon_id: int) -> bool:
        """Count one use, but only while the limit allows it (safe when two orders race)."""
        result = await self.session.execute(
            update(Coupon)
            .where(Coupon.id == coupon_id, or_(Coupon.usage_limit.is_(None), Coupon.used_count < Coupon.usage_limit))
            .values(used_count=Coupon.used_count + 1)
        )
        return result.rowcount == 1

    async def give_back_use(self, coupon_id: int) -> None:
        await self.session.execute(
            update(Coupon).where(Coupon.id == coupon_id, Coupon.used_count > 0).values(used_count=Coupon.used_count - 1)
        )

    async def campaigns(self) -> list[tuple[str, int, int, Decimal, datetime]]:
        given = func.coalesce(func.sum(CouponRedemption.amount), 0)
        used = func.count(CouponRedemption.id)
        stmt = (
            select(Coupon.campaign, func.count(func.distinct(Coupon.id)), used, given, func.min(Coupon.created_at))
            .outerjoin(CouponRedemption, CouponRedemption.coupon_id == Coupon.id)
            .where(Coupon.campaign.is_not(None), Coupon.source == "generated")
            .group_by(Coupon.campaign)
            .order_by(func.min(Coupon.created_at).desc())
        )
        return [(c, int(n), int(u), Decimal(g), at) for c, n, u, g, at in (await self.session.execute(stmt)).all()]

    async def codes_in_campaign(self, campaign: str, limit: int = 5000) -> list[Coupon]:
        stmt = select(Coupon).where(Coupon.campaign == campaign).order_by(Coupon.id).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def welcome_for(self, email: str) -> Coupon | None:
        stmt = select(Coupon).where(Coupon.source == "welcome", Coupon.issued_to == email.strip().lower()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()
