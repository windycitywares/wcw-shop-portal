# Working in batches (small PRs)

Owner's instruction, for every session that works on this repo (people or Claude):

> Work in batches and keep opening smaller PRs. Making all changes in one shot exhausts the session limit.

## The rules

1. **One batch = one focused PR.** A batch is one layer or one feature area that can be reviewed in a few minutes
   (aim for under ~1,500 changed lines, excluding generated files). Never hold weeks of work in one branch.
2. **Every PR is green and safe on its own.** It must pass CI and be safe to deploy by itself, even if the next PR
   never lands (e.g. a new NOT NULL column gets a database default so the code already on the server keeps working).
3. **Commit and push early.** Don't leave work uncommitted in the working tree across a long session; push the branch
   and open the PR (draft is fine) as soon as a batch is done, so CI runs and nothing is lost if a session ends.
4. **Stack when needed, base on `main` when possible.** If batch N needs batch N-1, branch from it and say so in the
   PR description ("Depends on #12 — merge that first"). Merge in order.
5. **Finish the batch, then report.** After each PR: one short status message to the owner (what the PR does, what's
   next). Then start the next batch, or stop if the session is running long.
6. **Write the plan down.** Keep the remaining batches listed below (update the list as PRs merge), so a new session can
   pick up the next batch without re-reading everything.
7. **Read only what the batch needs.** Don't re-read the whole codebase at the start of each batch; this file, `CLAUDE.md`
   and the files the batch touches are enough.

## Branch and PR naming

- Branch: `feat/<area>-<n>-<short-name>`, e.g. `feat/commerce-1-data-layer`.
- PR title: `<Area> <n>/<total>: <what it does>`, e.g. `Commerce 1/5: data layer (migrations, models, domain rules)`.

## Current plan: commerce, promotions, tracking and reports

Status as of 2026-10-15. Merge in the order listed; only merge a PR once its CI is green.

Backend:

| # | Batch | Contents | PR |
|---|-------|----------|----|
| 1 | Data layer | Migrations 0006–0008, models, core (permissions, limits, config), pure domain rules + unit tests | #19 + fix #20 (merged) |
| 2 | Pricing and promotions API | Store settings, sales, coupons (incl. bulk generation), cart offers, cart quote, sale prices on products | #21 (merged) |
| 3 | Checkout and orders | Checkout, payments (Stripe, pay later), order emails, stock, orders admin, abandoned carts | #22 (merged) |
| 4 | Engagement | Reviews, wishlist, back-in-stock, newsletter + welcome offer, customers, email campaigns | #23 (merged) |
| 5 | Tracking, reports, jobs | Consent-based analytics, report APIs, KPIs + suggestions, scheduled jobs, integration tests | #24 (merged) |

Storefront:

| # | Batch | PR |
|---|-------|----|
| 1 | Sale prices, badges, ratings, Deals page, announcement bar | #25 (merged) |
| 2 | Server-priced cart, discount codes, free-shipping progress, cart recovery links | #26 (merged) |
| 3 | Checkout + private order page | #27 (merged; fix #28) |
| 4 | Order history, find my order, unsubscribe page | #29 (merged) |
| 5 | Product reviews, wishlist hearts, notify-me, recently viewed, also bought | merged |
| 6 | Consent banner + behaviour tracking (needs backend #24) | merged |
| 7 | Info pages: FAQ, shipping, returns, privacy, terms (legal text needs the owner's review) | merged |

Admin:

| # | Batch | PR |
|---|-------|----|
| 1 | Navigation + dashboard (KPIs, attention list, suggestions) | merged |
| 2 | Orders (list, detail, fulfilment, refunds, CSV) | merged |
| 3 | Promotions: sales, coupons (bulk), cart offers | #36 (merged) |
| 4 | Customers, email campaigns, abandoned carts | #37 (merged) |
| 5 | Review moderation, store settings, audit log | #38 (merged) |
| 6a | Analytics: suggestions, sales, products | #39 (merged) |
| 6b | Analytics: traffic, funnel, behavior, site speed | #40 (merged) |
| 6c | Analytics: customers, promotions, inventory, catalog health | #41 |
| 7a | Contact inbox API (migration 0009) | #42 |
| 7b | Contact inbox admin page | #43 (stacked on #42) |

## CRM sync (with crm.windycitywares.com, started 2026-10-16)

The CRM's plan is in `wcw-crm-portal/docs/WORKING_IN_BATCHES.md` (M2); these are the shop-side batches.

| # | Batch | Contents | PR |
|---|-------|----------|----|
| 1 | Events to the CRM | `crm_outbox` (migration 0014), ORM hook records order/account/newsletter changes in the same transaction, `crm_sync` job signs and posts them with retries; off until `CRM_WEBHOOK_URL`/`CRM_WEBHOOK_SECRET` are set — `docs/CRM_SYNC.md` | #67 (merged) |
| 2 | Read API for the CRM | `/integrations/crm/{customers,orders,newsletter}` paged by id, `CRM_API_TOKEN` bearer token (server setting) | open |

Still open after these: Stripe live keys and the Illinois sales-tax rate (owner, in Settings), owner review of the
returns/privacy/terms drafts, drag-and-drop category tree, marketplace API sync (Etsy/Amazon).

Closed draft #18 (`feat/commerce-core`, an earlier one-shot version) is superseded. Its contact-messages inbox and
first admin pages for orders, promotions and settings are the starting point for those admin batches.

Parked, already-written backend code lives on branch `wip/commerce-rest` (not for merging): take files from it with
`git checkout wip/commerce-rest -- <paths>` when a batch needs them.

Lessons from these batches (check before pushing):
- Alembic revision headers: `tests/test_migration_chain.py` catches a broken chain.
- Raw SQL through asyncpg: parameters in a `SELECT` list need `CAST(:x AS type)`. Check new queries as untyped
  prepared statements (`PREPARE q AS ...` with `$1..$n`) against a migrated database.
- Stacked PRs: if the owner merges the base first, GitHub deletes the base branch and a PR opened against it
  fails with "base invalid". Merge `main` into the next branch and open it against `main` instead.
- Frontend can't be type-checked in the sandbox (npm is blocked); CI's `build` job is the type check. Watch for
  union types on shared components (e.g. Turnstile `action`).
