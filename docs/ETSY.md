# Etsy → shop

What it is: every Etsy listing and paid order appears in the shop admin automatically, so the team can record what each
order cost, track it, and see the real profit. **Shop only** — nothing here goes to the CRM.

Delivered in phases; the owner approves each before the next (`docs/WORKING_IN_BATCHES.md` → "Etsy → shop").

## Direction of data (the most important rule)

| Data | Direction |
|---|---|
| Listings, inventory | Etsy → shop only. Etsy is the source of truth; nothing Etsy owns can be edited in the shop. |
| Orders | Etsy → shop. The one exception (phase 2): tracking numbers go back to Etsy, which notifies the buyer. |
| Buyer messages | Phase 3. Etsy has no API to send messages: incoming ones are captured from Etsy's notification emails, replies are written in the shop and pasted into Etsy with one click. |

Never: scrape Etsy pages, automate the Etsy website, or contact buyers outside Etsy.

## Setup (admin, once)

1. Etsy developer portal → your app (a *seller app* for your own shop). Callback URL must be exactly
   `https://shop-api.windycitywares.com/api/v1/integrations/etsy/callback` (shown on the settings tab too).
2. Admin → Settings → External shops → **Etsy**: paste the keystring and shared secret → **Save Etsy keys**.
   The secret is sealed (`app/core/secretbox.py`) and never returned by the API.
3. **Connect Etsy** → Etsy's "Allow access". Tokens are sealed; refresh is automatic.
4. **External shops → Etsy** appears in the left menu, with Orders and Listings as tabs (an entry is shown only while
   its shop is connected: `GET /admin/channels`). Another marketplace is one item in `nav.ts` with its `channel` and
   `sections`, its pages, and its tab in `ExternalShops.tsx`.

Etsy requires `x-api-key: <keystring>:<shared secret>` on API calls (the token calls take the keystring alone).
Rotating the shared secret on Etsy means pasting the new one in the Etsy tab.

## Listings (`etsy_listings`, job `etsy_listings`, every 15 min)

All states (active, inactive, sold out, draft, expired) with images, variations, SKUs and stock. Each pass overwrites the
Etsy columns and never the team's `internal_supplier`, `internal_purchase_cost`, `internal_notes`. A listing Etsy no
longer returns becomes `removed` (kept, so old orders still link). "Sync from Etsy now" forces a pass.

## Orders (`etsy_orders`, `etsy_order_items`, `etsy_order_events`, job `etsy_orders`, every 5 min)

- Created once, when Etsy says the order is **paid**: Etsy order number, dates, buyer name and Etsy ID, address, items,
  prices, shipping charged, discounts, tax, gift message, buyer note, ship-by date. Buyer email only if Etsy gives it;
  phone is typed in by the team.
