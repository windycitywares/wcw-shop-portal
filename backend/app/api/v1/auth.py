from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep
from app.schemas.common import Message
from app.schemas.user import NewsletterIn, ProfileUpdate, RegisterIn, TokenOut, UserMe
from app.services.auth import AuthService, NewsletterService, UserService, to_me

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(session: SessionDep, form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """OAuth2 password flow: send `username` (the email) and `password` as form fields."""
    return await AuthService(session).authenticate(form.username, form.password)


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(session: SessionDep, data: RegisterIn):
    return await AuthService(session).register(data)


@router.get("/me", response_model=UserMe)
async def me(user: CurrentUser):
    return to_me(user)


@router.patch("/me", response_model=UserMe)
async def update_me(session: SessionDep, user: CurrentUser, data: ProfileUpdate):
    return to_me(await UserService(session).update_profile(user, data.full_name))


newsletter_router = APIRouter(prefix="/newsletter", tags=["newsletter"])


@newsletter_router.post("", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
async def subscribe(session: SessionDep, data: NewsletterIn):
    await NewsletterService(session).subscribe(data.email)
    return Message(detail="Thanks for subscribing!")
