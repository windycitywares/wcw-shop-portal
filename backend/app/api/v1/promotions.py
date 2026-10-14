"""Sales and coupons (admin)."""

import csv
import io
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.commerce import (
    CampaignOut,
    CouponGenerate,
    CouponIn,
    CouponOut,
    CouponSend,
    CouponUpdate,
    GenerateResult,
    SaleIn,
    SaleOut,
)
from app.schemas.common import Page
from app.services.promotions import PromotionService, coupon_status

router = APIRouter(prefix="/promotions", tags=["promotions"])
Manager = Annotated[User, Depends(require(Permission.PROMOTIONS_MANAGE))]


@router.get("/coupons", response_model=Page[CouponOut])
async def list_coupons(
    session: SessionDep, _: Manager,
    q: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, pattern=r"^(active|scheduled|expired|used_up|paused)$"),
    campaign: str | None = Query(default=None, max_length=80),
    source: str | None = Query(default=None, pattern=r"^(manual|generated|welcome|personal)$"),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    return await PromotionService(session).list_coupons(q=q, status=status, campaign=campaign, source=source, page=page, page_size=page_size)


@router.post("/coupons", response_model=CouponOut, status_code=status.HTTP_201_CREATED)
async def create_coupon(session: SessionDep, user: Manager, data: CouponIn):
    return await PromotionService(session).create_coupon(data, user)


@router.post("/coupons/generate", response_model=GenerateResult, status_code=status.HTTP_201_CREATED)
async def generate_coupons(session: SessionDep, user: Manager, data: CouponGenerate):
    """Make a batch of single-use codes, e.g. for a mailing or a QR code on a flyer."""
    return await PromotionService(session).generate(data, user)


@router.post("/coupons/send", response_model=CouponOut, status_code=status.HTTP_201_CREATED)
async def send_coupon(session: SessionDep, user: Manager, data: CouponSend):
    """Make a personal code for one customer and email it to them."""
    return await PromotionService(session).send_personal(data, user)


@router.get("/coupons/{coupon_id}", response_model=CouponOut)
async def get_coupon(coupon_id: int, session: SessionDep, _: Manager):
    return await PromotionService(session).get_coupon(coupon_id)


@router.put("/coupons/{coupon_id}", response_model=CouponOut)
async def update_coupon(coupon_id: int, session: SessionDep, _: Manager, data: CouponUpdate):
    return await PromotionService(session).update_coupon(coupon_id, data)


@router.delete("/coupons/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coupon(coupon_id: int, session: SessionDep, _: Manager):
    await PromotionService(session).delete_coupon(coupon_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/campaigns", response_model=list[CampaignOut])
async def campaigns(session: SessionDep, _: Manager):
    return await PromotionService(session).campaigns()


@router.get("/campaigns/{campaign}/codes.csv")
async def campaign_codes(campaign: str, session: SessionDep, _: Manager):
    """Every code in a batch, ready for a mail merge or a printer."""
    coupons = await PromotionService(session).campaign_codes(campaign)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["code", "status", "uses", "expires"])
    now = datetime.now(timezone.utc)
    for c in coupons:
        writer.writerow([c.code, coupon_status(c, now), c.used_count, c.expires_at.isoformat() if c.expires_at else ""])
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in campaign)
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="codes-{safe}.csv"'})


@router.get("/sales", response_model=list[SaleOut])
async def list_sales(session: SessionDep, _: Manager):
    return await PromotionService(session).list_sales()


@router.post("/sales", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
async def create_sale(session: SessionDep, user: Manager, data: SaleIn):
    return await PromotionService(session).create_sale(data, user)


@router.put("/sales/{sale_id}", response_model=SaleOut)
async def update_sale(sale_id: int, session: SessionDep, _: Manager, data: SaleIn):
    return await PromotionService(session).update_sale(sale_id, data)


@router.delete("/sales/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sale(sale_id: int, session: SessionDep, _: Manager):
    await PromotionService(session).delete_sale(sale_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
