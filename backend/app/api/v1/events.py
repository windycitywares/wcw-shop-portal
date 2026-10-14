"""Visit tracking (only used after the visitor accepts analytics) and the consent counter."""

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import SessionDep
from app.api.v1.auth import client_ip
from app.core.exceptions import ValidationFailedError
from app.core.rate_limit import events_by_ip
from app.schemas.analytics import ConsentIn, TrackIn
from app.services.tracking import TrackingService

router = APIRouter(tags=["analytics"])
MAX_BODY = 64_000


async def _small_body(request: Request) -> None:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY:
        raise ValidationFailedError("Request too large")


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(_small_body)])
async def track(request: Request, session: SessionDep, data: TrackIn) -> Response:
    """Always answers 204, so the page never shows an error because of analytics."""
    ip = client_ip(request)
    if not events_by_ip.is_blocked(ip):
        events_by_ip.hit(ip)
        await TrackingService(session).record(data, request.headers.get("user-agent"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/events/consent", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(_small_body)])
async def consent(request: Request, session: SessionDep, data: ConsentIn) -> Response:
    ip = client_ip(request)
    if not events_by_ip.is_blocked(ip):
        events_by_ip.hit(ip)
        await TrackingService(session).consent(data.accepted)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
