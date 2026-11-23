"""Background work, run from cron every few minutes (deploy/auto-deploy.sh calls it after each check for updates).

    python -m app.scripts.run_jobs                  # everything that is due
    python -m app.scripts.run_jobs --only outbox    # just some jobs (comma-separated names)
    python -m app.scripts.run_jobs --force-digest   # send the weekly email now

Safe to run by hand and safe to overlap: a database lock makes a second run exit straight away, and each job
remembers (or checks) what it has already done.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("wcw.jobs")
LOCK_KEY = 7_204_519_001  # any number unique to this app
RETENTION_HOUR = 3  # store time; the purge runs once a day, after this hour

Job = Callable[[AsyncSession, datetime, argparse.Namespace], Awaitable[Any]]


async def _outbox(session: AsyncSession, now: datetime, args: argparse.Namespace) -> Any:
    from app.services import emails

    return await emails.process_outbox(session)


async def _crm_sync(session: AsyncSession, now: datetime, args: argparse.Namespace) -> Any:
    from app.services.crm_sync import CrmSync

    return await CrmSync(session).deliver_due()


async def _cart_reminders(session: AsyncSession, now: datetime, args: argparse.Namespace) -> Any:
    from app.services.carts import CartRecoveryJob

    return await CartRecoveryJob(session).run()


async def _review_requests(session: AsyncSession, now: datetime, args: argparse.Namespace) -> Any:
    from app.services.engagement import ReviewRequestJob

    return await ReviewRequestJob(session).run()


async def _back_in_stock(session: AsyncSession, now: datetime, args: argparse.Namespace) -> Any:
    from app.services.engagement import StockAlertService

    return {"sent": await StockAlertService(session).notify_back_in_stock()}


async def _expire_unpaid(session: AsyncSession, now: datetime, args: argparse.Namespace) -> Any:
    from app.services.orders import OrderService

    return await OrderService(session).expire_unpaid()


async def _digest(session: AsyncSession, now: datetime, args: argparse.Namespace) -> Any:
    from app.services.digest import DigestJob

    return await DigestJob(session).run(now, force=args.force_digest)


async def _retention(session: AsyncSession, now: datetime, args: argparse.Namespace) -> Any:
    from app.domain.timeutil import to_store_time
    from app.services import jobstate, retention

    local = to_store_time(now)
    if local.hour < RETENTION_HOUR:
        return {"skipped": "not due"}
    if not await jobstate.claim(session, "retention", local.date().isoformat()):
        return {"skipped": "already done today"}
    await session.commit()  # keep the claim even if a later batch fails: tomorrow's run continues the work
    return await retention.purge(session, now)


async def _backup(session: AsyncSession, now: datetime, args: argparse.Namespace) -> Any:
    from app.core.database import engine
    from app.services.backups import BackupService

    return await BackupService(engine).run_if_due(now)


JOBS: dict[str, Job] = {
    "outbox": _outbox,
    "crm_sync": _crm_sync,
    "cart_reminders": _cart_reminders,
    "review_requests": _review_requests,
    "back_in_stock": _back_in_stock,
    "expire_unpaid": _expire_unpaid,
    "digest": _digest,
    "retention": _retention,
    "backup": _backup,
}


async def run(only: set[str] | None = None, args: argparse.Namespace | None = None) -> dict[str, Any]:
    from app.core.database import SessionFactory, engine

    from app.services.settings import apply_store_timezone

    await apply_store_timezone()  # hours such as the Monday digest follow the owner's time zone
    args = args or argparse.Namespace(force_digest=False)
    now = datetime.now(timezone.utc)
    results: dict[str, Any] = {}
    async with engine.connect() as lock:
        got = (await lock.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY})).scalar()
        if not got:
            return {"skipped": "another run is in progress"}
        try:
            for name, job in JOBS.items():
                if only and name not in only:
                    continue
                async with SessionFactory() as session:
                    try:
                        results[name] = await job(session, now, args)
                    except Exception as exc:  # one broken job must not stop the others
                        await session.rollback()
                        log.exception("Job %s failed", name)
                        results[name] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        finally:
            await lock.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
    return results


def _did_something(result: Any) -> bool:
    if not isinstance(result, dict):
        return bool(result)
    if "error" in result:
        return True
    return any(v for k, v in result.items() if k not in ("skipped", "reason"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="comma-separated job names: " + ", ".join(JOBS))
    parser.add_argument("--force-digest", action="store_true", help="send the weekly email now, whatever the day")
    args = parser.parse_args(argv)
    only = {n.strip() for n in args.only.split(",") if n.strip()} if args.only else None
    unknown = (only or set()) - set(JOBS)
    if unknown:
        parser.error(f"unknown job: {', '.join(sorted(unknown))}")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    results = asyncio.run(run(only, args))
    # Say something only when work was done (or failed), so the cron log stays readable.
    busy = {k: v for k, v in results.items() if _did_something(v)}
    if busy:
        print(f"{datetime.now():%F %T} jobs: {json.dumps(busy, default=str)}")
    return 1 if any(isinstance(v, dict) and "error" in v for v in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
