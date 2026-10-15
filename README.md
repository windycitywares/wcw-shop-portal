# Windy City Wares — e-commerce platform

Storefront + admin for **windycitywares.com**. Spec: [`docs/SPEC.md`](docs/SPEC.md).

| Part | Stack | Folder |
|---|---|---|
| API | Python 3.11+, FastAPI, async SQLAlchemy 2, PostgreSQL 13+ (`JSONB`, no extensions needed), JWT | `backend/` |
| Storefront & admin | Next.js (App Router), React 19, TypeScript, Tailwind CSS v4, Radix UI | `frontend/` |

## What's built

- **Catalog**: unlimited-depth categories (adjacency list + materialized path of ids), products with flexible
  `attributes` (JSONB, GIN-indexed), parent/child **variants**, draft → review → published workflow.
- **Roles (RBAC)**: Admin, Publisher, Author, Customer — permission map in `backend/app/core/permissions.py`.
- **Import / export**: Etsy listings CSV, Amazon Seller Central (All Listings Report or flat file, incl. parent/child
  variants), and a spreadsheet format (Excel/CSV). Preview before importing; re-imports update instead of duplicating.
  Export the whole catalog to Excel, edit, re-import. New sources plug in via `backend/app/importers/`.
- **Storefront**: template layout (Header / main / Footer), mega-menu from the category tree, search, faceted filters
  (price, stock, any attribute), product pages with gallery + variant/option picker, guest cart (local storage).
- **SEO**: server rendering, per-page metadata + canonical URLs, `sitemap.xml`, `robots.txt`, JSON-LD (Organization,
  Product, BreadcrumbList).
- **Accessibility**: semantic landmarks, skip link, visible `focus-visible` rings, labelled controls, accessible
  dialogs/menus (Radix), AA-contrast color tokens, reduced-motion support.
- **Admin** (`/admin`): dashboard counts, product list + editor (with attribute builder), import/export,
  category tree editor, user & role management.

## Run it locally

### 1. Database (PostgreSQL 13+)

```sql
CREATE USER wcw WITH PASSWORD 'wcw';
CREATE DATABASE wcw OWNER wcw;
```

### 2. API

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # then edit DATABASE_URL, JWT_SECRET, ADMIN_EMAIL/PASSWORD
alembic upgrade head            # create tables
python -m app.seed              # admin user + placeholder categories/products
uvicorn app.main:app --reload   # http://localhost:8000/docs
```

Tests: `python -m unittest discover tests`

### 3. Storefront

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev                     # http://localhost:3000  (admin: /admin)
```

## Importing your Etsy shop

1. Etsy → **Shop Manager → Settings → Options → Download Data → Download CSV** (currently for sale listings).
2. Sign in at `/login` with the admin account → **Admin → Import / Export**.
3. Source **Etsy**, choose the CSV, **Preview**, then **Import** (tick *Publish immediately* if you like).
4. Remove the placeholder products: Admin → Products, filter, unpublish/delete the ones from `sample`.

Product photos are linked from Etsy's image CDN (`i.etsystatic.com`).

## Deploying (cPanel shared hosting)

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — includes the HostItBro server details.

## Next steps (not built yet)

- Drag-and-drop category tree (the `/categories/reorder` API is ready).
- Marketplace API connectors (Etsy Open API v3 / Amazon SP-API) for scheduled syncing.
- Owner setup before launch: Stripe live keys, the Illinois sales-tax rate (Admin → Settings), and a review of the
  returns, privacy and terms drafts.