- First run reads 180 days back; later runs re-read 45 days so changes on older orders (shipped, cancelled) arrive.
- **Default cost:** one per listing (owner's decision 2026-11-17, not per size).
- **Prefill:** purchase cost = Σ listing default cost × quantity (only when every item has one; flagged
  `costs_prefilled` until someone edits it); supplier when all items share one.
- Team fields: purchase cost, supplier, supplier order #, actual shipping cost, carrier, tracking, notes, buyer phone.

### Statuses (`app/domain/etsy_status.py`)

Main path: New (paid) → Purchased → Shipped → Delivered → Closed.
Exceptions: Cancelled, Issue reported, Replacement sent, Return requested, Returned, Refunded.

- Etsy sets **New, Cancelled, Shipped, Delivered** only, and only **forward** on the main path; an order the team parked
  on an exception is left alone. A refund on Etsy does **not** cancel (refunds are recorded by the team, phase 3).
- The team can set any status, with an optional note.
- Every change (Etsy's or the team's), cost, tracking and note edit is a line in the order's history with who and when,
  and team changes also go to the audit log.

### Profit (`app/domain/etsy_profit.py`)

```
revenue    = items + shipping charged − discounts        (sales tax is not revenue)
total cost = purchase cost + actual shipping cost + Etsy fees (+ replacements and refunds, phase 3)
net profit = revenue − total cost;  margin = net / revenue
days to ship = shipped − paid (Etsy's own timestamps)
```
Missing figures count as zero and are listed as missing — never estimated. Etsy fees come from Etsy's ledger in phase 2.

### Needs attention (`app/domain/etsy_attention.py`, mirrored in SQL for the filter)

Paid > 24 h and not purchased · past ship-by and not shipped · purchase cost missing · shipping cost missing once shipped ·
negative profit. Cancelled orders never need attention, and neither do **past orders** — ones that were already shipped
or cancelled when they first came in from Etsy (`past_order`; owner's decision 2026-11-17). Costs can still be added. Phase 3 adds tracking failures, unanswered messages, connection
problems and the email alerts.

## Dashboard (External shops → Etsy → Dashboard, `GET /admin/etsy/dashboard`)

Filters: date range (compared with the period just before), product, supplier. KPIs: orders, revenue, net profit,
margin, average order, days to ship. Charts: revenue / profit / costs over time, orders per period, orders by status,
best sellers (profit of a multi-item order shared by item price), where buyers are, suppliers table, shipping speed,
on-time rate and cancellations. Profit and margin only count orders with a purchase cost; the page says how many.
Rules: `app/domain/etsy_dashboard.py` (tested in `tests/test_domain_etsy.py`).

## Supplier payments (External shops → Etsy → Supplier payments)

Owed to the supplier = purchase cost + actual shipping cost (the supplier buys and ships). States
(`app/domain/etsy_payments.py`): **Cost missing** (no purchase cost yet) → **Pending** → **Settled** (an admin recorded
the payment: date, amount, reference, who). Cancelled orders are *not due* unless already paid.

- Admins (`etsy:payments`) mark one order paid (any amount) or many at once (each at what it owes) — one supplier
  invoice in one go — and can undo. Staff see everything but can't record payments.
- A payment never changes the order's costs; payments and undos are in the order's history and the audit log.
- Per-supplier totals (pending / settled), tabs Pending · Settled · Cost missing · All, filters supplier and dates
  (order date; paid date on Settled).
- Export: CSV (opens in Excel), Excel (.xlsx, money formatted), and a printable statement (Print or save PDF).
- Migration 0026 adds `supplier_paid_at`, `supplier_paid_amount`, `supplier_payment_ref`, `supplier_paid_by`.

## Suppliers (External shops → Suppliers)

The supplier list (migration 0028, `app/services/suppliers.py`), shared by every marketplace: name, contact, email,
phone, notes, active. Listings' default supplier, orders' supplier and supplier logins are **picked** from it (the API
refuses a name that isn't listed or is switched off; an unchanged value is always accepted). Names already in use were
added when the list was created. Renaming a supplier renames it on its orders, listings and login. Suppliers are switched
off, not deleted.

**Since 2026-11-22 the CRM owns the supplier list** (owner's decision): suppliers are added and edited in the CRM, which
sends them to the shop (docs/CRM_SYNC.md → "Suppliers"); once the first one arrives, the shop's Suppliers page is
read-only with a "Manage in the CRM" link. The CRM supplier page shows the shop's figures for that supplier. Etsy
orders, costs, payments and supplier logins stay in the shop; Etsy buyers are never sent to the CRM (Etsy allows buyer
data only for fulfilling the order).

## Supplier logins (Team → Supplier logins)

An admin adds a login per supplier: email + password, the **supplier name** (must match the Supplier field on orders;
case doesn't matter) and the **external shops** they may see (Etsy now; each new marketplace becomes a tick box).
Role `supplier` (migration 0027) has one permission, `supplier:portal`, and nothing else.

A supplier signs in at /login and lands on External shops → Etsy → **My orders** / **My payments**
(`/admin/supplier/etsy…`, API `/supplier/…`, `app/services/supplier_portal.py`):

- Sees only orders whose supplier is theirs, on shops that are both allowed and connected; anything else is a 404/403.
- Sees what to make (items, options, personalisation), ship-to address, ship-by date (late flagged), buyer note and
  gift message, and what they are owed / were paid. Never the shop's prices, revenue, profit, other suppliers, the
  buyer's email or phone, or team notes and cost history.
- Can enter their own order number, carrier and tracking, and **Mark shipped** (tracking required) — written to the
  order's history under their name, exactly as a team member's change would be.
- Exports their payments (CSV / Excel). The rest of the admin (menu, search, notifications) is hidden and its API
  answers 403.

## Who can do what

Admin: everything, including Settings → External shops and recording supplier payments. Staff (the Publisher role): orders, listings, costs, status. Supplier logins: only their own orders (above).
Buyer details are only shown to signed-in team members and only used to fulfil the order.

## Test mode

Etsy tables live in the live data only; Test mode shows the same Etsy data (the sync always writes live).

## How to test (phase 1)

1. Settings → External shops → Etsy shows **Connected** with the shop name.
2. Etsy listings: listings appear within 15 minutes (or press *Sync from Etsy now*). Open one, set supplier and cost.
3. Etsy orders: a paid Etsy order appears within ~5 minutes, with cost prefilled from the listing.
4. Open it: enter shipping cost and tracking, change status to Purchased → the history shows each change with your
   name; profit and margin update; *Needs attention* clears.
5. Ship it on Etsy → within minutes the status becomes Shipped (source: Etsy) and Etsy's tracking appears.

Automated: `tests/test_domain_etsy.py` (rules), `tests/test_integration_etsy_*.py` (API and sync, Etsy mocked).
