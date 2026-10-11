"""Etsy listings export.

Etsy: Shop Manager -> Settings -> Options -> Download Data -> "Download CSV"
(Currently for sale listings). Columns include TITLE, DESCRIPTION, PRICE,
CURRENCY_CODE, QUANTITY, TAGS, MATERIALS, IMAGE1..IMAGE10,
VARIATION 1 TYPE/NAME/VALUES, VARIATION 2 TYPE/NAME/VALUES, SKU.
"""

from decimal import Decimal

from app.importers.base import ImportedProduct, ImportFormatError, ParseResult, ProductImporter
from app.importers.registry import register
from app.importers.tabular import first, parse_decimal, parse_int, read_table, split_list
from app.utils.text import slugify


@register
class EtsyCsvImporter(ProductImporter):
    key = "etsy"
    label = "Etsy listings (CSV)"
    description = (
        "The CSV from Etsy Shop Manager → Settings → Options → Download Data. "
        "Imports titles, descriptions, prices, quantities, tags, materials, variation "
        "options and image links."
    )
    accepted_extensions = (".csv",)
    source = "etsy"

    def parse(self, content: bytes, filename: str) -> ParseResult:
        table = read_table(content, filename, header_hints={"title"})
        if "price" not in table.keys:
            raise ImportFormatError("This doesn't look like an Etsy export (no PRICE column).")

        products: list[ImportedProduct] = []
        warnings: list[str] = []
        for line_no, rec in table.records():
            title = rec.get("title", "").strip()
            if not title:
                warnings.append(f"Row {line_no}: skipped (no title)")
                continue

            attributes: dict = {}
            materials = split_list(rec.get("materials"))
            if materials:
                attributes["Material"] = materials if len(materials) > 1 else materials[0]
            for n in (1, 2):
                name = first(rec, f"variation_{n}_name", f"variation_{n}_type")
                values = split_list(rec.get(f"variation_{n}_values"))
                if name and values:
                    attributes[name.strip()] = values

            images = [rec[f"image{i}"] for i in range(1, 11) if rec.get(f"image{i}")]
            sku = split_list(rec.get("sku"))
            price = parse_decimal(rec.get("price"))
            if price is None:
                warnings.append(f"Row {line_no}: '{title[:40]}' has no price; set to 0")

            products.append(
                ImportedProduct(
                    row=line_no,
                    title=title,
                    sku=sku[0] if sku else None,
                    description=rec.get("description") or None,
                    price=price or Decimal("0"),
                    currency=(rec.get("currency_code") or "USD").upper()[:3],
                    quantity=parse_int(rec.get("quantity")),
                    tags=split_list(rec.get("tags")),
                    attributes=attributes,
                    images=images,
                    # Etsy's export has no listing id; the SKU (or title) identifies re-imports
                    source_ref=sku[0] if sku else slugify(title),
                )
            )
        return ParseResult(source=self.source, products=products, warnings=warnings)
