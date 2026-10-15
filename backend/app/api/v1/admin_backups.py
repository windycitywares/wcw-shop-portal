"""Database backups to a private GitHub repository (admins only). Always the live data, whatever Test mode is set to."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api.deps import SessionDep, require
from app.core.database import engine
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.backups import BackupConfigIn, BackupResultOut, BackupsOut, RestoreChallengeOut, RestoreIn, RestoreOut, RestorePrepareIn
from app.services.backups import BackupError, BackupService, secrets_status
from app.services.restore import RestoreService

router = APIRouter(prefix="/admin/backups", tags=["admin: backups"])
Admin = Annotated[User, Depends(require(Permission.BACKUPS_MANAGE))]


async def _out(service: BackupService, with_files: bool = True) -> BackupsOut:
    cfg = await service.config()
    files, files_error = None, None
    if with_files and cfg.get("repo"):
        try:
            files = await service.remote_files()
        except BackupError as exc:
            files_error = str(exc)
    return BackupsOut(**cfg, secrets=secrets_status(), runs=await service.runs(), files=files, files_error=files_error)


@router.get("", response_model=BackupsOut)
async def backups(response: Response, _: Admin):
    """Settings, whether the server secrets are in place, the last runs, and the backups now in the repository."""
    response.headers["Cache-Control"] = "no-store"
    return await _out(BackupService(engine))


@router.put("", response_model=BackupsOut)
async def save_backup_settings(user: Admin, data: BackupConfigIn):
    service = BackupService(engine)
    await service.save_config(data.model_dump(), user.email)
    return await _out(service)


@router.post("/run", response_model=BackupResultOut)
async def back_up_now(user: Admin):
    """Make a backup now (takes a few seconds to a minute) and keep only the newest ones in the repository."""
    return await BackupService(engine).run("manual", user.email)


@router.post("/restore/prepare", response_model=RestoreChallengeOut)
async def prepare_restore(_: Admin, data: RestorePrepareIn):
    """Step 1: a random word the admin must type to confirm (valid 5 minutes, for this file only)."""
    return await RestoreService(engine).prepare(data.file)


@router.post("/restore", response_model=RestoreOut)
async def restore_backup(session: SessionDep, user: Admin, data: RestoreIn):
    """Step 2: replace the live data with the backup. A safety backup of the current data is made first; the restore
    runs in one transaction, so a failure changes nothing."""
    email = user.email
    await session.close()  # the sign-in check holds a lock on the users table, which the restore replaces
    try:
        return await RestoreService(engine).restore(data.file, data.word, data.token, email)
    except BackupError as exc:
        return RestoreOut(status="failed", file=data.file, error=str(exc))
