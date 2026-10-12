"""Apply a language to API output models (in place). See app/core/i18n.py."""

from app.core.i18n import CATEGORY_FIELDS, DEFAULT_LANGUAGE, PRODUCT_FIELDS
from app.schemas.category import CategoryDetail, CategoryNode, CategoryOut
from app.schemas.common import Page
from app.schemas.product import ProductDetail, ProductOut


def _apply(obj, fields: tuple[str, ...], lang: str | None, keep: bool) -> None:
    t = (obj.translations or {}).get(lang) if lang and lang != DEFAULT_LANGUAGE else None
    if t:
        translated_main = bool(t.get(fields[0]))
        for field in fields:
            value = t.get(field)
            if value:
                setattr(obj, field, value)
            elif translated_main and field.startswith("seo_"):
                # English SEO text next to a translated title would mix languages;
                # clear it so pages fall back to the translated title/description.
                setattr(obj, field, None)
    if not keep:
        obj.translations = {}


def category(c: CategoryOut | None, lang: str | None, keep: bool = False) -> None:
    if c is None:
        return
    _apply(c, CATEGORY_FIELDS, lang, keep)
    if isinstance(c, CategoryNode):
        for child in c.children:
            category(child, lang, keep)
    if isinstance(c, CategoryDetail):
        for other in (*c.breadcrumb, *c.children):
            category(other, lang, keep)


def product(p: ProductOut, lang: str | None, keep: bool = False) -> None:
    _apply(p, PRODUCT_FIELDS, lang, keep)
    if isinstance(p, ProductDetail):
        for v in p.variants:
            _apply(v, PRODUCT_FIELDS, lang, keep)
        category(p.category, lang, keep)
        for c in p.breadcrumb:
            category(c, lang, keep)


def page(result: Page[ProductOut], lang: str | None, keep: bool = False) -> Page[ProductOut]:
    for p in result.items:
        product(p, lang, keep)
    return result
