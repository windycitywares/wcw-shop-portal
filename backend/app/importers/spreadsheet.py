"""The site's own spreadsheet format (Excel or CSV) — also what /products/export
produces, so the catalog can be bulk-edited in Excel and re-imported.

Columns (case-insensitive; only `title` is required):
  sku, title, description, price, compare_at_price, currency, quantity,
  stock_status, status, category ("Home > Decor > Vases"), images (one URL per
  line, or separated by | ), tags (comma separated), parent_sku,
  seo_title, seo_description
  attr:<Name>  -> any number of attribute columns, e.g. "attr:Material".
               Use | to give several values: "Red|Blue".
"""

from decimal import Decimal

from app.core.enums import ContentStatus, StockStatus
from app.importers.base import ImportedProduct, ImportedVariant, ParseResult, ProductImporter
from app.importers.registry import register
from app.importers.tabular import normalize_header, parse_decimal, parse_int, read_table, split_list

TEMPLATE_COLUMNS = [
    "sku",
    "title",
    "description",
    "price",
    "compare_at_price",
    "currency",
    "quantity",
    "stock_status",
    "status",
    "category",
    "images",
    "tags",
    "parent_sku",
    "seo_title",
    "seo_description",
]
ATTR_PREFIX = "attr:"


def _enum(enum_cls, value: str):
    v = normalize_header(value)
    try:
        return enum_cls(v) if v else None
    except ValueError:
        return None


@register
class SpreadsheetImporter(ProductImporter):
    key = "spreadsheet"
    label = "Spreadsheet (Excel / CSV template)"
    description = (
        "This site's template — download it from the import page, or export your catalog, "
        "edit in Excel and import it back. Matches existing products by SKU."
    )
    accepted_extensions = (".xlsx", ".csv")
    source = "spreadsheet"

    def parse(self, content: bytes, filename: str) -> ParseResult:
        table = read_table(content, filename, header_hints={"title"})
        warnings: list[str] = []
        by_sku: dict[str, ImportedProduct] = {}
        products: list[ImportedProduct] = []
        pending_children: list[tuple[str, ImportedProduct]] = []

        for (line_no, rec), (_, raw) in zip(table.records(), table.raw_records()):
            title = rec.get("title", "")
            if not title:
                warnings.append(f"Row {line_no}: skipped (no title)")
                continue
            attributes: dict = {}
            for header, value in raw.items():
                if header.lower().startswith(ATTR_PREFIX) and value:
                    name = header[len(ATTR_PREFIX) :].strip()
                    values = split_list(value, "|")
                    attributes[name] = values if len(values) > 1 else values[0]

            category = rec.get("category", "")
            sep = ">" if ">" in category else "/"
            stock_status = _enum(StockStatus, rec.get("stock_status", ""))
            status = _enum(ContentStatus, rec.get("status", ""))
            if rec.get("status") and status is None:
                warnings.append(f"Row {line_no}: unknown status '{rec['status']}', using draft")

            sku = rec.get("sku") or None
            item = ImportedProduct(
                row=line_no,
                title=title,
                sku=sku,
                description=rec.get("description") or None,
                price=parse_decimal(rec.get("price")) or Decimal("0"),
                compare_at_price=parse_decimal(rec.get("compare_at_price")),
                currency=(rec.get("currency") or "USD").upper()[:3],
                quantity=parse_int(rec.get("quantity")),
                stock_status=stock_status,
                status=status,
                category_path=split_list(category, sep) or None,
                images=split_list(rec.get("images"), "|\n"),
                tags=split_list(rec.get("tags")),
                attributes=attributes,
                source_ref=sku,
                seo_title=rec.get("seo_title") or None,
                seo_description=rec.get("seo_description") or None,
            )
            parent_sku = rec.get("parent_sku")
            if parent_sku:
                pending_children.append((parent_sku, item))
            else:
                products.append(item)
                if sku:
                    by_sku[sku] = item

        for parent_sku, item in pending_children:
            parent = by_sku.get(parent_sku)
            if parent:
                parent.variants.append(
                    ImportedVariant(
                        sku=item.sku,
                        title=item.title,
                        price=item.price,
                        quantity=item.quantity,
                        attributes=item.attributes,
                        images=item.images,
                        source_ref=item.sku,
                    )
                )
            else:
                item.parent_sku = parent_sku  # resolved against the catalog by the service
                products.append(item)
        return ParseResult(source=self.source, products=products, warnings=warnings)
