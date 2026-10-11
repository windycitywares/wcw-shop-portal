from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import UserRole
from app.schemas.common import ORMModel

Password = Field(min_length=8, max_length=72)


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime


class UserMe(UserOut):
    permissions: list[str]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Password
    full_name: str | None = Field(default=None, max_length=200)


class UserCreate(RegisterIn):
    role: UserRole = UserRole.CUSTOMER


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    role: UserRole | None = None
    is_active: bool | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Password


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserMe


class NewsletterIn(BaseModel):
    email: EmailStr
