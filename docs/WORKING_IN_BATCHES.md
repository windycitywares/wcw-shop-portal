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

Status as of 2026-10-14. Merge in the order listed; only merge a PR once its CI is green.

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
| 4 | Order history, find my order, unsubscribe page | #29 |
| 5 | Product reviews, wishlist hearts, notify-me, recently viewed, also bought | next |
| 6 | Consent banner + behaviour tracking (needs backend #24) | |
| 7 | Info pages: FAQ, shipping, returns, privacy, terms (legal text needs the owner's review) | |

Admin (one PR each): new navigation + dashboard · orders · promotions (sales, coupons, offers) · customers + campaigns ·
reviews + settings + audit log · analytics pages + suggestions · contact-messages inbox.

Closed draft #18 (`feat/commerce-core`, an earlier one-shot version) is superseded. Its contact-messages inbox and
first admin pages for orders, promotions and settings are the starting point for those admin batches.

Parked, already-written backend code lives on branch `wip/commerce-rest` (not for merging): take files from it with
`git checkout wip/commerce-rest -- <paths>` when a batch needs them.

Lessons from these batches (check before pushing):
- Alembic revision headers: `tests/test_migration_chain.py` catches a broken chain.
- Raw SQL through asyncpg: parameters in a `SELECT` list need `CAST(:x AS type)`. Check new queries as untyped
  prepared statements (`PREPARE q AS ...` with `$1..$n`) against a migrated database.
- Frontend can't be type-checked in the sandbox (npm is blocked); CI's `build` job is the type check. Watch for
  union types on shared components (e.g. Turnstile `action`).
