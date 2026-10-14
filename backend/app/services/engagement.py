"""Reviews, wishlist and "tell me when it's back" requests, plus the cron jobs that email about them."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, exists, func, not_, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.enums import ContentStatus, OrderStatus, StockStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.domain import emailtext
from app.models.commerce import EmailOutbox
from app.models.engagement import Review, ReviewVote, StockAlert, WishlistItem
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.schemas.engagement import (
    ReviewAdminListOut,
    ReviewAdminOut,
    ReviewIn,
    ReviewModerateIn,
    ReviewOut,
    ReviewsOut,
    ReviewSubmittedOut,
    ReviewSummary,
)
from app.schemas.product import ProductCard, ProductOut
from app.services import audit, emails, localize, promo_catalog
from app.services.auth import NewsletterService
from app.services.promo_catalog import decorate
from app.services.settings import SettingsService
from app.utils.text import escape_like

log = logging.getLogger("wcw.engagement")
LINK = re.compile(r"https?://|www\.|\.com\b", re.IGNORECASE)
REVIEW_SORTS = {
    "helpful": (Review.helpful_count.desc(), Review.created_at.desc()),
    "newest": (Review.created_at.desc(),),
    "highest": (Review.rating.desc(), Review.created_at.desc()),
    "lowest": (Review.rating.asc(), Review.created_at.desc()),
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def display_name(user: User) -> str:
    """"Ana López" -> "Ana L." — reviews never show a full name or email."""
    parts = (user.full_name or "").split()
    if not parts:
        return "Customer"
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0].upper()}."


def available_clause():
    """SQL: the product can be bought right now (and, if it has variants, at least one can)."""
    child = aliased(Product)

    def buyable(p):
        return or_(
            and_(p.stock_status == StockStatus.IN_STOCK, or_(p.stock_quantity.is_(None), p.stock_quantity > 0)),
            p.stock_status.in_([StockStatus.BACKORDER, StockStatus.PREORDER]),
        )

    has_children = exists().where(child.parent_id == Product.id).correlate(Product)
    child_ok = exists().where(child.parent_id == Product.id, child.status == ContentStatus.PUBLISHED, buyable(child)).correlate(Product)
    return and_(Product.status == ContentStatus.PUBLISHED, buyable(Product), or_(not_(has_children), child_ok))


async def recompute_rating(session: AsyncSession, product_id: int) -> None:
    avg, count = (await session.execute(
        select(func.coalesce(func.avg(Review.rating), 0), func.count()).where(Review.product_id == product_id, Review.status == "approved")
    )).one()
    await session.execute(
        text("UPDATE products SET rating_avg = :avg, rating_count = :n WHERE id = :id"),
        {"avg": round(float(avg), 2), "n": count, "id": product_id},
    )


class ReviewService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _root(self, slug: str) -> Product:
        product = (await self.session.execute(select(Product).where(Product.slug == slug))).scalar_one_or_none()
        if product is None or product.status != ContentStatus.PUBLISHED:
            raise NotFoundError("Product not found")
        if product.parent_id:
            parent = await self.session.get(Product, product.parent_id)
            if parent is None or parent.status != ContentStatus.PUBLISHED:
                raise NotFoundError("Product not found")
            return parent
        return product

    async def _bought(self, user: User, product_id: int) -> int | None:
        """The id of a paid, still-valid order of this shopper that includes the product (or one of its variants)."""
        variant = aliased(Product)
        return (await self.session.execute(
            select(Order.id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .join(variant, variant.id == OrderItem.product_id)
            .where(Order.user_id == user.id, Order.paid_at.is_not(None), Order.status.notin_([OrderStatus.CANCELLED, OrderStatus.REFUNDED]),
                   or_(variant.id == product_id, variant.parent_id == product_id))
            .order_by(Order.id.desc()).limit(1)
        )).scalar_one_or_none()

    async def list(self, slug: str, viewer: User | None, sort: str, page: int, page_size: int) -> ReviewsOut:
        product = await self._root(slug)
        where = and_(Review.product_id == product.id, Review.status == "approved")
        rows = (await self.session.execute(
            select(Review.rating, func.count()).where(where).group_by(Review.rating)
        )).all()
        distribution = {stars: 0 for stars in range(1, 6)}
        distribution.update({int(r): n for r, n in rows})
        count = sum(distribution.values())
        average = sum(stars * n for stars, n in distribution.items()) / count if count else 0
        items = (await self.session.execute(
            select(Review).where(where).order_by(*REVIEW_SORTS.get(sort, REVIEW_SORTS["helpful"])).offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        voted: set[int] = set()
        if viewer and items:
            voted = set((await self.session.execute(
                select(ReviewVote.review_id).where(ReviewVote.user_id == viewer.id, ReviewVote.review_id.in_([r.id for r in items]))
            )).scalars().all())
        outs = []
        for r in items:
            o = ReviewOut.model_validate(r)
            o.helpful_by_me = r.id in voted
            outs.append(o)
        can_review = purchased = False
        if viewer:
            mine = (await self.session.execute(select(Review.id).where(Review.product_id == product.id, Review.user_id == viewer.id))).first()
            can_review = mine is None
            purchased = await self._bought(viewer, product.id) is not None
        return ReviewsOut(
            summary=ReviewSummary(average=round(average, 2), count=count, distribution=distribution),
            items=outs, total=count, page=page, page_size=page_size, can_review=can_review, purchased=purchased,
        )

    async def submit(self, slug: str, user: User, data: ReviewIn) -> ReviewSubmittedOut:
        product = await self._root(slug)
        existing = (await self.session.execute(select(Review.id).where(Review.product_id == product.id, Review.user_id == user.id))).first()
        if existing is not None:
            raise ConflictError("You've already reviewed this product. Thank you!")
        order_id = await self._bought(user, product.id)
        settings = await SettingsService(self.session).load()
        has_link = bool(LINK.search(data.body) or (data.title and LINK.search(data.title)))
        approved = bool(order_id) and settings.reviews.auto_approve_verified and not has_link
        review = Review(
            product_id=product.id, user_id=user.id, order_id=order_id, author_name=display_name(user), rating=data.rating, title=data.title,
            body=data.body, locale=data.locale, verified=order_id is not None, status="approved" if approved else "pending",
        )
        self.session.add(review)
        try:
            await self.session.flush()
        except IntegrityError as exc:  # unique (product, user) when two requests race
            await self.session.rollback()
            raise ConflictError("You've already reviewed this product. Thank you!") from exc
        if approved:
            await recompute_rating(self.session, product.id)
        await self.session.commit()
        return ReviewSubmittedOut(status="approved" if approved else "pending", review=ReviewOut.model_validate(review))

    async def vote(self, review_id: int, user: User) -> ReviewOut:
        review = await self.session.get(Review, review_id)
        if review is None or review.status != "approved":
            raise NotFoundError("Review not found")
        if review.user_id == user.id:
            raise ValidationFailedError("You can't mark your own review as helpful.")
        existing = await self.session.get(ReviewVote, (review_id, user.id))
        if existing is None:
            self.session.add(ReviewVote(review_id=review_id, user_id=user.id))
            review.helpful_count += 1
        else:
            await self.session.delete(existing)
            review.helpful_count = max(0, review.helpful_count - 1)
        await self.session.commit()
        out = ReviewOut.model_validate(review)
        out.helpful_by_me = existing is None
        return out

    # ---- staff ---------------------------------------------------------------------------
    async def admin_list(self, status: str | None, q: str | None, page: int, page_size: int) -> ReviewAdminListOut:
        conds = []
        if status:
            conds.append(Review.status == status)
        if q:
            like = f"%{escape_like(q.strip())}%"
            conds.append(or_(Review.body.ilike(like), Review.title.ilike(like), Review.author_name.ilike(like), Product.title.ilike(like)))
        base = select(Review, Product.title, Product.slug).join(Product, Product.id == Review.product_id).where(*conds)
        total = (await self.session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        rows = (await self.session.execute(base.order_by(Review.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()
        counts = dict((await self.session.execute(select(Review.status, func.count()).group_by(Review.status))).all())
        items = []
        for review, title, slug in rows:
            o = ReviewAdminOut.model_validate(review)
            o.product_title, o.product_slug = title, slug
            items.append(o)
        return ReviewAdminListOut(items=items, total=total, page=page, page_size=page_size,
                                  counts={k: counts.get(k, 0) for k in ("pending", "approved", "rejected")})

    async def moderate(self, review_id: int, data: ReviewModerateIn, user: User) -> ReviewAdminOut:
        review = await self.session.get(Review, review_id)
        if review is None:
            raise NotFoundError("Review not found")
        review.status = data.status
        if data.reply is not None:
            review.reply, review.replied_at = data.reply, utcnow()
        await self.session.flush()
        await recompute_rating(self.session, review.product_id)
        audit.record(self.session, user, f"review.{data.status}", "review", review.id, f"Marked a review {data.status}")
        await self.session.commit()
        product = await self.session.get(Product, review.product_id)
        out = ReviewAdminOut.model_validate(review)
        out.product_title, out.product_slug = (product.title, product.slug) if product else ("", "")
        return out

    async def delete(self, review_id: int, user: User) -> None:
        review = await self.session.get(Review, review_id)
        if review is None:
            raise NotFoundError("Review not found")
        product_id = review.product_id
        await self.session.delete(review)
        await self.session.flush()
        await recompute_rating(self.session, product_id)
        audit.record(self.session, user, "review.delete", "review", review_id, "Deleted a review")
        await self.session.commit()


class WishlistService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ids(self, user: User) -> list[int]:
        return list((await self.session.execute(
            select(WishlistItem.product_id).where(WishlistItem.user_id == user.id).order_by(WishlistItem.created_at.desc())
        )).scalars().all())

    async def cards(self, user: User, lang: str | None) -> list[ProductCard]:
        ids = await self.ids(user)
        if not ids:
            return []
        rows = (await self.session.execute(
            select(Product).where(Product.id.in_(ids), Product.status == ContentStatus.PUBLISHED, Product.parent_id.is_(None))
        )).scalars().all()
        by_id = {p.id: p for p in rows}
        outs = [ProductOut.model_validate(by_id[i]) for i in ids if i in by_id]
        promo = await promo_catalog.load(self.session)
        decorate(outs, promo, lang, (await SettingsService(self.session).load()).general.low_stock_threshold)
        cards = []
        for o in outs:
            localize.product(o, lang)
            cards.append(ProductCard(id=o.id, slug=o.slug, title=o.title, base_price=o.base_price, sale_price=o.sale_price,
                                     compare_at_price=o.compare_at_price, image=o.images[0].url if o.images else None))
        return cards

    async def add(self, user: User, product_id: int) -> None:
        product = await self.session.get(Product, product_id)
        if product is None or product.status != ContentStatus.PUBLISHED:
            raise NotFoundError("Product not found")
        root_id = product.parent_id or product.id
        await self.session.execute(pg_insert(WishlistItem).values(user_id=user.id, product_id=root_id).on_conflict_do_nothing())
        await self.session.commit()

    async def remove(self, user: User, product_id: int) -> None:
        product = await self.session.get(Product, product_id)
        root_id = (product.parent_id or product.id) if product else product_id
        item = await self.session.get(WishlistItem, (user.id, root_id))
        if item is not None:
            await self.session.delete(item)
            await self.session.commit()


class StockAlertService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def request(self, product_id: int, email: str, locale: str, user: User | None) -> None:
        product = await self.session.get(Product, product_id)
        if product is None or product.status != ContentStatus.PUBLISHED:
            raise NotFoundError("Product not found")
        await self.session.execute(
            pg_insert(StockAlert).values(product_id=product.id, email=email.strip().lower(), user_id=user.id if user else None, locale=locale)
            .on_conflict_do_nothing()
        )
        await self.session.commit()

    async def notify_back_in_stock(self, limit: int = 100) -> int:
        """Cron: email everyone waiting for a product that can be bought again."""
        rows = (await self.session.execute(
            select(StockAlert, Product)
            .join(Product, Product.id == StockAlert.product_id)
            .where(StockAlert.notified_at.is_(None), available_clause())
            .order_by(StockAlert.id).limit(limit).with_for_update(of=StockAlert, skip_locked=True)
        )).all()
        now, queued = utcnow(), []
        for alert, product in rows:
            parent = await self.session.get(Product, product.parent_id) if product.parent_id else None
            source = parent or product
            lang = emailtext.loc(alert.locale)
            title = ((source.translations or {}).get(lang) or {}).get("title") if lang != "en" else None
            queued.append(emails.enqueue(self.session, "back_in_stock", alert.email, {
                "name": None, "title": title or source.title, "link": emails.site_link(f"/product/{source.slug}", lang),
            }, locale=lang, related_type="product", related_id=product.id))
            alert.notified_at = now
        await self.session.commit()
        await emails.deliver(self.session, queued)
        return len(queued)


class ReviewRequestJob:
    """Cron: ask for a review some days after an order arrives (once per order, never to anyone who unsubscribed)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(self, limit: int = 50) -> dict[str, int]:
        settings = await SettingsService(self.session).load()
        result = {"sent": 0, "skipped": 0}
        if not settings.reviews.request_enabled:
            return result
        cutoff = utcnow() - timedelta(days=settings.reviews.request_after_days)
        arrived = func.coalesce(Order.delivered_at, Order.shipped_at)
        orders = (await self.session.execute(
            select(Order).where(
                Order.review_requested_at.is_(None), Order.paid_at.is_not(None), Order.status.in_([OrderStatus.SHIPPED, OrderStatus.DELIVERED]),
                arrived <= cutoff, arrived > utcnow() - timedelta(days=90),
            ).order_by(Order.id).limit(limit).with_for_update(skip_locked=True)
        )).scalars().all()
        queued: list[EmailOutbox] = []
        news = NewsletterService(self.session)
        for order in orders:
            order.review_requested_at = utcnow()
            contact = await news.contact(order.email, order.locale, "order")
            if contact.unsubscribed_at is not None:
                result["skipped"] += 1
                continue
            lang = emailtext.loc(order.locale)
            items, seen = [], set()
            for item in order.items:
                if item.slug and item.slug not in seen:
                    seen.add(item.slug)
                    items.append({"title": item.title.split(" — ")[0], "url": emails.site_link(f"/product/{item.slug}#reviews", lang)})
            if not items:
                continue
            queued.append(emails.enqueue(self.session, "review_request", order.email, {
                "name": order.customer_name, "items": items[:3], "unsubscribe_url": emails.unsubscribe_url(contact.unsubscribe_token, lang),
            }, locale=lang, related_type="order", related_id=order.id))
            result["sent"] += 1
        await self.session.commit()
        await emails.deliver(self.session, queued)
        return result

