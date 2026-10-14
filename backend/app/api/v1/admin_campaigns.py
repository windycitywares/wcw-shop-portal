"""Email campaigns."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.campaigns import SEGMENT_LABELS, AudienceOut, CampaignIn, CampaignListOut, CampaignOut
from app.schemas.common import Message
from app.services.campaigns import CampaignService

router = APIRouter(prefix="/admin/campaigns", tags=["admin: campaigns"])
Staff = Annotated[User, Depends(require(Permission.PROMOTIONS_MANAGE))]
SEGMENT_PATTERN = "^(" + "|".join(SEGMENT_LABELS) + ")$"


@router.get("", response_model=CampaignListOut)
async def list_campaigns(response: Response, session: SessionDep, _: Staff):
    response.headers["Cache-Control"] = "no-store"
    return await CampaignService(session).list()


@router.get("/audience", response_model=AudienceOut)
async def audience(response: Response, session: SessionDep, _: Staff, segment: str = Query("subscribers", pattern=SEGMENT_PATTERN)):
    """How many people a campaign to this group would reach."""
    response.headers["Cache-Control"] = "no-store"
    return await CampaignService(session).audience_size(segment)


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(session: SessionDep, user: Staff, data: CampaignIn):
    return await CampaignService(session).create(data, user)


@router.put("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(campaign_id: int, session: SessionDep, user: Staff, data: CampaignIn):
    return await CampaignService(session).update(campaign_id, data, user)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(campaign_id: int, session: SessionDep, user: Staff):
    await CampaignService(session).delete(campaign_id, user)


@router.post("/{campaign_id}/test", response_model=Message)
async def send_test(campaign_id: int, session: SessionDep, user: Staff):
    """Send the campaign to your own address first."""
    await CampaignService(session).send_test(campaign_id, user)
    return Message(detail=f"Test email sent to {user.email}")


@router.post("/{campaign_id}/send", response_model=CampaignOut)
async def send_campaign(campaign_id: int, session: SessionDep, user: Staff):
    """Send the campaign to its audience. This can only be done once."""
    return await CampaignService(session).send(campaign_id, user)
