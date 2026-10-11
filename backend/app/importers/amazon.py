"""Amazon Seller Central files.

Supports two common downloads:
* "All Listings Report" (Inventory Reports, tab-delimited .txt):
  item-name, item-description, seller-sku, price, quantity, asin1, image-url...
* Category inventory / flat-file template (.txt, .csv or .xlsx):
  item_sku, item_name, standard_price, quantity, main_image_url,
  other_image_url1..8, product_description, bullet_point1..5, brand_name,
  parent_child, parent_sku, color_name, size_name, material_type...
  Parent/child rows become a product with variants.
"""

from decimal import Decimal

from app.importers.base import (
    ImportedProduct,
    ImportedVariant,
    ImportFormatError,
    ParseResult,
    ProductImporter,
)
from app.importers.registry import register
from app.importers.tabular import first, parse_decimal, parse_int, read_table

_ATTRIBUTE_COLUMNS = {
    "brand_name": "Brand",
    "brand": "Brand",
    "color_name": "Color",
    "color": "Color",
    "size_name": "Size",
    "size": "Size",
    "material_type": "Material",
    "material": "Material",
    "style_name": "Style",
    "pattern_name": "Pattern",
    "item_shape": "Shape",
}
_VARIATION_ATTRS = ("Color", "Size", "Material", "Style", "Pattern")


@register
class AmazonImporter(ProductImporter):
    key = "amazon"
    label = "Amazon Seller Central (listings report / flat file)"
    description = (
        "Amazon's 'All Listings Report' (.txt) or a category inventory flat file "
        "(.txt/.csv/.xlsx). Parent/child rows are imported as one product with variants."
    )
    accepted_extensions = (".txt", ".tsv", ".csv", ".xlsx")
    source = "amazon"

    def parse(self, content: bytes, filename: str) -> ParseResult:
        table = read_table(
            content,
            filename,
            header_hints={"item_sku", "seller_sku", "contribution_sku", "item_name"},
        )
        keys = set(table.keys)
        if not keys & {"item_sku", "seller_sku", "contribution_sku", "sku"}:
            raise ImportFormatError("This doesn't look like an Amazon file (no SKU column).")

        warnings: list[str] = []
        parents: dict[str, ImportedProduct] = {}
        children: list[tuple[int, str, dict]] = []
        products: list[ImportedProduct] = []

        for line_no, rec in table.records():
            sku = first(rec, "item_sku", "seller_sku", "contribution_sku", "sku")
            title = first(rec, "item_name", "title", "product_name")
            if not sku and not title:
                continue
            relation = rec.get("parent_child", "").lower()
            parent_sku = rec.get("parent_sku", "")
            if relation == "child" and parent_sku:
                children.append((line_no, parent_sku, rec))
                continue
            if not title:
                warnings.append(f"Row {line_no}: SKU {sku} skipped (no title)")
                continue
            product = self._to_product(line_no, sku, title, rec)
            if relation == "parent":
                parents[sku] = product
            products.append(product)

        for line_no, parent_sku, rec in children:
            sku = first(rec, "item_sku", "seller_sku", "contribution_sku", "sku")
            parent = parents.get(parent_sku)
            attrs = self._attributes(rec)
            if parent is None:
                # Parent not in this file: attach to an existing catalog product if there is one.
                title = first(rec, "item_name", "title") or sku
                product = self._to_product(line_no, sku, title, rec)
                product.parent_sku = parent_sku
                products.append(product)
                continue
            parent.variants.append(
                ImportedVariant(
                    sku=sku,
                    title=first(rec, "item_name", "title") or None,
                    price=parse_decimal(first(rec, "standard_price", "price", "your_price")),
                    quantity=parse_int(rec.get("quantity")),
                    attributes={k: v for k, v in attrs.items() if k in _VARIATION_ATTRS},
                    images=self._images(rec),
                    source_ref=sku or None,
                )
            )
            # Surface variation options on the parent for filtering, e.g. Color: [Red, Blue]
            for k in _VARIATION_ATTRS:
                if k in attrs:
                    current = parent.attributes.get(k, [])
                    current = current if isinstance(current, list) else [current]
                    if attrs[k] not in current:
                        parent.attributes[k] = current + [attrs[k]]

        for p in parents.values():
            if p.price == 0 and p.variants:
                prices = [v.price for v in p.variants if v.price is not None]
                if prices:
                    p.price = min(prices)
        return ParseResult(source=self.source, products=products, warnings=warnings)

    # -- helpers ---------------------------------------------------------
    def _attributes(self, rec: dict[str, str]) -> dict[str, str]:
        attrs: dict[str, str] = {}
        for col, name in _ATTRIBUTE_COLUMNS.items():
            if rec.get(col) and name not in attrs:
                attrs[name] = rec[col]
        asin = first(rec, "asin1", "asin", "external_product_id")
        if asin:
            attrs["ASIN"] = asin
        return attrs

    def _images(self, rec: dict[str, str]) -> list[str]:
        cols = ["main_image_url", "main_product_image_locator", "image_url"] + [
            f"other_image_url{i}" for i in range(1, 9)
        ] + [f"other_product_image_locator_{i}" for i in range(1, 9)]
        seen: list[str] = []
        for c in cols:
            v = rec.get(c, "")
            if v.startswith("http") and v not in seen:
                seen.append(v)
        return seen

    def _to_product(self, line_no: int, sku: str, title: str, rec: dict[str, str]) -> ImportedProduct:
        description = first(rec, "product_description", "item_description", "description")
        bullets = [rec[f"bullet_point{i}"] for i in range(1, 6) if rec.get(f"bullet_point{i}")]
        bullets += [rec[f"bullet_point_{i}"] for i in range(1, 6) if rec.get(f"bullet_point_{i}")]
        if bullets:
            description = (description + "\n\n" if description else "") + "\n".join(f"• {b}" for b in bullets)
        keywords = first(rec, "generic_keywords", "search_terms")
        attrs = self._attributes(rec)
        return ImportedProduct(
            row=line_no,
            title=title,
            sku=sku or None,
            description=description or None,
            price=parse_decimal(first(rec, "standard_price", "price", "your_price", "list_price")) or Decimal("0"),
            currency=(rec.get("currency") or "USD").upper()[:3],
            quantity=parse_int(rec.get("quantity")),
            images=self._images(rec),
            tags=[t for t in keywords.replace(",", " ").split() if t][:20] if keywords else [],
            attributes=attrs,
            source_ref=attrs.get("ASIN") or sku or None,
        )
