from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep
from app.core.exceptions import AuthenticationError, TooManyRequestsError
from app.core.rate_limit import failed_logins_by_email, failed_logins_by_ip, registrations_by_ip
from app.schemas.common import Message
from app.schemas.user import NewsletterIn, PasswordChange, ProfileUpdate, RegisterIn, TokenOut, UserMe
from app.services.auth import AuthService, NewsletterService, UserService, to_me

router = APIRouter(prefix="/auth", tags=["auth"])


def client_ip(request: Request) -> str:
    # LiteSpeed/Passenger put the visitor's address first in X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.post("/login", response_model=TokenOut)
async def login(
    request: Request,
    response: Response,
    session: SessionDep,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    """OAuth2 password flow: send `username` (the email) and `password` as form fields."""
    no_store(response)
    email_key, ip_key = form.username.strip().lower(), client_ip(request)
    if failed_logins_by_email.is_blocked(email_key) or failed_logins_by_ip.is_blocked(ip_key):
        raise TooManyRequestsError("Too many sign-in attempts. Please wait 15 minutes and try again.")
    try:
        token = await AuthService(session).authenticate(form.username, form.password)
    except AuthenticationError:
        failed_logins_by_email.hit(email_key)
        failed_logins_by_ip.hit(ip_key)
        raise
    failed_logins_by_email.reset(email_key)
    return token


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(request: Request, response: Response, session: SessionDep, data: RegisterIn):
    no_store(response)
    ip_key = client_ip(request)
    if registrations_by_ip.is_blocked(ip_key):
        raise TooManyRequestsError("Too many new accounts from this network. Please try again later.")
    registrations_by_ip.hit(ip_key)
    return await AuthService(session).register(data)


@router.get("/me", response_model=UserMe)
async def me(response: Response, user: CurrentUser):
    no_store(response)
    return to_me(user)


@router.patch("/me", response_model=UserMe)
async def update_me(session: SessionDep, user: CurrentUser, data: ProfileUpdate):
    return to_me(await UserService(session).update_profile(user, data.full_name))


@router.post("/change-password", response_model=TokenOut)
async def change_password(response: Response, session: SessionDep, user: CurrentUser, data: PasswordChange):
    """Change your password. Every other signed-in session is signed out."""
    no_store(response)
    return await UserService(session).change_password(user, data.current_password, data.new_password)


newsletter_router = APIRouter(prefix="/newsletter", tags=["newsletter"])


@newsletter_router.post("", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
async def subscribe(session: SessionDep, data: NewsletterIn):
    await NewsletterService(session).subscribe(data.email)
    return Message(detail="Thanks for subscribing!")
