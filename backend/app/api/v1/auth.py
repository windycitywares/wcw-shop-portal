from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep
from app.core import captcha
from app.core.exceptions import AuthenticationError, NotFoundError, TooManyRequestsError
from app.core.rate_limit import (
    failed_logins_by_email,
    failed_logins_by_ip,
    newsletter_by_ip,
    registrations_by_ip,
    reset_attempts_by_ip,
    reset_requests_by_email,
    reset_requests_by_ip,
)
from app.schemas.account import ForgotPasswordIn, ResetPasswordIn
from app.schemas.common import Message
from app.schemas.user import NewsletterIn, PasswordChange, ProfileUpdate, SignUpIn, TokenOut, UnsubscribeIn, UserMe
from app.services.account import PasswordResetService
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
async def register(request: Request, response: Response, session: SessionDep, data: SignUpIn):
    no_store(response)
    ip_key = client_ip(request)
    if registrations_by_ip.is_blocked(ip_key):
        raise TooManyRequestsError("Too many new accounts from this network. Please try again later.")
    await captcha.verify(data.captcha_token, ip_key, action="signup")
    registrations_by_ip.hit(ip_key)
    return await AuthService(session).register(data)


@router.post("/forgot-password", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(request: Request, session: SessionDep, data: ForgotPasswordIn):
    """Email a one-time reset link. The answer is the same whether or not the account exists."""
    email_key, ip_key = str(data.email).strip().lower(), client_ip(request)
    if reset_requests_by_ip.is_blocked(ip_key):
        raise TooManyRequestsError("Too many requests. Please wait an hour and try again.")
    reset_requests_by_ip.hit(ip_key)
    if reset_requests_by_email.is_blocked(email_key):
        # Say so plainly. A quiet "we've sent a link" here is exactly how "forgot password is broken" starts.
        raise TooManyRequestsError(
            "We've already sent a reset link to that address. Check your inbox and your spam folder, "
            "or try again in an hour."
        )
    reset_requests_by_email.hit(email_key)
    await PasswordResetService(session).request(email_key, data.locale)
    return Message(detail="If an account exists for that email, we've sent a link to reset the password.")


@router.post("/reset-password", response_model=Message)
async def reset_password(request: Request, response: Response, session: SessionDep, data: ResetPasswordIn):
    """Set a new password with the token from the email. Signs out every existing session."""
    no_store(response)
    ip_key = client_ip(request)
    if reset_attempts_by_ip.is_blocked(ip_key):
        raise TooManyRequestsError("Too many attempts. Please wait 15 minutes and try again.")
    reset_attempts_by_ip.hit(ip_key)
    await PasswordResetService(session).reset(data.token, data.new_password)
    return Message(detail="Your password has been changed. You can sign in now.")


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
async def subscribe(request: Request, session: SessionDep, data: NewsletterIn):
    """Join the email list. The answer is the same for new and existing addresses; new ones get the welcome offer by email."""
    ip_key = client_ip(request)
    if newsletter_by_ip.is_blocked(ip_key):
        raise TooManyRequestsError("Too many sign-ups from this network. Please try again later.")
    newsletter_by_ip.hit(ip_key)
    await NewsletterService(session).subscribe(str(data.email), data.locale)
    return Message(detail="Thanks for subscribing! If this is your first time, your welcome offer is on its way.")


@newsletter_router.post("/unsubscribe", response_model=Message)
async def unsubscribe(session: SessionDep, data: UnsubscribeIn):
    """Opt out using the token from the link in any of our emails."""
    if not await NewsletterService(session).unsubscribe(data.token):
        raise NotFoundError("This unsubscribe link isn't valid.")
    return Message(detail="You're unsubscribed. We won't email you again.")
