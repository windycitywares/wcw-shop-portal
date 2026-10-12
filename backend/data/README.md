# Catalog data

`etsy_catalog.json` — the store's catalog as collected from the Etsy shop
[WindyCityWaresUS](https://www.etsy.com/shop/WindyCityWaresUS) on 2026-10-11 (105 listings).

Load it (downloads every photo into `MEDIA_ROOT`, replaces all products and categories):

```bash
cd backend && python -m app.scripts.import_catalog --file data/etsy_catalog.json --replace
```

Re-running without `--replace` updates the same products (matched by Etsy listing id) and only
downloads photos that aren't already on disk. `--dry-run` previews the categories.

## Format

```jsonc
{
  "categories": [
    { "slug": "cremation-urns", "name": "Cremation Urns", "parent": null, "sort_order": 0, "description": "…" },
    { "slug": "faith-angels", "name": "Faith & Angels", "parent": "cremation-urns", "sort_order": 3, "description": "…" }
  ],
  "products": [
    {
      "source": "etsy", "source_ref": "<Etsy listing id>", "sku": "ETSY-<id>", "slug": "…",
      "title": "Star Cremation Urn", "seo_title": "<original Etsy title>", "seo_description": "…",
      "description": "…", "category": "celestial",
      "price": "68.00", "compare_at_price": "80.00", "quantity": 7,
      "attributes": { "Material": "Aluminum", "Finish": "High-gloss enamel", "Size": ["3 inch Keepsake", "…"] },
      "tags": ["cremation urn", "stars & cosmos"],
      "images": [{ "url": "https://i.etsystatic.com/…/il_1588xN….jpg", "alt": "…" }],
      "variants": [{ "name": "3 inch Keepsake", "price": "68.00", "compare_at_price": "80.00" }],
      "etsy_url": "https://www.etsy.com/listing/<id>"
    }
  ]
}
```

Categories were assigned by theme from the listing titles (the Etsy shop has no sections).
Change a product's `"category"` here, or move it in Admin → Products, to recategorise.

## Translations

`translations/es.json` (Spanish) and `translations/nl.json` (Dutch) hold the storefront's product
and category text in those languages. The import loads them automatically from this folder:

```jsonc
{
  "categories": { "<slug>": { "name": "…", "description": "…" } },
  "products":   { "<Etsy listing id>": { "title": "…", "description": "…" } }
}
```

Anything missing falls back to English, field by field. Product details, size names and filter
labels are translated in the storefront itself (`frontend/src/i18n/dictionaries`).
