"""Customers (people who bought) with purchase-history segments."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.domain.rfm import SEGMENTS
from app.models.user import User
from app.schemas.customers import CustomerDetail, CustomerListOut
from app.services.customers import SORTS, CustomerService

router = APIRouter(prefix="/admin/customers", tags=["admin: customers"])
Staff = Annotated[User, Depends(require(Permission.CUSTOMERS_VIEW))]
SEGMENT_PATTERN = "^(" + "|".join(SEGMENTS) + ")$"
SORT_PATTERN = "^(" + "|".join(SORTS) + ")$"


@router.get("", response_model=CustomerListOut)
async def list_customers(
    response: Response, session: SessionDep, _: Staff,
    q: str | None = Query(None, max_length=100), segment: str | None = Query(None, pattern=SEGMENT_PATTERN),
    sort: str = Query("revenue", pattern=SORT_PATTERN), page: int = Query(1, ge=1, le=10_000), page_size: int = Query(25, ge=1, le=100),
):
    response.headers["Cache-Control"] = "no-store"
    return await CustomerService(session).list(q, segment, sort, page, page_size)


@router.get("/export.csv")
async def export_customers(
    session: SessionDep, _: Staff, q: str | None = Query(None, max_length=100),
    segment: str | None = Query(None, pattern=SEGMENT_PATTERN), sort: str = Query("revenue", pattern=SORT_PATTERN),
):
    data = await CustomerService(session).export_csv(q, segment, sort)
    return Response(
        data, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="wcw-customers.csv"', "Cache-Control": "no-store"},
    )


@router.get("/detail", response_model=CustomerDetail)
async def customer_detail(response: Response, session: SessionDep, _: Staff, email: str = Query(max_length=320)):
    """One customer by email address (a query parameter so addresses stay out of URLs in server logs)."""
    response.headers["Cache-Control"] = "no-store"
    return await CustomerService(session).detail(email)
