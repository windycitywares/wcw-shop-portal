from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import ContentStatus, StockStatus
from app.schemas.category import CategoryOut
from app.schemas.common import Money, ORMModel

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class ProductImage(BaseModel):
    url: str = Field(max_length=2000)
    alt: str | None = Field(default=None, max_length=300)


class ProductFields(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    base_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    compare_at_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    stock_status: StockStatus = StockStatus.IN_STOCK
    stock_quantity: int | None = Field(default=None, ge=0)
    category_id: int | None = None
    attributes: dict[str, Any] = {}
    images: list[ProductImage] = []
    tags: list[str] = []
    seo_title: str | None = Field(default=None, max_length=300)
    seo_description: str | None = Field(default=None, max_length=500)


class ProductCreate(ProductFields):
    sku: str = Field(min_length=1, max_length=100)
    slug: str | None = Field(default=None, max_length=255, pattern=SLUG_PATTERN)
    parent_id: int | None = None
    status: ContentStatus = ContentStatus.DRAFT


class ProductUpdate(BaseModel):
    """Partial update: only fields that are sent are changed."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    sku: str | None = Field(default=None, min_length=1, max_length=100)
    slug: str | None = Field(default=None, max_length=255, pattern=SLUG_PATTERN)
    description: str | None = None
    base_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    compare_at_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    stock_status: StockStatus | None = None
    stock_quantity: int | None = Field(default=None, ge=0)
    category_id: int | None = None
    attributes: dict[str, Any] | None = None
    images: list[ProductImage] | None = None
    tags: list[str] | None = None
    status: ContentStatus | None = None
    seo_title: str | None = Field(default=None, max_length=300)
    seo_description: str | None = Field(default=None, max_length=500)


class StatusChange(BaseModel):
    status: ContentStatus


class ProductOut(ORMModel):
    id: int
    parent_id: int | None
    category_id: int | None
    sku: str
    slug: str
    title: str
    description: str | None
    base_price: Money
    compare_at_price: Money | None
    currency: str
    stock_status: StockStatus
    stock_quantity: int | None
    attributes: dict[str, Any]
    images: list[ProductImage]
    tags: list[str]
    status: ContentStatus
    source: str
    seo_title: str | None
    seo_description: str | None
    created_by_id: int | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProductDetail(ProductOut):
    variants: list[ProductOut]
    category: CategoryOut | None
    breadcrumb: list[CategoryOut]


class FacetValue(BaseModel):
    value: str
    count: int


class AttributeFacet(BaseModel):
    key: str
    values: list[FacetValue]


class Facets(BaseModel):
    price_min: Money | None
    price_max: Money | None
    attributes: list[AttributeFacet]
