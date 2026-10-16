"""Record changes the CRM must hear about, in the same transaction as the change (transactional outbox).

A Session `after_flush` hook looks at the orders, customer accounts and newsletter rows that were just written
and adds one `crm_outbox` row per changed record ("order 987 changed"). Every code path that writes through the
ORM is covered (checkout, Stripe webhooks, admin edits, refunds, the expiry job …) without each one having to
remember. `app/services/crm_sync.py` sends them later with the record's state at that moment.

Nothing is recorded while the CRM isn't configured, or while the shop works on its Test copy of the data.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

INFO_KEY = "crm_outbox_seen"
# Fields whose change the CRM cares about (anything else, e.g. a tracking token, is not worth an event).
ORDER_FIELDS = ("status", "payment_status", "grand_total", "refunded_total", "email", "user_id", "customer_name",
                "phone", "placed_at", "billing_address", "marketing_opt_in")
USER_FIELDS = ("email", "full_name", "role")
SUBSCRIBER_FIELDS = ("unsubscribed_at", "source", "email")


def _changed(obj: Any, fields: tuple[str, ...]) -> bool:
    attrs = inspect(obj).attrs
    return any(attrs[f].history.has_changes() for f in fields if f in attrs)


def _kind_for(obj: Any, is_new: bool) -> str | None:
    from app.core.enums import UserRole
    from app.models.order import Order
    from app.models.user import NewsletterSubscriber, User

    if isinstance(obj, Order):
        return "order" if is_new or _changed(obj, ORDER_FIELDS) else None
    if isinstance(obj, User):
        role = inspect(obj).dict.get("role")
        if role != UserRole.CUSTOMER and not (not is_new and _changed(obj, ("role",))):
            return None
        return "customer" if is_new or _changed(obj, USER_FIELDS) else None
    if isinstance(obj, NewsletterSubscriber):
        return "newsletter" if is_new or _changed(obj, SUBSCRIBER_FIELDS) else None
    return None


def _after_flush(session: Session, flush_context: Any) -> None:  # noqa: ARG001
    from app.core import appmode
    from app.core.config import get_settings

    if not get_settings().crm_sync_enabled or appmode.is_test():
        return
    from app.models.crm import CrmOutbox

    seen: set[tuple[str, int]] = session.info.setdefault(INFO_KEY, set())
    for obj, is_new in [(o, True) for o in session.new] + [(o, False) for o in session.dirty]:
        kind = _kind_for(obj, is_new)
        ref_id = inspect(obj).dict.get("id") if kind else None
        if kind and ref_id is not None and (kind, ref_id) not in seen:
            seen.add((kind, ref_id))
            session.add(CrmOutbox(kind=kind, ref_id=ref_id))  # written by the commit's next flush


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
