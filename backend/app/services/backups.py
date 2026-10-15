"""Automatic database backups to a private GitHub repository, keeping only the newest few.

Each backup is `pg_dump` of the live data (custom format, already compressed), encrypted with AES-256-GCM using a key
derived (scrypt) from BACKUP_PASSPHRASE, and committed to `backups/` in the repository named in Admin → Backups.
The commit has no parent and holds only the newest `keep` files, and the branch is moved to it: older backups stop
being part of the repository's history, so GitHub really discards them instead of keeping every copy forever.

Secrets live only in backend/.env: BACKUP_GITHUB_TOKEN (fine-grained token, Contents read and write on that one
repository) and BACKUP_PASSPHRASE (without it the files can't be read, so keep a copy somewhere safe).
Restoring: docs/DEPLOYMENT.md → "Backups".
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import secrets
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core import appmode
from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError
from app.domain.timeutil import to_store_time

MAGIC = b"WCWBACKUP1\n"
FOLDER = "backups"
NAME = re.compile(r"^wcw-backup-(\d{8}-\d{6})\.dump\.enc$")
MAX_ATTEMPTS_PER_DAY = 3
GITHUB_LIMIT = 95 * 1024 * 1024  # GitHub refuses files over 100 MB
REPO_PATTERN = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
README = """# Windy City Wares database backups

Written automatically by the shop (Admin → Backups). Only the newest few are kept.

