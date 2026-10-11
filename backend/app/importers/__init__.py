"""Product importers. Importing a module registers it (see registry.register).

To add a source: create a module with a `ProductImporter` subclass decorated
with `@register`, then import it below.
"""

from app.importers import amazon, etsy, spreadsheet  # noqa: F401  (registration side effect)
from app.importers.base import (
    ImportedProduct,
    ImportedVariant,
    ImportFormatError,
    ParseResult,
    ProductImporter,
)
from app.importers.registry import get_importer, list_importers

__all__ = [
    "ImportFormatError",
    "ImportedProduct",
    "ImportedVariant",
    "ParseResult",
    "ProductImporter",
    "get_importer",
    "list_importers",
]
