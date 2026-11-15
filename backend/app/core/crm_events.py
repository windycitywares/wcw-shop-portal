"""Record changes the CRM must hear about, in the same transaction as the change (transactional outbox).

A Session `after_flush` hook looks at the orders, customer accounts, newsletter rows and contact-form messages
that were just written and adds one `crm_outbox` row per changed record ("order 987 changed"). Every code path
that writes through the ORM is covered (checkout, Stripe webhooks, admin edits, refunds, the expiry job, the
contact page …) without each one having to remember. `app/services/crm_sync.py` sends them later with the
record's state at that moment.

Nothing is recorded while the CRM isn't configured. While the shop works on its Test copy, the rows go into the
copy's own outbox and are sent as test events, which the CRM files in its Test copy (docs/CRM_SYNC.md).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

log = logging.getLogger("wcw.crm_sync")
INFO_KEY = "crm_outbox_seen"
ADDED_KEY = "crm_outbox_added"
PUSH_NOW = True  # send right after the commit instead of waiting for the next cron run (tests switch it off)
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
    from app.models.account import ContactMessage
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
    if isinstance(obj, ContactMessage):
        # Sent once, when it is written: "open", "closed" and the emailed flag are the shop's own bookkeeping
        # and the CRM has the ticket already, so a later change is not news (and never a second ticket).
        return "contact" if is_new else None
    return None


def _after_flush(session: Session, flush_context: Any) -> None:  # noqa: ARG001
    from app.core.config import get_settings

    if not get_settings().crm_sync_enabled:
        return
    from app.models.crm import CrmOutbox

    seen: set[tuple[str, int]] = session.info.setdefault(INFO_KEY, set())
    for obj, is_new in [(o, True) for o in session.new] + [(o, False) for o in session.dirty]:
        kind = _kind_for(obj, is_new)
        ref_id = inspect(obj).dict.get("id") if kind else None
        if kind and ref_id is not None and (kind, ref_id) not in seen:
            seen.add((kind, ref_id))
            session.add(CrmOutbox(kind=kind, ref_id=ref_id))  # written by the commit's next flush
            session.info[ADDED_KEY] = True


def _forget(session: Session, *_: Any) -> None:
    session.info.pop(INFO_KEY, None)
    session.info.pop(ADDED_KEY, None)


_tasks: set[asyncio.Task] = set()
_pushing = False
_again = False


async def push_now() -> None:
    """Send what was just recorded, so the CRM hears within a second or two instead of at the next cron run.

    Best effort: the `crm_sync` job still retries anything this misses. Calls that arrive while a push is running
    make it go round once more, so a burst of changes is not left waiting for the cron.
    """
    global _pushing, _again
    if _pushing:
        _again = True
        return
    _pushing = True
    try:
        while True:
            _again = False
            await asyncio.sleep(0.3)  # let the request that caused it finish and release its connection
            from app.core.database import SessionFactory
            from app.services.crm_sync import CrmSync

            async with SessionFactory() as session:
                await CrmSync(session).deliver_due()
            if not _again:
                break
    except Exception:  # noqa: BLE001 - the cron job picks the rest up
        log.debug("immediate CRM push failed", exc_info=True)
    finally:
        _pushing = False


def _after_commit(session: Session) -> None:
    added = session.info.get(ADDED_KEY)
    _forget(session)
    if not added or not PUSH_NOW:
        return
    try:
        task = asyncio.get_running_loop().create_task(push_now())
    except RuntimeError:  # no event loop here (a script): the cron job sends it
        return
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


_installed = False


def install() -> None:
    global _installed
    if _installed:
        return
    event.listen(Session, "after_flush", _after_flush)
    event.listen(Session, "after_commit", _after_commit)
    event.listen(Session, "after_rollback", _forget)
    _installed = True
