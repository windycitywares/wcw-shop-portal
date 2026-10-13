# Main site — windycitywares.com

A single static landing page for `public_html` on the main domain. It shows every collection and links
each card to its page on the shop (`https://shop.windycitywares.com/category/<slug>`, or `/es/…` and
`/nl/…` for Spanish and Dutch visitors). Language follows the browser like the shop does, with an
EN / ES / NL switch.

Files: `index.html` (self-contained: styles, logo SVGs, script) and `brand/` (favicon).

## Publish

1. cPanel → File Manager → `public_html`: rename the current `index.html` to `index.old.html`.
2. Upload `main-site/index.html` and the `main-site/brand/` folder into `public_html`.

Or from cPanel → Terminal:

```bash
cd ~/repos/wcw-portal && git pull
cp ~/public_html/index.html ~/public_html/index.old.html
cp main-site/index.html ~/public_html/ && mkdir -p ~/public_html/brand && cp main-site/brand/* ~/public_html/brand/
```

## Updating collections

The collection list is the `COLLECTIONS` array near the bottom of `index.html` (slug, cover photo folder
on media.windycitywares.com, design count, and the name and description in English, Spanish and Dutch).
Add, remove or edit an entry there when the shop's categories change. The slug must match the category
slug in the shop admin.

When the store moves to the main domain (docs/DEPLOYMENT.md → "Go live"), this page is replaced by the
store's own home page.
