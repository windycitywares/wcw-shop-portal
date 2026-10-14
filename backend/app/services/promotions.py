"""Sales and coupons: creating, editing, generating codes in bulk and sending personal ones."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.models.category import Category
from app.models.commerce import Coupon, Sale
from app.models.product import Product
from app.models.user import User
from app.pricing.codes import random_code
from app.repositories.commerce import CouponRepository, SaleRepository
from app.repositories.order import OrderRepository
from app.schemas.commerce import (
    CampaignOut,
    CouponGenerate,
    CouponIn,
    CouponOut,
    CouponRules,
    CouponSend,
    CouponUpdate,
    GenerateResult,
    SaleIn,
    SaleOut,
)
from app.schemas.common import Page
from app.services import order_emails
from app.services.settings import SettingsService

log = logging.getLogger("wcw.promotions")


def coupon_status(c: Coupon, now: datetime) -> str:
    if not c.is_active:
        return "paused"
    if c.expires_at is not None and c.expires_at <= now:
        return "expired"
    if c.starts_at is not None and c.starts_at > now:
        return "scheduled"
    if c.usage_limit is not None and c.used_count >= c.usage_limit:
        return "used_up"
    return "active"


def sale_status(s: Sale, now: datetime) -> str:
    if not s.is_active:
        return "paused"
    if s.ends_at is not None and s.ends_at <= now:
        return "ended"
    if s.starts_at is not None and s.starts_at > now:
        return "scheduled"
    return "live"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PromotionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.coupons = CouponRepository(session)
        self.sales = SaleRepository(session)

    # -- shared --------------------------------------------------------------------
    async def _targeting(self, scope: str, category_id: int | None, product_ids: list[int]) -> tuple[int | None, list[int]]:
        """Check what a sale or code points at, and drop the fields its scope doesn't use."""
        if scope == "category":
            if not await self.session.get(Category, category_id):
                raise NotFoundError("Category not found")
            return category_id, []
        if scope == "products":
            ids = sorted(set(product_ids))
            found = set((await self.session.execute(select(Product.id).where(Product.id.in_(ids)))).scalars().all())
            if found != set(ids):
                raise NotFoundError("One of the chosen products no longer exists")
            return None, ids
        return None, []

    def _coupon_out(self, c: Coupon, given=0, orders=0) -> CouponOut:
        out = CouponOut.model_validate(c)
        out.status = coupon_status(c, _now())
        out.discount_given, out.orders = given, orders
        return out

    # -- coupons ----------------------------------------------------------------------
    async def list_coupons(self, *, q, status, campaign, source, page: int, page_size: int) -> Page[CouponOut]:
        rows, total = await self.coupons.search(q=q, status=status, campaign=campaign, source=source, now=_now(),
                                                page=page, page_size=page_size)
        return Page[CouponOut](items=[self._coupon_out(c, g, n) for c, g, n in rows], total=total, page=page, page_size=page_size)

    async def get_coupon(self, coupon_id: int) -> CouponOut:
        c = await self.coupons.get(coupon_id)
        if c is None:
            raise NotFoundError("Coupon not found")
        given, orders = await self.coupons.usage_totals(c.id)
        return self._coupon_out(c, given, orders)

    def _rule_values(self, data: CouponRules) -> dict:
        return {
            "description": data.description, "kind": data.kind, "value": data.value, "min_subtotal": data.min_subtotal,
            "max_discount": data.max_discount, "scope": data.scope, "exclude_sale_items": data.exclude_sale_items,
            "first_order_only": data.first_order_only, "per_customer_limit": data.per_customer_limit,
            "starts_at": data.starts_at, "expires_at": data.expires_at,
        }

    async def create_coupon(self, data: CouponIn, actor: User) -> CouponOut:
        if await self.coupons.get_by_code(data.code):
            raise ConflictError("A code with that name already exists.")
        category_id, product_ids = await self._targeting(data.scope, data.category_id, data.product_ids)
        coupon = Coupon(code=data.code, usage_limit=data.usage_limit, is_active=data.is_active, category_id=category_id,
                        product_ids=product_ids, source="manual", created_by_id=actor.id, **self._rule_values(data))
        self.coupons.add(coupon)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("A code with that name already exists.") from exc
        return self._coupon_out(coupon)

    async def update_coupon(self, coupon_id: int, data: CouponUpdate) -> CouponOut:
        coupon = await self.coupons.get(coupon_id)
        if coupon is None:
            raise NotFoundError("Coupon not found")
        if data.usage_limit is not None and data.usage_limit < coupon.used_count:
            raise ValidationFailedError(f"This code has already been used {coupon.used_count} times, so the limit can't be lower than that.")
        coupon.category_id, coupon.product_ids = await self._targeting(data.scope, data.category_id, data.product_ids)
        for field, value in self._rule_values(data).items():
            setattr(coupon, field, value)
        coupon.usage_limit, coupon.is_active = data.usage_limit, data.is_active
        await self.session.commit()
        given, orders = await self.coupons.usage_totals(coupon.id)
        return self._coupon_out(coupon, given, orders)

    async def delete_coupon(self, coupon_id: int) -> None:
        coupon = await self.coupons.get(coupon_id)
        if coupon is None:
            raise NotFoundError("Coupon not found")
        if coupon.used_count > 0:
            raise ConflictError("This code has been used, so it's kept for your records. Pause it instead.")
        await self.coupons.delete(coupon)
        await self.session.commit()

    async def _fresh_codes(self, count: int, prefix: str, length: int = 8) -> list[str]:
        codes: set[str] = set()
        for _ in range(6):
            while len(codes) < count:
                codes.add(random_code(prefix, length))
            taken = await self.coupons.existing_codes(sorted(codes))
            codes -= taken
            if len(codes) == count:
                return sorted(codes)
        raise ConflictError("Couldn't make enough unique codes. Try a different prefix.")

    async def generate(self, data: CouponGenerate, actor: User) -> GenerateResult:
        if await self.coupons.codes_in_campaign(data.campaign, limit=1):
            raise ConflictError("A batch with that name already exists. Choose another name.")
        category_id, product_ids = await self._targeting(data.scope, data.category_id, data.product_ids)
        codes = await self._fresh_codes(data.count, data.prefix)
        rules = self._rule_values(data)
        for code in codes:
            self.coupons.add(Coupon(code=code, usage_limit=data.usage_limit, category_id=category_id, product_ids=product_ids,
                                    campaign=data.campaign, source="generated", created_by_id=actor.id, **rules))
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Some of those codes were taken a moment ago. Please try again.") from exc
        return GenerateResult(campaign=data.campaign, count=len(codes), codes=codes)

    async def campaigns(self) -> list[CampaignOut]:
        return [CampaignOut(campaign=c, codes=n, used=u, discount_given=g, created_at=at)
                for c, n, u, g, at in await self.coupons.campaigns()]

    async def campaign_codes(self, campaign: str) -> list[Coupon]:
        codes = await self.coupons.codes_in_campaign(campaign)
        if not codes:
            raise NotFoundError("Batch not found")
        return codes

    async def send_personal(self, data: CouponSend, actor: User) -> CouponOut:
        category_id, product_ids = await self._targeting(data.scope, data.category_id, data.product_ids)
        email = str(data.email).strip().lower()
        (code,) = await self._fresh_codes(1, "FOR")
        rules = self._rule_values(data)
        if data.valid_days and not data.expires_at:
            rules["expires_at"] = _now() + timedelta(days=data.valid_days)
        rules["description"] = rules["description"] or f"Personal code for {email}"
        coupon = Coupon(code=code, usage_limit=1, category_id=category_id, product_ids=product_ids, email=email,
                        issued_to=email, source="personal", created_by_id=actor.id, **rules)
        self.coupons.add(coupon)
        await self.session.commit()
        await order_emails.coupon_email(
            to=email, code=code, kind=coupon.kind, value=coupon.value, locale=data.locale, welcome=False,
            expires_at=coupon.expires_at, min_subtotal=coupon.min_subtotal, message=data.message,
        )
        return self._coupon_out(coupon)

    async def issue_welcome(self, email: str, locale: str = "en") -> bool:
        """Email a one-time welcome code to a new subscriber. At most one per address, and never to existing customers."""
        cfg = await SettingsService(self.session).load()
        email = email.strip().lower()
        if not cfg.welcome_enabled or await self.coupons.welcome_for(email):
            return False
        if await OrderRepository(self.session).prior_orders(None, email) > 0:
            return False
        (code,) = await self._fresh_codes(1, "WELCOME")
        coupon = Coupon(
            code=code, description=f"Welcome code for {email}", kind=cfg.welcome_kind, value=cfg.welcome_value,
            min_subtotal=cfg.welcome_min_subtotal or None, usage_limit=1, first_order_only=True,
            expires_at=_now() + timedelta(days=cfg.welcome_valid_days), issued_to=email, source="welcome", campaign="welcome",
        )
        self.coupons.add(coupon)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            return False
        await order_emails.coupon_email(
            to=email, code=code, kind=coupon.kind, value=coupon.value, locale=locale, welcome=True,
            expires_at=coupon.expires_at, min_subtotal=coupon.min_subtotal,
        )
        return True

    # -- sales -------------------------------------------------------------------------
    async def _sale_outs(self, sales: list[Sale]) -> list[SaleOut]:
        now = _now()
        ids = {i for s in sales for i in s.product_ids}
        titles: dict[int, str] = {}
        if ids:
            titles = dict((await self.session.execute(select(Product.id, Product.title).where(Product.id.in_(ids)))).all())
        cat_ids = {s.category_id for s in sales if s.category_id}
        names: dict[int, str] = {}
        if cat_ids:
            names = dict((await self.session.execute(select(Category.id, Category.name).where(Category.id.in_(cat_ids)))).all())
        outs = []
        for s in sales:
            out = SaleOut.model_validate(s)
            out.status = sale_status(s, now)
            out.category_name = names.get(s.category_id) if s.category_id else None
            out.products = [titles[i] for i in s.product_ids if i in titles]
            outs.append(out)
        return outs

    async def list_sales(self) -> list[SaleOut]:
        return await self._sale_outs(await self.sales.list_all())

    async def create_sale(self, data: SaleIn, actor: User) -> SaleOut:
        category_id, product_ids = await self._targeting(data.scope, data.category_id, data.product_ids)
        sale = Sale(name=data.name, label=data.label or None, kind=data.kind, value=data.value, scope=data.scope,
                    category_id=category_id, product_ids=product_ids, starts_at=data.starts_at, ends_at=data.ends_at,
                    is_active=data.is_active, created_by_id=actor.id)
        self.sales.add(sale)
        await self.session.commit()
        return (await self._sale_outs([sale]))[0]

    async def update_sale(self, sale_id: int, data: SaleIn) -> SaleOut:
        sale = await self.sales.get(sale_id)
        if sale is None:
            raise NotFoundError("Sale not found")
        sale.category_id, sale.product_ids = await self._targeting(data.scope, data.category_id, data.product_ids)
        sale.name, sale.label, sale.kind, sale.value = data.name, data.label or None, data.kind, data.value
        sale.scope, sale.starts_at, sale.ends_at, sale.is_active = data.scope, data.starts_at, data.ends_at, data.is_active
        await self.session.commit()
        return (await self._sale_outs([sale]))[0]

    async def delete_sale(self, sale_id: int) -> None:
        sale = await self.sales.get(sale_id)
        if sale is None:
            raise NotFoundError("Sale not found")
        await self.sales.delete(sale)
        await self.session.commit()
