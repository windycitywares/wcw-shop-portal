"""Password reset, saved addresses and the contact form."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import mailer
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.i18n import LANGUAGES
from app.core.security import hash_password
from app.models.account import Address, ContactMessage, PasswordResetToken
from app.models.user import User
from app.repositories.account import AddressRepository, ContactRepository, PasswordResetRepository
from app.repositories.user import UserRepository
from app.schemas.account import AddressIn, ContactIn
from app.services import emails

log = logging.getLogger("wcw.account")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def localized_path(locale: str, path: str) -> str:
    return path if locale == "en" else f"/{locale}{path}"


class PasswordResetService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.tokens = PasswordResetRepository(session)

    async def request(self, email: str, locale: str = "en") -> None:
        """Email a reset link if the account exists. Says nothing either way (no account probing)."""
        user = await self.users.get_by_email(email.strip().lower())
        if not user or not user.is_active:
            return
        settings = get_settings()
        now = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        await self.tokens.expire_all_for(user.id, now)
        self.tokens.add(PasswordResetToken(
            user_id=user.id, token_hash=hash_token(token),
            expires_at=now + timedelta(minutes=settings.password_reset_minutes),
        ))
        locale = locale if locale in LANGUAGES else "en"
        link = f"{settings.site_url.rstrip('/')}{localized_path(locale, '/reset-password')}?token={token}"
        queued = [emails.enqueue(
            self.session, "password_reset", user.email,
            {"name": user.full_name or "", "link": link, "minutes": settings.password_reset_minutes},
            locale=locale, related_type="user", related_id=user.id,
        )]
        await self.session.commit()
        await emails.deliver(self.session, queued)

    async def reset(self, token: str, new_password: str) -> None:
        now = datetime.now(timezone.utc)
        record = await self.tokens.get_by_hash(hash_token(token))
        if not record or record.used_at is not None or record.expires_at <= now:
            raise ValidationFailedError("This reset link is invalid or has expired. Please request a new one.")
        user = await self.users.get(record.user_id)
        if not user or not user.is_active:
            raise ValidationFailedError("This reset link is invalid or has expired. Please request a new one.")
        user.hashed_password = hash_password(new_password)
        user.password_changed_at = now  # signs out every existing session
        await self.tokens.expire_all_for(user.id, now)
        await self.session.commit()


class AddressService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AddressRepository(session)

    async def list(self, user: User) -> list[Address]:
        return await self.repo.list_for(user.id)

    async def _get(self, user: User, address_id: int) -> Address:
        address = await self.repo.get_for(user.id, address_id)
        if not address:
            raise NotFoundError("Address not found")
        return address

    async def create(self, user: User, data: AddressIn) -> Address:
        existing = await self.repo.list_for(user.id)
        limit = get_settings().max_addresses_per_user
        if len(existing) >= limit:
            raise ValidationFailedError(f"You can save up to {limit} addresses. Delete one to add another.")
        make_default = data.is_default or not existing  # the first address is the default
        if make_default:
            await self.repo.clear_default(user.id)
        address = self.repo.add(Address(user_id=user.id, **data.model_dump(exclude={"is_default"}),
                                        is_default=make_default))
        await self.session.commit()
        await self.session.refresh(address)
        return address

    async def update(self, user: User, address_id: int, data: AddressIn) -> Address:
        address = await self._get(user, address_id)
        if data.is_default and not address.is_default:
            await self.repo.clear_default(user.id)
        for field, value in data.model_dump(exclude={"is_default"}).items():
            setattr(address, field, value)
        if data.is_default:
            address.is_default = True
        await self.session.commit()
        await self.session.refresh(address)
        return address

    async def make_default(self, user: User, address_id: int) -> Address:
        address = await self._get(user, address_id)
        if not address.is_default:
            await self.repo.clear_default(user.id)
            address.is_default = True
            await self.session.commit()
            await self.session.refresh(address)
        return address

    async def delete(self, user: User, address_id: int) -> None:
        address = await self._get(user, address_id)
        was_default = address.is_default
        await self.repo.delete(address)
        await self.session.flush()
        if was_default:  # promote the most recent remaining address
            remaining = await self.repo.list_for(user.id)
            if remaining:
                remaining[0].is_default = True
        await self.session.commit()


class ContactService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ContactRepository(session)

    async def submit(self, data: ContactIn, user: User | None, ip: str | None) -> None:
        msg = self.repo.add(ContactMessage(
            user_id=user.id if user else None, name=data.name, email=str(data.email).lower(),
            subject=data.subject, message=data.message.strip(), order_number=data.order_number,
            locale=data.locale, ip_address=ip,
        ))
        from app.services.contacts import ContactService as _ContactService
        await _ContactService(self.session).upsert(str(data.email).lower(), full_name=data.name, source="contact_form")
        await self.session.commit()  # keep the message even if the email below fails

        settings = get_settings()
        to = settings.contact_to or settings.admin_email
        if not to:
            log.warning("CONTACT_TO is not set — contact message %s saved but not emailed", msg.id)
            return
        lines = [f"From: {msg.name} <{msg.email}>"]
        if msg.order_number:
            lines.append(f"Order: {msg.order_number}")
        lines += [f"Language: {msg.locale}", f"Signed in: {'yes, ' + user.email if user else 'no'}",
                  "", msg.message, "", f"— Sent from the contact form on {settings.site_url} (message #{msg.id})"]
        try:
            await mailer.send(mailer.Mail(to=to, subject=f"[Contact] {msg.subject}", text="\n".join(lines),
                                          reply_to=msg.email))
        except mailer.MailError:
            return  # stored in the database; the visitor still gets a success message
        msg.emailed = True
        await self.session.commit()
