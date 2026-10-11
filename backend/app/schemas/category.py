from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CategoryOut(ORMModel):
    id: int
    parent_id: int | None
    name: str
    slug: str
    description: str | None
    image_url: str | None
    sort_order: int
    is_active: bool
    depth: int


class CategoryNode(CategoryOut):
    children: list["CategoryNode"] = []


class CategoryDetail(CategoryOut):
    breadcrumb: list[CategoryOut]
    children: list[CategoryOut]


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=220, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    parent_id: int | None = None
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=1000)
    sort_order: int = 0
    is_active: bool = True


class CategoryUpdate(BaseModel):
    """Only fields that are sent are changed; send parent_id=null to move to the top level."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=220, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    parent_id: int | None = None
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=1000)
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryReorderItem(BaseModel):
    id: int
    parent_id: int | None
    sort_order: int


class CategoryReorder(BaseModel):
    items: list[CategoryReorderItem]


CategoryNode.model_rebuild()