Each `backups/wcw-backup-YYYYMMDD-HHMMSS.dump.enc` is the live database, encrypted with the backup passphrase.
To restore one, see docs/DEPLOYMENT.md → "Backups" in the wcw-portal repository.
"""


class BackupError(Exception):
    """A backup step failed; the message is safe to show in the admin (never contains the token or passphrase)."""


# ---- encryption ------------------------------------------------------------------------------------------


def _key(passphrase: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode("utf-8"))


def encrypt(data: bytes, passphrase: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    return MAGIC + salt + nonce + AESGCM(_key(passphrase, salt)).encrypt(nonce, data, MAGIC)


def decrypt(blob: bytes, passphrase: str) -> bytes:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not blob.startswith(MAGIC):
        raise BackupError("This isn't a Windy City Wares backup file")
    salt, nonce, body = blob[len(MAGIC):len(MAGIC) + 16], blob[len(MAGIC) + 16:len(MAGIC) + 28], blob[len(MAGIC) + 28:]
    try:
        return AESGCM(_key(passphrase, salt)).decrypt(nonce, body, MAGIC)
    except InvalidTag as exc:
        raise BackupError("Wrong passphrase, or the file is damaged") from exc


# ---- naming and retention -------------------------------------------------------------------------------


def file_name(moment: datetime) -> str:
    return f"wcw-backup-{moment.astimezone(timezone.utc):%Y%m%d-%H%M%S}.dump.enc"


def to_keep(existing: list[str], new: str, keep: int) -> list[str]:
    """Names to keep, newest first: the new backup plus the newest `keep - 1` existing ones (others are ignored)."""
    ours = sorted({n for n in existing if NAME.match(n) and n != new}, reverse=True)
    return [new, *ours[: max(keep - 1, 0)]]


def is_due(now: datetime, hour: int, runs_today: list[dict[str, Any]]) -> bool:
    """After the configured hour (shop time), once a day, with a few retries if it failed."""
    if to_store_time(now).hour < hour:
        return False
    if any(r["status"] == "success" for r in runs_today):
        return False
    if any(r["status"] == "running" and now - r["started_at"] < timedelta(minutes=30) for r in runs_today):
        return False
    return sum(1 for r in runs_today if r["status"] == "failed") < MAX_ATTEMPTS_PER_DAY


# ---- pg_dump ----------------------------------------------------------------------------------------------


def pg_dump_path() -> str | None:
    configured = get_settings().backup_pg_dump
    return configured if os.path.isabs(configured) and os.path.exists(configured) else shutil.which(configured)


def dump_live_database() -> bytes:
    """pg_dump of the live data only (the `public` schema, not the test copy)."""
    binary = pg_dump_path()
    if not binary:
        raise BackupError("pg_dump wasn't found on the server (set BACKUP_PG_DUMP to its full path)")
    url = make_url(get_settings().database_url)
    env = {**os.environ, "PGPASSWORD": url.password or "", "PGCONNECT_TIMEOUT": "20"}
    args = [binary, "--format=custom", "--schema=public", "--no-owner", "--no-privileges", "--compress=6",
            "--host", url.host or "localhost", "--port", str(url.port or 5432), "--username", url.username or "", url.database or ""]
    try:
        done = subprocess.run(args, env=env, capture_output=True, timeout=900, check=False)  # noqa: S603 - fixed arguments
    except subprocess.TimeoutExpired as exc:
        raise BackupError("pg_dump took longer than 15 minutes") from exc
    if done.returncode != 0:
        message = done.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["unknown error"]
        raise BackupError(f"pg_dump failed: {message[0][:300]}")
    return done.stdout


# ---- GitHub -----------------------------------------------------------------------------------------------


@dataclass
class GitHub:
    repo: str
    branch: str
    token: str
    base: str = "https://api.github.com"

    def call(self, method: str, path: str, body: dict[str, Any] | None = None, ok_missing: bool = False) -> Any:
        req = urllib.request.Request(  # noqa: S310 - fixed https base
            f"{self.base}/repos/{self.repo}{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
        )
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "WindyCityWares-backup/1.0")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            if ok_missing and exc.code in (404, 409):
                return None
            try:
                detail = json.loads(exc.read()).get("message", "")
            except (ValueError, OSError):
                detail = ""
            hint = {401: " (check BACKUP_GITHUB_TOKEN)", 403: " (the token needs Contents: read and write on this repository)",
                    404: " (check the repository name, and that the token can see it)"}.get(exc.code, "")
            raise BackupError(f"GitHub answered {exc.code}: {detail}{hint}") from exc
        except (OSError, ValueError) as exc:
            raise BackupError(f"Could not reach GitHub: {exc}") from exc

    def check_private(self) -> None:
        info = self.call("GET", "")
        if not info.get("private"):
            raise BackupError(f"{self.repo} is public. Backups are only written to a private repository.")

    def current_files(self) -> dict[str, dict[str, Any]]:
        """{name: {sha, size}} in backups/ on the branch (empty for a new, empty repository)."""
        ref = self.call("GET", f"/git/ref/heads/{self.branch}", ok_missing=True)
        if not ref:
            return {}
        tree = self.call("GET", f"/git/trees/{ref['object']['sha']}?recursive=1")
        out = {}
        for item in tree.get("tree", []):
            path = item.get("path", "")
            if item.get("type") == "blob" and path.startswith(f"{FOLDER}/"):
                out[path[len(FOLDER) + 1:]] = {"sha": item["sha"], "size": item.get("size")}
        return out

    def ensure_initialised(self) -> None:
        """The Git data API doesn't work on an empty repository; the contents API can create its first file."""
        if self.call("GET", f"/git/ref/heads/{self.branch}", ok_missing=True):
            return
        self.call("PUT", "/contents/README.md", {
            "message": "Start the backup repository", "content": base64.b64encode(README.encode()).decode(), "branch": self.branch,
        })

    def publish(self, name: str, data: bytes, keep: int) -> list[str]:
        """Commit the new file with only the newest `keep` backups, as a commit with no history; returns the names kept."""
        self.ensure_initialised()
        existing = self.current_files()
        kept = to_keep(list(existing), name, keep)
        new_blob = self.call("POST", "/git/blobs", {"content": base64.b64encode(data).decode(), "encoding": "base64"})["sha"]
        readme = self.call("POST", "/git/blobs", {"content": README, "encoding": "utf-8"})["sha"]
        entries = [{"path": "README.md", "mode": "100644", "type": "blob", "sha": readme}]
        for n in kept:
            entries.append({"path": f"{FOLDER}/{n}", "mode": "100644", "type": "blob", "sha": new_blob if n == name else existing[n]["sha"]})
        tree = self.call("POST", "/git/trees", {"tree": entries})["sha"]
        commit = self.call("POST", "/git/commits", {"message": f"Backup {name} (keeping {len(kept)})", "tree": tree, "parents": []})["sha"]
        self.call("PATCH", f"/git/refs/heads/{self.branch}", {"sha": commit, "force": True})
        return kept


# ---- the service ------------------------------------------------------------------------------------------


def secrets_status() -> dict[str, bool]:
    s = get_settings()
    return {"token": bool(s.backup_github_token), "passphrase": bool(s.backup_passphrase), "pg_dump": pg_dump_path() is not None}


