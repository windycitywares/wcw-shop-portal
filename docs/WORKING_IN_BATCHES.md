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

Backend (merge in order):

| # | Batch | Contents |
|---|-------|----------|
| 1 | Data layer | Migrations 0006–0008, models, core (permissions, limits, config), pure domain rules + unit tests |
| 2 | Pricing and promotions API | Store settings, sales, coupons (incl. bulk generation), cart offers, cart quote, sale prices on products |
| 3 | Checkout and orders | Checkout, payments (Stripe, pay later), order emails, stock, orders admin, abandoned carts |
| 4 | Engagement | Reviews, wishlist, back-in-stock, newsletter + welcome offer, customers, email campaigns |
| 5 | Tracking, reports, jobs | Consent-based analytics, report APIs, KPIs + suggestions, scheduled jobs, integration tests |

Storefront (one PR each): sale badges + deals page · cart with coupon and free-shipping progress · checkout ·
order page + order lookup + unsubscribe · reviews, wishlist, notify-me · consent banner + tracking · info pages
(FAQ, shipping, returns, privacy, terms).

Admin (one PR each): new navigation + dashboard · orders · promotions (sales, coupons, offers) · customers + campaigns ·
reviews + settings + audit log · analytics pages + suggestions.
