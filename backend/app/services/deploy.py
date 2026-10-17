"""Admin → Deployments: when the server updates itself, "Deploy now", and the gate the cron job asks every minute.

Always the live table (public.deploy_control), whatever Test mode is set to: there is one server and one checkout.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.core import appmode
from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError
from app.domain.deploy_policy import Decision, decide
from app.domain.timeutil import STORE_TZ_NAME
from app.models.user import User
from app.schemas.deploy import DeployConfigIn, DeployStatusOut, Version

LOG_MAX_LINES = 400
STUCK_AFTER = timedelta(minutes=30)  # a run that never reported back is treated as finished
CRON_FRESH = timedelta(minutes=3)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def git_version(repo: str) -> Version:
    try:
        out = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%h%x1f%s%x1f%cI"], capture_output=True,
                             text=True, timeout=5, check=True).stdout.strip()
        commit, subject, date = out.split("\x1f")
        return Version(commit=commit, subject=subject[:200], date=date)
    except (OSError, subprocess.SubprocessError, ValueError):
        return Version(commit=None, subject=None, date=None)


def read_build(app_dir: str) -> str | None:
    try:
        return Path(app_dir, "BUILD_SHA").read_text(encoding="utf-8", errors="replace").strip()[:12] or None
    except OSError:
        return None


def log_tail(path: str, lines: int = 200) -> str:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 200_000))
            data = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(data.splitlines()[-min(lines, LOG_MAX_LINES):])


class DeployService:
    def __init__(self, engine):
        self.engine = engine

    async def _rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        with appmode.use(appmode.LIVE):
            async with self.engine.connect() as conn:
                await conn.execute(text("SET search_path TO public"))  # the live table, also while Test mode is on
                result = await conn.execute(text(sql), params)
                found = [dict(r) for r in result.mappings().all()] if result.returns_rows else []
                await conn.commit()
                return found

    async def _row(self) -> dict[str, Any]:
        rows = await self._rows("SELECT * FROM deploy_control WHERE id = 1")
        if rows:
            return rows[0]
        await self._rows("INSERT INTO deploy_control (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
        return (await self._rows("SELECT * FROM deploy_control WHERE id = 1"))[0]

    async def _audit(self, user: User, action: str, summary: str, data: dict[str, Any] | None = None) -> None:
        await self._rows(
            "INSERT INTO audit_log (actor_id, actor_email, action, entity_type, summary, data) "
            "VALUES (:id, :email, :action, 'deploy', :summary, CAST(:data AS JSONB))",
            id=user.id, email=user.email, action=action, summary=summary[:500], data=json.dumps(data or {}),
        )

    async def status(self) -> DeployStatusOut:
        row = await self._row()
        settings = get_settings()
        now = _now()
        started, finished = row["started_at"], row["finished_at"]
        running = bool(started and (not finished or finished < started) and now - started < STUCK_AFTER)
        api = await asyncio.to_thread(git_version, settings.deploy_repo_dir)
        return DeployStatusOut(
            mode=row["mode"], interval_minutes=row["interval_minutes"], schedule_times=list(row["schedule_times"] or []),
            timezone=STORE_TZ_NAME, requested_at=row["requested_at"], requested_by=row["requested_by_email"],
            last_check_at=row["last_check_at"], started_at=started, finished_at=finished, running=running,
            last_reason=row["last_reason"], last_result=row["last_result"], updated_at=row["updated_at"],
            updated_by=row["updated_by_email"], api=api,
            storefront_build=read_build(settings.storefront_app_dir), main_site_build=read_build(settings.main_site_app_dir),
            cron_seen=bool(row["last_seen_at"] and now - row["last_seen_at"] < CRON_FRESH), last_seen_at=row["last_seen_at"],
        )

    async def configure(self, data: DeployConfigIn, user: User) -> None:
        if data.mode == "schedule" and not data.schedule_times:
            raise ValidationFailedError("Add at least one time for scheduled updates")
        before = await self._row()
        await self._rows(
            "UPDATE deploy_control SET mode = :mode, interval_minutes = :minutes, schedule_times = CAST(:times AS JSONB), "
            "updated_at = now(), updated_by_email = :email WHERE id = 1",
            mode=data.mode, minutes=data.interval_minutes, times=json.dumps(data.schedule_times), email=user.email,
        )
        await self._audit(user, "deploy.configure", f"Updates: {describe(data)}", {
            "before": {"mode": before["mode"], "interval_minutes": before["interval_minutes"], "schedule_times": before["schedule_times"]},
            "after": data.model_dump(),
        })

    async def request_now(self, user: User) -> None:
        await self._row()
        await self._rows("UPDATE deploy_control SET requested_at = now(), requested_by_email = :email WHERE id = 1", email=user.email)
        await self._audit(user, "deploy.requested", "Asked the server to deploy now")

    async def cancel_request(self, user: User) -> None:
        await self._rows("UPDATE deploy_control SET requested_at = NULL, requested_by_email = NULL WHERE id = 1")
        await self._audit(user, "deploy.request_cancelled", "Cancelled 'Deploy now'")

    # ---- the server's cron job ------------------------------------------------------------------------------------
    async def gate_begin(self) -> Decision:
        row = await self._row()
        now = _now()
        decision = decide(now=now, mode=row["mode"], interval_minutes=row["interval_minutes"],
                          schedule_times=list(row["schedule_times"] or []), tz=STORE_TZ_NAME,
                          requested=row["requested_at"] is not None, last_check=row["last_check_at"])
        if decision.go:
            await self._rows(
                "UPDATE deploy_control SET last_seen_at = :now, last_check_at = :now, started_at = :now, last_reason = :reason, "
                "requested_at = NULL, requested_by_email = NULL WHERE id = 1",
                now=now, reason=decision.reason[:40],
            )
        else:
            await self._rows("UPDATE deploy_control SET last_seen_at = :now WHERE id = 1", now=now)
        return decision

    async def gate_end(self, ok: bool, summary: str) -> None:
        result = ("✓ " if ok else "✗ ") + (summary.strip() or ("no changes" if ok else "failed"))[:2000]
        await self._rows("UPDATE deploy_control SET finished_at = now(), last_result = :result WHERE id = 1", result=result)


def describe(data: DeployConfigIn) -> str:
    if data.mode == "paused":
        return "paused"
    if data.mode == "schedule":
        return "at " + ", ".join(data.schedule_times)
    return f"automatically every {data.interval_minutes} min"
