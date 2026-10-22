import json
import secrets
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import appmode
from app.core.enums import OrderStatus, UserRole
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.core.i18n import LANGUAGES
from app.core.permissions import permissions_for
from app.core.security import create_access_token, hash_password, verify_password
from app.domain import emailtext
from app.domain.contacts import SERVICE_ONLY_SOURCES  # noqa: F401  (also imported from here by other services)
from app.domain.testlogin import test_login_allowed
from app.models.order import Order
from app.models.user import NewsletterSubscriber, User
from app.repositories.user import NewsletterRepository, UserRepository
from app.schemas.user import RegisterIn, TokenOut, UserCreate, UserMe, UserUpdate
from app.services import audit, emails
from app.services.promotions import issue_coupon
from app.services.settings import SettingsService


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


def may_sign_in(user: User) -> bool:
    """Whether this account may sign in right now.

    On live data, everyone active may. On the test copy, the copy holds every live customer and their
    password, so only staff, the addresses the owner listed, and accounts made inside the copy (someone
    signing up while testing) may sign in.
    """
    if user.role != UserRole.CUSTOMER or not appmode.is_test():
        return True
    state = appmode.current()
    if user.email.strip().lower() in state.login_emails:
        return True
    return bool(state.test_synced_at and user.created_at and user.created_at > state.test_synced_at)


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
        if appmode.is_test() and not test_login_allowed(user.email, user.role, await self._test_login_emails()):
            raise AuthenticationError("Sign-in is limited to approved accounts while the shop is in test mode")
        return self.issue_token(user)

    async def _test_login_emails(self) -> list[str]:
        """Read from the live table, whichever copy the session is on."""
        raw = (await self.session.execute(text("SELECT test_login_emails::text FROM public.app_mode WHERE id = 1"))).scalar_one_or_none()
        try:
            found = json.loads(raw) if raw else []
        except ValueError:
            return []
        return [e for e in found if isinstance(e, str)]

    async def register(self, data: RegisterIn) -> TokenOut:
        user = await self._create(data.email, data.password, data.full_name, UserRole.CUSTOMER)
        from app.services.contacts import ContactService
        await ContactService(self.session).upsert(data.email, full_name=data.full_name, source="signup", user_id=user.id, marketing_opt_in=False)
        locale = data.locale if data.locale in LANGUAGES else "en"
        queued = [emails.enqueue(
            self.session, "account_welcome", user.email,
            {"name": user.full_name or "", "account_url": emails.site_link("/account", locale)},
            locale=locale, related_type="user", related_id=user.id,
        )]
        await self.session.commit()
        await emails.deliver(self.session, queued)
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
        password = changes.pop("password", None)
        if password is not None:
            if user.id == acting.id:
                raise PermissionDeniedError("Change your own password in Your account → Password")
            user.hashed_password = hash_password(password)
            user.password_changed_at = datetime.now(timezone.utc)  # older sign-ins stop working
            audit.record(self.session, acting, "user.password_set", "user", user.id,
                         f"Set a new password for {user.email}")
        if "email" in changes and changes["email"] is not None:
            new_email = str(changes["email"]).strip().lower()
            if new_email != user.email:
                existing = await self.users.get_by_email(new_email)
                if existing is not None and existing.id != user.id:
                    raise ConflictError("That email address is already in use")
                user.email = new_email
                changes.pop("email")
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
    """The marketing consent registry: who opted in, when they left, and the one-time welcome offer."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = NewsletterRepository(session)

    async def _has_ordered(self, email: str) -> bool:
        return (await self.session.execute(
            select(func.count()).select_from(Order).where(Order.email == email, Order.status != OrderStatus.CANCELLED)
        )).scalar_one() > 0

    async def add(
        self, email: str, locale: str | None = "en", *, source: str = "site", welcome: bool = True, commit: bool = True,
    ) -> NewsletterSubscriber:
        """Subscribe an address (or welcome it back). New subscribers get the welcome coupon when that is switched on."""
        email = email.strip().lower()
        locale = locale if locale in LANGUAGES else "en"
        row = await self.repo.get_by(email=email)
        if row is not None and row.source not in SERVICE_ONLY_SOURCES:
            if row.unsubscribed_at is not None:  # coming back: no second welcome offer
                row.unsubscribed_at = None
                row.locale = locale
            if commit:
                await self.session.commit()
            return row
        if row is not None:  # so far only allowed to send service emails: now a real subscriber
            row.source, row.unsubscribed_at, row.locale = source, None, locale
        else:
            row = self.repo.add(NewsletterSubscriber(email=email, locale=locale, source=source, unsubscribe_token=secrets.token_urlsafe(24)))
        from app.services.contacts import ContactService
        await ContactService(self.session).upsert(email, source="newsletter", marketing_opt_in=True)
        queued = []
        settings = await SettingsService(self.session).load()
        if welcome and settings.welcome.enabled and not await self._has_ordered(email):
            coupon = await issue_coupon(
                self.session, email=email, kind="percent", value=Decimal(settings.welcome.percent), expires_days=settings.welcome.expires_days,
                source="welcome", prefix="WELCOME", campaign="welcome", min_subtotal=settings.welcome.min_subtotal, first_order_only=True,
                name="Welcome offer",
            )
            row.welcome_coupon = coupon.code
            queued.append(emails.enqueue(self.session, "welcome_offer", email, {
                "name": None, "percent": settings.welcome.percent, "expires": emailtext.long_date(coupon.expires_at, locale),
                "code": coupon.code, "shop_url": emails.site_link("/shop", locale),
                "unsubscribe_url": emails.unsubscribe_url(row.unsubscribe_token, locale),
            }, locale=locale, related_type="newsletter"))
        if commit:
            try:
                await self.session.commit()
            except IntegrityError:  # two sign-ups for the same address at once
                await self.session.rollback()
                return await self.repo.get_by(email=email) or row
            await emails.deliver(self.session, queued)
        return row

    async def contact(self, email: str, locale: str | None, source: str) -> NewsletterSubscriber:
        """The consent row for an address, created (for service emails only) when missing. Flushes, no commit."""
        email = email.strip().lower()
        row = await self.repo.get_by(email=email)
        if row is None:
            row = self.repo.add(NewsletterSubscriber(email=email, locale=locale if locale in LANGUAGES else "en", source=source,
                                                     unsubscribe_token=secrets.token_urlsafe(24)))
            await self.session.flush()
        return row

    async def subscribe(self, email: str, locale: str | None = "en") -> None:
        await self.add(email, locale, source="site", welcome=True)

    async def unsubscribe(self, token: str) -> bool:
        """Opt out with the link from an email. True when the token is known (repeating it is harmless)."""
        row = await self.repo.get_by(unsubscribe_token=token)
        if row is None:
            return False
        if row.unsubscribed_at is None:
            row.unsubscribed_at = datetime.now(timezone.utc)
            await self.session.commit()
        return True
