"""Write a `live_events` row, in the same transaction, whenever something staff may want to hear about at once happens.

A Session `after_flush` hook (the same idea as app/core/crm_events.py) looks at the orders, accounts, newsletter
rows, contact messages, reviews, stock requests and products just written, so every code path (checkout, Stripe,
admin edits, imports, jobs) is covered without remembering to. The words come from app/domain/live.py; the admin
reads the rows as "everything after id N" (GET /admin/live/events) and turns them into toasts, the bell and
"updates available" bars. Changes made with raw SQL are not seen; backups add their own row (services/backups.py).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.permissions import Permission
from app.domain.live import Said, order_change, products_changed

INFO_KEY = "live_events_seen"
ORDER_FIELDS = ("placed_at", "payment_status", "status")
# What an editor changes; stock counts, sales and ratings move on their own and are not news.
PRODUCT_FIELDS = ("title", "slug", "description", "base_price", "compare_at_price", "status", "stock_status",
                  "category_id", "attributes", "sku")


def _value(obj: Any, field: str, before: bool) -> Any:
    hist = inspect(obj).attrs[field].history
    if before:
        if hist.deleted:
            return hist.deleted[0]
        return hist.unchanged[0] if hist.unchanged else None
    return getattr(obj, field, None)


def _changed(obj: Any, fields: tuple[str, ...]) -> bool:
    attrs = inspect(obj).attrs
    return any(attrs[f].history.has_changes() for f in fields if f in attrs)


def _said(obj: Any, is_new: bool) -> tuple[Said, str, str | None] | None:
    """(what to say, permission, link) for one written object, or None."""
    from app.core.enums import UserRole
    from app.models.account import ContactMessage
    from app.models.engagement import Review, StockAlert
    from app.models.order import Order
    from app.models.user import NewsletterSubscriber, User

    oid = inspect(obj).dict.get("id")
    if isinstance(obj, Order):
        if not is_new and not _changed(obj, ORDER_FIELDS):
            return None
        before = {f: (None if is_new else _value(obj, f, True)) for f in ORDER_FIELDS}
        after = {f: getattr(obj, f, None) for f in ORDER_FIELDS}
        said = order_change(obj.number, obj.customer_name or obj.email, obj.grand_total, before, after, is_new)
        return (said, Permission.ORDERS_MANAGE.value, f"/admin/orders/{oid}") if said else None
    if isinstance(obj, User):
        if is_new and inspect(obj).dict.get("role") == UserRole.CUSTOMER:
            who = " · ".join(x for x in (obj.full_name, obj.email) if x)
            return Said("customer.new", "New customer account", who), Permission.CUSTOMERS_VIEW.value, f"/admin/customers?q={obj.email}"
        return None
    if isinstance(obj, NewsletterSubscriber):
        if is_new:
            return Said("subscriber.new", "New newsletter subscriber", obj.email), Permission.CUSTOMERS_VIEW.value, f"/admin/subscribers?q={obj.email}"
        if _changed(obj, ("unsubscribed_at",)) and obj.unsubscribed_at is not None:
            return Said("subscriber.left", "Unsubscribed from the newsletter", obj.email), Permission.CUSTOMERS_VIEW.value, f"/admin/subscribers?q={obj.email}"
        return None
    if isinstance(obj, ContactMessage):
        if is_new and obj.status != "spam":
            return Said("message.new", f"Message: {obj.subject}", f"From {obj.name}"), Permission.MESSAGES_MANAGE.value, f"/admin/messages?id={oid}"
        return None
    if isinstance(obj, Review):
        if is_new:
            return (Said("review.new", f"New {obj.rating}★ review", f"By {obj.author_name}"), Permission.REVIEWS_MODERATE.value,
                    "/admin/reviews?status=pending")
        return None
    if isinstance(obj, StockAlert):
        if is_new:
            special = obj.kind == "request"
            return (Said("stock_request.new", "Special request" if special else "Back-in-stock request", obj.email),
                    Permission.CUSTOMERS_VIEW.value, "/admin/stock-requests" if special else "/admin/stock-requests?view=restock")
        return None
    return None


def _after_flush(session: Session, flush_context: Any) -> None:  # noqa: ARG001
    from app.models.live import LiveEvent
    from app.models.product import Product

    seen: set[tuple[str, Any]] = session.info.setdefault(INFO_KEY, set())
    products: list[tuple[int | None, str, bool]] = []
    for obj, is_new in [(o, True) for o in session.new] + [(o, False) for o in session.dirty]:
        if isinstance(obj, LiveEvent):
            continue
        if isinstance(obj, Product):
            if is_new or _changed(obj, PRODUCT_FIELDS):
                products.append((inspect(obj).dict.get("id"), obj.title, is_new))
            continue
        found = _said(obj, is_new)
        if not found:
            continue
        said, permission, href = found
        key = (said.kind, inspect(obj).dict.get("id"))
        if key in seen:
            continue
        seen.add(key)
        session.add(LiveEvent(kind=said.kind, ref_id=key[1], title=said.title[:200], detail=(said.detail or None) and said.detail[:300],
                              href=href, permission=permission))
    fresh = [p for p in products if ("product.changed", p[0]) not in seen]
    if fresh:
        seen.update(("product.changed", p[0]) for p in fresh)
        lines = products_changed([(title, new) for _, title, new in fresh])
        single = len(lines) == len(fresh)
        for i, said in enumerate(lines):
            pid = fresh[i][0] if single else None
            session.add(LiveEvent(kind=said.kind, ref_id=pid, title=said.title[:200], detail=None,
                                  href=f"/admin/products/{pid}" if pid else "/admin/products",
                                  permission=Permission.CATALOG_VIEW_UNPUBLISHED.value))


def _forget(session: Session, *_: Any) -> None:
    session.info.pop(INFO_KEY, None)


_installed = False


def install() -> None:
    global _installed
    if _installed:
        return
    event.listen(Session, "after_flush", _after_flush)
    event.listen(Session, "after_commit", _forget)
    event.listen(Session, "after_rollback", _forget)
    _installed = True