class BackupService:
    """Always works on the live data's tables (backup_config, backup_runs), whatever Test mode is set to."""

    def __init__(self, engine):
        self.engine = engine

    async def _rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        with appmode.use(appmode.LIVE):
            async with self.engine.connect() as conn:
                await conn.execute(text("SET search_path TO public"))  # the live tables, also while Test mode is on
                found = [dict(r) for r in (await conn.execute(text(sql), params)).mappings().all()]
                await conn.commit()
                return found

    async def config(self) -> dict[str, Any]:
        rows = await self._rows("SELECT enabled, hour, keep, repo, branch, updated_at, updated_by_email FROM backup_config WHERE id = 1")
        return rows[0] if rows else {"enabled": False, "hour": 3, "keep": 5, "repo": None, "branch": "main", "updated_at": None, "updated_by_email": None}

    async def save_config(self, data: dict[str, Any], actor_email: str) -> dict[str, Any]:
        repo = (data.get("repo") or "").strip() or None
        if repo and not REPO_PATTERN.match(repo):
            raise ValidationFailedError("Enter the repository as owner/name, e.g. windycitywares/wcw-backups")
        if repo and repo.lower() == "windycitywares/wcw-portal":
            raise ValidationFailedError("Use a separate private repository for backups, not the code repository")
        if data.get("enabled") and not repo:
            raise ValidationFailedError("Choose the repository before turning backups on")
        await self._rows(
            """UPDATE backup_config SET enabled = :enabled, hour = :hour, keep = :keep, repo = :repo, branch = :branch,
               updated_at = now(), updated_by_email = :email WHERE id = 1""",
            enabled=bool(data.get("enabled")), hour=int(data["hour"]), keep=int(data["keep"]), repo=repo,
            branch=(data.get("branch") or "main").strip(), email=actor_email,
        )
        await self._audit(actor_email, "backup.settings", f"Backups {'on' if data.get('enabled') else 'off'}: {repo or 'no repository'}, "
                          f"daily after {int(data['hour']):02d}:00, keep {int(data['keep'])}")
        return await self.config()

    async def runs(self, limit: int = 20) -> list[dict[str, Any]]:
        return await self._rows(
            "SELECT id, started_at, finished_at, status, trigger, actor_email, file_name, size_bytes, error FROM backup_runs ORDER BY started_at DESC LIMIT :n",
            n=limit,
        )

    async def _audit(self, email: str | None, action: str, summary: str) -> None:
        await self._rows(
            "INSERT INTO audit_log (actor_email, action, entity_type, entity_id, summary, data) VALUES (:e, :a, 'backup', 'app', :s, '{}'::jsonb)",
            e=email, a=action, s=summary[:500],
        )

    def _github(self, cfg: dict[str, Any]) -> GitHub:
        token = get_settings().backup_github_token
        if not token:
            raise BackupError("BACKUP_GITHUB_TOKEN isn't set in backend/.env")
        if not cfg.get("repo"):
            raise BackupError("No backup repository is set")
        return GitHub(cfg["repo"], cfg.get("branch") or "main", token)

    async def remote_files(self) -> list[dict[str, Any]]:
        cfg = await self.config()
        files = await asyncio.to_thread(self._github(cfg).current_files)
        return sorted(({"name": n, "size": f["size"]} for n, f in files.items() if NAME.match(n)), key=lambda f: f["name"], reverse=True)

    async def run(self, trigger: str, actor_email: str | None = None) -> dict[str, Any]:
        cfg = await self.config()
        started = datetime.now(timezone.utc)
        name = file_name(started)
        run_id = (await self._rows(
            "INSERT INTO backup_runs (trigger, actor_email, file_name) VALUES (:t, :e, :n) RETURNING id", t=trigger, e=actor_email, n=name,
        ))[0]["id"]
        try:
            passphrase = get_settings().backup_passphrase
            if not passphrase or len(passphrase) < 12:
                raise BackupError("BACKUP_PASSPHRASE isn't set in backend/.env (use at least 12 characters)")
            github = self._github(cfg)
            await asyncio.to_thread(github.check_private)
            data = await asyncio.to_thread(dump_live_database)
            sealed = await asyncio.to_thread(encrypt, data, passphrase)
            if len(sealed) > GITHUB_LIMIT:
                raise BackupError(f"The backup is {len(sealed) // (1024 * 1024)} MB; GitHub accepts files up to 100 MB")
            kept = await asyncio.to_thread(github.publish, name, sealed, int(cfg["keep"]))
        except BackupError as exc:
            await self._rows("UPDATE backup_runs SET status = 'failed', finished_at = now(), error = :e WHERE id = :i", e=str(exc)[:1000], i=run_id)
            await self._audit(actor_email, "backup.failed", f"Backup failed: {exc}")
            return {"status": "failed", "error": str(exc), "file_name": name}
        await self._rows(
            "UPDATE backup_runs SET status = 'success', finished_at = now(), size_bytes = :s WHERE id = :i", s=len(sealed), i=run_id,
        )
        await self._rows("DELETE FROM backup_runs WHERE id NOT IN (SELECT id FROM backup_runs ORDER BY started_at DESC LIMIT 200)")
        if trigger == "manual":
            await self._audit(actor_email, "backup.manual", f"Backed up the database to {cfg['repo']} ({name})")
        return {"status": "success", "file_name": name, "size_bytes": len(sealed), "kept": kept}

    async def run_if_due(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        cfg = await self.config()
        if not cfg["enabled"] or not cfg["repo"]:
            return {"skipped": "backups are off"}
        local = to_store_time(now)
        day_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        today = await self._rows("SELECT status, started_at FROM backup_runs WHERE trigger = 'schedule' AND started_at >= :d", d=day_start)
        if not is_due(now, int(cfg["hour"]), today):
            return {"skipped": "not due"}
        return await self.run("schedule")
