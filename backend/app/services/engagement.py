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
from app.domain import emailtext, stock_requests
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

    parent = aliased(Product)
    has_children = exists().where(child.parent_id == Product.id).correlate(Product)
    parent_off = exists().where(parent.id == Product.parent_id, parent.stock_status == StockStatus.OUT_OF_STOCK).correlate(Product)
    child_ok = exists().where(child.parent_id == Product.id, child.status == ContentStatus.PUBLISHED, buyable(child)).correlate(Product)
    return and_(Product.status == ContentStatus.PUBLISHED, buyable(Product), or_(not_(has_children), child_ok), not_(parent_off))


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


def _buyable(p: Product) -> bool:
    return p.status == ContentStatus.PUBLISHED and (
        (p.stock_status == StockStatus.IN_STOCK and (p.stock_quantity is None or p.stock_quantity > 0))
        or p.stock_status in (StockStatus.BACKORDER, StockStatus.PREORDER)
    )


def request_status(alert: StockAlert) -> str:
    return "notified" if alert.notified_at else "closed" if alert.closed_at else "waiting"


class StockAlertService:
    """Stock requests from signed-in customers: "email me when it's back" for a combination the shop sells, or a
    request for one it doesn't (staff answer those). See app/domain/stock_requests.py."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _product_and_variants(self, product_id: int) -> tuple[Product, list[Product]]:
        product = await self.session.get(Product, product_id)
        if product is None or product.status != ContentStatus.PUBLISHED:
            raise NotFoundError("Product not found")
        if product.parent_id:  # asked from a variant: work with its product
            product = await self.session.get(Product, product.parent_id)
            if product is None or product.status != ContentStatus.PUBLISHED:
                raise NotFoundError("Product not found")
        variants = (await self.session.execute(
            select(Product).where(Product.parent_id == product.id, Product.status == ContentStatus.PUBLISHED).order_by(Product.id)
        )).scalars().all()
        return product, list(variants)

    async def create(self, product_id: int, options: dict[str, str], note: str | None, locale: str, user: User) -> dict[str, Any]:
        product, variants = await self._product_and_variants(product_id)
        groups = stock_requests.option_groups(product.attributes or {}, [v.attributes or {} for v in variants])
        try:
            chosen = stock_requests.clean_options(groups, options or {})
        except ValueError as exc:
            raise ValidationFailedError(str(exc)) from exc
        switched_off = product.stock_status == StockStatus.OUT_OF_STOCK  # the product's own switch covers its variants
        target = stock_requests.resolve(
            product.id, _buyable(product), [(v.id, v.attributes or {}, _buyable(v) and not switched_off) for v in variants], chosen,
        )
        if target.available:
            raise ConflictError("Good news: this one is available now. Add it to your cart instead.")
        note = (note or "").strip()[: stock_requests.MAX_NOTE] or None
        result = await self.session.execute(
            pg_insert(StockAlert).values(
                product_id=target.product_id, email=user.email.strip().lower(), user_id=user.id, locale=locale,
                options=chosen, note=note, kind=target.kind,
            ).on_conflict_do_nothing().returning(StockAlert.id)
        )
        created = result.scalar_one_or_none() is not None
        await self.session.commit()
        return {"kind": target.kind, "options": chosen, "already": not created}

    async def mine(self, user: User) -> list[dict[str, Any]]:
        rows = (await self.session.execute(
            select(StockAlert, Product).join(Product, Product.id == StockAlert.product_id)
            .where(or_(StockAlert.user_id == user.id, func.lower(StockAlert.email) == user.email.lower()))
            .order_by(StockAlert.created_at.desc()).limit(100)
        )).all()
        out = []
        for alert, product in rows:
            source = await self.session.get(Product, product.parent_id) if product.parent_id else product
            out.append({
                "id": alert.id, "product_id": source.id, "title": source.title, "slug": source.slug,
                "image": ((source.images or [{}])[0] or {}).get("url"), "options": alert.options or {}, "note": alert.note,
                "kind": alert.kind, "status": request_status(alert), "created_at": alert.created_at, "notified_at": alert.notified_at,
            })
        return out

    async def cancel(self, user: User, alert_id: int) -> None:
        alert = await self.session.get(StockAlert, alert_id)
        if alert is None or (alert.user_id != user.id and alert.email.lower() != user.email.lower()):
            raise NotFoundError("Request not found")
        if alert.notified_at is None and alert.closed_at is None:
            alert.closed_at = utcnow()
            await self.session.commit()

    # ---- staff ------------------------------------------------------------------------------------------

    async def admin_list(self, status: str, kind: str | None, q: str | None, page: int, page_size: int) -> dict[str, Any]:
        conds = []
        if status == "waiting":
            conds += [StockAlert.notified_at.is_(None), StockAlert.closed_at.is_(None)]
        elif status == "done":
            conds.append(or_(StockAlert.notified_at.is_not(None), StockAlert.closed_at.is_not(None)))
        if kind:
            conds.append(StockAlert.kind == kind)
        parent = aliased(Product)
        if q:
            like = f"%{escape_like(q.strip())}%"
            conds.append(or_(StockAlert.email.ilike(like), Product.title.ilike(like), parent.title.ilike(like), Product.sku.ilike(like)))
        base = select(StockAlert, Product, parent).join(Product, Product.id == StockAlert.product_id).outerjoin(parent, parent.id == Product.parent_id).where(*conds)
        total = (await self.session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        rows = (await self.session.execute(base.order_by(StockAlert.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()
        waiting = and_(StockAlert.notified_at.is_(None), StockAlert.closed_at.is_(None))
        counts = dict((await self.session.execute(select(StockAlert.kind, func.count()).where(waiting).group_by(StockAlert.kind))).all())
        items = []
        for alert, product, root in rows:
            source = root or product
            items.append({
                "id": alert.id, "product_id": source.id, "title": source.title, "slug": source.slug, "sku": product.sku,
                "image": ((source.images or [{}])[0] or {}).get("url"),
                "variant": product.title if root else None, "in_stock": _buyable(product), "email": alert.email, "options": alert.options or {},
                "note": alert.note, "kind": alert.kind, "status": request_status(alert), "created_at": alert.created_at,
                "notified_at": alert.notified_at, "closed_at": alert.closed_at, "handled_by_email": alert.handled_by_email,
            })
        return {"items": items, "total": total, "page": page, "page_size": page_size,
                "counts": {"restock": counts.get("restock", 0), "request": counts.get("request", 0)}}

    async def admin_notify(self, alert_id: int, message: str | None, staff: User) -> None:
        """Email the customer that what they asked for can be ordered now (with an optional personal line)."""
        alert = await self.session.get(StockAlert, alert_id)
        if alert is None:
            raise NotFoundError("Request not found")
        if alert.notified_at or alert.closed_at:
            raise ConflictError("This request has already been answered")
        product = await self.session.get(Product, alert.product_id)
        source = (await self.session.get(Product, product.parent_id)) if product and product.parent_id else product
        lang = emailtext.loc(alert.locale)
        row = emails.enqueue(self.session, "request_available", alert.email, {
            "name": None, "title": _title_with_options(source, alert, lang), "link": emails.site_link(f"/product/{source.slug}", lang),
            "message": (message or "").strip()[:1000] or None,
        }, locale=lang, related_type="product", related_id=source.id)
        alert.notified_at, alert.handled_by_email = utcnow(), staff.email
        audit.record(self.session, staff, "stock_request.notify", "stock_alert", alert.id, f"Told {alert.email} that {source.title} is available")
        await self.session.commit()
        await emails.deliver(self.session, [row])

    async def admin_close(self, alert_id: int, staff: User) -> None:
        alert = await self.session.get(StockAlert, alert_id)
        if alert is None:
            raise NotFoundError("Request not found")
        if alert.notified_at is None and alert.closed_at is None:
            alert.closed_at, alert.handled_by_email = utcnow(), staff.email
            audit.record(self.session, staff, "stock_request.close", "stock_alert", alert.id, f"Closed the request from {alert.email}")
            await self.session.commit()

    async def notify_back_in_stock(self, limit: int = 100) -> int:
        """Cron: email everyone waiting for a combination that can be bought again (special requests wait for staff)."""
        rows = (await self.session.execute(
            select(StockAlert, Product)
            .join(Product, Product.id == StockAlert.product_id)
            .where(StockAlert.notified_at.is_(None), StockAlert.closed_at.is_(None), StockAlert.kind == "restock", available_clause())
            .order_by(StockAlert.id).limit(limit).with_for_update(of=StockAlert, skip_locked=True)
        )).all()
        now, queued = utcnow(), []
        for alert, product in rows:
            parent = await self.session.get(Product, product.parent_id) if product.parent_id else None
            source = parent or product
            lang = emailtext.loc(alert.locale)
            queued.append(emails.enqueue(self.session, "back_in_stock", alert.email, {
                "name": None, "title": _title_with_options(source, alert, lang), "link": emails.site_link(f"/product/{source.slug}", lang),
            }, locale=lang, related_type="product", related_id=product.id))
            alert.notified_at = now
        await self.session.commit()
        await emails.deliver(self.session, queued)
        return len(queued)


def _title_with_options(source: Product, alert: StockAlert, lang: str) -> str:
    title = (((source.translations or {}).get(lang) or {}).get("title") if lang != "en" else None) or source.title
    chosen = stock_requests.describe(alert.options or {})
    return f"{title} ({chosen})" if chosen else title


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

