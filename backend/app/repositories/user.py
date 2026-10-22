from sqlalchemy import func, or_, select

from app.core.enums import UserRole
from app.models.user import NewsletterSubscriber, User
from app.repositories.base import BaseRepository
from app.utils.text import escape_like


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        return await self.get_by(email=email.strip().lower())

    async def search(
        self, q: str | None, role: UserRole | None, page: int, page_size: int, staff: bool | None = None
    ) -> tuple[list[User], int]:
        stmt = select(User)
        if q:
            like = f"%{escape_like(q)}%"
            stmt = stmt.where(or_(User.email.ilike(like), User.full_name.ilike(like)))
        if role:
            stmt = stmt.where(User.role == role)
        if staff is True:
            stmt = stmt.where(User.role != UserRole.CUSTOMER)
        elif staff is False:
            stmt = stmt.where(User.role == UserRole.CUSTOMER)
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = await self.session.execute(
            stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(rows.scalars().all()), total


class NewsletterRepository(BaseRepository[NewsletterSubscriber]):
    model = NewsletterSubscriber
