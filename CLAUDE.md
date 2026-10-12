# CLAUDE.md — working notes for this repo

Windy City Wares e-commerce platform (windycitywares.com). Full spec: `docs/SPEC.md`. Hosting: HostItBro
cPanel shared hosting — Python 3.11, Node 20/22, PostgreSQL 13, no DB extensions (see `docs/DEPLOYMENT.md`).
Product source: Etsy shop WindyCityWaresUS. Repo: github.com/windycitywares/wcw-portal.
Rollout: build-out runs on **shop.windycitywares.com** (API on api.windycitywares.com) while the main
domain keeps its existing `index.html`; move to the main domain at launch (`docs/DEPLOYMENT.md` →
"Go live"). Keep `NEXT_PUBLIC_ALLOW_INDEXING=false` until then.

## Layout

- `backend/` — FastAPI API (Python 3.11+, async SQLAlchemy 2, asyncpg, PostgreSQL)
  - `app/core/` config, db engine, enums, **permissions (RBAC map)**, security (JWT/bcrypt), domain exceptions
  - `app/models/` ORM models · `app/schemas/` Pydantic I/O · `app/repositories/` DB queries only
  - `app/services/` business rules (permissions, workflow, imports) — routes stay thin
  - `app/importers/` one class per import source, registered with `@register`; no DB access
  - `app/api/v1/` routers · `migrations/` Alembic (initial schema is `migrations/sql/0001_initial.sql`)
- `frontend/` — Next.js App Router + Tailwind v4
  - `src/app/layout.tsx` = template (Header / main / Footer); theme tokens in `src/app/globals.css`
  - `src/components/ui/` primitives · `layout/` header, mega-menu, footer · `catalog/` · `cart/` · `admin/`
  - `src/lib/api.ts` server-side fetches (cached) · `src/lib/client-api.ts` browser fetches with JWT

## Commands

```bash
# backend (from backend/, venv active)
uvicorn app.main:app --reload
alembic upgrade head
python -m app.seed
python -m unittest discover tests

# frontend (from frontend/)
npm run dev
npm run build
npm run typecheck
```

## Conventions

- Routes depend on **permissions**, never role names: `Depends(require(Permission.X))`.
- Authors can create/edit their own drafts; only Publisher/Admin can publish or archive.
- Categories: `path` is a plain-text chain of ids ("1.4.9"), matched by prefix via
  `repositories/paths.subtree_of()`. **Don't use `ltree` or any PostgreSQL extension** — the HostItBro
  server doesn't have them (spec section 5 adapted for this). Never write `path` by hand; use
  `CategoryService` (`create`, `_move`, `ensure_path`). Reserve ids with `CategoryRepository.next_id()`.
- Products: put marketplace-specific data in `attributes` (JSONB), not new columns. List values
  (`["Red","Blue"]`) are options; scalars are details. Variants = child rows with `parent_id`.
- New import source: add `app/importers/<name>.py` with a `ProductImporter` subclass + `@register`,
  import it in `app/importers/__init__.py`, add a parser test in `tests/test_importers.py`.
- Schema change: edit the model, then `alembic revision --autogenerate -m "..."` and review it.
- Async ORM relationships are `lazy="raise"`; load with `selectinload(...)` explicitly.
- Frontend: storefront pages are Server Components that call `src/lib/api.ts`; admin pages are client
  components using `apiFetch`. Every control needs a label; keep `focus-visible` styles.
- Images from hosts other than those in `next.config.ts` are shown unoptimized (see `ProductImage`).
- Email: `app/core/mailer.py` (`await mailer.send(Mail(...))`); CAPTCHA: `await captcha.verify(token, ip)`.
  Both skip when unconfigured in development — see docs/DEPLOYMENT.md → "Email and CAPTCHA".
- Server entry point is `backend/wsgi.py` (cPanel generates `passenger_wsgi.py` to load it — never commit one).
- Deploys are automatic: merge to `main` → Actions builds the storefront → server cron (`deploy/auto-deploy.sh`)
  updates API + storefront within ~10 min. Frontend changes must pass `npm run build` + `tsc` in Actions.

## Not built yet

Checkout + payments (Stripe), orders admin, contact-messages admin, server-side cart, wishlist, site settings,
drag-and-drop category UI, marketplace API sync. See README "Next steps".
