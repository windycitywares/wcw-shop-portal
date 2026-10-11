"""Export the catalog to Excel in the same format the spreadsheet importer reads."""

import io

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.importers.spreadsheet import ATTR_PREFIX, TEMPLATE_COLUMNS
from app.models.category import Category
from app.models.product import Product

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_SAMPLE = {
    "sku": "WCW-001",
    "title": "Example product",
    "description": "Replace this row with your own products.",
    "price": 24.0,
    "quantity": 10,
    "stock_status": "in_stock",
    "status": "draft",
    "category": "Home > Decor",
    "images": "https://example.com/photo-1.jpg|https://example.com/photo-2.jpg",
    "tags": "gift, handmade",
    "attr:Material": "Oak",
    "attr:Color": "Natural|Walnut",
}


def _value(v):
    return "|".join(map(str, v)) if isinstance(v, list) else v


class ExportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def catalog_xlsx(self) -> bytes:
        products = list((await self.session.execute(select(Product).order_by(Product.parent_id.nulls_first(), Product.id))).scalars())
        categories = {c.id: c for c in (await self.session.execute(select(Category))).scalars()}
        skus = {p.id: p.sku for p in products}

        def category_label(cid: int | None) -> str:
            if not cid or cid not in categories:
                return ""
            ids = [int(x) for x in categories[cid].path.split(".")]
            return " > ".join(categories[i].name for i in ids if i in categories)

        attr_names: list[str] = []
        for p in products:
            for k in p.attributes or {}:
                if k not in attr_names:
                    attr_names.append(k)

        rows = []
        for p in products:
            row = {
                "sku": p.sku,
                "title": p.title,
                "description": p.description or "",
                "price": float(p.base_price),
                "compare_at_price": float(p.compare_at_price) if p.compare_at_price is not None else None,
                "currency": p.currency,
                "quantity": p.stock_quantity,
                "stock_status": p.stock_status.value,
                "status": p.status.value,
                "category": category_label(p.category_id) if not p.parent_id else "",
                "images": "|".join(i.get("url", "") for i in p.images or []),
                "tags": ", ".join(p.tags or []),
                "parent_sku": skus.get(p.parent_id, "") if p.parent_id else "",
                "seo_title": p.seo_title or "",
                "seo_description": p.seo_description or "",
            }
            for name in attr_names:
                row[ATTR_PREFIX + name] = _value((p.attributes or {}).get(name, ""))
            rows.append(row)
        return self._workbook(TEMPLATE_COLUMNS + [ATTR_PREFIX + n for n in attr_names], rows)

    @staticmethod
    def template_xlsx() -> bytes:
        columns = TEMPLATE_COLUMNS + ["attr:Material", "attr:Color"]
        return ExportService._workbook(columns, [_SAMPLE])

    @staticmethod
    def _workbook(columns: list[str], rows: list[dict]) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = "Products"
        ws.append(columns)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "C2"
        for row in rows:
            ws.append([row.get(c) for c in columns])
        for col in ws.columns:
            width = max(len(str(c.value or "")) for c in col[:50])
            ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
