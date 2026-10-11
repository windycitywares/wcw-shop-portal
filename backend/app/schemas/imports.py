from typing import Any

from pydantic import BaseModel


class ImporterInfo(BaseModel):
    key: str
    label: str
    description: str
    accepted_extensions: list[str]


class PreviewRow(BaseModel):
    row: int
    sku: str | None
    title: str
    price: float
    quantity: int | None
    images: int
    variants: int
    category: str | None
    attributes: dict[str, Any]


class ImportPreview(BaseModel):
    source: str
    total: int
    rows: list[PreviewRow]
    warnings: list[str]


class ImportRowError(BaseModel):
    row: int
    title: str | None
    error: str


class ImportSummary(BaseModel):
    source: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    variants: int = 0
    errors: list[ImportRowError] = []
    warnings: list[str] = []
