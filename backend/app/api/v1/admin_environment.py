"""Live / Test switch: work on a copy of the live data, refresh the copy, and delete it when done (admins only)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import SessionDep, require
from app.core.config import get_settings
from app.core.database import engine
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.environment import EnvironmentOut, LoginsIn, MailToIn, ModeIn
from app.services.testenv import TestEnvironment

router = APIRouter(prefix="/admin/environment", tags=["admin: environment"])
Admin = Annotated[User, Depends(require(Permission.ENVIRONMENT_MANAGE))]


async def _out(stats: dict | None = None) -> EnvironmentOut:
    return EnvironmentOut(**await TestEnvironment(engine).status(), stripe_test_configured=bool(get_settings().stripe_test_secret_key), stats=stats or None)


async def _release(session) -> None:
    """End the request's own transaction first: it may hold locks on the test copy that copying has to replace.
    close() (not rollback) keeps the signed-in user's loaded fields readable afterwards."""
    await session.close()


@router.get("", response_model=EnvironmentOut)
async def environment(response: Response, _: Admin):
    response.headers["Cache-Control"] = "no-store"
    return await _out()


@router.put("/mode", response_model=EnvironmentOut)
async def switch_mode(session: SessionDep, user: Admin, data: ModeIn):
    """Test: copy the live data afresh and work on the copy. Live: back to the real data (the copy is kept until deleted).
    Everyone is signed out by the switch and signs in again (accounts are matched within one copy only)."""
    await _release(session)
    stats = await TestEnvironment(engine).switch(data.mode, user)
    return await _out(stats)


@router.post("/sync", response_model=EnvironmentOut)
async def sync(session: SessionDep, user: Admin):
    """Replace the test data with a fresh copy of the live data (anything done during testing is lost)."""
    await _release(session)
    return await _out(await TestEnvironment(engine).sync(user, switch_on=False))


@router.delete("/test-data", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_data(session: SessionDep, user: Admin):
    """Delete the test copy. Only while the shop is on live data."""
    await _release(session)
    await TestEnvironment(engine).delete_copy(user)


@router.put("/mail-to", response_model=EnvironmentOut)
async def set_mail_to(session: SessionDep, user: Admin, data: MailToIn):
    """Where every email goes while test mode is on (none: emails are not sent at all)."""
    await _release(session)
    await TestEnvironment(engine).set_mail_to(str(data.email).lower() if data.email else None, user)
    return await _out()


@router.put("/test-logins", response_model=EnvironmentOut)
async def set_test_logins(session: SessionDep, user: Admin, data: LoginsIn):
    """Which copied shoppers may sign in while the shop is on test data (staff always may)."""
    await _release(session)
    await TestEnvironment(engine).set_logins([str(email).lower() for email in data.emails], user)
    return await _out()
