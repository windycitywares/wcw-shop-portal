"""Reports and improvement suggestions for the owner.

Every endpoint takes an optional date range (`start`, `end`; default: the last 30 days up to today, store time) and
answers with plain numbers; nothing here changes data. Definitions of each figure are in `services/reports/sql.py`.
"""

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response

from app.api.deps import SessionDep, require
from app.core.exceptions import PermissionDeniedError
from app.core.permissions import Permission, has_permission
from app.domain.timeutil import DateRange, resolve_range
from app.models.user import User
from app.services.reports.service import ReportService

router = APIRouter(prefix="/admin/reports", tags=["admin: reports"])
Staff = Annotated[User, Depends(require(Permission.REPORTS_VIEW))]
CustomerStaff = Annotated[User, Depends(require(Permission.REPORTS_VIEW, Permission.CUSTOMERS_VIEW))]
Report = dict[str, Any]


def _range(start: date | None = None, end: date | None = None) -> DateRange:
    return resolve_range(start, end, default_days=30)


Range = Annotated[DateRange, Depends(_range)]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("/overview", response_model=Report)
async def overview(response: Response, session: SessionDep, _: Staff, rng: Range):
    """The dashboard: key numbers with last period's for comparison, a trend, what needs attention, and the top suggestions."""
    _private(response)
    return await ReportService(session).overview(rng)


@router.get("/sales", response_model=Report)
async def sales(response: Response, session: SessionDep, _: Staff, rng: Range):
    _private(response)
    return await ReportService(session).sales(rng)


@router.get("/products", response_model=Report)
async def products(response: Response, session: SessionDep, _: Staff, rng: Range):
    _private(response)
    return await ReportService(session).products(rng)


@router.get("/traffic", response_model=Report)
async def traffic(response: Response, session: SessionDep, _: Staff, rng: Range):
    _private(response)
    return await ReportService(session).traffic(rng)


@router.get("/funnel", response_model=Report)
async def funnel(response: Response, session: SessionDep, _: Staff, rng: Range):
    _private(response)
    return await ReportService(session).funnel(rng)


@router.get("/behavior", response_model=Report)
async def behavior(response: Response, session: SessionDep, _: Staff, rng: Range):
    _private(response)
    return await ReportService(session).behavior(rng)


@router.get("/performance", response_model=Report)
async def performance(response: Response, session: SessionDep, _: Staff, rng: Range):
    _private(response)
    return await ReportService(session).performance(rng)


@router.get("/customers", response_model=Report)
async def customers(response: Response, session: SessionDep, _: CustomerStaff, rng: Range):
    """Contains customer email addresses, so it needs the customers permission as well."""
    _private(response)
    return await ReportService(session).customers(rng)


@router.get("/promotions", response_model=Report)
async def promotions(response: Response, session: SessionDep, _: Staff, rng: Range):
    _private(response)
    return await ReportService(session).promotions(rng)


@router.get("/inventory", response_model=Report)
async def inventory(response: Response, session: SessionDep, _: Staff):
    _private(response)
    return await ReportService(session).inventory()


@router.get("/catalog", response_model=Report)
async def catalog(response: Response, session: SessionDep, _: Staff):
    _private(response)
    return await ReportService(session).catalog()


@router.get("/suggestions", response_model=Report)
async def suggestions(response: Response, session: SessionDep, _: Staff, rng: Range):
    """Recommendations drawn from the numbers above, most urgent first."""
    _private(response)
    return await ReportService(session).suggestions(rng)


ExportKind = Literal["sales", "products", "traffic", "funnel", "customers", "promotions", "inventory", "catalog"]


@router.get("/export/{kind}.csv")
async def export(kind: ExportKind, session: SessionDep, user: Staff, rng: Range):
    """The same figures as the report, as a spreadsheet file."""
    if kind == "customers" and not has_permission(user.role, Permission.CUSTOMERS_VIEW):
        raise PermissionDeniedError("You don't have permission to do that")
    name, data = await ReportService(session).export(kind, rng)
    return Response(
        data, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )
