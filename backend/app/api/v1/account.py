from fastapi import APIRouter, Request, Response, status

from app.api.deps import CurrentUser, OptionalUser, SessionDep
from app.api.v1.auth import client_ip, no_store
from app.core import captcha
from app.core.config import get_settings
from app.core.exceptions import TooManyRequestsError
from app.core.rate_limit import contact_by_ip
from app.schemas.account import AddressIn, AddressOut, ContactIn, SiteConfig
from app.schemas.common import Message
from app.services.account import AddressService, ContactService

addresses_router = APIRouter(prefix="/account/addresses", tags=["account"])


@addresses_router.get("", response_model=list[AddressOut])
async def list_addresses(response: Response, session: SessionDep, user: CurrentUser):
    no_store(response)
    return await AddressService(session).list(user)


@addresses_router.post("", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def add_address(session: SessionDep, user: CurrentUser, data: AddressIn):
    return await AddressService(session).create(user, data)


@addresses_router.put("/{address_id}", response_model=AddressOut)
async def update_address(address_id: int, session: SessionDep, user: CurrentUser, data: AddressIn):
    return await AddressService(session).update(user, address_id, data)


@addresses_router.post("/{address_id}/default", response_model=AddressOut)
async def make_default_address(address_id: int, session: SessionDep, user: CurrentUser):
    return await AddressService(session).make_default(user, address_id)


@addresses_router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(address_id: int, session: SessionDep, user: CurrentUser):
    await AddressService(session).delete(user, address_id)


contact_router = APIRouter(tags=["contact"])


@contact_router.post("/contact", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
async def contact(request: Request, session: SessionDep, user: OptionalUser, data: ContactIn):
    ok = Message(detail="Thanks — your message has been sent. We'll reply by email.")
    if data.website:  # honeypot filled in: a bot. Pretend it worked.
        return ok
    ip_key = client_ip(request)
    if contact_by_ip.is_blocked(ip_key):
        raise TooManyRequestsError("You've sent several messages already. Please try again in an hour.")
    await captcha.verify(data.captcha_token, ip_key, action="contact")
    contact_by_ip.hit(ip_key)
    await ContactService(session).submit(data, user, ip_key)
    return ok


@contact_router.get("/site-config", response_model=SiteConfig)
async def site_config(response: Response):
    """Public, non-secret settings the storefront needs at runtime (e.g. the Turnstile site key)."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return SiteConfig(turnstile_site_key=get_settings().turnstile_site_key)
