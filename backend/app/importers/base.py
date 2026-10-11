"""Importer contract.

Every marketplace/file format is a small class that turns uploaded bytes into
a list of `ImportedProduct`s. It never touches the database — the
ImportService does that — so adding a new source (Shopify, eBay, WooCommerce,
an API client...) means writing one parser and registering it.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, ClassVar

from app.core.enums import ContentStatus, StockStatus


@dataclass
class ImportedVariant:
    sku: str | None
    title: str | None = None
    price: Decimal | None = None
    quantity: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    images: list[str] = field(default_factory=list)
    source_ref: str | None = None


@dataclass
class ImportedProduct:
    title: str
    row: int
    sku: str | None = None
    description: str | None = None
    price: Decimal = Decimal("0")
    compare_at_price: Decimal | None = None
    currency: str = "USD"
    quantity: int | None = None
    stock_status: StockStatus | None = None
    images: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    category_path: list[str] | None = None
    status: ContentStatus | None = None
    source_ref: str | None = None
    parent_sku: str | None = None  # variant whose parent is already in the catalog
    seo_title: str | None = None
    seo_description: str | None = None
    variants: list[ImportedVariant] = field(default_factory=list)


@dataclass
class ParseResult:
    source: str
    products: list[ImportedProduct]
    warnings: list[str] = field(default_factory=list)


class ImportFormatError(ValueError):
    """The file isn't in the format this importer expects."""


class ProductImporter(ABC):
    key: ClassVar[str]
    label: ClassVar[str]
    description: ClassVar[str]
    accepted_extensions: ClassVar[tuple[str, ...]]
    # The `products.source` value written for rows from this importer
    source: ClassVar[str]

    @abstractmethod
    def parse(self, content: bytes, filename: str) -> ParseResult: ...
