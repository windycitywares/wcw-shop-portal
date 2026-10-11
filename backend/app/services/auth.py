from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.core.permissions import permissions_for
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import NewsletterSubscriber, User
from app.repositories.user import NewsletterRepository, UserRepository
from app.schemas.user import RegisterIn, TokenOut, UserCreate, UserMe, UserUpdate


def to_me(user: User) -> UserMe:
    return UserMe(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        permissions=permissions_for(user.role),
    )


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)

    def issue_token(self, user: User) -> TokenOut:
        token = create_access_token(user.id, user.role.value)
        return TokenOut(access_token=token, user=to_me(user))

    async def authenticate(self, email: str, password: str) -> TokenOut:
        user = await self.users.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Incorrect email or password")
        if not user.is_active:
            raise AuthenticationError("This account is disabled")
        return self.issue_token(user)

    async def register(self, data: RegisterIn) -> TokenOut:
        user = await self._create(data.email, data.password, data.full_name, UserRole.CUSTOMER)
        return self.issue_token(user)

    async def _create(self, email: str, password: str, full_name: str | None, role: UserRole) -> User:
        email = email.strip().lower()
        if await self.users.get_by_email(email):
            raise ConflictError("An account with this email already exists")
        user = self.users.add(
            User(email=email, hashed_password=hash_password(password), full_name=full_name, role=role)
        )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("An account with this email already exists") from exc
        await self.session.refresh(user)
        return user


class UserService(AuthService):
    """Admin-side account management."""

    async def create(self, data: UserCreate) -> User:
        return await self._create(data.email, data.password, data.full_name, data.role)

    async def update(self, user_id: int, data: UserUpdate, acting: User) -> User:
        user = await self.users.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        changes = data.model_dump(exclude_unset=True)
        if user.id == acting.id and (
            changes.get("is_active") is False or ("role" in changes and changes["role"] != user.role)
        ):
            raise PermissionDeniedError("You can't change your own role or disable your own account")
        for field, value in changes.items():
            if value is not None or field == "full_name":
                setattr(user, field, value)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def change_password(self, user: User, current: str, new: str) -> TokenOut:
        """Verify the current password, store the new one, and invalidate older tokens."""
        if not verify_password(current, user.hashed_password):
            raise ValidationFailedError("Current password is incorrect")
        if current == new:
            raise ValidationFailedError("Choose a password different from the current one")
        user.hashed_password = hash_password(new)
        user.password_changed_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(user)
        return self.issue_token(user)  # fresh token so this browser stays signed in

    async def update_profile(self, user: User, full_name: str | None) -> User:
        user.full_name = full_name
        await self.session.commit()
        await self.session.refresh(user)
        return user


class NewsletterService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = NewsletterRepository(session)

    async def subscribe(self, email: str) -> None:
        email = email.strip().lower()
        if await self.repo.get_by(email=email):
            return  # already subscribed; don't reveal membership
        self.repo.add(NewsletterSubscriber(email=email))
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
