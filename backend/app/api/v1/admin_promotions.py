"""Sales, coupons and automatic cart offers for staff."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.promotions import (
    BulkResultOut,
    CartRuleIn,
    CartRuleOut,
    CouponBulkIn,
    CouponDetailOut,
    CouponIn,
    CouponListOut,
    CouponOut,
    SaleIn,
    SaleOut,
)
from app.services.promotions import PromotionService

router = APIRouter(prefix="/admin/promotions", tags=["admin: promotions"])
Staff = Annotated[User, Depends(require(Permission.PROMOTIONS_MANAGE))]


class ActiveIn(BaseModel):
    is_active: bool


class DeletedOut(BaseModel):
    result: str  # deleted | paused


# ---- sales ------------------------------------------------------------------------------------


@router.get("/sales", response_model=list[SaleOut])
async def list_sales(response: Response, session: SessionDep, _: Staff):
    response.headers["Cache-Control"] = "no-store"
    return await PromotionService(session).list_sales()


@router.post("/sales", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
async def create_sale(session: SessionDep, user: Staff, data: SaleIn):
    return await PromotionService(session).create_sale(data, user)


@router.put("/sales/{sale_id}", response_model=SaleOut)
async def update_sale(sale_id: int, session: SessionDep, user: Staff, data: SaleIn):
    return await PromotionService(session).update_sale(sale_id, data, user)


@router.post("/sales/{sale_id}/active", response_model=SaleOut)
async def set_sale_active(sale_id: int, session: SessionDep, user: Staff, data: ActiveIn):
    """Pause or resume a sale without losing its settings."""
    return await PromotionService(session).set_sale_active(sale_id, data.is_active, user)


@router.delete("/sales/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sale(sale_id: int, session: SessionDep, user: Staff):
    await PromotionService(session).delete_sale(sale_id, user)


# ---- coupons ----------------------------------------------------------------------------------

COUPON_STATUS = "^(active|scheduled|expired|used_up|paused)$"


@router.get("/coupons", response_model=CouponListOut)
async def list_coupons(
    response: Response, session: SessionDep, _: Staff,
    q: str | None = Query(None, max_length=100), source: str | None = Query(None, max_length=16),
    status_: str | None = Query(None, alias="status", pattern=COUPON_STATUS),
    campaign: str | None = Query(None, max_length=80), page: int = Query(1, ge=1, le=10_000), page_size: int = Query(25, ge=1, le=100),
):
    response.headers["Cache-Control"] = "no-store"
    return await PromotionService(session).list_coupons(q, source, status_, campaign, page, page_size)


@router.get("/coupons/export.csv")
async def export_coupons(
    session: SessionDep, _: Staff,
    q: str | None = Query(None, max_length=100), source: str | None = Query(None, max_length=16),
    status_: str | None = Query(None, alias="status", pattern=COUPON_STATUS),
    campaign: str | None = Query(None, max_length=80),
):
    """Codes with their status and uses, e.g. to hand a batch to a mailing tool."""
    data = await PromotionService(session).export_csv(q, source, status_, campaign)
    return Response(
        data, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="wcw-coupons.csv"', "Cache-Control": "no-store"},
    )


@router.post("/coupons/bulk", response_model=BulkResultOut, status_code=status.HTTP_201_CREATED)
async def bulk_create_coupons(session: SessionDep, user: Staff, data: CouponBulkIn):
    """Generate many single-purpose codes at once, or one personal code per email address."""
    return await PromotionService(session).bulk_create(data, user)


@router.post("/coupons", response_model=CouponOut, status_code=status.HTTP_201_CREATED)
async def create_coupon(session: SessionDep, user: Staff, data: CouponIn):
    return await PromotionService(session).create_coupon(data, user)


@router.get("/coupons/{coupon_id}", response_model=CouponDetailOut)
async def coupon_detail(coupon_id: int, response: Response, session: SessionDep, _: Staff):
    response.headers["Cache-Control"] = "no-store"
    return await PromotionService(session).coupon_detail(coupon_id)


@router.put("/coupons/{coupon_id}", response_model=CouponOut)
async def update_coupon(coupon_id: int, session: SessionDep, user: Staff, data: CouponIn):
    return await PromotionService(session).update_coupon(coupon_id, data, user)


@router.delete("/coupons/{coupon_id}", response_model=DeletedOut)
async def delete_coupon(coupon_id: int, session: SessionDep, user: Staff):
    """An unused coupon is deleted; one that was used is paused so past orders keep their history."""
    return DeletedOut(result=await PromotionService(session).delete_coupon(coupon_id, user))


# ---- automatic cart offers ----------------------------------------------------------------------


@router.get("/offers", response_model=list[CartRuleOut])
async def list_offers(response: Response, session: SessionDep, _: Staff):
    response.headers["Cache-Control"] = "no-store"
    return await PromotionService(session).list_rules()


@router.post("/offers", response_model=CartRuleOut, status_code=status.HTTP_201_CREATED)
async def create_offer(session: SessionDep, user: Staff, data: CartRuleIn):
    return await PromotionService(session).create_rule(data, user)


@router.put("/offers/{rule_id}", response_model=CartRuleOut)
async def update_offer(rule_id: int, session: SessionDep, user: Staff, data: CartRuleIn):
    return await PromotionService(session).update_rule(rule_id, data, user)


@router.delete("/offers/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_offer(rule_id: int, session: SessionDep, user: Staff):
    await PromotionService(session).delete_rule(rule_id, user)
