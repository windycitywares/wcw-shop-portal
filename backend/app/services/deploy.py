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
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.domain.deploy_policy import Decision, decide
from app.domain.releases import describe_commit
from app.domain.timeutil import store_tz_name
from app.models.user import User
from app.schemas.deploy import DeployConfigIn, DeployStatusOut, ReleaseOut, ReleasesOut, Version

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


KEEP_RELEASES = 5


def git_release(repo: str, rev: str = "HEAD") -> dict[str, Any] | None:
    """The version at `rev` in the server's checkout, described from its pull request. None when git can't say."""
    try:
        out = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%H%x1f%cI%x1f%s%x1f%b", rev], capture_output=True,
                             text=True, timeout=5, check=True).stdout
        sha, date, subject, body = out.rstrip("\n").split("\x1f", 3)
        children: list[tuple[str, str]] = []
        if subject.startswith("Merge pull request #"):
            kids = subprocess.run(["git", "-C", repo, "log", "--reverse", "--format=%s%x1f%b%x1e", f"{sha}^1..{sha}^2"],
                                  capture_output=True, text=True, timeout=5, check=False).stdout
            for chunk in kids.split("\x1e"):
                if chunk.strip():
                    subj, _, kid_body = chunk.strip("\n").partition("\x1f")
                    children.append((subj.strip(), kid_body))
        pr, title, details = describe_commit(subject, body, children)
        return {"commit": sha, "pr_number": pr, "title": title, "details": details, "committed_at": datetime.fromisoformat(date)}
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def commit_exists(repo: str, sha: str) -> bool:
    try:
        return subprocess.run(["git", "-C", repo, "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def recent_commits(repo: str, count: int) -> list[str]:
    try:
        out = subprocess.run(["git", "-C", repo, "log", "--first-parent", f"-{count}", "--format=%H"], capture_output=True,
                             text=True, timeout=5, check=True).stdout
        return out.split()
    except (OSError, subprocess.SubprocessError):
        return []


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
            timezone=store_tz_name(), requested_at=row["requested_at"], requested_by=row["requested_by_email"],
            last_check_at=row["last_check_at"], started_at=started, finished_at=finished, running=running,
            last_reason=row["last_reason"], last_result=row["last_result"], updated_at=row["updated_at"],
            updated_by=row["updated_by_email"], api=api,
            storefront_build=read_build(settings.storefront_app_dir), main_site_build=read_build(settings.main_site_app_dir),
            cron_seen=bool(row["last_seen_at"] and now - row["last_seen_at"] < CRON_FRESH), last_seen_at=row["last_seen_at"],
            pinned_commit=(row["pinned_commit"] or "")[:7] or None, pinned_by=row["pinned_by_email"], pinned_at=row["pinned_at"],
            restore_pending=bool(row["restore_pending"]),
        )

    async def record_release(self, reason: str | None = None) -> None:
        """Note the version now running. A new API commit adds a row; a storefront or main-site build that arrives later
        for the same commit is added to that row, so the list shows one entry per change."""
        settings = get_settings()
        cur = await asyncio.to_thread(git_release, settings.deploy_repo_dir)
        if not cur:
            return
        store, site = read_build(settings.storefront_app_dir), read_build(settings.main_site_app_dir)
        last = await self._rows("SELECT id, commit FROM deploy_releases ORDER BY deployed_at DESC, id DESC LIMIT 1")
        if last and last[0]["commit"] == cur["commit"]:
            await self._rows("UPDATE deploy_releases SET storefront_build = :s, main_site_build = :m WHERE id = :id",
                             s=store, m=site, id=last[0]["id"])
            return
        # A version put back (restore) is already in the list: move it to the top instead of listing it twice.
        await self._rows("DELETE FROM deploy_releases WHERE commit = :c", c=cur["commit"])
        await self._insert_release(cur, store, site, reason)

    async def _insert_release(self, rel: dict[str, Any], store: str | None, site: str | None, reason: str | None,
                              deployed_at: datetime | None = None) -> None:
        await self._rows(
            "INSERT INTO deploy_releases (commit, pr_number, title, details, committed_at, deployed_at, storefront_build, "
            "main_site_build, reason) VALUES (:commit, :pr, :title, :details, :committed, :deployed, :s, :m, :reason)",
            commit=rel["commit"], pr=rel["pr_number"], title=rel["title"], details=rel["details"], committed=rel["committed_at"],
            deployed=deployed_at or _now(), s=store, m=site, reason=reason,
        )

    async def releases(self) -> ReleasesOut:
        """The last five versions, newest first; the first is the one running. On a server that has never recorded one,
        the list starts from the checkout's own history so the page isn't empty."""
        settings = get_settings()
        rows = await self._rows("SELECT * FROM deploy_releases ORDER BY deployed_at DESC, id DESC LIMIT :n", n=KEEP_RELEASES)
        if not rows:
            shas = await asyncio.to_thread(recent_commits, settings.deploy_repo_dir, KEEP_RELEASES)
            base = _now()
            for i, sha in reversed(list(enumerate(shas))):  # oldest first, so ids and order agree
                rel = await asyncio.to_thread(git_release, settings.deploy_repo_dir, sha)
                if rel:
                    stamp = rel["committed_at"] or base - timedelta(minutes=i)
                    current = i == 0
                    await self._insert_release(rel, read_build(settings.storefront_app_dir) if current else None,
                                               read_build(settings.main_site_app_dir) if current else None, "history", stamp)
            rows = await self._rows("SELECT * FROM deploy_releases ORDER BY deployed_at DESC, id DESC LIMIT :n", n=KEEP_RELEASES)
        fresh = {r["commit"]: await asyncio.to_thread(git_release, settings.deploy_repo_dir, r["commit"]) for r in rows}
        repo = settings.deploy_github_repo
        return ReleasesOut(releases=[
            ReleaseOut(id=r["id"], commit=r["commit"][:7], pr_number=(fresh[r["commit"]] or r)["pr_number"],
                       pr_url=(f"https://github.com/{repo}/pull/{(fresh[r['commit']] or r)['pr_number']}"
                               if (fresh[r["commit"]] or r)["pr_number"] else None),
                       title=(fresh[r["commit"]] or r)["title"], details=(fresh[r["commit"]] or r)["details"],
                       committed_at=r["committed_at"], deployed_at=r["deployed_at"], storefront_build=r["storefront_build"],
                       main_site_build=r["main_site_build"], current=i == 0, restorable=i > 0)
            for i, r in enumerate(rows)
        ])

    async def restore(self, release_id: int, user: User) -> None:
        """Put an earlier version back: the server installs it on its next run and then holds it (pinned) until
        "Return to latest"."""
        found = await self._rows("SELECT * FROM deploy_releases WHERE id = :id", id=release_id)
        if not found:
            raise NotFoundError("That version isn't in the list any more")
        rel = found[0]
        live = await asyncio.to_thread(git_release, get_settings().deploy_repo_dir)
        if live and live["commit"] == rel["commit"]:
            raise ValidationFailedError("That version is already live")
        if not await asyncio.to_thread(commit_exists, get_settings().deploy_repo_dir, rel["commit"]):
            raise ValidationFailedError("The server no longer has that version's code, so it can't be restored")
        await self._row()
        await self._rows(
            "UPDATE deploy_control SET pinned_commit = :c, restore_pending = TRUE, pinned_by_email = :email, pinned_at = now(), "
            "requested_at = now(), requested_by_email = :email WHERE id = 1",
            c=rel["commit"], email=user.email,
        )
        await self._audit(user, "deploy.restore", f"Restore: {rel['title']} ({rel['commit'][:7]})",
                          {"commit": rel["commit"], "pr_number": rel["pr_number"], "title": rel["title"]})

    async def return_to_latest(self, user: User) -> None:
        await self._row()
        await self._rows(
            "UPDATE deploy_control SET pinned_commit = NULL, restore_pending = FALSE, pinned_by_email = NULL, pinned_at = NULL, "
            "requested_at = now(), requested_by_email = :email WHERE id = 1", email=user.email,
        )
        await self._audit(user, "deploy.unpin", "Returned to the latest version")

    async def pinned_commit(self) -> str:
        """For the cron script: "<commit> <storefront build, or - when unknown>", or nothing when following the latest."""
        row = await self._row()
        commit = row["pinned_commit"]
        if not commit:
            return ""
        rel = await self._rows("SELECT storefront_build FROM deploy_releases WHERE commit = :c", c=commit)
        return f"{commit} {(rel[0]['storefront_build'] if rel else None) or '-'}"

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
        if row["restore_pending"] and row["pinned_commit"]:
            await self._rows(
                "UPDATE deploy_control SET last_seen_at = :now, last_check_at = :now, started_at = :now, last_reason = 'restore', "
                "requested_at = NULL, requested_by_email = NULL WHERE id = 1", now=now,
            )
            return Decision(go=True, reason="restore")
        decision = decide(now=now, mode=row["mode"], interval_minutes=row["interval_minutes"],
                          schedule_times=list(row["schedule_times"] or []), tz=store_tz_name(),
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
        # A restore that failed leaves the previous code running, so there is nothing to hold.
        await self._rows("UPDATE deploy_control SET pinned_commit = CASE WHEN :ok THEN pinned_commit ELSE NULL END, "
                         "pinned_by_email = CASE WHEN :ok THEN pinned_by_email ELSE NULL END, "
                         "pinned_at = CASE WHEN :ok THEN pinned_at ELSE NULL END, restore_pending = FALSE "
                         "WHERE id = 1 AND restore_pending", ok=ok)
        try:  # the version history is a record, never a reason for the gate to fail
            row = await self._row()
            await self.record_release(row["last_reason"])
        except Exception:  # noqa: BLE001
            pass


def describe(data: DeployConfigIn) -> str:
    if data.mode == "paused":
        return "paused"
    if data.mode == "schedule":
        return "at " + ", ".join(data.schedule_times)
    return f"automatically every {data.interval_minutes} min"
