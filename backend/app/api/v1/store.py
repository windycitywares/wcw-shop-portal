"""Store settings, shipping methods and tax rates (admin)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.commerce import (
    ShippingMethodIn,
    ShippingMethodOut,
    StoreSettingsOut,
    StoreSettingsPatch,
    TaxRateIn,
    TaxRateOut,
)
from app.services.settings import SettingsService
from app.services.store import ShippingService, TaxService

router = APIRouter(prefix="/settings", tags=["settings"])
Manager = Annotated[User, Depends(require(Permission.SETTINGS_MANAGE))]


@router.get("", response_model=StoreSettingsOut)
async def get_settings_(session: SessionDep, _: Manager):
    return await SettingsService(session).admin_view()


@router.patch("", response_model=StoreSettingsOut)
async def update_settings(session: SessionDep, user: Manager, data: StoreSettingsPatch):
    return await SettingsService(session).update(data, user)


@router.get("/shipping", response_model=list[ShippingMethodOut])
async def list_shipping(session: SessionDep, _: Manager):
    return await ShippingService(session).list_all()


@router.post("/shipping", response_model=ShippingMethodOut, status_code=status.HTTP_201_CREATED)
async def create_shipping(session: SessionDep, _: Manager, data: ShippingMethodIn):
    return await ShippingService(session).create(data)


@router.put("/shipping/{method_id}", response_model=ShippingMethodOut)
async def update_shipping(method_id: int, session: SessionDep, _: Manager, data: ShippingMethodIn):
    return await ShippingService(session).update(method_id, data)


@router.delete("/shipping/{method_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shipping(method_id: int, session: SessionDep, _: Manager):
    await ShippingService(session).delete(method_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tax", response_model=list[TaxRateOut])
async def list_tax(session: SessionDep, _: Manager):
    return await TaxService(session).list_all()


@router.post("/tax", response_model=TaxRateOut, status_code=status.HTTP_201_CREATED)
async def create_tax(session: SessionDep, _: Manager, data: TaxRateIn):
    return await TaxService(session).create(data)


@router.put("/tax/{rate_id}", response_model=TaxRateOut)
async def update_tax(rate_id: int, session: SessionDep, _: Manager, data: TaxRateIn):
    return await TaxService(session).update(rate_id, data)


@router.delete("/tax/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tax(rate_id: int, session: SessionDep, _: Manager):
    await TaxService(session).delete(rate_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
