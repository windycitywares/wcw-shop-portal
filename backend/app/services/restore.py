"""Restore a backup from the GitHub repository into the live database (Admin → Backups → Restore).

Guard rails, in order:
1. A typed confirmation: the server picks a random word (e.g. "cedar-4817") and signs it; the restore only runs when
   the admin types exactly that word within 5 minutes. The word can't be guessed or reused for another file.
2. Only while the shop is on live data (not in Test mode), and never while the scheduled jobs are running.
3. The chosen backup is downloaded and decrypted first (a wrong passphrase or damaged file stops here, nothing changed).
4. A fresh backup of the current data is made and must succeed, so the restore itself can be undone.
5. pg_restore runs as ONE transaction (--single-transaction): it either replaces everything or nothing.
6. Migrations run afterwards (`alembic upgrade head`) in case the backup is from an older version of the shop.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core import appmode
from app.core.config import BACKEND_DIR, get_settings
from app.core.exceptions import ConflictError, ValidationFailedError
from app.services.backups import NAME, BackupError, BackupService, decrypt, pg_dump_path

CHALLENGE_SECONDS = 300
JOBS_LOCK_KEY = 7_204_519_001  # the same advisory lock the scheduled jobs take (app/scripts/run_jobs.py)
WORDS = (
    "amber", "aspen", "birch", "cedar", "clover", "coral", "delta", "ember", "falcon", "fern", "harbor", "hazel",
    "indigo", "juniper", "lagoon", "lantern", "maple", "meadow", "orchid", "pebble", "prairie", "quartz", "raven",
    "river", "saffron", "sierra", "spruce", "summit", "thistle", "timber", "velvet", "willow",
)


# ---- the typed confirmation --------------------------------------------------------------------------------


def _sign(file: str, word: str, expires: int) -> str:
    key = hashlib.sha256(f"restore:{get_settings().jwt_secret}".encode()).digest()
    return hmac.new(key, f"{file}|{word}|{expires}".encode(), hashlib.sha256).hexdigest()


def new_challenge(file: str, now: float | None = None) -> dict[str, Any]:
    """A random word to type, and a signed token that proves the server issued it for this file."""
    word = f"{secrets.choice(WORDS)}-{secrets.randbelow(9000) + 1000}"
    expires = int((now or time.time()) + CHALLENGE_SECONDS)
    return {"word": word, "token": f"{expires}.{_sign(file, word, expires)}", "expires_in": CHALLENGE_SECONDS}


def check_challenge(file: str, typed: str, token: str, now: float | None = None) -> None:
    try:
        expires_s, signature = token.split(".", 1)
        expires = int(expires_s)
    except (ValueError, AttributeError) as exc:
        raise ValidationFailedError("The confirmation is invalid. Open the restore box again.") from exc
    if (now or time.time()) > expires:
        raise ValidationFailedError("The confirmation word has expired. Open the restore box again for a new one.")
    if not hmac.compare_digest(_sign(file, (typed or "").strip().lower(), expires), signature):
        raise ValidationFailedError("The word you typed doesn't match. Type the word shown in the box exactly.")


# ---- restoring ----------------------------------------------------------------------------------------------


def pg_restore_path() -> str | None:
    configured = get_settings().backup_pg_restore
    if configured:
        return configured if os.path.exists(configured) else shutil.which(configured)
    dump = pg_dump_path()  # usually installed side by side
    if dump:
        sibling = os.path.join(os.path.dirname(dump), "pg_restore")
        if os.path.exists(sibling):
            return sibling
    return shutil.which("pg_restore")


def restore_command(binary: str, dump_file: str) -> tuple[list[str], dict[str, str]]:
    url = make_url(get_settings().database_url)
    args = [binary, "--clean", "--if-exists", "--no-owner", "--no-privileges", "--single-transaction", "--exit-on-error",
            "--schema=public", "--host", url.host or "localhost", "--port", str(url.port or 5432), "--username", url.username or "",
            "--dbname", url.database or "", dump_file]
    env = {**os.environ, "PGPASSWORD": url.password or "", "PGCONNECT_TIMEOUT": "20", "PGOPTIONS": "-c lock_timeout=60s"}
    return args, env


def _run_restore(data: bytes) -> None:
    binary = pg_restore_path()
    if not binary:
        raise BackupError("pg_restore wasn't found on the server (set BACKUP_PG_RESTORE to its full path)")
    with tempfile.NamedTemporaryFile(prefix="wcw-restore-", suffix=".dump", delete=False) as fh:
        fh.write(data)
        path = fh.name
    try:
        os.chmod(path, 0o600)  # it holds customer data
        args, env = restore_command(binary, path)
        done = subprocess.run(args, env=env, capture_output=True, timeout=1800, check=False)  # noqa: S603 - fixed arguments
        if done.returncode != 0:
            lines = [ln for ln in done.stderr.decode("utf-8", "replace").splitlines() if ln.strip()]
            raise BackupError(f"pg_restore failed, nothing was changed: {(lines[-1] if lines else 'unknown error')[:300]}")
    except subprocess.TimeoutExpired as exc:
        raise BackupError("pg_restore took longer than 30 minutes and was stopped; nothing was changed") from exc
    finally:
        os.unlink(path)


def _migrate() -> None:
    done = subprocess.run(  # noqa: S603 - fixed arguments
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, capture_output=True, timeout=600, check=False,
    )
    if done.returncode != 0:
        tail = done.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["unknown error"]
        raise BackupError(f"The backup was restored, but updating its tables failed: {tail[0][:300]}. Run `alembic upgrade head` on the server.")


class RestoreService:
    def __init__(self, engine):
        self.engine = engine
        self.backups = BackupService(engine)

    async def prepare(self, file: str) -> dict[str, Any]:
        if not NAME.match(file):
            raise ValidationFailedError("Choose one of the backups in the list")
        return {"file": file, **new_challenge(file)}

    async def _download(self, file: str) -> bytes:
        cfg = await self.backups.config()
        github = self.backups._github(cfg)
        files = await asyncio.to_thread(github.current_files)
        if file not in files:
            raise BackupError(f"{file} is no longer in {cfg['repo']}")
        blob = await asyncio.to_thread(github.call, "GET", f"/git/blobs/{files[file]['sha']}")
        return base64.b64decode(blob["content"])

    async def restore(self, file: str, typed: str, token: str, actor_email: str) -> dict[str, Any]:
        check_challenge(file, typed, token)
        if appmode.current().chosen == appmode.TEST:
            raise ConflictError("Switch the shop back to live data (Admin → Test mode) before restoring a backup")
        passphrase = get_settings().backup_passphrase
        if not passphrase:
            raise BackupError("BACKUP_PASSPHRASE isn't set in backend/.env")

        with appmode.use(appmode.LIVE):
            async with self.engine.connect() as lock:
                await lock.execute(text("SET search_path TO public"))
                if not (await lock.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": JOBS_LOCK_KEY})).scalar():
                    raise ConflictError("Scheduled jobs (or another restore) are running. Try again in a minute.")
                await lock.commit()
                try:
                    copy = await lock.execute(text("SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = :s)"), {"s": appmode.TEST_SCHEMA})
                    if copy.scalar():
                        raise ConflictError("Delete the test data first (Admin → Test mode): it shares parts of the database the restore replaces")
                    await lock.commit()
                    data = decrypt(await self._download(file), passphrase)  # 3. readable before anything changes
                    safety = await self.backups.run("manual", f"{actor_email} (before restore)")  # 4.
                    if safety["status"] != "success":
                        raise BackupError(f"Couldn't make a safety backup first, so nothing was restored: {safety.get('error')}")
                    await asyncio.to_thread(_run_restore, data)  # 5.
                    await asyncio.to_thread(_migrate)  # 6.
                finally:
                    await lock.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": JOBS_LOCK_KEY})
                    await lock.commit()
            appmode.forget()
            # The restored tables replaced the audit log and backup history: record the restore in the restored data.
            await self.backups._audit(actor_email, "backup.restore", f"Restored the database from {file}; safety backup {safety['file_name']}")
        return {"status": "restored", "file": file, "safety_backup": safety["file_name"]}
