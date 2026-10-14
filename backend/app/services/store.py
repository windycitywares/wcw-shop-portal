"""Shipping methods and tax rates."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.commerce import ShippingMethod, TaxRate
from app.repositories.commerce import ShippingRepository, TaxRepository
from app.schemas.commerce import ShippingMethodIn, TaxRateIn


class ShippingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ShippingRepository(session)

    async def list_all(self) -> list[ShippingMethod]:
        return await self.repo.list_all()

    async def _get(self, method_id: int) -> ShippingMethod:
        method = await self.repo.get(method_id)
        if method is None:
            raise NotFoundError("Shipping method not found")
        return method

    async def create(self, data: ShippingMethodIn) -> ShippingMethod:
        method = self.repo.add(ShippingMethod(**data.model_dump()))
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("A shipping method with that code already exists.") from exc
        return method

    async def update(self, method_id: int, data: ShippingMethodIn) -> ShippingMethod:
        method = await self._get(method_id)
        for field, value in data.model_dump().items():
            setattr(method, field, value)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("A shipping method with that code already exists.") from exc
        return method

    async def delete(self, method_id: int) -> None:
        await self.repo.delete(await self._get(method_id))  # orders keep the name they were placed with
        await self.session.commit()


class TaxService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TaxRepository(session)

    async def list_all(self) -> list[TaxRate]:
        return await self.repo.list_all()

    async def _get(self, rate_id: int) -> TaxRate:
        rate = await self.repo.get(rate_id)
        if rate is None:
            raise NotFoundError("Tax rate not found")
        return rate

    async def create(self, data: TaxRateIn) -> TaxRate:
        rate = self.repo.add(TaxRate(**data.model_dump()))
        await self.session.commit()
        return rate

    async def update(self, rate_id: int, data: TaxRateIn) -> TaxRate:
        rate = await self._get(rate_id)
        for field, value in data.model_dump().items():
            setattr(rate, field, value)
        await self.session.commit()
        return rate

    async def delete(self, rate_id: int) -> None:
        await self.repo.delete(await self._get(rate_id))
        await self.session.commit()
