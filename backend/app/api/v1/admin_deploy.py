"""Admin → Deployments: automatic / scheduled / paused updates, "Deploy now", live versions and the deploy log."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import require
from app.core.config import get_settings
from app.core.database import engine
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.deploy import DeployConfigIn, DeployLogOut, DeployStatusOut, ReleasesOut, RestoreIn
from app.services.deploy import DeployService, log_tail

router = APIRouter(prefix="/admin/deploy", tags=["admin: deploy"])
Admin = Annotated[User, Depends(require(Permission.SETTINGS_MANAGE))]


@router.get("", response_model=DeployStatusOut)
async def deploy_status(response: Response, _: Admin) -> DeployStatusOut:
    response.headers["Cache-Control"] = "no-store"
    return await DeployService(engine).status()


@router.put("/config", response_model=DeployStatusOut)
async def deploy_configure(user: Admin, data: DeployConfigIn) -> DeployStatusOut:
    service = DeployService(engine)
    await service.configure(data, user)
    return await service.status()


@router.post("/now", response_model=DeployStatusOut, status_code=status.HTTP_202_ACCEPTED)
async def deploy_now(user: Admin) -> DeployStatusOut:
    """Ask the server to look for updates on its next cron run (within a minute), whatever the mode."""
    service = DeployService(engine)
    await service.request_now(user)
    return await service.status()


@router.delete("/now", response_model=DeployStatusOut)
async def cancel_deploy_now(user: Admin) -> DeployStatusOut:
    service = DeployService(engine)
    await service.cancel_request(user)
    return await service.status()


@router.get("/log", response_model=DeployLogOut)
async def deploy_log(response: Response, _: Admin, lines: Annotated[int, Query(ge=10, le=400)] = 200) -> DeployLogOut:
    response.headers["Cache-Control"] = "no-store"
    return DeployLogOut(log=log_tail(get_settings().deploy_log, lines))


@router.get("/releases", response_model=ReleasesOut)
async def deploy_releases(response: Response, _: Admin) -> ReleasesOut:
    """The last five versions the server has run, newest (the live one) first."""
    response.headers["Cache-Control"] = "no-store"
    return await DeployService(engine).releases()


@router.post("/restore", response_model=DeployStatusOut, status_code=status.HTTP_202_ACCEPTED)
async def deploy_restore(user: Admin, data: RestoreIn) -> DeployStatusOut:
    """Put an earlier version back on the server's next run and hold it there until "Return to latest"."""
    service = DeployService(engine)
    await service.restore(data.release_id, user)
    return await service.status()


@router.delete("/restore", response_model=DeployStatusOut)
async def deploy_return_to_latest(user: Admin) -> DeployStatusOut:
    service = DeployService(engine)
    await service.return_to_latest(user)
    return await service.status()
