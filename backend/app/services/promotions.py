"""Staff tools for sales, coupons and automatic offers, plus the helper that issues personal coupons."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ContentStatus, OrderStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.domain import coupons as codes
from app.domain.csvsafe import to_csv
from app.models.category import Category
from app.models.commerce import CartRule, Coupon, CouponRedemption, Sale
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.schemas.promotions import (
    BulkResultOut,
    CartRuleIn,
    CartRuleOut,
    CouponBulkIn,
    CouponDetailOut,
    CouponIn,
    CouponListOut,
    CouponOut,
    CouponRedemptionOut,
    SaleIn,
    SaleOut,
    window_status,
)
from app.services import audit, promo_catalog
from app.utils.text import escape_like

UNIQUE_RETRIES = 5


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def coupon_status(c: Coupon, now: datetime) -> str:
    if not c.is_active:
        return "paused"
    if c.usage_limit is not None and c.used_count >= c.usage_limit:
        return "used_up"
    if c.starts_at and now < c.starts_at:
        return "scheduled"
    if c.expires_at and now >= c.expires_at:
        return "expired"
    return "active"


def coupon_out(c: Coupon, now: datetime | None = None) -> CouponOut:
    out = CouponOut.model_validate(c)
    out.status = coupon_status(c, now or utcnow())
    return out


async def issue_coupon(
    session: AsyncSession, *, email: str | None, kind: str, value: Decimal, expires_days: int | None, source: str,
    prefix: str, campaign: str | None = None, min_subtotal: Decimal = Decimal("0"), first_order_only: bool = False,
    usage_limit: int | None = 1, per_customer_limit: int | None = 1, name: str | None = None, code_length: int = 6,
) -> Coupon:
    """Create a personal, single-use coupon (welcome offer, cart recovery, win-back). Adds the row, no commit."""
    for _ in range(UNIQUE_RETRIES):
        code = codes.generate_code(prefix, code_length)
        if (await session.execute(select(Coupon.id).where(Coupon.code == code))).first() is None:
            break
    else:  # pragma: no cover - 32^6 possibilities per prefix
        raise ConflictError("Could not create a unique code. Please try again.")
    coupon = Coupon(
        code=code, name=name, kind=kind, value=value, min_subtotal=min_subtotal, first_order_only=first_order_only,
        assigned_email=email.lower() if email else None, usage_limit=usage_limit, per_customer_limit=per_customer_limit,
        expires_at=utcnow() + timedelta(days=expires_days) if expires_days else None, source=source, campaign=campaign,
    )
    session.add(coupon)
    await session.flush()
    return coupon


class PromotionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _check_refs(self, category_ids: list[int], product_ids: list[int]) -> None:
        if category_ids:
            found = (await self.session.execute(select(func.count()).select_from(Category).where(Category.id.in_(set(category_ids))))).scalar_one()
            if found != len(set(category_ids)):
                raise ValidationFailedError("One of the chosen categories no longer exists.")
        if product_ids:
            found = (await self.session.execute(select(func.count()).select_from(Product).where(Product.id.in_(set(product_ids))))).scalar_one()
            if found != len(set(product_ids)):
                raise ValidationFailedError("One of the chosen products no longer exists.")

    def _changed(self) -> None:
        promo_catalog.clear_cache()

    # ---- sales ---------------------------------------------------------------------------
    async def _affected(self, sale: Sale) -> int:
        promo = await promo_catalog.load(self.session)
        rule = promo_catalog.sale_rule(sale, promo.category_paths)
        solo = promo_catalog.PromoCatalog(sales=[rule], category_paths=promo.category_paths)
        # Count as if the sale were running now, whatever its dates.
        clause = promo_catalog.on_sale_clause(solo, now=sale.starts_at or utcnow())
        return (await self.session.execute(
            select(func.count()).select_from(Product).where(Product.parent_id.is_(None), Product.status == ContentStatus.PUBLISHED, clause)
        )).scalar_one()

    async def sale_out(self, sale: Sale, now: datetime | None = None, with_count: bool = True) -> SaleOut:
        out = SaleOut.model_validate(sale)
        out.status = window_status(sale.is_active, sale.starts_at, sale.ends_at, now or utcnow())
        out.affected_products = await self._affected(sale) if with_count else 0
        return out

    async def list_sales(self) -> list[SaleOut]:
        rows = (await self.session.execute(select(Sale).order_by(Sale.is_active.desc(), Sale.starts_at.desc().nulls_first(), Sale.id.desc()))).scalars().all()
        now = utcnow()
        return [await self.sale_out(r, now) for r in rows]

    async def _sale(self, sale_id: int) -> Sale:
        sale = await self.session.get(Sale, sale_id)
        if sale is None:
            raise NotFoundError("Sale not found")
        return sale

    async def create_sale(self, data: SaleIn, user: User) -> SaleOut:
        await self._check_refs(data.category_ids, data.product_ids + data.exclude_product_ids)
        sale = Sale(**data.model_dump(), created_by_id=user.id)
        self.session.add(sale)
        await self.session.flush()
        audit.record(self.session, user, "sale.create", "sale", sale.id, f"Created sale “{sale.name}”")
        await self.session.commit()
        await self.session.refresh(sale)
        self._changed()
        return await self.sale_out(sale)

    async def update_sale(self, sale_id: int, data: SaleIn, user: User) -> SaleOut:
        sale = await self._sale(sale_id)
        await self._check_refs(data.category_ids, data.product_ids + data.exclude_product_ids)
        for field, value in data.model_dump().items():
            setattr(sale, field, value)
        audit.record(self.session, user, "sale.update", "sale", sale.id, f"Changed sale “{sale.name}”")
        await self.session.commit()
        self._changed()
        return await self.sale_out(sale)

    async def set_sale_active(self, sale_id: int, active: bool, user: User) -> SaleOut:
        sale = await self._sale(sale_id)
        sale.is_active = active
        audit.record(self.session, user, "sale.resume" if active else "sale.pause", "sale", sale.id, f"{'Resumed' if active else 'Paused'} sale “{sale.name}”")
        await self.session.commit()
        self._changed()
        return await self.sale_out(sale)

    async def delete_sale(self, sale_id: int, user: User) -> None:
        sale = await self._sale(sale_id)
        audit.record(self.session, user, "sale.delete", "sale", sale.id, f"Deleted sale “{sale.name}”")
        await self.session.delete(sale)
        await self.session.commit()
        self._changed()

    # ---- coupons -------------------------------------------------------------------------
    def _coupon_filters(self, q: str | None, source: str | None, status: str | None, campaign: str | None, now: datetime):
        conds = []
        if q:
            like = f"%{escape_like(q.strip())}%"
            conds.append(or_(Coupon.code.ilike(like), Coupon.name.ilike(like), Coupon.assigned_email.ilike(like), Coupon.campaign.ilike(like)))
        if source:
            conds.append(Coupon.source == source)
        if campaign:
            conds.append(Coupon.campaign == campaign)
        not_used_up = or_(Coupon.usage_limit.is_(None), Coupon.used_count < Coupon.usage_limit)
        if status == "active":
            conds += [Coupon.is_active, or_(Coupon.starts_at.is_(None), Coupon.starts_at <= now), or_(Coupon.expires_at.is_(None), Coupon.expires_at > now), not_used_up]
        elif status == "paused":
            conds.append(Coupon.is_active.is_(False))
        elif status == "scheduled":
            conds += [Coupon.is_active, Coupon.starts_at > now]
        elif status == "expired":
            conds += [Coupon.is_active, Coupon.expires_at <= now]
        elif status == "used_up":
            conds += [Coupon.usage_limit.is_not(None), Coupon.used_count >= Coupon.usage_limit]
        return conds

    async def list_coupons(self, q: str | None, source: str | None, status: str | None, campaign: str | None, page: int, page_size: int) -> CouponListOut:
        now = utcnow()
        conds = self._coupon_filters(q, source, status, campaign, now)
        total = (await self.session.execute(select(func.count()).select_from(Coupon).where(*conds))).scalar_one()
        rows = (await self.session.execute(
            select(Coupon).where(*conds).order_by(Coupon.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        campaigns = (await self.session.execute(
            select(Coupon.campaign).where(Coupon.campaign.is_not(None)).group_by(Coupon.campaign).order_by(func.max(Coupon.id).desc()).limit(50)
        )).scalars().all()
        return CouponListOut(items=[coupon_out(r, now) for r in rows], total=total, page=page, page_size=page_size, campaigns=list(campaigns))

    async def export_csv(self, q: str | None, source: str | None, status: str | None, campaign: str | None) -> str:
        now = utcnow()
        rows = (await self.session.execute(
            select(Coupon).where(*self._coupon_filters(q, source, status, campaign, now)).order_by(Coupon.id).limit(20000)
        )).scalars().all()
        header = ["Code", "Status", "Type", "Value", "Minimum order", "Assigned email", "Campaign", "Uses", "Limit", "Starts", "Expires"]
        return to_csv(header, [
            (c.code, coupon_status(c, now), c.kind, c.value, c.min_subtotal, c.assigned_email, c.campaign, c.used_count, c.usage_limit,
             c.starts_at, c.expires_at) for c in rows
        ])

    async def _coupon(self, coupon_id: int) -> Coupon:
        coupon = await self.session.get(Coupon, coupon_id)
        if coupon is None:
            raise NotFoundError("Coupon not found")
        return coupon

    async def coupon_detail(self, coupon_id: int) -> CouponDetailOut:
        coupon = await self._coupon(coupon_id)
        out = CouponDetailOut.model_validate(coupon)
        out.status = coupon_status(coupon, utcnow())
        rows = (await self.session.execute(
            select(CouponRedemption, Order).join(Order, Order.id == CouponRedemption.order_id)
            .where(CouponRedemption.coupon_id == coupon.id).order_by(CouponRedemption.id.desc()).limit(100)
        )).all()
        out.redemptions = [CouponRedemptionOut(order_id=o.id, order_number=o.number, email=r.email, amount=r.amount, created_at=r.created_at) for r, o in rows]
        revenue = (await self.session.execute(
            select(func.coalesce(func.sum(Order.grand_total - Order.refunded_total), 0))
            .where(Order.coupon_code == coupon.code, Order.paid_at.is_not(None), Order.status.notin_([OrderStatus.CANCELLED, OrderStatus.REFUNDED]))
        )).scalar_one()
        out.revenue = revenue
        return out

    def _terms(self, data) -> dict:
        return data.model_dump(exclude={"code", "assigned_email", "count", "prefix", "length", "emails"})

    async def create_coupon(self, data: CouponIn, user: User) -> CouponOut:
        await self._check_refs(data.category_ids, data.product_ids)
        code = codes.normalize_code(data.code) if data.code else None
        if code and not codes.is_valid_code(code):
            raise ValidationFailedError("A code needs 3 to 40 letters or digits.")
        if code is None:
            code = codes.generate_codes(1, "", 8, taken=[])[0]
        coupon = Coupon(code=code, assigned_email=str(data.assigned_email).lower() if data.assigned_email else None,
                        source="manual", created_by_id=user.id, **self._terms(data))
        self.session.add(coupon)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(f"The code {code} already exists.") from exc
        audit.record(self.session, user, "coupon.create", "coupon", coupon.id, f"Created coupon {coupon.code}")
        await self.session.commit()
        await self.session.refresh(coupon)
        return coupon_out(coupon)

    async def update_coupon(self, coupon_id: int, data: CouponIn, user: User) -> CouponOut:
        coupon = await self._coupon(coupon_id)
        await self._check_refs(data.category_ids, data.product_ids)
        new_code = codes.normalize_code(data.code) if data.code else coupon.code
        if new_code != coupon.code:
            if coupon.used_count > 0:
                raise ConflictError("A code that has been used can't be renamed. Create a new one instead.")
            if not codes.is_valid_code(new_code):
                raise ValidationFailedError("A code needs 3 to 40 letters or digits.")
            coupon.code = new_code
        coupon.assigned_email = str(data.assigned_email).lower() if data.assigned_email else None
        for field, value in self._terms(data).items():
            setattr(coupon, field, value)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(f"The code {new_code} already exists.") from exc
        audit.record(self.session, user, "coupon.update", "coupon", coupon.id, f"Changed coupon {coupon.code}")
        await self.session.commit()
        return coupon_out(coupon)

    async def delete_coupon(self, coupon_id: int, user: User) -> str:
        """Unused coupons are deleted. Used ones are paused instead, so past orders keep their history."""
        coupon = await self._coupon(coupon_id)
        if coupon.used_count > 0:
            coupon.is_active = False
            audit.record(self.session, user, "coupon.pause", "coupon", coupon.id, f"Paused used coupon {coupon.code}")
            await self.session.commit()
            return "paused"
        audit.record(self.session, user, "coupon.delete", "coupon", coupon.id, f"Deleted coupon {coupon.code}")
        await self.session.delete(coupon)
        await self.session.commit()
        return "deleted"

    async def bulk_create(self, data: CouponBulkIn, user: User) -> BulkResultOut:
        await self._check_refs(data.category_ids, data.product_ids)
        emails_ = [str(e).lower() for e in dict.fromkeys(str(e).lower() for e in data.emails)]
        count = len(emails_) or data.count
        prefix = codes.clean_prefix(data.prefix)
        taken = (await self.session.execute(select(Coupon.code).where(Coupon.code.like(f"{escape_like(prefix)}%")))).scalars().all() if prefix else \
            (await self.session.execute(select(Coupon.code))).scalars().all()
        try:
            new_codes = codes.generate_codes(count, prefix, data.length, taken=taken)
        except ValueError as exc:
            raise ValidationFailedError(str(exc)) from exc
        terms = self._terms(data)
        terms["campaign"] = data.campaign
        for i, code in enumerate(new_codes):
            email = emails_[i] if emails_ else None
            self.session.add(Coupon(code=code, assigned_email=email, source="bulk", created_by_id=user.id,
                                    **({**terms, "usage_limit": terms["usage_limit"] or 1} if email else terms)))
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Some of the new codes already exist. Please try again.") from exc
        audit.record(self.session, user, "coupon.bulk", "coupon", None, f"Created {count} coupons for “{data.campaign}”", {"count": count})
        await self.session.commit()
        return BulkResultOut(created=count, campaign=data.campaign, sample=new_codes[:5])

    # ---- automatic offers ----------------------------------------------------------------
    async def _rule(self, rule_id: int) -> CartRule:
        rule = await self.session.get(CartRule, rule_id)
        if rule is None:
            raise NotFoundError("Offer not found")
        return rule

    def rule_out(self, rule: CartRule, now: datetime | None = None) -> CartRuleOut:
        out = CartRuleOut.model_validate(rule)
        out.status = window_status(rule.is_active, rule.starts_at, rule.ends_at, now or utcnow())
        return out

    async def list_rules(self) -> list[CartRuleOut]:
        rows = (await self.session.execute(select(CartRule).order_by(CartRule.is_active.desc(), CartRule.id.desc()))).scalars().all()
        now = utcnow()
        return [self.rule_out(r, now) for r in rows]

    async def create_rule(self, data: CartRuleIn, user: User) -> CartRuleOut:
        await self._check_refs(data.category_ids, data.product_ids)
        rule = CartRule(**data.model_dump(), created_by_id=user.id)
        self.session.add(rule)
        await self.session.flush()
        audit.record(self.session, user, "offer.create", "cart_rule", rule.id, f"Created offer “{rule.name}”")
        await self.session.commit()
        await self.session.refresh(rule)
        self._changed()
        return self.rule_out(rule)

    async def update_rule(self, rule_id: int, data: CartRuleIn, user: User) -> CartRuleOut:
        rule = await self._rule(rule_id)
        await self._check_refs(data.category_ids, data.product_ids)
        for field, value in data.model_dump().items():
            setattr(rule, field, value)
        audit.record(self.session, user, "offer.update", "cart_rule", rule.id, f"Changed offer “{rule.name}”")
        await self.session.commit()
        self._changed()
        return self.rule_out(rule)

    async def delete_rule(self, rule_id: int, user: User) -> None:
        rule = await self._rule(rule_id)
        audit.record(self.session, user, "offer.delete", "cart_rule", rule.id, f"Deleted offer “{rule.name}”")
        await self.session.delete(rule)
        await self.session.commit()
        self._changed()

