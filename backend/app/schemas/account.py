from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.i18n import LANG_PATTERN
from app.schemas.common import ORMModel
from app.schemas.user import Password

CaptchaToken = Field(default=None, max_length=4096)
Locale = Field(default="en", pattern=LANG_PATTERN)


class ForgotPasswordIn(BaseModel):
    email: EmailStr
    locale: str = Locale


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Password


# ---------- addresses ----------

def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    v = " ".join(v.split())
    return v or None


class AddressFields(BaseModel):
    label: str | None = Field(default=None, max_length=50)
    full_name: str = Field(min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    postal_code: str = Field(min_length=1, max_length=20)
    country: str = Field(default="US", pattern=r"^[A-Za-z]{2}$")
    phone: str | None = Field(default=None, max_length=40, pattern=r"^[0-9+()\-.\s]*$")

    @field_validator("label", "full_name", "company", "line1", "line2", "city", "region", "postal_code", "phone")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return _clean(v)

    @field_validator("country")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class AddressIn(AddressFields):
    is_default: bool = False


class AddressOut(ORMModel, AddressFields):
    id: int
    is_default: bool
    created_at: datetime


# ---------- contact ----------

class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=10, max_length=5000)
    order_number: str | None = Field(default=None, max_length=32)
    locale: str = Locale
    captcha_token: str | None = CaptchaToken
    website: str | None = Field(default=None, max_length=200)  # honeypot: humans never fill this in

    @field_validator("name", "subject", "order_number")
    @classmethod
    def _one_line(cls, v: str | None) -> str | None:
        return _clean(v)


class SiteConfig(BaseModel):
    turnstile_site_key: str | None
