from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import appmode
from app.core.config import get_settings
from app.core.database import get_session
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.permissions import Permission, has_permission
from app.core.live_events import ACTOR_KEY
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{get_settings().api_prefix}/auth/login", auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def store_time(session: SessionDep) -> None:
    """Runs before every request: makes this worker use the store time zone the owner picked (settings are cached for seconds)."""
    from app.services.settings import SettingsService

    try:
        await SettingsService(session).load()
    except Exception:  # never fail a request over this: the previous or default zone stays in force
        try:
            await session.rollback()
        except Exception:
            pass


async def get_optional_user(
    session: SessionDep, token: Annotated[str | None, Depends(oauth2_scheme)]
) -> User | None:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise AuthenticationError("Invalid or expired token")
    user = await session.get(User, user_id)
    if payload.get("env", "live") != appmode.current().effective:
        raise AuthenticationError("The shop was switched between live and test data — please sign in again")
    if not user or not user.is_active:
        raise AuthenticationError("Account not found or disabled")
    if user.password_changed_at and int(payload.get("iat", 0)) < int(user.password_changed_at.timestamp()):
        raise AuthenticationError("Your password was changed — please sign in again")
    # Live updates name who made a change, and a person's own edits don't come back to them as news.
    session.info[ACTOR_KEY] = (user.id, user.full_name or user.email)
    return user


async def get_current_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise AuthenticationError("Not authenticated")
    return user


OptionalUser = Annotated[User | None, Depends(get_optional_user)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def require(*permissions: Permission):
    """Dependency factory: `user: User = Depends(require(Permission.CATALOG_PUBLISH))`."""

    async def _checker(user: CurrentUser) -> User:
        missing = [p for p in permissions if not has_permission(user.role, p)]
        if missing:
            raise PermissionDeniedError("You don't have permission to do that")
        return user

    return _checker
