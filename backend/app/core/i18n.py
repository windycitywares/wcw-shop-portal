"""Languages the storefront offers, and how API responses are localized.

English is the source language stored in the regular columns. Other languages live in
each row's `translations` JSONB ({"es": {"title": ...}, "nl": {...}}); a missing
translation falls back to English, field by field.
"""

DEFAULT_LANGUAGE = "en"
LANGUAGES = ("en", "es", "nl")
LANG_PATTERN = "^(" + "|".join(LANGUAGES) + ")$"

PRODUCT_FIELDS = ("title", "description", "seo_title", "seo_description")
CATEGORY_FIELDS = ("name", "description")
